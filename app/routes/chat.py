from fastapi import APIRouter, HTTPException
from app.core.schemas import ChatRequest, ChatResponse
from app.graph import executar_fluxo_assessor
from app.domain.memory import iniciar_sessao, _sessoes_ativas

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def conversar(req: ChatRequest) -> ChatResponse:
    # Garante que existe uma sessao (documento no Mongo) para esse session_id
    # antes de rodar o fluxo. Se ja existir, nao recria.
    if req.session_id not in _sessoes_ativas:
        iniciar_sessao(req.session_id, user_id=req.user_id)

    try:
        resultado = executar_fluxo_assessor(
            pergunta_usuario=req.question,
            session_id=req.session_id,
            user_id=req.user_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar a mensagem: {e}")

    return ChatResponse(
        response=resultado["resposta"],
        agentes_chamados=resultado["agentes_chamados"],
        raciocinio=resultado.get("raciocinio") or None,
    )
