from datetime import datetime
import pytz
from dotenv import load_dotenv
import psycopg2
from typing import Optional, List
from langchain.tools import tool
from app.tools.args import AddTransactionArgs, QueryTransactionsArgs, DailyBalanceArgs, UpdateTransactionArgs
from app.tools.db import get_conn


# -- conexão com o banco -----------------------------------------------

# -- alias para traduzir os inputs pro banco ---------------------------
TYPE_ALIASES = {
    "INCOME": "INCOME", "ENTRADA": "INCOME", "RECEITA": "INCOME", "SALÁRIO": "INCOME",
    "EXPENSE": "EXPENSES", "EXPENSES": "EXPENSES", "DESPESA": "EXPENSES", "GASTO": "EXPENSES",
    "TRANSFER": "TRANSFER", "TRANSFÊRENCIA": "TRANSFER", "TRANSFERENCIA": "TRANSFER",
}

TYPE_CATEGORIES = {
    # COMIDA
    "COMIDA": "comida", "ALIMENTO": "comida", "ALIMENTOS": "comida",
    "RESTAURANTE": "comida", "LANCHONETE": "comida", "FAST FOOD": "comida",
    "MC DONALDS": "comida", "MCDONALD'S": "comida", "BURGER KING": "comida",
    "PIZZA": "comida", "HAMBURGUER": "comida", "LANCHE": "comida",
    "ALMOÇO": "comida", "JANTAR": "comida", "CAFÉ": "comida",
    "ARROZ": "comida", "FEIJÃO": "comida", "COMPRAS MERCADO": "comida",
    "SUPERMERCADO": "comida", "IFOOD": "comida",

    # BESTEIRA
    "BESTEIRA": "besteira", "DOCE": "besteira", "DOCES": "besteira",
    "CHOCOLATE": "besteira", "BALAS": "besteira", "BALA": "besteira",
    "SORVETE": "besteira", "SNACK": "besteira", "SALGADINHO": "besteira",
    "REFRIGERANTE": "besteira", "COCA": "besteira",

    # ESTUDO
    "ESTUDO": "estudo", "ESCOLA": "estudo", "FACULDADE": "estudo",
    "CURSO": "estudo", "CURSOS": "estudo", "LIVRO": "estudo",
    "LIVROS": "estudo", "MATERIAL": "estudo", "CADERNO": "estudo",
    "CANETA": "estudo", "APOSTILA": "estudo", "EDUCAÇÃO": "estudo",

    # FÉRIAS
    "FERIAS": "férias", "FÉRIAS": "férias", "VIAGEM": "férias",
    "HOTEL": "férias", "PASSAGEM": "férias", "AVIÃO": "férias",
    "AEROPORTO": "férias", "RESORT": "férias", "TURISMO": "férias",

    # TRANSPORTE
    "TRANSPORTE": "transporte", "UBER": "transporte", "99": "transporte",
    "TAXI": "transporte", "ÔNIBUS": "transporte", "METRO": "transporte",
    "GASOLINA": "transporte", "COMBUSTIVEL": "transporte",
    "PEDAGIO": "transporte", "ESTACIONAMENTO": "transporte",
    "UBER": "transaporte",

    # MORADIA
    "MORADIA": "moradia", "ALUGUEL": "moradia", "CONDOMINIO": "moradia",
    "CASA": "moradia", "APARTAMENTO": "moradia", "REFORMA": "moradia",
    "MÓVEIS": "moradia", "MOVEIS": "moradia",

    # SAÚDE
    "SAUDE": "saúde", "SAÚDE": "saúde", "MEDICO": "saúde",
    "CONSULTA": "saúde", "HOSPITAL": "saúde", "REMEDIO": "saúde",
    "REMÉDIO": "saúde", "FARMACIA": "saúde", "PLANO DE SAUDE": "saúde",
    "DENTISTA": "saúde",

    # LAZER
    "LAZER": "lazer", "CINEMA": "lazer", "FILME": "lazer",
    "NETFLIX": "lazer", "SPOTIFY": "lazer", "JOGO": "lazer",
    "GAMES": "lazer", "SHOW": "lazer", "FESTA": "lazer",
    "BALADA": "lazer",

    # CONTAS
    "CONTAS": "contas", "BOLETO": "contas", "LUZ": "contas",
    "ÁGUA": "contas", "AGUA": "contas", "INTERNET": "contas",
    "WIFI": "contas", "ENERGIA": "contas", "TELEFONE": "contas",

    # INVESTIMENTO
    "INVESTIMENTO": "investimento", "INVESTIR": "investimento",
    "AÇÃO": "investimento", "ACOES": "investimento", "AÇÕES": "investimento",
    "CRIPTO": "investimento", "BITCOIN": "investimento",
    "RENDA FIXA": "investimento", "TESOURO DIRETO": "investimento",

    # PRESENTE
    "PRESENTE": "presente", "PRESENTEAR": "presente",
    "ANIVERSARIO": "presente", "ANIVERSÁRIO": "presente",
    "NATAL": "presente", "SURPRESA": "presente",

    # SALÁRIO
    "SALARIO": "salário", "SALÁRIO": "salário", "VALE": "salário",
    "PAGAMENTO": "salário", "CONTRACHEQUE": "salário", "HOLERITE": "salário",
    "RENDA": "salário", "FREELANCE": "salário", "FREELA": "salário", "TRABALHO": "salário",

    # COMPRAS
    "COMPRAS": "compras", "ROUPA": "compras", "ROUPAS": "compras",
    "TENIS": "compras", "TÊNIS": "compras", "SAPATO": "compras", "SAPATOS": "compras",
    "PERFUME": "compras", "MAQUIAGEM": "compras", "COSMETICO": "compras", "COSMÉTICO": "compras",
    "ACESSORIO": "compras", "ACESSÓRIO": "compras", "BOLSA": "compras", "CARTEIRA": "compras",
    "CAMISETA": "compras", "CALCA": "compras", "CALÇA": "compras", "VESTIDO": "compras",
    "SHORTS": "compras", "JAQUETA": "compras", "CASACO": "compras",
    "SHEIN": "compras", "ZARA": "compras", "RENNER": "compras", "RIACHUELO": "compras",

    # OUTROS
    "OUTROS": "outros", "DIVERSOS": "outros", "VARIOS": "outros"
}


