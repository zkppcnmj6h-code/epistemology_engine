from dagster import Definitions

from src.orchestration.jobs import ingest_job

# You might also need to define resources like the database connection here later
# from dagster_sqlalchemy import sqlalchemy_resource
# db_resource = sqlalchemy_resource.configured({"sqlalchemy_url": {"env": "DATABASE_URL"}})

defs = Definitions(
    jobs=[ingest_job]
    # resources={"db": db_resource}
)
