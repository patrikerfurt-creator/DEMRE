import re
import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.api.deps import get_db, require_admin
from app.models.user import User

router = APIRouter(prefix="/query", tags=["query"])
logger = structlog.get_logger()

DB_SCHEMA = """
PostgreSQL-Datenbankschema (DEMRE Immobilienverwaltungs-Abrechnungssystem):

Tabellen:
- customers (id uuid PK, customer_number varchar, customer_type varchar [weg/company/person], company_name varchar, salutation varchar, first_name varchar, last_name varchar, address_line1 varchar, address_line2 varchar, postal_code varchar, city varchar, country_code varchar, email varchar, phone varchar, vat_id varchar, iban varchar, bic varchar, bank_name varchar, account_holder varchar, datev_account_number varchar, is_active bool, notes text, created_at timestamptz)
- contracts (id uuid PK, contract_number varchar, customer_id uuid FK→customers, status varchar [active/inactive/cancelled], start_date date, end_date date, billing_day smallint, payment_terms_days int, property_ref varchar, notes text, created_at timestamptz)
- contract_items (id uuid PK, contract_id uuid FK→contracts, article_id uuid FK→articles, billing_period varchar [monthly/annual], is_active bool, quantity numeric, override_price numeric, override_vat_rate numeric, description_override varchar, sort_order smallint, valid_from date, valid_until date)
- articles (id uuid PK, article_number varchar, name varchar, description text, unit_price numeric, vat_rate numeric, unit varchar, is_active bool)
- invoices (id uuid PK, invoice_number varchar, contract_id uuid FK→contracts, customer_id uuid FK→customers, invoice_date date, due_date date, billing_period_from date, billing_period_to date, status varchar [draft/issued/sent/paid/overdue/cancelled], subtotal_net numeric, total_vat numeric, total_gross numeric, currency varchar, notes text, created_at timestamptz)
- invoice_items (id uuid PK, invoice_id uuid FK→invoices, article_id uuid FK→articles, position smallint, description varchar, quantity numeric, unit_price_net numeric, vat_rate numeric, total_net numeric, total_vat numeric, total_gross numeric)
- creditors (id uuid PK, creditor_number varchar, company_name varchar, first_name varchar, last_name varchar, email varchar, iban varchar, bic varchar, address_line1 varchar, postal_code varchar, city varchar, country_code varchar, is_active bool, notes text, created_at timestamptz)
- incoming_invoices (id uuid PK, document_number varchar, external_invoice_number varchar, creditor_id uuid FK→creditors, invoice_date date, receipt_date date, due_date date, total_net numeric, total_vat numeric, total_gross numeric, currency varchar, description text, cost_account varchar, status varchar [open/approved/scheduled/paid/rejected/cancelled], approved_at timestamptz, paid_at timestamptz, is_direct_debit bool, notes text, created_at timestamptz)
- expense_receipts (id uuid PK, receipt_number varchar, submitted_by uuid FK→users, merchant varchar, amount_gross numeric, amount_net numeric, vat_amount numeric, vat_rate numeric, receipt_date date, category varchar, payment_method varchar, status varchar, iban varchar, notes text, created_at timestamptz)
- users (id uuid PK, email varchar, full_name varchar, is_active bool, is_admin bool, employee_number varchar)

Beispiele für typische Abfragen:
- Kunden OHNE Vertrag (Aborechnung): SELECT c.customer_number, COALESCE(c.company_name, c.first_name || ' ' || c.last_name) AS name FROM customers c LEFT JOIN contracts co ON co.customer_id = c.id WHERE co.id IS NULL AND c.is_active = true
- Kunden MIT aktivem Vertrag: SELECT c.customer_number, COALESCE(c.company_name, c.first_name || ' ' || c.last_name) AS name FROM customers c INNER JOIN contracts co ON co.customer_id = c.id WHERE co.status = 'active'
- Eingangsrechnungen eines Kreditors: JOIN creditors ON creditor_id = creditors.id WHERE creditor_number = '10001'
- Offene Eingangsrechnungen: WHERE status = 'open'
- Summe nach Kreditor: GROUP BY creditors.company_name
"""

FORBIDDEN = re.compile(
    r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|COPY|EXECUTE|CALL)\b',
    re.IGNORECASE,
)

SYSTEM_PROMPT = f"""Du bist ein PostgreSQL-Experte für ein deutsches Immobilienverwaltungs-Abrechnungssystem.
Basierend auf dem folgenden Datenbankschema generierst du präzise SELECT-Abfragen.

{DB_SCHEMA}

Regeln:
- Antworte NUR mit dem SQL-Statement — keine Erklärungen, keine Markdown-Code-Blöcke, kein Semikolon am Ende
- Ausschließlich SELECT-Abfragen
- Maximal 200 Zeilen (LIMIT 200 wenn kein explizites Limit angegeben)
- Verwende aussagekräftige Spaltennamen mit AS
- Geldbeträge mit ROUND(..., 2)
- Bei unklarer Frage oder fehlenden Daten: SELECT 'Frage kann nicht beantwortet werden' AS hinweis
- Alle Textwerte in der Datenbank sind auf Deutsch"""


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    sql: str
    columns: list[str]
    rows: list[list]
    row_count: int


@router.post("", response_model=QueryResponse)
async def run_natural_language_query(
    req: QueryRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    from app.config import settings

    if not settings.anthropic_api_key:
        raise HTTPException(status_code=503, detail="Kein ANTHROPIC_API_KEY konfiguriert — KI-Abfragen nicht verfügbar")

    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Frage darf nicht leer sein")

    import anthropic
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": req.question}],
        )
    except Exception as e:
        logger.error("query.ai_error", error=str(e))
        raise HTTPException(status_code=502, detail=f"KI-Fehler: {str(e)}")

    sql = response.content[0].text.strip()
    if sql.startswith("```"):
        parts = sql.split("```", 2)
        sql = parts[1].lstrip("sql").lstrip("SQL").strip()
    sql = sql.rstrip(";")

    if not sql.upper().lstrip().startswith("SELECT"):
        raise HTTPException(status_code=400, detail="Nur SELECT-Abfragen sind erlaubt")
    if FORBIDDEN.search(sql):
        raise HTTPException(status_code=400, detail="Ungültige SQL-Operation erkannt")

    try:
        result = await db.execute(text(sql))
        columns = list(result.keys())
        rows = [[str(v) if v is not None else None for v in row] for row in result.fetchall()]
        logger.info("query.success", question=req.question, row_count=len(rows))
        return QueryResponse(sql=sql, columns=columns, rows=rows, row_count=len(rows))
    except Exception as e:
        logger.error("query.sql_error", sql=sql, error=str(e))
        raise HTTPException(status_code=400, detail=f"SQL-Fehler: {str(e)}")