# -- funções auxiliares ------------------------------------------------
def _resolve_type_id(cur, type_id: Optional[int], type_name: Optional[str]) -> Optional[int]:
    if type_name:
        t = type_name.strip().upper()
        if t in TYPE_ALIASES:
            t = TYPE_ALIASES[t]
        cur.execute("SELECT id FROM transaction_types WHERE UPPER(type)=%s LIMIT 1;", (t,))
        row = cur.fetchone()
        return row[0] if row else None
    if type_id:
        return int(type_id)
    return 2

def _resolve_type_categories(cur, category_id: Optional[int], category_name: Optional[str]) -> Optional[int]:
    if category_name:
        nome = category_name.strip().upper()

        if nome in TYPE_CATEGORIES:
            nome = TYPE_CATEGORIES[nome]

        # busca pelo nome exato primeiro, depois sem acento como fallback
        cur.execute("SELECT id FROM categories WHERE name ILIKE %s LIMIT 1;", (nome,))
        row = cur.fetchone()
        return row[0] if row else None

    if category_id:
        return int(category_id)
    return 12

def _local_date_filter_sql(field: str = "occurred_at") -> str:
    return f"(({field} AT TIME ZONE 'America/Sao_Paulo')::date = %s::date)"


# -- tools -------------------------------------------------------------
@tool("add_transaction", args_schema=AddTransactionArgs)
def add_transaction(
    amount: float,
    source_text: str,
    occurred_at: Optional[str] = None,
    type_id: Optional[int] = None,
    type_name: Optional[str] = None,
    category_id: Optional[int] = None,
    category_name: Optional[str] = None,
    description: Optional[str] = None,
    payment_method: Optional[str] = None,
) -> dict:
    """Insere uma transação financeira no banco de dados Postgres."""
    conn = get_conn()
    cur = conn.cursor()

    try:
        amount = float(amount)
        if type_id is not None:
            type_id = int(type_id)
        if category_id is not None:
            category_id = int(category_id)

        resolved_type_id = _resolve_type_id(cur, type_id, type_name)
        resolved_category_id = _resolve_type_categories(cur, category_id, category_name)

        if not resolved_type_id:
            return {"status": "error", "message": "Tipo inválido (use type_id ou type_name: INCOME/EXPENSES/TRANSFER)."}

        tz = pytz.timezone("America/Sao_Paulo")
        now_sp = datetime.now(tz).isoformat()

        ts = occurred_at if occurred_at else now_sp

        cur.execute(
            """
            INSERT INTO transactions
                (amount, type, category_id, description, payment_method, occurred_at, source_text)
            VALUES
                (%s, %s, %s, %s, %s, %s::timestamptz, %s)
            RETURNING id, occurred_at;
            """,
            (amount, resolved_type_id, resolved_category_id, description, payment_method, ts, source_text),
        )
        new_id, occurred = cur.fetchone()
        conn.commit()
        return {"status": "ok", "id": new_id, "occurred_at": str(occurred)}

    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}

    finally:
        cur.close()
        conn.close()


