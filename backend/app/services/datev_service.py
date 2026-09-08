"""
DATEV Buchungsstapel EXTF CSV generator (format version 700, Stapelversion 13).
"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
import io
import csv

from app.config import settings
from app.models.invoice import DocumentType


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
        created_at = datetime.now().strftime("%Y%m%d%H%M%S") + "000"
        header1_fields = [
            "EXTF",
            "700",      # format version
            "21",       # data category: 21 = Buchungsstapel
            "Buchungsstapel",
            "13",       # Formatversion Buchungsstapel
            created_at,
            "",         # Importiert      (Index 6)
            "DV",       # Herkunft        (Index 7)
            "",         # Exportiert von  (Index 8)
            "",         # Importiert von  (Index 9)
            settings.datev_berater_number or "",  # Berater   (Index 10)
            settings.datev_mandant_number or "",  # Mandant   (Index 11)
            period_from.strftime("%Y") + "0101",  # WJ-Beginn (Index 12)
            "4",        # Sachkontenlänge (Index 13)
            period_from.strftime("%Y%m%d"),  # Datum von (Index 14)
            period_to.strftime("%Y%m%d"),    # Datum bis (Index 15)
            f"RE/GS {period_from.strftime('%m/%Y')}",  # Bezeichnung (Index 16)
            "",         # Diktatzeichen   (Index 17)
            "1",        # Buchungstyp     (Index 18)
            "0",        # Rechnungslegungszweck (Index 19)
            "0",        # Festschreibung  (Index 20)
            "",         # WKZ             (Index 21)
            "",         # reserved        (Index 22)
            "",         # Derivatskennzeichen (Index 23)
            "",         # reserved        (Index 24)
            "",         # reserved        (Index 25)
            "",         # SKR             (Index 26)
            "",         # Branchenlösungs-ID (Index 27)
            "",         # reserved        (Index 28)
            "",         # reserved        (Index 29)
            "",         # Anwendungsinformation (Index 30)
        ]
        while len(header1_fields) < 126:
            header1_fields.append("")
        output.write(";".join(header1_fields) + "\r\n")

        # ── Row 2: Column headers ──
        header2_fields = [
            "Umsatz (ohne Soll/Haben-Kz)", "Soll/Haben-Kennzeichen", "WKZ Umsatz",
            "Kurs", "Basis-Umsatz", "WKZ Basis-Umsatz", "Konto",
            "Gegenkonto (ohne BU-Schlüssel)", "BU-Schlüssel", "Belegdatum",
            "Belegfeld 1", "Belegfeld 2", "Skonto", "Buchungstext", "Postensperre",
            "Diverse Adressnummer", "Geschäftspartnerbank", "Sachverhalt",
            "Zinssperre", "Beleglink",
            "Beleginfo - Art 1", "Beleginfo - Inhalt 1",
            "Beleginfo - Art 2", "Beleginfo - Inhalt 2",
            "Beleginfo - Art 3", "Beleginfo - Inhalt 3",
            "Beleginfo - Art 4", "Beleginfo - Inhalt 4",
            "Beleginfo - Art 5", "Beleginfo - Inhalt 5",
            "Beleginfo - Art 6", "Beleginfo - Inhalt 6",
            "Beleginfo - Art 7", "Beleginfo - Inhalt 7",
            "Beleginfo - Art 8", "Beleginfo - Inhalt 8",
            "KOST1 - Kostenstelle", "KOST2 - Kostenstelle", "Kost-Menge",
            "EU-Land u. UStID (Bestimmung)", "EU-Steuersatz (Bestimmung)",
            "Abw. Versteuerungsart", "Sachverhalt L+L", "Funktionsergänzung L+L",
            "BU 49 Hauptfunktionstyp", "BU 49 Hauptfunktionsnummer",
            "BU 49 Funktionsergänzung",
            "Zusatzinformation - Art 1",  "Zusatzinformation- Inhalt 1",
            "Zusatzinformation - Art 2",  "Zusatzinformation- Inhalt 2",
            "Zusatzinformation - Art 3",  "Zusatzinformation- Inhalt 3",
            "Zusatzinformation - Art 4",  "Zusatzinformation- Inhalt 4",
            "Zusatzinformation - Art 5",  "Zusatzinformation- Inhalt 5",
            "Zusatzinformation - Art 6",  "Zusatzinformation- Inhalt 6",
            "Zusatzinformation - Art 7",  "Zusatzinformation- Inhalt 7",
            "Zusatzinformation - Art 8",  "Zusatzinformation- Inhalt 8",
            "Zusatzinformation - Art 9",  "Zusatzinformation- Inhalt 9",
            "Zusatzinformation - Art 10", "Zusatzinformation- Inhalt 10",
            "Zusatzinformation - Art 11", "Zusatzinformation- Inhalt 11",
            "Zusatzinformation - Art 12", "Zusatzinformation- Inhalt 12",
            "Zusatzinformation - Art 13", "Zusatzinformation- Inhalt 13",
            "Zusatzinformation - Art 14", "Zusatzinformation- Inhalt 14",
            "Zusatzinformation - Art 15", "Zusatzinformation- Inhalt 15",
            "Zusatzinformation - Art 16", "Zusatzinformation- Inhalt 16",
            "Zusatzinformation - Art 17", "Zusatzinformation- Inhalt 17",
            "Zusatzinformation - Art 18", "Zusatzinformation- Inhalt 18",
            "Zusatzinformation - Art 19", "Zusatzinformation- Inhalt 19",
            "Zusatzinformation - Art 20", "Zusatzinformation- Inhalt 20",
            "Stück", "Gewicht", "Zahlweise", "Forderungsart", "Veranlagungsjahr",
            "Zugeordnete Fälligkeit", "Skontotyp", "Auftragsnummer",
            "Buchungstyp (Anzahlungen)", "USt-Schlüssel (Anzahlungen)",
            "EU-Land (Anzahlungen)", "Sachverhalt L+L (Anzahlungen)",
            "EU-Steuersatz (Anzahlungen)", "Erlöskonto (Anzahlungen)",
            "Herkunft-Kz", "Buchungs GUID", "KOST-Datum", "SEPA-Mandatsreferenz",
            "Skontosperre", "Gesellschaftername", "Beteiligtennummer",
            "Identifikationsnummer", "Zeichnernummer", "Postensperre bis",
            "Bezeichnung SoBil-Sachverhalt", "Kennzeichen SoBil-Buchung",
            "Festschreibung", "Leistungsdatum", "Datum Zuord. Steuerperiode",
            "Fälligkeit", "Generalumkehr (GU)", "Steuersatz", "Land",
            "Abrechnungsreferenz", "BVV-Position",
            "EU-Land u. UStID (Ursprung)", "EU-Steuersatz (Ursprung)",
            "Abw. Skontokonto", "Besteuerungsart Leistender",
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
            konto = (
                (customer.datev_account_number if customer and customer.datev_account_number else None)
                or (customer.customer_number if customer else None)
                or "10000"
            )
            is_credit_note = getattr(invoice, "document_type", None) == DocumentType.credit_note
            # Die GS-Nummer traegt die Belegart schon im Praefix
            buchungstext = (
                invoice.invoice_number if is_credit_note
                else f"Re. {invoice.invoice_number}"
            )[:60]
            belegfeld1 = invoice.invoice_number[:36]

            for group in vat_groups.values():
                gegenkonto = get_gegenkonto(group["rate"])
                # DATEV akzeptiert kein Minus im Umsatzfeld - die Richtung
                # steckt allein im Soll/Haben-Kennzeichen.
                umsatz = str(
                    abs(group["gross"]).quantize(Decimal("0.01"))
                ).replace(".", ",")

                row = [
                    umsatz,        # Umsatz
                    # Gutschrift = Erloesminderung: Haben statt Soll,
                    # Konto (Debitor) und Gegenkonto (Erloeskonto) bleiben gleich
                    "H" if is_credit_note else "S",  # Soll/Haben
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
                while len(row) < 126:
                    row.append("")

                output.write(";".join(row) + "\r\n")

        content = output.getvalue()
        # DATEV expects Windows-1252 encoding
        try:
            return content.encode("cp1252")
        except UnicodeEncodeError:
            return content.encode("utf-8-sig")
