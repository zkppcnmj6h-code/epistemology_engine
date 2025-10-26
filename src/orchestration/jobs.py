# src/orchestration/jobs.py
from dagster import job
from src.orchestration.assets.ingest import ingest
from src.orchestration.assets.ocr_parse import ocr_parse

@job(name="ingest_and_parse_document")
def ingest_job():
    """
    Defines the M1 pipeline: Ingest source URI -> Parse/OCR pages.
    Takes 'source_uri' as input configuration for the 'ingest' op.
    """
    # Call the first op (ingest)
    doc_id_output = ingest()

    # Pass the output (doc_id) from 'ingest' to the input of 'ocr_parse'
    ocr_parse(doc_id=doc_id_output)

# Note: You will add more complex jobs here later, potentially using
# Dagster Assets instead of just Ops for better lineage and dependency tracking.
# For M1, this simple job definition is sufficient.