@tool("query_transactions", args_schema=QueryTransactionsArgs)
def query_transactions(
    source_text: Optional[str] = None,
    initial_date: Optional[str] = None,
    final_date: Optional[str] = None,
    category_name: Optional[str] = None
) -> dict:
    """
    Consulta transações com filtros por texto (source_text/description), categoria e datas locais (America/Sao_Paulo).
    Sem filtros retorna todas as transações.
    """
    conn = get_conn()
    cur = conn.cursor()

    query = """
        SELECT t.*, c.name AS category_name
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        WHERE 1=1
    """
    params = []

    try:
        if source_text:
            query += " AND (t.source_text ILIKE %s OR t.description ILIKE %s)"
            params.extend([f"%{source_text}%", f"%{source_text}%"])

        if initial_date and final_date:
            query += " AND (t.occurred_at AT TIME ZONE 'America/Sao_Paulo')::date BETWEEN %s::date AND %s::date"
            params.extend([initial_date, final_date])
        elif initial_date:
            query += " AND (t.occurred_at AT TIME ZONE 'America/Sao_Paulo')::date >= %s::date"
            params.append(initial_date)

        if category_name:
            query += " AND c.name ILIKE %s"
            params.append(f"%{category_name}%")

        query += " ORDER BY t.occurred_at DESC"

        cur.execute(query, params)
        rows = cur.fetchall()
        return {"status": "ok", "transactions": rows}

    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}

    finally:
        cur.close()
        conn.close()


