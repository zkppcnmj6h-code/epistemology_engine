# src/orchestration/jobs.py
from dagster import job
from src.orchestration.assets.ingest import ingest
from src.orchestration.assets.ocr_parse import ocr_parse

@job(name="ingest_and_parse_document")
def ingest_job():
    """Defines the M1 pipeline: Ingest source URI -> Parse/OCR pages."""
    doc_id_output = ingest()
    ocr_parse(doc_id=doc_id_output) # Pass the output doc_id to the next op