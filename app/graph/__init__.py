import json
import operator
from typing import Annotated
from langchain_core.messages import RemoveMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, MessagesState, StateGraph
from app.graph.guardrail import anonimizar_entrada, desanonimizar_saida, guardrail_entrada, guardrail_saida
from app.graph.agents import faq_app, router_app, get_agenda_app, financeiro_app, orquestrador_app
from app.tools.calendar_mcp import CalendarIndisponivel
from app.domain.memory import salvar_mensagem
from app.domain.observabilidade import abrir_turno, fechar_turno, status_do_estado
from app.tools import financeiro
from app.juiz import no_juiz


# ==============================================================================
# ESTADO
# ==============================================================================
class Estado(MessagesState):
    agentes_chamados: Annotated[list[str], operator.add]  # acumula entre nós
    rota: str
    mapa_pii: dict  # tokens → valores originais gerados na anonimização
    raciocinio: str  # texto de <think> do modelo que gerou a resposta final deste turno


# ==============================================================================
# NÓS
# ==============================================================================
def no_guardrail_entrada(estado: Estado, config: RunnableConfig) -> dict:
    session_id = config["configurable"]["thread_id"]
    # .get() com fallback: se algum caller esquecer de passar user_id no config
    # (ex: um teste manual), a sessão ainda funciona, só sem memória de longo
    # prazo entre conversas — melhor que o request inteiro quebrar.
    user_id    = config["configurable"].get("user_id", "usuario_teste")

    # list() materializa HumanMessage com .text e .id (estado["messages"][-1] retorna TextAccessor)
    human_message = list(estado["messages"])[-1]

    # 1. Salva input original e anonimiza — o LLM nunca vê CPF, e-mail, etc.
    texto_anonimizado, mapa = anonimizar_entrada(human_message.text)

    # 2. Roda as verificações de segurança na mensagem já anonimizada
    resultado = guardrail_entrada(texto_anonimizado)

    if resultado["bloqueado"]:
        return {
            "messages":         [{"role": "assistant", "content": resultado["mensagem"]}],
            "rota":             "fim",
            "mapa_pii":         {},
            "raciocinio":       "",
            "agentes_chamados": [f"guardrail_entrada:{resultado['motivo']}"],
        }

    # Grava a versão ANONIMIZADA no MongoDB — nunca o texto original com PII.
    # É por isso que salvar_mensagem() mora aqui, e não em routes/chat.py: só
    # depois do guardrail de entrada o texto está seguro para persistir.
    salvar_mensagem(session_id, "usuario", texto_anonimizado, user_id=user_id)

    return {
        "messages": [
            RemoveMessage(id=human_message.id),            # remove a mensagem original
            {"role": "human", "content": texto_anonimizado},  # substitui pela anonimizada
        ],
        "mapa_pii":         mapa,
        "rota":             "",
        "agentes_chamados": ["guardrail_entrada:aprovado"],
    }


def no_roteador(estado: Estado, config: RunnableConfig) -> dict:
    # O `config` é injetado pelo LangGraph nos nós que o declaram na
    # assinatura, mas cada wrapper precisa repassá-lo à mão no .invoke() do
    # agente interno — é o mesmo padrão usado em no_financeiro/no_agenda/no_faq.
    # Sem esta linha a tool buscar_historico não recebe o thread_id/user_id e
    # não consegue identificar de quem é o histórico.
    saida = router_app.invoke({"messages": list(estado["messages"])}, config=config)
    ultima_msg = saida["messages"][-1]
    texto = ultima_msg.text

    # Se o roteador não devolveu ROUTE=, responde diretamente e encerra
    if "ROUTE=" not in texto:
        return {
            "messages":         [{"role": "assistant", "content": texto}],
            "rota":             "fim",
            "raciocinio":       ultima_msg.additional_kwargs.get("reasoning_content", ""),
            "agentes_chamados": ["roteador"],
        }

    rota = "fim"
    for linha in texto.splitlines():
        if linha.startswith("ROUTE="):
            rota = linha.split("=", 1)[1].strip()
            break

    return {
        "rota":             rota,
        "raciocinio":       "",  # a resposta final ainda vai ser gerada por outro nó
        "agentes_chamados": ["roteador"],
    }


