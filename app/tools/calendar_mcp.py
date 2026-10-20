"""
Ponte entre o agente de agenda (SÍNCRONO) e o MCP do Google Calendar (ASSÍNCRONO).

Por que isso existe
-------------------
O grafo do Assessor.IA roda tudo de forma síncrona (agente.invoke(...)), mas as
tools que vêm de um servidor MCP são assíncronas: chamá-las num .invoke() normal
dá erro. Em vez de converter o projeto inteiro para async, este módulo:

  1. sobe o servidor MCP (@cocal/google-calendar-mcp, via npx) UMA vez, num
     processo filho (stdio), dentro de uma thread própria com event loop próprio;
  2. mantém a sessão aberta enquanto o app roda (subir o npx a cada mensagem
     custaria vários segundos);
  3. expõe cada tool do Calendar como uma tool SÍNCRONA comum, que por baixo
     despacha a chamada para o event loop dessa thread e espera o resultado.

A conexão é PREGUIÇOSA: nada é iniciado no import nem no startup do FastAPI. O
servidor só sobe na primeira mensagem que chegar na rota "agenda". Se o Calendar
estiver indisponível, o app continua de pé e só a agenda devolve um aviso.

Pré-requisitos (uma vez só): veja o passo a passo no .env.example.
"""

import asyncio
import atexit
import logging
import shutil
import threading
from concurrent.futures import TimeoutError as FuturoTimeout
from pathlib import Path
from typing import Any

from langchain_core.tools import StructuredTool, ToolException

from app.core.config import (
    BASE_DIR,
    GOOGLE_CALENDAR_MCP_TOKEN_PATH,
    GOOGLE_OAUTH_CREDENTIALS,
)

log = logging.getLogger("assessor.calendar_mcp")

# Pacote npm do servidor MCP.
PACOTE_MCP = "@cocal/google-calendar-mcp"

# O servidor expõe mais tools do que o agente precisa (contas, cores, convites...).
# Só estas chegam ao agente — o resto fica fora do alcance do modelo de propósito.
TOOLS_PERMITIDAS = {
    "get-current-time",
    "list-events",
    "search-events",
    "get-event",
    "get-freebusy",
    "create-event",
    "update-event",
    "delete-event",
}

TIMEOUT_CONEXAO_S = 120   # a 1ª subida baixa o pacote via npx; pode demorar
TIMEOUT_CHAMADA_S = 60


class CalendarIndisponivel(RuntimeError):
    """O servidor MCP do Google Calendar não pôde ser iniciado/conectado."""


def _caminho_credenciais() -> Path:
    if not GOOGLE_OAUTH_CREDENTIALS:
        raise CalendarIndisponivel(
            "GOOGLE_OAUTH_CREDENTIALS não está definido no .env "
            "(caminho do JSON de credenciais OAuth do Google)."
        )
    caminho = Path(GOOGLE_OAUTH_CREDENTIALS).expanduser()
    if not caminho.is_absolute():
        caminho = BASE_DIR / caminho
    if not caminho.exists():
        raise CalendarIndisponivel(f"Arquivo de credenciais do Google não encontrado: {caminho}")
    return caminho


def _como_texto(resultado: Any) -> str:
    """Normaliza o retorno da tool MCP (str ou lista de blocos) para texto puro."""
    if isinstance(resultado, str):
        return resultado
    if isinstance(resultado, list):
        partes = []
        for bloco in resultado:
            if isinstance(bloco, dict) and "text" in bloco:
                partes.append(str(bloco["text"]))
            elif isinstance(bloco, str):
                partes.append(bloco)
            else:
                partes.append(str(bloco))
        return "\n".join(partes)
    return str(resultado)


