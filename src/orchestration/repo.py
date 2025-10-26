from dagster import Definitions

from src.orchestration.jobs import ingest_job

# Additional jobs, assets, and resources can be registered here as the
# orchestration layer grows. For M1 we only expose the ingest/parse job.
defs = Definitions(
    jobs=[ingest_job],
)
