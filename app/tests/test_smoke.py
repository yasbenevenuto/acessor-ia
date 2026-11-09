from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def test_health_responde():
    # Evita conectar em Qdrant e MongoDB reais durante a importação do app
    with patch("qdrant_client.QdrantClient", MagicMock()), \
         patch("pymongo.MongoClient", MagicMock()):
        from app.main import app
        resposta = TestClient(app).get("/health")
    assert resposta.status_code == 200