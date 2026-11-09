from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


def test_health_responde():
    with patch("qdrant_client.QdrantClient", MagicMock()):
        from app.main import app
        resposta = TestClient(app).get("/health")
    assert resposta.status_code == 200