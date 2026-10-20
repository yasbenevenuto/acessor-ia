import uuid
from datetime import datetime, timezone

from pymongo import MongoClient
from qdrant_client import models

from app.core.config import MONGODB_URI
from app.domain.vectorstore import qdrant, gerar_embedding, COLLECTION_PERFIL

_mongo     = MongoClient(MONGODB_URI)
db         = _mongo["assessor"]
col_perfis = db["perfis"]

col_perfis.create_index("user_id", unique=True)

_NAMESPACE = uuid.UUID("12345678-1234-5678-1234-567812345678")


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _id_qdrant(user_id: str) -> str:
    """Mesmo user_id → mesmo UUID sempre, então o upsert substitui o ponto
    antigo em vez de criar um novo a cada 'salvar perfil'."""
    return str(uuid.uuid5(_NAMESPACE, user_id))


def salvar_perfil(user_id: str, renda_mensal: float, objetivo: str,
                   tolerancia_risco: str, preferencias: str) -> dict:
    documento = {
        "user_id":          user_id,
        "renda_mensal":     renda_mensal,
        "objetivo":         objetivo,
        "tolerancia_risco": tolerancia_risco,
        "preferencias":     preferencias,
        "atualizado_em":    _agora(),
    }

    col_perfis.update_one({"user_id": user_id}, {"$set": documento}, upsert=True)

    vetor = gerar_embedding(preferencias)
    qdrant.upsert(
        collection_name=COLLECTION_PERFIL,
        points=[models.PointStruct(
            id=_id_qdrant(user_id),
            vector=vetor,
            payload={"user_id": user_id, "preferencias": preferencias},
        )],
    )
    return documento


def buscar_perfil_estruturado(user_id: str) -> dict | None:
    return col_perfis.find_one({"user_id": user_id}, {"_id": 0})


def buscar_preferencias_relevantes(user_id: str, pergunta: str) -> str | None:
    vetor = gerar_embedding(pergunta)
    resultados = qdrant.query_points(
        collection_name=COLLECTION_PERFIL,
        query=vetor,
        query_filter=models.Filter(must=[
            models.FieldCondition(key="user_id", match=models.MatchValue(value=user_id))
        ]),
        limit=1,
    ).points
    return resultados[0].payload["preferencias"] if resultados else None