from app.core.config import DATABASE_URL
import psycopg2

def get_conn():
    """Abre e devolve uma conexão com o Postgres. Quem chama fecha"""
    return psycopg2.connect(DATABASE_URL)