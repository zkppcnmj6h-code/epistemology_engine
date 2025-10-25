from dagster import Definitions, job, op
@op
def hello_op():
    return "ok"
@job
def hello_job():
    hello_op()
defs = Definitions(jobs=[hello_job])
