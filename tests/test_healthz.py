from fastapi.testclient import TestClient
from epistemology_engine.web.app import app
def test_healthz():
    c = TestClient(app)
    r = c.get("/healthz")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"