@tool("total_balance")
def total_balance() -> dict:
    """Retorna o saldo total (INCOME - EXPENSES) em todo o histórico. Ignora TRANSFER (type=3)."""
    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN type = 1 THEN amount ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN type = 2 THEN amount ELSE 0 END), 0)
            FROM transactions
            WHERE type != 3;
            """
        )
        row = cur.fetchone()
        total_income = float(row[0])
        total_expenses = float(row[1])
        return {
            "status": "ok",
            "total_income": total_income,
            "total_expenses": total_expenses,
            "balance": total_income - total_expenses
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

    finally:
        cur.close()
        conn.close()


@tool("daily_balance", args_schema=DailyBalanceArgs)
def daily_balance(date_local: Optional[str] = None) -> dict:
    """
    Retorna o saldo (INCOME - EXPENSES) do dia local (America/Sao_Paulo).
    Se date_local não for informado, usa o dia atual.
    Ignora TRANSFER (type=3).
    """
    conn = get_conn()
    cur = conn.cursor()

    try:
        if not date_local:
            tz = pytz.timezone("America/Sao_Paulo")
            date_local = datetime.now(tz).strftime("%Y-%m-%d")

        cur.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN type = 1 THEN amount ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN type = 2 THEN amount ELSE 0 END), 0)
            FROM transactions
            WHERE type != 3
              AND (occurred_at AT TIME ZONE 'America/Sao_Paulo')::date = %s::date;
            """,
            (date_local,)
        )
        row = cur.fetchone()
        total_income = float(row[0])
        total_expenses = float(row[1])
        return {
            "status": "ok",
            "date": date_local,
            "total_income": total_income,
            "total_expenses": total_expenses,
            "balance": total_income - total_expenses
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

    finally:
        cur.close()
        conn.close()


@tool("update_transaction", args_schema=UpdateTransactionArgs)
def update_transaction(
    id: Optional[int] = None,
    match_text: Optional[str] = None,
    date_local: Optional[str] = None,
    amount: Optional[float] = None,
    type_id: Optional[int] = None,
    type_name: Optional[str] = None,
    category_id: Optional[int] = None,
    category_name: Optional[str] = None,
    description: Optional[str] = None,
    payment_method: Optional[str] = None,
    occurred_at: Optional[str] = None,
) -> dict:
    """
    Atualiza uma transação existente.
    - Se 'id' for informado: atualiza diretamente por ID.
    - Caso contrário: localiza por match_text + date_local e atualiza.
    """
    if not any([amount, type_id, type_name, category_id, category_name, description, payment_method, occurred_at]):
        return {"status": "error", "message": "Nada para atualizar: forneça pelo menos um campo."}

    conn = get_conn()
    cur = conn.cursor()

    try:
        target_id = id
        if target_id is None:
            if not match_text or not date_local:
                return {"status": "error", "message": "Sem 'id': informe match_text E date_local para localizar o registro."}

            cur.execute(
                f"""
                SELECT t.id FROM transactions t
                WHERE (t.source_text ILIKE %s OR t.description ILIKE %s)
                  AND {_local_date_filter_sql("t.occurred_at")}
                ORDER BY t.occurred_at DESC
                LIMIT 1;
                """,
                (f"%{match_text}%", f"%{match_text}%", date_local)
            )
            row = cur.fetchone()
            if not row:
                return {"status": "error", "message": "Nenhuma transação encontrada para os filtros fornecidos."}
            target_id = row[0]

        resolved_type_id = _resolve_type_id(cur, type_id, type_name) if (type_id or type_name) else None
        resolved_category_id = _resolve_type_categories(cur, None, category_name) if category_name else category_id  # Bug 5 corrigido

        sets = []
        params: List[object] = []
        if amount is not None:
            sets.append("amount = %s")
            params.append(amount)
        if resolved_type_id is not None:
            sets.append("type = %s")
            params.append(resolved_type_id)
        if resolved_category_id is not None:
            sets.append("category_id = %s")
            params.append(resolved_category_id)
        if description is not None:
            sets.append("description = %s")
            params.append(description)
        if payment_method is not None:
            sets.append("payment_method = %s")
            params.append(payment_method)
        if occurred_at is not None:
            sets.append("occurred_at = %s::timestamptz")
            params.append(occurred_at)

        if not sets:
            return {"status": "error", "message": "Nenhum campo válido para atualizar."}

        params.append(target_id)
        cur.execute(f"UPDATE transactions SET {', '.join(sets)} WHERE id = %s;", params)
        rows_affected = cur.rowcount
        conn.commit()

        cur.execute(
            """
            SELECT t.id, t.occurred_at, t.amount, tt.type,
                   c.name, t.description, t.payment_method, t.source_text
            FROM transactions t
            JOIN transaction_types tt ON tt.id = t.type
            LEFT JOIN categories c ON c.id = t.category_id
            WHERE t.id = %s;
            """,
            (target_id,)
        )
        r = cur.fetchone()
        updated = None
        if r:
            updated = {
                "id": r[0], "occurred_at": str(r[1]), "amount": float(r[2]),
                "type": r[3], "category": r[4], "description": r[5],
                "payment_method": r[6], "source_text": r[7],
            }

        return {"status": "ok", "rows_affected": rows_affected, "id": target_id, "updated": updated}

    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}

    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass


# -- exporta a lista de tools ------------------------------------------
TOOLS = [add_transaction, query_transactions, total_balance, daily_balance, update_transaction]