"""
KI-basierte Rechnungsdaten-Extraktion via Claude Vision.
Liest PDF- und Bilddateien aus und gibt strukturierte Rechnungsdaten zurück.
"""
import base64
import json
import os
from typing import Optional
import structlog

logger = structlog.get_logger()

SUPPORTED_IMAGE_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}

EXTRACTION_PROMPT = """Analysiere diese Eingangsrechnung und extrahiere alle relevanten Daten.
Antworte NUR mit einem validen JSON-Objekt, ohne Markdown-Code-Blöcke oder sonstige Erläuterungen.

Felder (null wenn nicht vorhanden oder nicht lesbar):
{
  "creditor_name": "Firmenname oder vollständiger Name des Rechnungsstellers",
  "creditor_street": "Straße und Hausnummer",
  "creditor_zip": "Postleitzahl",
  "creditor_city": "Stadt",
  "creditor_country": "Länderkürzel z.B. DE",
  "creditor_vat_id": "USt-IdNr. z.B. DE123456789",
  "creditor_tax_number": "Steuernummer falls vorhanden",
  "creditor_iban": "IBAN ohne Leerzeichen",
  "creditor_bic": "BIC/SWIFT-Code",
  "external_invoice_number": "Rechnungsnummer des Ausstellers",
  "invoice_date": "Rechnungsdatum als YYYY-MM-DD",
  "due_date": "Fälligkeitsdatum als YYYY-MM-DD oder null",
  "total_net": "Nettobetrag als Dezimalzahl z.B. 100.00",
  "total_vat": "MwSt-Betrag als Dezimalzahl",
  "total_gross": "Bruttobetrag als Dezimalzahl",
  "vat_rate": "MwSt-Satz in Prozent als Zahl z.B. 19.0",
  "currency": "Währungskürzel z.B. EUR",
  "description": "Kurze Beschreibung der Leistung oder Ware (max 200 Zeichen)",
  "is_direct_debit": true wenn die Rechnung auf SEPA-Lastschrift/Bankeinzug hinweist (Begriffe: Lastschrift, wird abgebucht, Bankeinzug, SEPA-Mandat, Einzugsermächtigung), sonst false
}"""


RECEIPT_EXTRACTION_PROMPT = """Analysiere diesen Beleg (Kassenbon, Quittung, Rechnung) und extrahiere alle relevanten Daten.
Antworte NUR mit einem validen JSON-Objekt, ohne Markdown-Code-Blöcke oder sonstige Erläuterungen.

Felder (null wenn nicht vorhanden oder nicht lesbar):
{
  "merchant": "Name des Händlers oder Lieferanten",
  "receipt_date": "Belegdatum als YYYY-MM-DD",
  "amount_gross": "Bruttobetrag als Dezimalzahl z.B. 42.50",
  "vat_amount": "MwSt-Betrag als Dezimalzahl oder 0",
  "amount_net": "Nettobetrag als Dezimalzahl oder 0",
  "vat_rate": "MwSt-Satz in Prozent als Zahl z.B. 19.0",
  "currency": "Währungskürzel z.B. EUR",
  "category": "Eine der folgenden Kategorien je nach Beleginhalt: Büromaterial, Reisekosten, Bewirtung, Porto, Telefon, Software, Sonstiges",
  "description": "Kurze Beschreibung des Kaufs (max 150 Zeichen)",
  "payment_method": "Zahlungsart wenn erkennbar: Bar, EC-Karte, Kreditkarte, Überweisung — sonst null"
}"""


async def _extract_with_prompt(filepath: str, prompt: str) -> dict:
    """
    Gemeinsame Hilfsfunktion: Sendet eine Datei + Prompt an Claude Vision und gibt das geparste JSON zurück.
    Bei Fehler: dict mit 'extraction_error'-Schlüssel.
    """
    from app.config import settings

    if not settings.anthropic_api_key:
        return {"extraction_error": "Kein ANTHROPIC_API_KEY konfiguriert"}

    ext = os.path.splitext(filepath)[1].lower()

    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

        with open(filepath, "rb") as f:
            file_bytes = f.read()
        encoded = base64.standard_b64encode(file_bytes).decode("utf-8")

        if ext == ".pdf":
            content_block = {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": encoded,
                },
            }
        elif ext in SUPPORTED_IMAGE_TYPES:
            content_block = {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": SUPPORTED_IMAGE_TYPES[ext],
                    "data": encoded,
                },
            }
        else:
            return {"extraction_error": f"Dateityp {ext} wird für Extraktion nicht unterstützt"}

        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        content_block,
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        return json.loads(raw)

    except json.JSONDecodeError as e:
        logger.error("extractor.json_error", filepath=filepath, error=str(e))
        return {"extraction_error": f"Ungültiges JSON vom Modell: {e}"}
    except Exception as e:
        logger.error("extractor.error", filepath=filepath, error=str(e))
        return {"extraction_error": str(e)}


async def extract_invoice_data(filepath: str) -> dict:
    """
    Extrahiert Rechnungsdaten aus einer Eingangsrechnung mit Claude Vision.
    Gibt ein dict mit den extrahierten Feldern zurück (inkl. is_direct_debit).
    Bei Fehler: dict mit 'extraction_error'-Schlüssel.
    """
    data = await _extract_with_prompt(filepath, EXTRACTION_PROMPT)
    if "extraction_error" not in data:
        logger.info("invoice_extractor.success", filepath=filepath, creditor=data.get("creditor_name"))
    return data


async def extract_receipt_data(filepath: str) -> dict:
    """
    Extrahiert Belegdaten (Kassenbon/Quittung) aus einer Datei mit Claude Vision.
    Gibt ein dict mit merchant, receipt_date, amount_gross etc. zurück.
    Bei Fehler: dict mit 'extraction_error'-Schlüssel.
    """
    data = await _extract_with_prompt(filepath, RECEIPT_EXTRACTION_PROMPT)
    if "extraction_error" not in data:
        logger.info("receipt_extractor.success", filepath=filepath, merchant=data.get("merchant"))
    return data


async def find_matching_creditor(extracted_name: Optional[str], db) -> Optional[dict]:
    """
    Sucht in der Datenbank nach einem Kreditor, dessen Name zum extrahierten Namen passt.
    Gibt ein dict mit id, creditor_number und company_name zurück oder None.
    """
    if not extracted_name:
        return None

    from sqlalchemy import text

    name_lower = extracted_name.lower().strip()
    result = await db.execute(
        text("""
            SELECT id::text, creditor_number,
                   COALESCE(company_name, first_name || ' ' || last_name) AS display_name
            FROM creditors
            WHERE is_active = true
              AND (
                  LOWER(company_name) LIKE :pattern
                  OR LOWER(last_name) LIKE :pattern
              )
            ORDER BY
                CASE WHEN LOWER(COALESCE(company_name, '')) = :exact THEN 0 ELSE 1 END,
                company_name
            LIMIT 1
        """),
        {"pattern": f"%{name_lower}%", "exact": name_lower},
    )
    row = result.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "creditor_number": row[1],
        "company_name": row[2],
    }