class _PonteCalendar:
    def __init__(self) -> None:
        self._trava = threading.RLock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._parar: asyncio.Event | None = None    # vive dentro do event loop da thread
        self._tools_async: dict[str, Any] = {}      # nome -> tool assíncrona do adapter
        self._tools_sync: list[StructuredTool] | None = None
        self._erro: BaseException | None = None

    # ------------------------------------------------------------------
    # Ciclo de vida da conexão
    # ------------------------------------------------------------------
    def carregar(self) -> list[StructuredTool]:
        """Garante a conexão e devolve as tools síncronas para o agente."""
        with self._trava:
            self._garantir()
            return list(self._tools_sync or [])

    def _garantir(self) -> None:
        with self._trava:
            if self._tools_sync is None:
                self._conectar()

    def _conectar(self) -> None:
        credenciais = _caminho_credenciais()
        env = {"GOOGLE_OAUTH_CREDENTIALS": str(credenciais)}
        if GOOGLE_CALENDAR_MCP_TOKEN_PATH:
            env["GOOGLE_CALENDAR_MCP_TOKEN_PATH"] = GOOGLE_CALENDAR_MCP_TOKEN_PATH

        npx = shutil.which("npx")
        if not npx:
            raise CalendarIndisponivel(
                "npx não encontrado no PATH. Instale o Node.js (versão LTS) e reabra o terminal."
            )

        config_servidor = {
            "gcal": {
                "transport": "stdio",
                "command": npx,
                "args": ["-y", PACOTE_MCP],
                "env": env,
            }
        }

        pronto = threading.Event()
        self._erro = None
        loop = asyncio.new_event_loop()
        self._loop = loop

        def alvo() -> None:
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._sessao(config_servidor, pronto))
            finally:
                pronto.set()
                loop.close()

        self._thread = threading.Thread(target=alvo, name="gcal-mcp", daemon=True)
        self._thread.start()

        if not pronto.wait(TIMEOUT_CONEXAO_S):
            self._derrubar()
            raise CalendarIndisponivel("Tempo esgotado ao iniciar o servidor MCP do Google Calendar.")
        if self._erro is not None or self._tools_sync is None:
            erro = self._erro
            self._derrubar()
            raise CalendarIndisponivel(
                f"Não foi possível conectar ao Google Calendar: {erro}"
            ) from erro

    async def _sessao(self, config_servidor: dict, pronto: threading.Event) -> None:
        """Roda dentro da thread: abre a sessão MCP e a mantém viva até pedirem para parar."""
        try:
            # Import tardio: se o pacote não estiver instalado, só a agenda reclama
            # (o resto do Assessor.IA continua subindo normalmente).
            from langchain_mcp_adapters.client import MultiServerMCPClient
            from langchain_mcp_adapters.tools import load_mcp_tools

            cliente = MultiServerMCPClient(config_servidor)
            async with cliente.session("gcal") as sessao:
                todas = await load_mcp_tools(sessao)
                self._tools_async = {t.name: t for t in todas if t.name in TOOLS_PERMITIDAS}
                if not self._tools_async:
                    nomes = ", ".join(sorted(t.name for t in todas)) or "nenhuma"
                    raise RuntimeError(f"Nenhuma tool esperada do Calendar foi encontrada (recebi: {nomes}).")

                self._parar = asyncio.Event()
                self._tools_sync = [self._envolver(t) for t in self._tools_async.values()]
                log.info("Google Calendar MCP conectado: %s", ", ".join(sorted(self._tools_async)))
                pronto.set()
                await self._parar.wait()
        except BaseException as e:  # noqa: BLE001 — qualquer falha vira CalendarIndisponivel
            self._erro = e
            log.error("Falha na sessão do Google Calendar MCP: %s", e)
        finally:
            pronto.set()

    def _derrubar(self) -> None:
        """Pede para a sessão atual encerrar (fecha também o processo do npx)."""
        with self._trava:
            self._tools_sync = None
            loop, parar, thread = self._loop, self._parar, self._thread
            self._parar = None
            if loop is not None and parar is not None and not loop.is_closed():
                loop.call_soon_threadsafe(parar.set)
            if thread is not None and thread is not threading.current_thread():
                thread.join(timeout=5)

    def fechar(self) -> None:
        self._derrubar()

    # ------------------------------------------------------------------
    # Tools síncronas
    # ------------------------------------------------------------------
    def _envolver(self, tool_async: Any) -> StructuredTool:
        nome = tool_async.name

        def _executar(**kwargs: Any) -> str:
            return self.chamar(nome, kwargs)

        return StructuredTool(
            name=nome,
            description=tool_async.description,
            args_schema=tool_async.args_schema,   # schema JSON vindo do próprio servidor MCP
            func=_executar,
        )

    def chamar(self, nome: str, argumentos: dict) -> str:
        """Executa uma tool do Calendar de forma síncrona. Nunca levanta: devolve texto."""
        try:
            with self._trava:
                self._garantir()
                tool = self._tools_async[nome]
                loop = self._loop
            futuro = asyncio.run_coroutine_threadsafe(tool.ainvoke(argumentos), loop)
            return _como_texto(futuro.result(timeout=TIMEOUT_CHAMADA_S))
        except CalendarIndisponivel as e:
            return f"ERRO: Google Calendar indisponível. {e}"
        except FuturoTimeout:
            return "ERRO: o Google Calendar demorou demais para responder."
        except ToolException as e:
            # Erro "de negócio" da tool (ex.: evento não encontrado, argumento inválido).
            return f"ERRO da tool {nome}: {e}"
        except Exception as e:  # noqa: BLE001
            if type(e).__name__ == "McpError":
                # Erro de protocolo do servidor (ex.: ainda não autenticado, -32600).
                return f"ERRO do servidor Google Calendar: {e}"
            # Qualquer outra coisa sugere conexão caída: derruba para reconectar na próxima.
            log.exception("Falha ao chamar %s; a conexão será refeita na próxima chamada.", nome)
            self._derrubar()
            return f"ERRO ao acessar o Google Calendar: {e}"


_ponte = _PonteCalendar()
atexit.register(_ponte.fechar)


def carregar_tools_calendar() -> list[StructuredTool]:
    """Tools do Google Calendar prontas para o agente de agenda (levanta CalendarIndisponivel)."""
    return _ponte.carregar()
