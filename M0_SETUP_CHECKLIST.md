	1.	Install and start Docker Desktop (and note zsh heredoc gotchas)

	•	Run:

brew install --cask docker
open -a Docker


	•	Use quoted heredocs (<<'EOF') whenever your content includes *, !, $, or globs to avoid zsh expansions.

	2.	Create the repository and initialize Git

	•	Run:

mkdir -p ~/epistemology_engine && cd ~/epistemology_engine
git init


	•	Create this directory scaffold (empty dirs tracked with .gitkeep):

.github/workflows/
config/
data/inputs/
data/transcripts/
db/migrations/
db/procedures/
docs/specs/
eval/
logs/
notebooks/
src/engine/
src/orchestration/
src/clients/
src/eval/
src/web/
tests/


	•	Add .gitkeep placeholders inside the empty data/inputs/, data/transcripts/, and logs/ directories.

	3.	Refine .gitignore so .gitkeep files are tracked

	•	Add the following lines to .gitignore (ignore contents, allow .gitkeep):

data/inputs/*
!data/inputs/.gitkeep
data/transcripts/*
!data/transcripts/.gitkeep
logs/*
!logs/.gitkeep



	4.	Add core docs and config files

	•	Create README.md and include the CI badge line:

![ci](https://github.com/<user>/epistemology_engine/actions/workflows/ci.yml/badge.svg)

(The rest of README.md can remain a placeholder for now.)

	•	Create docs/specs/VISION.md as a placeholder for Project Vision & Guiding Principles.
	•	Create config/topic_taxonomy.json with:

[
  {"topic_id":"PFC_101","name":"Blueprint Reading Basics","parent_id":null,"tags":["construction"]},
  {"topic_id":"PFC_101_L01","name":"Lesson 1: Intro","parent_id":"PFC_101","tags":["construction","blueprint"]}
]


	•	Create config/.env.example (placeholder with DB/model/integration keys) and copy it to config/.env for local use (kept ignored).

	5.	Create a Python virtual environment and install dependencies

	•	Run:

python3 -m venv .venv && source .venv/bin/activate


	•	Create requirements.txt exactly as follows:

fastapi>=0.115
uvicorn[standard]>=0.30
pydantic>=2.8
sqlalchemy>=2.0
psycopg[binary]>=3.2
pgvector>=0.2
dagster>=1.11
dagster-webserver>=1.11
httpx>=0.27
openai>=1.43
google-generativeai
boto3>=1.34
tenacity>=8.3
opentelemetry-sdk>=1.26
opentelemetry-instrumentation-fastapi>=0.48b0
python-json-logger>=2.0
python-dotenv>=1.0
langdetect>=1.0.9
pytest>=8.0
ruff>=0.6
mypy>=1.10


	•	Install and lock:

pip install -r requirements.txt
pip freeze > requirements.lock.txt



	6.	Create docker-compose.yml for Postgres (pgvector), FastAPI, and Dagster

	•	Add this full content:

services:
  db:
    image: pgvector/pgvector:pg17
    container_name: ee_db
    restart: unless-stopped
    env_file: config/.env
    environment:
      POSTGRES_DB: epistemology_engine
      POSTGRES_USER: ${PGUSER:-user}
      POSTGRES_PASSWORD: ${PGPASSWORD:-password}
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${PGUSER:-user} -d ${PGDATABASE:-epistemology_engine}"]
      interval: 5s
      timeout: 5s
      retries: 20
    volumes:
      - postgres_data:/var/lib/postgresql/data

  dagster-webserver:
    image: python:3.12-slim
    container_name: ee_dagster_web
    working_dir: /app
    command: bash -lc "pip install -r requirements.txt && dagster-webserver -h 0.0.0.0 -p 3000 -m src.orchestration.repo"
    env_file: config/.env
    volumes: [ "./:/app" ]
    ports: [ "3000:3000" ]
    depends_on: [ db ]

  dagster-daemon:
    image: python:3.12-slim
    container_name: ee_dagster_daemon
    working_dir: /app
    command: bash -lc "pip install -r requirements.txt && dagster-daemon run"
    env_file: config/.env
    volumes: [ "./:/app" ]
    depends_on: [ db, dagster-webserver ]

  api:
    image: python:3.12-slim
    container_name: ee_api
    working_dir: /app
    command: bash -lc "pip install -r requirements.txt && uvicorn src.web.app:app --host 0.0.0.0 --port 8000 --reload"
    env_file: config/.env
    volumes: [ "./:/app" ]
    ports: [ "8000:8000" ]
    depends_on: [ db ]

volumes:
  postgres_data:



	7.	Add the starter database migration and a rollback stub

	•	Create db/migrations/V0001__initial_schema.sql (enables uuid-ossp, pgcrypto, vector; creates core.migrations_applied and inserts V0001).
	•	Create db/procedures/rollback_run.sql as a stub in the ops schema.

	8.	Start the database and apply the migration

	•	Run:

docker compose up -d db
docker compose exec -T db bash -lc 'until pg_isready -U "${PGUSER:-user}" -d "${PGDATABASE:-epistemology_engine}"; do sleep 1; done'
docker compose cp db/migrations/V0001__initial_schema.sql db:/tmp/init.sql
docker compose exec -T db psql -U "${PGUSER:-user}" -d "${PGDATABASE:-epistemology_engine}" -f /tmp/init.sql


	•	Verify inside psql:

\dx
SELECT * FROM core.migrations_applied;



	9.	Add minimal application code (FastAPI + Dagster)

	•	Create src/web/app.py:

from fastapi import FastAPI

app = FastAPI()

@app.get("/healthz")
def healthz():
    return {"status": "ok"}


	•	Create src/orchestration/repo.py:

from dagster import Definitions, job, op

@op
def hello_op():
    return "ok"

@job
def hello_job():
    hello_op()

defs = Definitions(jobs=[hello_job])


	•	Add empty __init__.py files in src/, src/web/, and src/orchestration/.

	10.	Bring up the full stack and validate locally

	•	Run:

docker compose up -d --build


	•	Check the API:

curl -s http://127.0.0.1:8000/healthz

Expected: {"status":"ok"}

	•	Open Dagster UI at http://localhost:3000 and confirm it loads.

	11.	Add tests and tooling configs; fix Python path for tests

	•	Create tests/test_healthz.py to exercise /healthz (content per your local test).
	•	Create ruff.toml and mypy.ini (configuration files).
	•	Add tests/conftest.py to ensure src-layout imports work:

import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


	•	Run tests:

pytest -q

Expected: tests pass.

	12.	Add a basic CI workflow and push to GitHub

	•	Create .github/workflows/ci.yml that runs on push/PR and:
	•	Spins up Postgres+pgvector.
	•	Applies the migration SQL.
	•	Runs: ruff check ., mypy src/, and pytest -q.
	•	Add the remote and push:

git remote add origin https://github.com/<user>/epistemology_engine.git
git push -u origin main
git checkout -b chore/m0-verification
git push -u origin chore/m0-verification



	13.	Add the CI badge to README.md

	•	Ensure this line is present (added safely, e.g., via a quoted heredoc as needed to avoid zsh ! expansion):

![ci](https://github.com/<user>/epistemology_engine/actions/workflows/ci.yml/badge.svg)



	14.	Final M0 verification checklist

	•	API health: curl -s http://127.0.0.1:8000/healthz → {"status":"ok"}.
	•	Dagster UI reachable at http://localhost:3000.
	•	Tests: pytest -q → green.
	•	GitHub Actions: push a commit and confirm the CI run executes lint/type/tests + migration and succeeds; CI badge renders in README.md.

Outcome: With the above steps completed and verifications passing, Milestone M0 — Foundation & CI is replicated exactly as logged.