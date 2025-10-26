# src/orchestration/jobs.py
from dagster import job, define_asset_job, AssetSelection
from src.orchestration.assets.ingest import ingest
from .assets.ocr_parse import ocr_parse

# Option 1: If using @op
@job(name="ingest_and_parse_document")
def ingest_job():
    """Defines the M1 pipeline: Ingest source URI -> Parse/OCR pages."""
    doc_id = ingest()
    ocr_parse(doc_id)

# Option 2: If defining using Assets (more modern Dagster)
# Define ingest and ocr_parse using @asset instead of @op
# Then create a job targeting the final asset:
# parse_job = define_asset_job(name="parse_document_job", selection=AssetSelection.keys("parsed_document_asset"))
# For M1, using @op and the job above is simpler.