def no_orquestrador(estado: Estado, config: RunnableConfig) -> dict:
    # Pega a última resposta de um agente especialista
    ultimo_especialista = ""
    for msg in reversed(estado["messages"]):
        if msg.type == "ai" and msg.content:
            ultimo_especialista = msg.content
            break

    saida = orquestrador_app.invoke(
        {"messages": [{"role": "human", "content": ultimo_especialista}]},
        config=config,
    )
    ultima_msg = saida["messages"][-1]

    return {
        "messages":         [{"role": "assistant", "content": ultima_msg.text}],
        "raciocinio":       ultima_msg.additional_kwargs.get("reasoning_content", ""),
        "agentes_chamados": ["orquestrador"],
    }


def no_faq(estado: Estado, config: RunnableConfig) -> dict:
    # faq_app entrava direto como nó do grafo; virou uma função-wrapper para
    # dar pra capturar o reasoning_content da mesma forma que os outros nós.
    saida = faq_app.invoke({"messages": list(estado["messages"])}, config=config)
    ultima_msg = saida["messages"][-1]

    return {
        "messages":         [{"role": "assistant", "content": ultima_msg.text}],
        "raciocinio":       ultima_msg.additional_kwargs.get("reasoning_content", ""),
        "agentes_chamados": ["faq"],
    }


def no_financeiro(estado: Estado, config: RunnableConfig) -> dict:
    # financeiro_app entrava direto como nó do grafo; virou uma função-wrapper
    # pelo mesmo motivo do no_faq: capturar reasoning_content e, principalmente,
    # registrar "financeiro" em agentes_chamados (o agente bruto não sabe que
    # esse campo existe no Estado, só devolve "messages").
    saida = financeiro_app.invoke({"messages": list(estado["messages"])}, config=config)
    ultima_msg = saida["messages"][-1]

    return {
        "messages":         [{"role": "assistant", "content": ultima_msg.text}],
        "raciocinio":       ultima_msg.additional_kwargs.get("reasoning_content", ""),
        "agentes_chamados": ["financeiro"],
    }


def no_agenda(estado: Estado, config: RunnableConfig) -> dict:
    # Mesmo motivo do no_financeiro: sem isso, uma rota inteira do assessor
    # (marcar/consultar compromissos) não deixava rastro em agentes_chamados.
    try:
        saida = get_agenda_app().invoke({"messages": list(estado["messages"])}, config=config)
    except CalendarIndisponivel as e:
        # Calendar fora do ar (npx/credenciais/login pendente): responde no mesmo
        # formato JSON que o orquestrador espera, em vez de derrubar o /chat com 500.
        return {
            "messages": [{"role": "assistant", "content": json.dumps({
                "dominio": "agenda",
                "intencao": "consultar",
                "resposta": "Não consegui acessar o Google Calendar agora.",
                "recomendacao": f"Verifique a configuração do Google Calendar e tente novamente. Detalhe técnico: {e}",
            }, ensure_ascii=False)}],
            "raciocinio":       "",
            "agentes_chamados": ["agenda"],
        }
    ultima_msg = saida["messages"][-1]

    return {
        "messages":         [{"role": "assistant", "content": ultima_msg.text}],
        "raciocinio":       ultima_msg.additional_kwargs.get("reasoning_content", ""),
        "agentes_chamados": ["agenda"],
    }


def no_guardrail_saida(estado: Estado, config: RunnableConfig) -> dict:
    session_id = config["configurable"]["thread_id"]

    # Pega a última resposta do modelo (ignora tool calls e mensagens humanas)
    ultima = ""
    for msg in reversed(estado["messages"]):
        if msg.type == "ai" and msg.content:
            ultima = msg.content
            break

    mapa_pii = estado.get("mapa_pii", {})

    # Desanonimiza antes de passar pelo compliance
    ultima = desanonimizar_saida(ultima, mapa_pii)

    resultado = guardrail_saida(ultima, mapa_pii)

    # Fecha o par de turno: a pergunta (anonimizada) já foi salva em
    # no_guardrail_entrada; aqui salvamos a resposta final que o usuário
    # realmente recebe — é este par que vira o resumo no Bloco B.
    salvar_mensagem(session_id, "assistente", resultado["conteudo"])

    return {
        "messages":         [{"role": "assistant", "content": resultado["conteudo"]}],
        "agentes_chamados": ["guardrail_saida"],
    }


