"""
Einmalig: Kopiert alle Mai-2026-Rechnungen in den outgoing_export-Ordner.
Aufruf: docker compose -f docker-compose.prod.yml exec -T backend python3 scripts/copy_invoices_to_outgoing.py
"""
import os
import shutil
from datetime import date

from sqlalchemy import create_engine, text

engine = create_engine(os.environ["DATABASE_URL_SYNC"])

with engine.connect() as conn:
    rows = conn.execute(
        text("SELECT invoice_number FROM invoices WHERE invoice_date = '2026-05-01' AND status != 'cancelled'")
    ).fetchall()

outgoing = os.path.join("/app/storage/invoices/outgoing_export")
os.makedirs(outgoing, exist_ok=True)

copied, missing = 0, 0
for row in rows:
    num = row[0].strip()
    src = f"/app/storage/invoices/{num}.pdf"
    dst = os.path.join(outgoing, f"{num}.pdf")
    if os.path.exists(src):
        shutil.copy2(src, dst)
        print(f"Kopiert: {num}.pdf")
        copied += 1
    else:
        print(f"FEHLT:   {num}.pdf")
        missing += 1

print(f"\nFertig: {copied} kopiert, {missing} fehlend.")
