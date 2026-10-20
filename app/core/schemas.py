from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime

class ChatRequest(BaseModel):
    session_id: str = Field(
        ...,
        description="Identificador da conversa",
        examples=["id_usuario"],
    )

    user_id: str = Field(
        default="usuario_teste",
        description="Identifica o usuário de forma estável entre sessões. "
                    "É o que permite a memória de longo prazo funcionar.",
        examples=["usuario_teste"],
    )

    question: str = Field(
        ...,
        min_length=1,
        description="Mensagem do usuário",
        examples=["gastei 50 reais no mercado"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "session_id": "teste-123",
                "question": "gastei 50 reais no mercado",
            }
        }
    }


class ChatResponse(BaseModel):
    response: str = Field(
        ...,
        description="Resposta gerada",
        examples=["Anotei: R$ 50,00 em mercado."],
    )
    agentes_chamados: list[str] = Field(
        default_factory=list,
        description="Agentes acionados nesta chamada",
        examples=[["financeiro"]],
    )
    raciocinio: str | None = Field(
        None,
        description="Raciocínio interno (<think>) do modelo que gerou a resposta final, quando disponível.",
    )


class SessionResponse(BaseModel):
    session_id: str = Field(..., examples=["teste-123"])
    resumo: str | None = None

class ProfileRequest(BaseModel):
    user_id: str = Field(default="usuario_teste", examples=["usuario_teste"])
    renda_mensal: float = Field(..., gt=0)
    objetivo: str = Field(..., min_length=1, max_length=120)
    tolerancia_risco: Literal["baixa", "media", "alta"]
    preferencias: str = Field(..., min_length=1)


class ProfileResponse(BaseModel):
    user_id: str
    renda_mensal: float
    objetivo: str
    tolerancia_risco: str
    preferencias: str
    atualizado_em: datetime