from fastapi import APIRouter
from app.core.schemas import ProfileRequest, ProfileResponse
from app.domain.perfil import salvar_perfil

router = APIRouter(tags=["profile"])


@router.post("/perfil", response_model=ProfileResponse)
def cadastrar_perfil(req: ProfileRequest) -> ProfileResponse:
    """
    Única rota de perfil: cria ou atualiza (upsert). Não existe leitura,
    listagem nem exclusão.
    """
    documento = salvar_perfil(
        user_id=req.user_id,
        renda_mensal=req.renda_mensal,
        objetivo=req.objetivo,
        tolerancia_risco=req.tolerancia_risco,
        preferencias=req.preferencias,
    )
    return ProfileResponse(**documento)