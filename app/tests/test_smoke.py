from fastapi.testclient import TestClient
from app.main import app

def test_health_responde():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200