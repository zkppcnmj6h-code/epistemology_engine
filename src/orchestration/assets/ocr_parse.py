from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Optional, TypedDict
from urllib.parse import urlparse
from uuid import uuid4

from dagster import DagsterLogManager, In, Nothing, op

from src.clients.db_client import db_session, execute_sql, fetch_one_sql


class PageData(TypedDict):
    page_num: int
    dpi: Optional[int]
    text: str
    vision_features: dict[str, bool]
    content_hash: bytes

try:
    from PyPDF2 import PdfReader

    pypdf_available = True
except ImportError:
    PdfReader = None
    pypdf_available = False

try:
    import pytesseract
    from PIL import Image

    pytesseract_available = True
except ImportError:
    Image = None
    pytesseract_available = False


def _sha256_bytes(source: bytes) -> bytes:
    return hashlib.sha256(source).digest()


def _get_local_path_from_uri(uri: str, log: DagsterLogManager) -> Optional[Path]:
    """Translate a file:// URI (or bare path) into the container's filesystem."""
    try:
        parsed = urlparse(uri)
        if parsed.scheme in {"file", ""}:
            relative_path = parsed.path.lstrip("/")
            abs_path = os.path.abspath(os.path.join("/app", relative_path))
            path_obj = Path(abs_path)
            if path_obj.exists():
                return path_obj
            log.error(
                "File not found at expected path %s (derived from URI %s)",
                abs_path,
                uri,
            )
            return None
        log.warning("Non-local URI scheme (%s) encountered for %s. Skipping.", parsed.scheme, uri)
        return None
    except Exception as exc:  # pragma: no cover - defensive logging
        log.error("Failed to parse URI %s: %s", uri, exc)
        return None


