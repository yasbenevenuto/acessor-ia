from app.core.llms import llm_especialista, llm_gemini, llm_groq_pesado, llm_rapido
from app.graph.prompts import (
    AGENDA_PROMPT_COMPLETO,
    FAQ_PROMPT_COMPLETO,
    FINANCEIRO_PROMPT_COMPLETO,
    ORQUESTRADOR_PROMPT_COMPLETO,
    ROUTER_PROMPT_COMPLETO,
)
from app.tools.financeiro import TOOLS
from app.tools.calendar_mcp import carregar_tools_calendar
from app.tools.faq import faq_retriever
from app.tools.memoria import TOOLS_MEMORIA
from app.tools.perfil import TOOLS_PERFIL
from langchain.agents import create_agent
import threading

# ==============================================================================
# AGENTES
# ------------------------------------------------------------------------------
# TOOLS_MEMORIA (buscar_historico) vai para o roteador, o financeiro e a
# agenda, porque cada um usa a memória para coisas diferentes:
#
#   roteador     → perguntas que SÓ dependem do passado ("o que eu te falei
#                  sobre a viagem?"). Não existe especialista para isso; sem a
#                  tool aqui, a pergunta cairia em fora_escopo.
#   especialista → perguntas em que o passado é insumo da RESPOSTA ("lembrando
#                  da viagem, quanto preciso separar?"). O resultado da tool
#                  nasce dentro do contexto dele e alimenta o JSON de saída.
#
# O FAQ fica de fora de propósito: ele responde sobre as regras do Assessor.AI
# a partir do PDF, não sobre o que este usuário conversou. O orquestrador
# também fica de fora: ele só reformata o JSON que já chegou, não decide nada.
# ==============================================================================
router_app = create_agent(
    model=llm_rapido,
    tools=TOOLS_MEMORIA,
    system_prompt=ROUTER_PROMPT_COMPLETO,
)

financeiro_app = create_agent(
    model=llm_especialista,
    tools=TOOLS + TOOLS_MEMORIA + TOOLS_PERFIL,
    system_prompt=FINANCEIRO_PROMPT_COMPLETO,
)

# A agenda usa o Google Calendar via MCP. As tools do Calendar só existem depois
# que o servidor MCP sobe (npx), então o agente é montado na PRIMEIRA mensagem de
# agenda — e não no import — para o app subir rápido e sem depender do Google.
# Se a conexão falhar, nada é guardado: a próxima mensagem tenta de novo.
_agenda_app = None
_agenda_trava = threading.Lock()


def get_agenda_app():
    global _agenda_app
    with _agenda_trava:
        if _agenda_app is None:
            _agenda_app = create_agent(
                model=llm_especialista,
                tools=carregar_tools_calendar() + TOOLS_MEMORIA,
                system_prompt=AGENDA_PROMPT_COMPLETO,
            )
        return _agenda_app

orquestrador_app = create_agent(
    model=llm_rapido,
    system_prompt=ORQUESTRADOR_PROMPT_COMPLETO,
)

faq_app = create_agent(
    model=llm_rapido,
    tools=[faq_retriever],
    system_prompt=FAQ_PROMPT_COMPLETO,
)
