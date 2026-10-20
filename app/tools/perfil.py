from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

from app.domain.perfil import buscar_perfil_estruturado, buscar_preferencias_relevantes


@tool
def consultar_perfil_financeiro(pergunta: str, config: RunnableConfig) -> str:
    """Consulta o perfil financeiro cadastrado do usuário (renda, objetivo,
    tolerância a risco e preferências) para embasar um conselho.

    Use SEMPRE que for aconselhar algo que dependa desses dados.
    NÃO use para alterar o perfil — só leitura.

    Args:
        pergunta: o assunto financeiro sendo discutido agora.
    """
    configuravel = (config or {}).get("configurable", {})
    user_id      = configuravel.get("user_id") or configuravel.get("thread_id")

    if not user_id:
        return "Não foi possível identificar o usuário para consultar o perfil."

    perfil = buscar_perfil_estruturado(user_id)
    if not perfil:
        return ("Nenhum perfil cadastrado para este usuário. Oriente-o a "
                 "preencher a tela de Perfil (/perfil.html).")

    preferencia = buscar_preferencias_relevantes(user_id, pergunta)
    partes = [
        f"Renda mensal: R$ {perfil['renda_mensal']:.2f}",
        f"Objetivo: {perfil['objetivo']}",
        f"Tolerância a risco: {perfil['tolerancia_risco']}",
    ]
    if preferencia:
        partes.append(f"Preferência relevante: {preferencia}")
    return "\n".join(partes)


TOOLS_PERFIL = [consultar_perfil_financeiro]