"""
DATEV Buchungsstapel EXTF CSV generator (format version 700, Stapelversion 13).
"""
from datetime import date
from decimal import Decimal
from typing import List, Optional
import io
import csv

from app.config import settings


# DATEV Gegenkonto mapping by VAT rate
GEGENKONTO_MAP = {
    Decimal("19.00"): "8400",
    Decimal("7.00"): "8300",
    Decimal("0.00"): "8200",
}


def get_gegenkonto(vat_rate: Decimal) -> str:
    # Normalize the rate
    rate = vat_rate.quantize(Decimal("0.01"))
    return GEGENKONTO_MAP.get(rate, "8400")


class DatevService:

    def generate_datev_export(
        self,
        invoices: list,
        period_from: date,
        period_to: date,
    ) -> bytes:
        """
        Generate DATEV Buchungsstapel CSV (EXTF format version 700, Stapelversion 13).
        Returns bytes (UTF-8 with BOM for Excel compatibility).
        """
        output = io.StringIO()

        # ── Row 1: DATEV format header ──
        # EXTF;\Version;Datenkategorie;Formatname;Formatversion;Erzeugt am;...
        created_at = date.today().strftime("%Y%m%d%H%M%S") + "000"
        header1_fields = [
            "EXTF",
            "700",      # format version
            "21",       # data category: 21 = Buchungsstapel
            "Buchungsstapel",
            "13",       # Formatversion Buchungsstapel
            created_at,
            "",         # Importiert
            "",         # Herkunft
            "",         # Exportiert von
            "",         # Importiert von
            settings.datev_berater_number or "",  # Berater
            settings.datev_mandant_number or "",  # Mandant
            period_from.strftime("%Y%m%d"),  # WJ-Beginn
            "4",        # Sachkontenlänge
            period_from.strftime("%Y%m%d"),  # Datum von
            period_to.strftime("%Y%m%d"),    # Datum bis
            f"RE {period_from.strftime('%m/%Y')}",  # Bezeichnung
            "",         # Diktatzeichen
            "1",        # Buchungstyp: 1 = Finanzbuchführung
            "0",        # Rechnungslegungszweck
            "0",        # Festschreibung
            "EUR",      # WKZ
            "",         # reserved
            "",         # Derivatskennzeichen
            "",         # reserved
            "",         # reserved
            "",         # SKR
            "",         # Branchenlösungs-ID
            "",         # reserved
            "",         # reserved
            "",         # Anwendungsinformation
        ]
        output.write(";".join(header1_fields) + "\r\n")

        # ── Row 2: Column headers ──
        header2_fields = [
            "Umsatz (ohne Soll/Haben-Kz)",
            "Soll/Haben-Kennzeichen",
            "WKZ Umsatz",
            "Kurs",
            "Basis-Umsatz",
            "WKZ Basis-Umsatz",
            "Konto",
            "Gegenkonto (ohne BU-Schlüssel)",
            "BU-Schlüssel",
            "Belegdatum",
            "Belegfeld 1",
            "Belegfeld 2",
            "Skonto",
            "Buchungstext",
            "Postensperre",
            "Diverse Adressnummer",
            "Geschäftspartnerbank",
            "Sachverhalt",
            "Zinssperre",
            "Beleglink",
            "Beleginfo-Art 1",
            "Beleginfo-Inhalt 1",
            "Beleginfo-Art 2",
            "Beleginfo-Inhalt 2",
            "Beleginfo-Art 3",
            "Beleginfo-Inhalt 3",
            "Beleginfo-Art 4",
            "Beleginfo-Inhalt 4",
            "Beleginfo-Art 5",
            "Beleginfo-Inhalt 5",
            "Beleginfo-Art 6",
            "Beleginfo-Inhalt 6",
            "Beleginfo-Art 7",
            "Beleginfo-Inhalt 7",
            "Beleginfo-Art 8",
            "Beleginfo-Inhalt 8",
            "KOST1 - Kostenstelle",
            "KOST2 - Kostenstelle",
            "KOST-Menge",
            "EU-Land u. UStID",
            "EU-Steuersatz",
            "Abw. Versteuerungsart",
            "Sachverhalt L+L",
            "Funktionsergänzung L+L",
            "BU 49 Hauptfunktionstyp",
            "BU 49 Hauptfunktionsnummer",
            "BU 49 Funktionsergänzung",
            "Zusatzinformation-Art 1",
            "Zusatzinformation-Inhalt 1",
            "Zusatzinformation-Art 2",
            "Zusatzinformation-Inhalt 2",
            "Stück",
            "Gewicht",
            "Zahlweise",
            "Forderungsart",
            "Veranlagungsjahr",
            "Zugeordnete Fälligkeit",
            "Skontotyp",
            "Auftragsnummer",
            "Land",
            "Abrechnungsreferenz",
            "BVV-Position (Betriebsvermögensvergleich)",
            "EU-Mitgliedstaat u. UStID Ursprungsland",
            "EU-Steuersatz Ursprungsland",
        ]
        output.write(";".join(header2_fields) + "\r\n")

        # ── Data rows ──
        for invoice in invoices:
            customer = invoice.customer

            # Per-VAT-rate booking
            vat_groups: dict = {}
            for item in invoice.items:
                rate_key = str(item.vat_rate)
                if rate_key not in vat_groups:
                    vat_groups[rate_key] = {
                        "rate": item.vat_rate,
                        "gross": Decimal("0.00"),
                    }
                vat_groups[rate_key]["gross"] += item.total_gross

            belegdatum = invoice.invoice_date.strftime("%d%m")  # DDMM
            konto = (customer.datev_account_number if customer else None) or "10000"
            buchungstext = f"Re. {invoice.invoice_number}"[:60]
            belegfeld1 = invoice.invoice_number[:36]

            for group in vat_groups.values():
                gegenkonto = get_gegenkonto(group["rate"])
                umsatz = str(group["gross"]).replace(".", ",")

                row = [
                    umsatz,        # Umsatz
                    "S",           # Soll/Haben
                    "EUR",         # WKZ
                    "",            # Kurs
                    "",            # Basis-Umsatz
                    "",            # WKZ Basis-Umsatz
                    konto,         # Konto (Debitor)
                    gegenkonto,    # Gegenkonto (Erlöskonto)
                    "",            # BU-Schlüssel
                    belegdatum,    # Belegdatum
                    belegfeld1,    # Belegfeld 1
                    "",            # Belegfeld 2
                    "",            # Skonto
                    buchungstext,  # Buchungstext
                ]
                # Pad to 64 fields (Stapelversion 13)
                while len(row) < 64:
                    row.append("")

                output.write(";".join(row) + "\r\n")

        content = output.getvalue()
        # DATEV expects Windows-1252 encoding
        try:
            return content.encode("cp1252")
        except UnicodeEncodeError:
            return content.encode("utf-8-sig")
