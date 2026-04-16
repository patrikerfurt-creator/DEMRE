"""
SEPA pain.001.003.03 credit transfer generator.
Covers both outgoing customer debits and creditor/expense credit transfers.
"""
import re
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
import uuid as uuidlib

from app.config import settings

# Valides BIC-Muster (ISO 9362)
_BIC_RE = re.compile(r'^[A-Z]{6}[A-Z2-9][A-NP-Z0-9]([A-Z0-9]{3})?$')


class SepaService:

    def generate_pain001(
        self,
        invoices: list,
        execution_date: Optional[date] = None,
    ) -> bytes:
        """
        Generate a SEPA pain.001.003.03 credit transfer XML.
        Falls back to a manual XML construction if sepaxml fails.
        """
        exec_date = execution_date or date.today()

        try:
            from sepaxml import SepaTransfer
            return self._generate_with_sepaxml(invoices, exec_date)
        except Exception:
            return self._generate_manual_xml(invoices, exec_date)

    def _generate_with_sepaxml(self, invoices: list, exec_date: date) -> bytes:
        from sepaxml import SepaTransfer

        debtor_iban = settings.company_iban or "DE00000000000000000000"
        debtor_bic = settings.company_bic or "NOTPROVIDED"

        sepa = SepaTransfer(
            {
                "name": settings.company_name,
                "IBAN": debtor_iban,
                "BIC": debtor_bic,
                "batch": True,
                "currency": "EUR",
            },
            schema="pain.001.003.03",
            clean=True,
        )

        for invoice in invoices:
            customer = invoice.customer
            if not customer or not customer.iban:
                continue

            end_to_end = invoice.invoice_number[:35]
            customer_name = (
                customer.company_name
                or f"{customer.first_name or ''} {customer.last_name or ''}".strip()
                or "Unbekannt"
            )[:70]

            try:
                sepa.add_transaction(
                    {
                        "name": customer_name,
                        "IBAN": customer.iban,
                        "BIC": customer.bic or "NOTPROVIDED",
                        "amount": int(Decimal(str(invoice.total_gross)) * 100),
                        "execution_date": exec_date,
                        "description": f"Rechnung {invoice.invoice_number}"[:140],
                        "endtoend_id": end_to_end,
                    }
                )
            except Exception:
                continue

        return sepa.export(validate=False)

    def _generate_manual_xml(self, invoices: list, exec_date: date) -> bytes:
        """Fallback: manually build pain.001 XML."""
        msg_id = f"DEMRE-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        creation_dt = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        exec_date_str = exec_date.strftime("%Y-%m-%d")

        transactions = []
        total_amount = Decimal("0")
        tx_count = 0

        for invoice in invoices:
            customer = invoice.customer
            if not customer or not customer.iban:
                continue

            amount = Decimal(str(invoice.total_gross))
            total_amount += amount
            tx_count += 1
            end_to_end = invoice.invoice_number[:35]
            customer_name = (
                customer.company_name
                or f"{customer.first_name or ''} {customer.last_name or ''}".strip()
                or "Unbekannt"
            )[:70]

            transactions.append(f"""
      <CdtTrfTxInf>
        <PmtId>
          <EndToEndId>{end_to_end}</EndToEndId>
        </PmtId>
        <Amt>
          <InstdAmt Ccy="EUR">{amount:.2f}</InstdAmt>
        </Amt>
        <CdtrAgt>
          <FinInstnId>
            <BIC>{customer.bic or 'NOTPROVIDED'}</BIC>
          </FinInstnId>
        </CdtrAgt>
        <Cdtr>
          <Nm>{customer_name}</Nm>
        </Cdtr>
        <CdtrAcct>
          <Id>
            <IBAN>{customer.iban}</IBAN>
          </Id>
        </CdtrAcct>
        <RmtInf>
          <Ustrd>Rechnung {invoice.invoice_number}</Ustrd>
        </RmtInf>
      </CdtTrfTxInf>""")

        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.003.03"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <CstmrCdtTrfInitn>
    <GrpHdr>
      <MsgId>{msg_id}</MsgId>
      <CreDtTm>{creation_dt}</CreDtTm>
      <NbOfTxs>{tx_count}</NbOfTxs>
      <CtrlSum>{total_amount:.2f}</CtrlSum>
      <InitgPty>
        <Nm>{settings.company_name}</Nm>
      </InitgPty>
    </GrpHdr>
    <PmtInf>
      <PmtInfId>{msg_id}-1</PmtInfId>
      <PmtMtd>TRF</PmtMtd>
      <NbOfTxs>{tx_count}</NbOfTxs>
      <CtrlSum>{total_amount:.2f}</CtrlSum>
      <PmtTpInf>
        <SvcLvl>
          <Cd>SEPA</Cd>
        </SvcLvl>
      </PmtTpInf>
      <ReqdExctnDt>{exec_date_str}</ReqdExctnDt>
      <Dbtr>
        <Nm>{settings.company_name}</Nm>
      </Dbtr>
      <DbtrAcct>
        <Id>
          <IBAN>{settings.company_iban or 'DE00000000000000000000'}</IBAN>
        </Id>
        <Ccy>EUR</Ccy>
      </DbtrAcct>
      <DbtrAgt>
        <FinInstnId>
          <BIC>{settings.company_bic or 'NOTPROVIDED'}</BIC>
        </FinInstnId>
      </DbtrAgt>
      {''.join(transactions)}
    </PmtInf>
  </CstmrCdtTrfInitn>