# ==============================================================================
# FUNÇÕES DE DECISÃO
# ==============================================================================
def decidir_pos_guardrail_entrada(estado: Estado) -> str:
    # "" = aprovado → roteador | "fim" = bloqueado → END
    return "roteador" if estado["rota"] == "" else "fim"


def decidir_especialista(estado: Estado) -> str:
    return estado["rota"] if estado["rota"] in ("financeiro", "agenda", "faq") else "fim"


# ==============================================================================
# GRAFO
# ==============================================================================
grafo = StateGraph(Estado)

grafo.add_node("guardrail_entrada", no_guardrail_entrada)
grafo.add_node("roteador",          no_roteador)
grafo.add_node("financeiro",        no_financeiro)
grafo.add_node("agenda",            no_agenda)
grafo.add_node("faq",               no_faq)
grafo.add_node("orquestrador",      no_orquestrador)
grafo.add_node("guardrail_saida",   no_guardrail_saida)
grafo.add_node("juiz",              no_juiz)

grafo.set_entry_point("guardrail_entrada")

grafo.add_conditional_edges(
    "guardrail_entrada",
    decidir_pos_guardrail_entrada,
    {"roteador": "roteador", "fim": END},
)

grafo.add_conditional_edges(
    "roteador",
    decidir_especialista,
    {"financeiro": "financeiro", "agenda": "agenda", "faq": "faq", "fim": END},
)

grafo.add_edge("financeiro",      "orquestrador")
grafo.add_edge("agenda",          "orquestrador")
grafo.add_edge("faq",             "juiz")              # bypassa o orquestrador e o guardrail de saída
grafo.add_edge("orquestrador",    "guardrail_saida")
grafo.add_edge("guardrail_saida", "juiz")
grafo.add_edge("juiz",            END)

# Memória centralizada no grafo — persiste o Estado inteiro entre turns
memory = MemorySaver()
fluxo_agentes = grafo.compile(checkpointer=memory)


# ==============================================================================
# FLUXO PRINCIPAL
# ==============================================================================
def executar_fluxo_assessor(pergunta_usuario: str, session_id: str, user_id: str = "usuario_teste") -> dict:
    """
    Executa o grafo completo (guardrail -> roteador -> especialista -> orquestrador
    -> guardrail de saida -> juiz) para uma pergunta do usuario.

    Retorna:
        {"resposta": str, "agentes_chamados": list[str]}
    """
    estado_inicial = {
        "messages":         [{"role": "human", "content": pergunta_usuario}],
        "agentes_chamados": [],
        "rota":             "",
        "mapa_pii":         {},
        "raciocinio":       "",
    }

    # O registro abre antes do invoke e fecha no finally, inclusive quando
    # o grafo levanta. A rota /monitor só lê o que ficou anotado.
    turno_id = abrir_turno()
    status = "erro"
    rota = ""
    try:
        estado_final = fluxo_agentes.invoke(
            estado_inicial,
            config={"configurable": {"thread_id": session_id, "user_id": user_id}},
        )

        status = status_do_estado(estado_final)
        rota = estado_final.get("rota") or ""

        print(f"[debug] agentes chamados: {estado_final['agentes_chamados']}")

        return {
            "resposta":         estado_final["messages"][-1].text,
            "agentes_chamados": estado_final["agentes_chamados"],
            "raciocinio":       estado_final.get("raciocinio", ""),
        }
    finally:
        fechar_turno(turno_id, session_id=session_id, rota=rota, status=status)


# ==============================================================================
# LOOP DE CONVERSA — removido na migração para a API
# ------------------------------------------------------------------------------
# Aqui existia um loop `while True` de terminal (modo script), que chamava
# iniciar_sessao() no início e encerrar_sessao() ao digitar "sair".
#
# Ele nunca rodava sozinho ao subir o uvicorn (estava protegido por
# `if __name__ == "__main__":`), mas era o ÚNICO ponto do sistema que chamava
# encerrar_sessao(). Na API, esse papel passa a ser da rota
# POST /sessions/{id}/encerrar (app/routes/sessions.py, Bloco B da Etapa 3).
# ==============================================================================