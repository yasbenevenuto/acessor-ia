import os
from pathlib import Path
from dotenv import load_dotenv

TYPESAFE_API_KEY = os.getenv("TYPESAFE_API_KEY")

# BASE_DIR aponta para migracao_fastAPI/. Montado a partir da localização
# do próprio arquivo: não depende da pasta de onde você rodou o uvicorn.
BASE_DIR     = Path(__file__).resolve().parent.parent.parent
DATA_DIR     = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"

FAQ_PDF_PATH = DATA_DIR / "FAQ_assessor_v1.2.pdf"

load_dotenv(BASE_DIR / ".env")          # o único load_dotenv() do projeto

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY   = os.getenv("GROQ_API_KEY")
DATABASE_URL   = os.getenv("DATABASE_URL")
MONGODB_URI    = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
QDRANT_URL     = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

# Google Calendar (MCP). O app sobe sem isso; só a rota de agenda depende.
GOOGLE_OAUTH_CREDENTIALS       = os.getenv("GOOGLE_OAUTH_CREDENTIALS")        # caminho do JSON OAuth (Desktop app)
GOOGLE_CALENDAR_MCP_TOKEN_PATH = os.getenv("GOOGLE_CALENDAR_MCP_TOKEN_PATH")  # opcional: onde guardar o token

OBRIGATORIAS = {
    "GEMINI_API_KEY": GEMINI_API_KEY,
    "GROQ_API_KEY":   GROQ_API_KEY,
    "DATABASE_URL":   DATABASE_URL,
    "MONGODB_URI":    MONGODB_URI,
    "QDRANT_URL":     QDRANT_URL,
    "QDRANT_API_KEY": QDRANT_API_KEY
}


def validar_config() -> list[str]:
    """Devolve a lista de problemas de configuração (vazia = tudo certo)."""
    problemas = []
    for nome, valor in OBRIGATORIAS.items():
        if not valor:
            problemas.append(f"Variável ausente no .env: {nome}")
    if not FAQ_PDF_PATH.exists():
        problemas.append(f"PDF do FAQ não encontrado em: {FAQ_PDF_PATH}")

    # Google Calendar: não é "obrigatória" para o app subir, mas a agenda depende dela.
    if not GOOGLE_OAUTH_CREDENTIALS:
        problemas.append("Variável ausente no .env: GOOGLE_OAUTH_CREDENTIALS (agenda/Google Calendar)")
    else:
        credenciais = Path(GOOGLE_OAUTH_CREDENTIALS).expanduser()
        if not credenciais.is_absolute():
            credenciais = BASE_DIR / credenciais
        if not credenciais.exists():
            problemas.append(f"Credenciais do Google Calendar não encontradas em: {credenciais}")
    return problemas
