"""
CSV import service for articles and customers.
Article columns: article_number, name, description, unit, unit_price, vat_rate, category
Customer columns: customer_number, company_name, salutation, first_name, last_name,
                  address_line1, address_line2, postal_code, city, country_code,
                  email, phone, vat_id, tax_number, iban, bic, bank_name,
                  account_holder, sepa_mandate_ref, sepa_mandate_date,
                  datev_account_number, notes
"""
import io
import csv
from decimal import Decimal, InvalidOperation
from typing import List
from app.schemas.article import ArticleImportRow
from app.schemas.customer import CustomerImportRow


REQUIRED_COLUMNS = {"article_number", "name", "unit_price"}
ALL_COLUMNS = {"article_number", "name", "description", "unit", "unit_price", "vat_rate", "category"}


def parse_csv(file_bytes: bytes) -> List[ArticleImportRow]:
    """Parse CSV bytes and return list of ArticleImportRow with validation."""
    # Try to detect encoding
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = file_bytes.decode("cp1252")
        except UnicodeDecodeError:
            text = file_bytes.decode("latin-1")

    # Detect delimiter
    sample = text[:2000]
    delimiter = ";"
    if sample.count(",") > sample.count(";"):
        delimiter = ","

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

    rows = []
    for row_num, row in enumerate(reader, start=2):  # row 1 is header
        # Normalize keys
        normalized = {k.strip().lower(): v.strip() if v else "" for k, v in row.items()}

        errors = []
        is_valid = True

        # Check required fields
        for col in REQUIRED_COLUMNS:
            if col not in normalized or not normalized[col]:
                errors.append(f"Pflichtfeld '{col}' fehlt")
                is_valid = False

        article_number = normalized.get("article_number", "")
        name = normalized.get("name", "")
        description = normalized.get("description") or None
        unit = normalized.get("unit") or None
        category = normalized.get("category") or None

        # Parse unit_price
        unit_price = None
        raw_price = normalized.get("unit_price", "").replace(",", ".")
        if raw_price:
            try:
                unit_price = Decimal(raw_price)
                if unit_price < 0:
                    errors.append("Einzelpreis darf nicht negativ sein")
                    is_valid = False
            except InvalidOperation:
                errors.append(f"Ungültiger Preis: '{normalized.get('unit_price')}'")
                is_valid = False

        # Parse vat_rate
        vat_rate = None
        raw_vat = normalized.get("vat_rate", "").replace(",", ".").replace("%", "").strip()
        if raw_vat:
            try:
                vat_rate = Decimal(raw_vat)
            except InvalidOperation:
                errors.append(f"Ungültiger MwSt-Satz: '{normalized.get('vat_rate')}'")
                is_valid = False
        else:
            vat_rate = Decimal("19.00")

        rows.append(ArticleImportRow(
            row_number=row_num,
            article_number=article_number,
            name=name,
            description=description,
            unit=unit,
            unit_price=unit_price,
            vat_rate=vat_rate,
            category=category,
            errors=errors,
            is_valid=is_valid and len(errors) == 0,
        ))

    return rows


def _decode_csv(file_bytes: bytes) -> tuple[str, str]:
    """Decode bytes and detect delimiter. Returns (text, delimiter)."""
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = file_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    sample = text[:2000]
    delimiter = ";" if sample.count(";") >= sample.count(",") else ","
    return text, delimiter


def parse_customers_csv(file_bytes: bytes) -> List[CustomerImportRow]:
    """Parse CSV bytes and return list of CustomerImportRow with validation."""
    text, delimiter = _decode_csv(file_bytes)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

    rows = []
    for row_num, row in enumerate(reader, start=2):
        normalized = {k.strip().lower(): v.strip() if v else "" for k, v in row.items()}

        errors = []

        customer_number = normalized.get("customer_number") or None

        def opt(key: str) -> str | None:
            return normalized.get(key) or None

        rows.append(CustomerImportRow(
            row_number=row_num,
            customer_number=customer_number,
            company_name=opt("company_name"),
            salutation=opt("salutation"),
            first_name=opt("first_name"),
            last_name=opt("last_name"),
            address_line1=opt("address_line1"),
            address_line2=opt("address_line2"),
            postal_code=opt("postal_code"),
            city=opt("city"),
            country_code=normalized.get("country_code") or "DE",
            email=opt("email"),
            phone=opt("phone"),
            vat_id=opt("vat_id"),
            tax_number=opt("tax_number"),
            iban=opt("iban"),
            bic=opt("bic"),
            bank_name=opt("bank_name"),
            account_holder=opt("account_holder"),
            sepa_mandate_ref=opt("sepa_mandate_ref"),
            sepa_mandate_date=opt("sepa_mandate_date"),
            datev_account_number=opt("datev_account_number"),
            notes=opt("notes"),
            errors=errors,
            is_valid=len(errors) == 0,
        ))

    return rows
