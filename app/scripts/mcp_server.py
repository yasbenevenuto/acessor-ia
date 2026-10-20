import sys
from pathlib import Path
from typing import Annotated, Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from app.tools.financeiro import (
    add_transaction as _add_transaction,
    daily_balance as _daily_balance,
    query_transactions as _query_transactions,
    total_balance as _total_balance,
    update_transaction as _update_transaction,
)

mcp = MCPServer(
    name="assessor-financeiro",
    version="1.0.0",
    instructions="Ferramentas financeiras do Assessor.AI...",
)

LEITURA = ToolAnnotations(readOnlyHint=True)
ESCRITA = ToolAnnotations(readOnlyHint=False, destructiveHint=False)


@mcp.tool(
    name="add_transaction",
    description="Insere uma transação financeira (receita, despesa ou transferência) no banco.",
    annotations=ESCRITA,
)
def add_transaction(
    amount: Annotated[float, Field(description="Valor da transação")],
    source_text: Annotated[str, Field(description="Texto original enviado pelo usuário")],
    occurred_at: Annotated[Optional[str], Field(description="Data/hora ISO; se omitido, usa agora (America/Sao_Paulo)")] = None,
    type_id: Annotated[Optional[int], Field(description="ID do tipo (1=INCOME, 2=EXPENSES, 3=TRANSFER)")] = None,
    type_name: Annotated[Optional[str], Field(description="Nome do tipo: INCOME/EXPENSES/TRANSFER")] = None,
    category_id: Annotated[Optional[int], Field(description="ID da categoria")] = None,
    category_name: Annotated[Optional[str], Field(description="Nome da categoria (ex: comida, transporte)")] = None,
    description: Annotated[Optional[str], Field(description="Descrição livre da transação")] = None,
    payment_method: Annotated[Optional[str], Field(description="Forma de pagamento")] = None,
) -> dict[str, Any]:
    return _add_transaction.invoke({
        "amount": amount,
        "source_text": source_text,
        "occurred_at": occurred_at,
        "type_id": type_id,
        "type_name": type_name,
        "category_id": category_id,
        "category_name": category_name,
        "description": description,
        "payment_method": payment_method,
    })


@mcp.tool(
    name="query_transactions",
    description="Consulta transações por texto, categoria e/ou intervalo de datas locais.",
    annotations=LEITURA,
)
def query_transactions(
    source_text: Annotated[Optional[str], Field(description="Filtro de texto em source_text/description")] = None,
    initial_date: Annotated[Optional[str], Field(description="Data inicial (YYYY-MM-DD, fuso local)")] = None,
    final_date: Annotated[Optional[str], Field(description="Data final (YYYY-MM-DD, fuso local)")] = None,
    category_name: Annotated[Optional[str], Field(description="Nome (ou parte) da categoria")] = None,
) -> dict[str, Any]:
    return _query_transactions.invoke({
        "source_text": source_text,
        "initial_date": initial_date,
        "final_date": final_date,
        "category_name": category_name,
    })


@mcp.tool(
    name="total_balance",
    description="Retorna o saldo total (INCOME - EXPENSES) de todo o histórico, ignorando TRANSFER.",
    annotations=LEITURA,
)
def total_balance() -> dict[str, Any]:
    return _total_balance.invoke({})


@mcp.tool(
    name="daily_balance",
    description="Retorna o saldo (INCOME - EXPENSES) de um dia local específico, ignorando TRANSFER.",
    annotations=LEITURA,
)
def daily_balance(
    date_local: Annotated[Optional[str], Field(description="Data local YYYY-MM-DD; se omitida, usa hoje")] = None,
) -> dict[str, Any]:
    return _daily_balance.invoke({"date_local": date_local})


@mcp.tool(
    name="update_transaction",
    description="Atualiza uma transação existente, por id ou por match_text + date_local.",
    annotations=ESCRITA,
)
def update_transaction(
    id: Annotated[Optional[int], Field(description="ID direto da transação")] = None,
    match_text: Annotated[Optional[str], Field(description="Texto para localizar, se id não for informado")] = None,
    date_local: Annotated[Optional[str], Field(description="Data local YYYY-MM-DD, usada junto com match_text")] = None,
    amount: Annotated[Optional[float], Field(description="Novo valor")] = None,
    type_id: Annotated[Optional[int], Field(description="Novo type_id")] = None,
    type_name: Annotated[Optional[str], Field(description="Novo type_name")] = None,
    category_id: Annotated[Optional[int], Field(description="Nova category_id")] = None,
    category_name: Annotated[Optional[str], Field(description="Nova category_name")] = None,
    description: Annotated[Optional[str], Field(description="Nova descrição")] = None,
    payment_method: Annotated[Optional[str], Field(description="Novo método de pagamento")] = None,
    occurred_at: Annotated[Optional[str], Field(description="Nova data/hora ISO")] = None,
) -> dict[str, Any]:
    return _update_transaction.invoke({
        "id": id,
        "match_text": match_text,
        "date_local": date_local,
        "amount": amount,
        "type_id": type_id,
        "type_name": type_name,
        "category_id": category_id,
        "category_name": category_name,
        "description": description,
        "payment_method": payment_method,
        "occurred_at": occurred_at,
    })

if __name__ == "__main__":
    from app.core.config import DATABASE_URL

    if not DATABASE_URL:
        print("[assessor-financeiro] DATABASE_URL ausente no .env", file=sys.stderr)

    mcp.run(transport="stdio")
