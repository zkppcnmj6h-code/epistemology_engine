# src/orchestration/assets/ingest.py
from dagster import op, Out, Output, Field, DagsterLogManager
from uuid import uuid4
from urllib.parse import urlparse
import mimetypes
import json
import os
from sqlalchemy import text # Direct SQL execution for M1 simplicity
from src.clients.db_client import db_session, execute_sql, fetch_one_sql # Use basic helpers

def _infer_mime(uri: str) -> str:
    """Guess MIME type from URI, default to octet-stream."""
    mime, _ = mimetypes.guess_type(uri)
    return mime or "application/octet-stream"

@op(
    config_schema={"source_uri": Field(str, description="URI of the source file (e.g., file:///app/data/inputs/sample.pdf)")},
    out=Out(str, description="The generated doc_id (UUID) for the ingested document.")
)
def ingest(context) -> str:
    """
    Dagster op to ingest a source document.
    Creates records in core.sources and core.documents.
    Performs basic idempotency check based on source_uri.
    Logs actions to ops.write_sets for rollback capability.
    """
    log: DagsterLogManager = context.log
    source_uri: str = context.op_config["source_uri"]
    source_id = str(uuid4())
    doc_id = str(uuid4())
    run_id = context.run_id # Dagster provides run_id

    mime_type = _infer_mime(source_uri)
    # Basic title extraction from filename
    title = os.path.basename(urlparse(source_uri).path) or "untitled"
    metadata = {"ingest_source": "dagster_m1", "original_filename": title}

    with db_session() as s:
        # Simplified idempotency check for M1 (based on URI)
        # Production should use content hashing if possible
        existing_doc = fetch_one_sql(s,
            """
            SELECT d.doc_id FROM core.documents d
            JOIN core.sources src ON d.source_id = src.source_id
            WHERE src.uri = :uri LIMIT 1
            """,
            {"uri": source_uri}
        )
        if existing_doc:
            log.warning(f"Source URI {source_uri} already ingested with doc_id {existing_doc['doc_id']}. Reusing.")
            return Output(existing_doc['doc_id']) # Output existing ID

        # Insert into core.sources
        execute_sql(s,
            """
            INSERT INTO core.sources (source_id, uri, mime_type, title, metadata)
            VALUES (:source_id::uuid, :uri, :mime, :title, :meta::jsonb)
            """,
            {"source_id": source_id, "uri": source_uri, "mime": mime_type, "title": title, "meta": json.dumps(metadata)}
        )
        # Insert into core.documents, linking to the run_id
        execute_sql(s,
            """
            INSERT INTO core.documents (doc_id, source_id, status, run_id)
            VALUES (:doc_id::uuid, :source_id::uuid, 'ingested', :run_id::uuid)
            """,
            {"doc_id": doc_id, "source_id": source_id, "run_id": run_id}
        )
        # Log write set for rollback capability
        pk_source_json = json.dumps({"source_id": source_id})
        # Note: 'after' state should ideally reflect the actual inserted row for perfect rollback
        after_source_json = json.dumps({"uri": source_uri, "mime_type": mime_type, "title": title, "metadata": metadata})
        pk_doc_json = json.dumps({"doc_id": doc_id})
        after_doc_json = json.dumps({"source_id": source_id, "status": "ingested", "run_id": run_id})

        execute_sql(s,
             """
             INSERT INTO ops.write_sets (run_id, step, table_name, pk, op, after)
             VALUES (:run_id::uuid, 'ingest', 'core.sources', :pk_src::jsonb, 'INSERT', :after_src::jsonb),
                    (:run_id::uuid, 'ingest', 'core.documents', :pk_doc::jsonb, 'INSERT', :after_doc::jsonb)
             """,
             {
                "run_id": run_id,
                "pk_src": pk_source_json, "after_src": after_source_json,
                "pk_doc": pk_doc_json, "after_doc": after_doc_json
             }
        )

    log.info(f"Ingested {source_uri} -> doc_id={doc_id}, run_id={run_id}")
    return Output(doc_id)