</Document>"""
        return xml.encode("utf-8")

    # ── Creditor & expense credit transfers ──────────────────────────────────

    def generate_creditor_pain001(self, invoices: list, execution_date: Optional[date] = None) -> bytes:
        """Generate SEPA credit transfer XML for approved incoming invoices."""
        exec_date = execution_date or date.today()
        items = []
        for inv in invoices:
            creditor = inv.creditor
            if not creditor or not creditor.iban:
                continue
            name = (
                creditor.account_holder
                or creditor.company_name
                or f"{creditor.first_name or ''} {creditor.last_name or ''}".strip()
                or "Unbekannt"
            )
            items.append({
                "name": name,
                "iban": creditor.iban,
                "bic": creditor.bic or "NOTPROVIDED",
                "amount": Decimal(str(inv.total_gross)),
                "reference": inv.document_number,
                "description": f"Eingangsrechnung {inv.document_number}",
            })
        return self._build_credit_transfer_xml(items, exec_date)

    def generate_expense_pain001(self, receipts: list, execution_date: Optional[date] = None) -> bytes:
        """Generate SEPA credit transfer XML for approved expense receipts.
        IBAN and BIC are always read from the submitter's master record (User),
        not from the reimbursement fields stored on the receipt.
        """
        exec_date = execution_date or date.today()
        items = []
        for r in receipts:
            if not r.submitter or not r.submitter.iban:
                continue
            name = r.submitter.full_name or "Unbekannt"
            items.append({
                "name": name,
                "iban": r.submitter.iban,
                "bic": r.submitter.bic or "NOTPROVIDED",
                "amount": Decimal(str(r.amount_gross)),
                "reference": r.receipt_number,
                "description": f"Beleg {r.receipt_number}",
            })
        return self._build_credit_transfer_xml(items, exec_date)

    @staticmethod
    def _x(text: str) -> str:
        """XML-Sonderzeichen escapen."""
        return (str(text)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&apos;"))

    @staticmethod
    def _norm_iban(iban: str) -> str:
        """Leerzeichen entfernen und Großschreibung sicherstellen."""
        return iban.replace(" ", "").replace("\t", "").upper()

    @staticmethod
    def _cdtr_agt(bic: str) -> str:
        """CdtrAgt-Element: gültiges BIC direkt, sonst Othr/NOTPROVIDED."""
        bic_clean = (bic or "").strip().upper()
        if _BIC_RE.match(bic_clean):
            return (
                "        <CdtrAgt>\n"
                "          <FinInstnId>\n"
                f"            <BIC>{bic_clean}</BIC>\n"
                "          </FinInstnId>\n"
                "        </CdtrAgt>"
            )
        return (
            "        <CdtrAgt>\n"
            "          <FinInstnId>\n"
            "            <Othr>\n"
            "              <Id>NOTPROVIDED</Id>\n"
            "            </Othr>\n"
            "          </FinInstnId>\n"
            "        </CdtrAgt>"
        )

    def _build_credit_transfer_xml(self, items: list, exec_date: date) -> bytes:
        """Build a pain.001.003.03 credit transfer XML from a list of payment dicts."""
        msg_id = f"DEMRE-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        creation_dt = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        exec_date_str = exec_date.strftime("%Y-%m-%d")

        transactions = []
        total_amount = Decimal("0")
        tx_count = 0

        for item in items:
            amount = item["amount"]
            total_amount += amount
            tx_count += 1

            iban = self._norm_iban(item["iban"])
            name = self._x(item["name"][:70])
            description = self._x(item["description"][:140])
            reference = self._x(item["reference"][:35])
            cdtr_agt = self._cdtr_agt(item.get("bic", ""))

            transactions.append(f"""
      <CdtTrfTxInf>
        <PmtId>
          <EndToEndId>{reference}</EndToEndId>
        </PmtId>
        <Amt>
          <InstdAmt Ccy="EUR">{amount:.2f}</InstdAmt>
        </Amt>
{cdtr_agt}
        <Cdtr>
          <Nm>{name}</Nm>
        </Cdtr>
        <CdtrAcct>
          <Id>
            <IBAN>{iban}</IBAN>
          </Id>
        </CdtrAcct>
        <RmtInf>
          <Ustrd>{description}</Ustrd>
        </RmtInf>
      </CdtTrfTxInf>""")

        if tx_count == 0:
            raise ValueError("Keine zahlbaren Positionen (fehlende IBAN)")

        # Debtor-BIC
        dbtr_bic = (settings.company_bic or "").strip().upper()
        if _BIC_RE.match(dbtr_bic):
            dbtr_agt_xml = (
                "      <DbtrAgt>\n"
                "        <FinInstnId>\n"
                f"          <BIC>{dbtr_bic}</BIC>\n"
                "        </FinInstnId>\n"
                "      </DbtrAgt>"
            )
        else:
            dbtr_agt_xml = (
                "      <DbtrAgt>\n"
                "        <FinInstnId>\n"
                "          <Othr>\n"
                "            <Id>NOTPROVIDED</Id>\n"
                "          </Othr>\n"
                "        </FinInstnId>\n"
                "      </DbtrAgt>"
            )

        dbtr_iban = self._norm_iban(settings.company_iban or "DE00000000000000000000")
        company = self._x(settings.company_name)

        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.003.03"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xsi:schemaLocation="urn:iso:std:iso:20022:tech:xsd:pain.001.003.03 pain.001.003.03.xsd">
  <CstmrCdtTrfInitn>
    <GrpHdr>
      <MsgId>{msg_id}</MsgId>
      <CreDtTm>{creation_dt}</CreDtTm>
      <NbOfTxs>{tx_count}</NbOfTxs>
      <CtrlSum>{total_amount:.2f}</CtrlSum>
      <InitgPty>
        <Nm>{company}</Nm>
      </InitgPty>
    </GrpHdr>
    <PmtInf>
      <PmtInfId>{msg_id}-1</PmtInfId>
      <PmtMtd>TRF</PmtMtd>
      <BtchBookg>false</BtchBookg>
      <NbOfTxs>{tx_count}</NbOfTxs>
      <CtrlSum>{total_amount:.2f}</CtrlSum>
      <PmtTpInf>
        <SvcLvl>
          <Cd>SEPA</Cd>
        </SvcLvl>
      </PmtTpInf>
      <ReqdExctnDt>{exec_date_str}</ReqdExctnDt>
      <Dbtr>
        <Nm>{company}</Nm>
      </Dbtr>
      <DbtrAcct>
        <Id>
          <IBAN>{dbtr_iban}</IBAN>
        </Id>
        <Ccy>EUR</Ccy>
      </DbtrAcct>
{dbtr_agt_xml}
      {''.join(transactions)}
    </PmtInf>
  </CstmrCdtTrfInitn>
</Document>"""
        return xml.encode("utf-8")
