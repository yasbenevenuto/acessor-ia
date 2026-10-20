"""
Schemas (args_schema) usados pelas tools do agente financeiro em app/tools/financeiro.py.
"""
from typing import Optional
from pydantic import BaseModel, Field


class AddTransactionArgs(BaseModel):
    amount: float = Field(..., description="Valor da transação, sempre positivo.")
    source_text: str = Field(..., description="Texto literal digitado pelo usuário, sem alterações.")
    occurred_at: Optional[str] = Field(
        None, description="Data/hora da transação em ISO 8601. Se omitido, usa o momento atual."
    )
    type_id: Optional[int] = Field(None, description="ID do tipo de transação (alternativa a type_name).")
    type_name: Optional[str] = Field(
        None, description="Tipo da transação: INCOME, EXPENSES ou TRANSFER."
    )
    category_id: Optional[int] = Field(None, description="ID da categoria (alternativa a category_name).")
    category_name: Optional[str] = Field(
        None,
        description=(
            "Categoria: comida, besteira, estudo, férias, transporte, moradia, "
            "saúde, lazer, contas, investimento, presente, salário, compras, outros."
        ),
    )
    description: Optional[str] = Field(None, description="Breve descrição da transação.")
    payment_method: Optional[str] = Field(None, description="Forma de pagamento, se informada.")


class QueryTransactionsArgs(BaseModel):
    source_text: Optional[str] = Field(
        None, description="Texto para buscar em source_text ou description (busca parcial)."
    )
    initial_date: Optional[str] = Field(None, description="Data inicial (YYYY-MM-DD).")
    final_date: Optional[str] = Field(None, description="Data final (YYYY-MM-DD).")
    category_name: Optional[str] = Field(None, description="Nome da categoria para filtrar.")


class DailyBalanceArgs(BaseModel):
    date_local: Optional[str] = Field(
        None, description="Data local (YYYY-MM-DD, America/Sao_Paulo). Se omitido, usa hoje."
    )


class AddEventArgs(BaseModel):
    title: str = Field(..., description="Título do compromisso.")
    start_time: str = Field(..., description="Data/hora de início em ISO 8601 (YYYY-MM-DDTHH:MM).")
    source_text: str = Field(..., description="Texto literal digitado pelo usuário, sem alterações.")
    end_time: Optional[str] = Field(
        None, description="Data/hora de término em ISO 8601. Pode ficar em aberto."
    )
    location: Optional[str] = Field(None, description="Local do compromisso.")
    notes: Optional[str] = Field(None, description="Observações/detalhes do compromisso.")


class QueryEventsArgs(BaseModel):
    initial_date: Optional[str] = Field(None, description="Data inicial (YYYY-MM-DD).")
    final_date: Optional[str] = Field(None, description="Data final (YYYY-MM-DD).")
    search_text: Optional[str] = Field(None, description="Texto para buscar em title/notes.")


class UpdateEventArgs(BaseModel):
    id: Optional[int] = Field(None, description="ID do compromisso a atualizar, se conhecido.")
    match_text: Optional[str] = Field(
        None, description="Texto para localizar o compromisso quando o ID não é conhecido."
    )
    title: Optional[str] = Field(None, description="Novo título.")
    start_time: Optional[str] = Field(None, description="Nova data/hora de início (ISO 8601).")
    end_time: Optional[str] = Field(None, description="Nova data/hora de término (ISO 8601).")
    location: Optional[str] = Field(None, description="Novo local.")
    notes: Optional[str] = Field(None, description="Novas observações.")
    status: Optional[str] = Field(None, description="Novo status: 'confirmado' ou 'cancelado'.")


class UpdateTransactionArgs(BaseModel):
    id: Optional[int] = Field(None, description="ID da transação a atualizar, se conhecido.")
    match_text: Optional[str] = Field(
        None, description="Texto para localizar a transação quando o ID não é conhecido."
    )
    date_local: Optional[str] = Field(
        None, description="Data local (YYYY-MM-DD) usada junto com match_text para localizar o registro."
    )
    amount: Optional[float] = Field(None, description="Novo valor.")
    type_id: Optional[int] = Field(None, description="Novo ID de tipo.")
    type_name: Optional[str] = Field(None, description="Novo tipo: INCOME, EXPENSES ou TRANSFER.")
    category_id: Optional[int] = Field(None, description="Novo ID de categoria.")
    category_name: Optional[str] = Field(None, description="Nova categoria.")
    description: Optional[str] = Field(None, description="Nova descrição.")
    payment_method: Optional[str] = Field(None, description="Nova forma de pagamento.")
    occurred_at: Optional[str] = Field(None, description="Nova data/hora ISO 8601.")
