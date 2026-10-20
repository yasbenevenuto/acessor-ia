from fastapi import FastAPI
from app.routes.chat import router as chat_router
from app.routes.sessions import router as sessions_router
from app.routes.profile import router as profile_router
from app.core.config import validar_config, FRONTEND_DIR
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.routes.monitor import router as monitor_router

app = FastAPI(
    title="Acessor AI",
    description="Acessor financeiro e de agenda com LangChain e LangGraph",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# A ordem importa por causa do mount em "/" lá embaixo: qualquer rota
# declarada DEPOIS dele nunca seria alcançada (o mount captura tudo que não
# casou com nenhuma rota registrada antes).
app.include_router(chat_router)
app.include_router(sessions_router)
app.include_router(profile_router)
app.include_router(monitor_router)

@app.get("/health")
def health() -> dict:
    problems = validar_config()
    return {
        "status": "ok" if not problems else "atencao",
        "problemas_de_configuracao": problems}

if (FRONTEND_DIR / "perfil" / "index.html").exists():
    app.mount("/perfil", StaticFiles(directory=FRONTEND_DIR / "perfil", html=True), name="perfil")

# A página do painel é servida à parte, em "/painel" (e não em "/monitor"),
# porque "/monitor" já é a rota de API que devolve o JSON (app/routes/monitor.py).
# E como o arquivo se chama "monitor.html" (não "index.html"), um mount estático
# com html=True não o serviria sozinho — por isso é uma rota explícita.
_MONITOR_HTML = FRONTEND_DIR / "monitor" / "monitor.html"
if _MONITOR_HTML.exists():
    @app.get("/painel")
    def painel_ui() -> FileResponse:
        return FileResponse(_MONITOR_HTML)

# Este mount fica por último de propósito (mesmo motivo do comentário acima
# sobre os routers): montado em "/", ele captura qualquer caminho que não
# bateu com nada registrado antes — inclusive o /perfil acima, se viesse depois.
if (FRONTEND_DIR / "chat" / "index.html").exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR / "chat", html=True), name="chat")