@op(ins={"doc_id": In(str)})
def ocr_parse(context, doc_id: str) -> Nothing:
    log: DagsterLogManager = context.log
    run_id = context.run_id

    with db_session() as session:
        doc_info = fetch_one_sql(
            session,
            """
            SELECT s.uri, s.mime_type
            FROM core.documents d
            JOIN core.sources s ON d.source_id = s.source_id
            WHERE d.doc_id = :doc_id AND d.status = 'ingested'
            """,
            {"doc_id": doc_id},
        )

        if not doc_info:
            log.warning(
                "Document %s not found or not in 'ingested' state. Skipping parse.", doc_id
            )
            return

        uri, mime = doc_info["uri"], doc_info["mime_type"]
        path = _get_local_path_from_uri(uri, log)

        if not path:
            execute_sql(
                session,
                "UPDATE core.documents SET status='failed', updated_at=NOW() WHERE doc_id=:doc_id",
                {"doc_id": doc_id},
            )
            log.error("Failed to access source file for doc_id %s. Marked as failed.", doc_id)
            return

        log.info("Processing file %s (MIME: %s)", path, mime)

        pages_data: list[PageData] = []
        page_count = 0

        try:
            if mime == "application/pdf" or str(path).lower().endswith(".pdf"):
                if not pypdf_available:
                    log.warning("PyPDF2 not available. Cannot process PDF text layer.")
                else:
                    reader = PdfReader(str(path))
                    page_count = len(reader.pages)
                    log.info("PDF detected with %s pages.", page_count)

                    for index, page in enumerate(reader.pages, start=1):
                        page_text = ""
                        ocr_attempted = False

                        try:
                            extracted = page.extract_text()
                            if extracted:
                                page_text = extracted.strip()
                        except Exception as exc:  # pragma: no cover - parser specific
                            log.warning("PyPDF2 text extraction failed for page %s: %s", index, exc)

                        if not page_text and pytesseract_available:
                            try:
                                log.info("Attempting OCR fallback for PDF page %s...", index)
                                img_base = f"/tmp/{path.stem}_page_{index}"
                                img_png = f"{img_base}.png"
                                command = [
                                    "pdftocairo",
                                    "-png",
                                    "-f",
                                    str(index),
                                    "-l",
                                    str(index),
                                    "-singlefile",
                                    str(path),
                                    img_base,
                                ]
                                process = subprocess.run(
                                    command,
                                    capture_output=True,
                                    text=True,
                                    check=False,
                                )
                                if process.returncode == 0 and os.path.exists(img_png):
                                    with Image.open(img_png) as image:
                                        page_text = pytesseract.image_to_string(image).strip()
                                    os.remove(img_png)
                                    ocr_attempted = True
                                else:
                                    log.warning(
                                        "pdftocairo failed for page %s. stdout=%s stderr=%s",
                                        index,
                                        process.stdout,
                                        process.stderr,
                                    )
                            except Exception as exc:
                                log.error("OCR fallback failed for PDF page %s: %s", index, exc)

                        content_hash_bytes = _sha256_bytes(page_text.encode("utf-8"))
                        pages_data.append(
                            {
                                "page_num": index,
                                "dpi": None,
                                "text": page_text,
                                "vision_features": {"ocr_attempted": ocr_attempted},
                                "content_hash": content_hash_bytes,
                            }
                        )

            elif mime and mime.startswith("image/") and pytesseract_available and Image:
                log.info("Image detected: %s", path)
                with Image.open(path) as image:
                    page_text = pytesseract.image_to_string(image).strip()
                content_hash_bytes = _sha256_bytes(page_text.encode("utf-8"))
                pages_data.append(
                    {
                        "page_num": 1,
                        "dpi": None,
                        "text": page_text,
                        "vision_features": {"ocr_attempted": True},
                        "content_hash": content_hash_bytes,
                    }
                )
                page_count = 1

            else:
                log.warning(
                    "Unsupported mime type '%s' or parser/OCR unavailable for %s. Skipping.",
                    mime,
                    path,
                )
                return

            if pages_data:
                inserted_count = 0
                for page_data in pages_data:
                    page_id = str(uuid4())
                    pk_json = json.dumps({"page_id": page_id})
                    after_json = json.dumps(
                        {
                            "doc_id": doc_id,
                            "page_num": page_data["page_num"],
                            "text_len": len(page_data["text"]),
                        }
                    )

                    try:
                        execute_sql(
                            session,
                            """
                            INSERT INTO core.pages (page_id, doc_id, page_num, dpi, text, vision_features, content_hash)
                            VALUES (:pid, :doc_id::uuid, :n, :dpi, :text, :vf::jsonb, :hash)
                            ON CONFLICT (doc_id, page_num) DO UPDATE SET
                                text = EXCLUDED.text,
                                vision_features = EXCLUDED.vision_features,
                                content_hash = EXCLUDED.content_hash,
                                page_id = EXCLUDED.page_id
                            """,
                            {
                                "pid": page_id,
                                "doc_id": doc_id,
                                "n": page_data["page_num"],
                                "dpi": page_data["dpi"],
                                "text": page_data["text"],
                                "vf": json.dumps(page_data["vision_features"]),
                                "hash": page_data["content_hash"],
                            },
                        )
                        execute_sql(
                            session,
                            """
                            INSERT INTO ops.write_sets (run_id, step, table_name, pk, op, after)
                            VALUES (:run_id::uuid, 'ocr_parse', 'core.pages', :pk::jsonb, 'UPSERT', :after::jsonb)
                            """,
                            {"run_id": run_id, "pk": pk_json, "after": after_json},
                        )
                        inserted_count += 1
                    except Exception as exc:
                        log.error(
                            "Failed to insert/update page %s for doc %s: %s",
                            page_data["page_num"],
                            doc_id,
                            exc,
                        )
                        raise

                execute_sql(
                    session,
                    "UPDATE core.documents SET status='parsed', updated_at=NOW() WHERE doc_id=:doc_id::uuid",
                    {"doc_id": doc_id},
                )
                pk_doc_json = json.dumps({"doc_id": doc_id})
                after_doc_json = json.dumps({"status": "parsed"})
                execute_sql(
                    session,
                    """
                    INSERT INTO ops.write_sets (run_id, step, table_name, pk, op, after)
                    VALUES (:run_id::uuid, 'ocr_parse', 'core.documents', :pk::jsonb, 'UPDATE', :after::jsonb)
                    """,
                    {"run_id": run_id, "pk": pk_doc_json, "after": after_doc_json},
                )

                log.info("Parsed and wrote %s/%s pages for doc_id=%s", inserted_count, page_count, doc_id)
            else:
                log.warning("No pages extracted for doc_id=%s. Document status remains 'ingested'.", doc_id)

        except Exception as exc:
            log.error("Error during parsing/OCR for doc_id %s: %s", doc_id, exc, exc_info=True)
            try:
                execute_sql(
                    session,
                    "UPDATE core.documents SET status='failed', updated_at=NOW() WHERE doc_id=:doc_id::uuid",
                    {"doc_id": doc_id},
                )
                pk_doc_json = json.dumps({"doc_id": doc_id})
                after_doc_json = json.dumps({"status": "failed"})
                execute_sql(
                    session,
                    """
                    INSERT INTO ops.write_sets (run_id, step, table_name, pk, op, after)
                    VALUES (:run_id::uuid, 'ocr_parse', 'core.documents', :pk::jsonb, 'UPDATE', :after::jsonb)
                    """,
                    {"run_id": run_id, "pk": pk_doc_json, "after": after_doc_json},
                )
            except Exception as db_exc:
                log.error("Failed to mark document %s as failed: %s", doc_id, db_exc)
            raise
