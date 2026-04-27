"""
ZUGFeRD EN16931 (Factur-X Comfort) service.
Generates ZUGFeRD XML and embeds it into PDF using reportlab + pikepdf.
"""
from decimal import Decimal
from datetime import date
from typing import Optional
import io
import os

from app.config import settings


class ZugferdService:

    def build_xml(self, invoice) -> bytes:
        """Build ZUGFeRD EN16931 XML using drafthorse."""
        try:
            return self._build_xml_drafthorse(invoice)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return self._build_xml_manual(invoice)

    def _build_xml_drafthorse(self, invoice) -> bytes:
        """Build using drafthorse library."""
        from drafthorse.models.document import Document
        from drafthorse.models.accounting import ApplicableTradeTax
        from drafthorse.models.party import TradeParty
        from drafthorse.models.payment import PaymentTerms

        doc = Document()
        doc.context.guideline_id.id = (
            "urn:cen.eu:en16931:2017#compliant#urn:factur-x.eu:1p0:en16931"
        )
        doc.header.id.id = invoice.invoice_number
        doc.header.type_code.value = "380"
        doc.header.name.value = "RECHNUNG"
        doc.header.issue_date_time.date = invoice.invoice_date

        # Seller
        seller = doc.trade.agreement.seller
        seller.name.value = settings.company_name
        seller.address.line_one.value = settings.company_street
        seller.address.postcode.value = settings.company_zip
        seller.address.city_name.value = settings.company_city
        seller.address.country_id.value = settings.company_country

        if settings.company_vat_id:
            from drafthorse.models.party import TaxRegistration
            reg = seller.tax_registrations.add()
            reg.id.value = settings.company_vat_id
            reg.id.scheme_id = "VA"

        # Buyer
        customer = invoice.customer
        buyer = doc.trade.agreement.buyer
        if customer:
            buyer_name = (
                customer.company_name
                or f"{customer.first_name or ''} {customer.last_name or ''}".strip()
                or "Unbekannt"
            )
            buyer.name.value = buyer_name
            buyer.address.line_one.value = customer.address_line1 or ""
            buyer.address.postcode.value = customer.postal_code or ""
            buyer.address.city_name.value = customer.city or ""
            buyer.address.country_id.value = customer.country_code or "DE"

        doc.trade.settlement.currency_code.value = invoice.currency or "EUR"

        # Payment terms
        if invoice.due_date:
            terms = doc.trade.settlement.payment_terms.add()
            terms.due.date = invoice.due_date

        # Line items + VAT accumulation
        vat_groups: dict = {}
        for item in invoice.items:
            line = doc.trade.items.add()
            line.document.line_id.value = str(item.position)
            line.product.name.value = item.description
            if item.additional_text:
                line.product.description.value = item.additional_text
            line.delivery.billed_quantity.amount = item.quantity
            line.delivery.billed_quantity.unit_code = item.unit or "C62"
            line.settlement.trade_tax.type_code.value = "VAT"
            line.settlement.trade_tax.category_code.value = (
                "S" if Decimal(str(item.vat_rate)) > 0 else "Z"
            )
            line.settlement.trade_tax.rate_applicable_percent.value = Decimal(str(item.vat_rate))
            line.settlement.monetary_summation.total_amount.amount = Decimal(str(item.total_net))
            line.settlement.monetary_summation.total_amount.currency = invoice.currency or "EUR"

            rate_key = str(item.vat_rate)
            if rate_key not in vat_groups:
                vat_groups[rate_key] = {
                    "rate": Decimal(str(item.vat_rate)),
                    "net": Decimal("0.00"),
                    "vat": Decimal("0.00"),
                }
            vat_groups[rate_key]["net"] += Decimal(str(item.total_net))
            vat_groups[rate_key]["vat"] += Decimal(str(item.total_vat))

        # Tax breakdown
        for group in vat_groups.values():
            tax = doc.trade.settlement.trade_tax.add()
            tax.type_code.value = "VAT"
            tax.category_code.value = "S" if group["rate"] > 0 else "Z"
            tax.rate_applicable_percent.value = group["rate"]
            tax.basis_amount.amount = group["net"]
            tax.basis_amount.currency = invoice.currency or "EUR"
            tax.calculated_amount.amount = group["vat"]
            tax.calculated_amount.currency = invoice.currency or "EUR"

        # Monetary summation
        s = doc.trade.settlement.monetary_summation
        s.line_total.amount = Decimal(str(invoice.subtotal_net))
        s.line_total.currency = invoice.currency or "EUR"
        s.charge_total.amount = Decimal("0.00")
        s.charge_total.currency = invoice.currency or "EUR"
        s.allowance_total.amount = Decimal("0.00")
        s.allowance_total.currency = invoice.currency or "EUR"
        s.tax_basis_total.amount = Decimal(str(invoice.subtotal_net))
        s.tax_basis_total.currency = invoice.currency or "EUR"
        s.tax_total.amount = Decimal(str(invoice.total_vat))
        s.tax_total.currency = invoice.currency or "EUR"
        s.grand_total.amount = Decimal(str(invoice.total_gross))
        s.grand_total.currency = invoice.currency or "EUR"
        s.due_amount.amount = Decimal(str(invoice.total_gross))
        s.due_amount.currency = invoice.currency or "EUR"

        return doc.serialize(schema_validation=False)

    def _build_xml_manual(self, invoice) -> bytes:
        """Fallback: build a minimal Factur-X XML manually."""
        customer = invoice.customer
        buyer_name = ""
        if customer:
            buyer_name = (
                customer.company_name
                or f"{customer.first_name or ''} {customer.last_name or ''}".strip()
                or "Unbekannt"
            )

        inv_date = invoice.invoice_date.strftime("%Y%m%d") if invoice.invoice_date else ""
        due_date = invoice.due_date.strftime("%Y%m%d") if invoice.due_date else ""

        # VAT groups
        vat_groups: dict = {}
        for item in invoice.items:
            rate = str(item.vat_rate)
            if rate not in vat_groups:
                vat_groups[rate] = {"net": Decimal("0"), "vat": Decimal("0"), "rate": item.vat_rate}
            vat_groups[rate]["net"] += Decimal(str(item.total_net))
            vat_groups[rate]["vat"] += Decimal(str(item.total_vat))

        vat_lines = ""
        for g in vat_groups.values():
            cat = "S" if Decimal(str(g["rate"])) > 0 else "Z"
            vat_lines += f"""
    <ram:ApplicableTradeTax>
      <ram:CalculatedAmount currencyID="{invoice.currency}">{g['vat']:.2f}</ram:CalculatedAmount>
      <ram:TypeCode>VAT</ram:TypeCode>
      <ram:BasisAmount currencyID="{invoice.currency}">{g['net']:.2f}</ram:BasisAmount>
      <ram:CategoryCode>{cat}</ram:CategoryCode>
      <ram:RateApplicablePercent>{g['rate']}</ram:RateApplicablePercent>
    </ram:ApplicableTradeTax>"""

        # Line items (required for EN16931 profile)
        line_items = ""
        for item in sorted(invoice.items, key=lambda x: x.position):
            cat = "S" if Decimal(str(item.vat_rate)) > 0 else "Z"
            line_items += f"""
  <ram:IncludedSupplyChainTradeLineItem>
    <ram:AssociatedDocumentLineDocument>
      <ram:LineID>{item.position}</ram:LineID>
    </ram:AssociatedDocumentLineDocument>
    <ram:SpecifiedTradeProduct>
      <ram:Name>{item.description}</ram:Name>
{f"      <ram:Description>{item.additional_text}</ram:Description>" if item.additional_text else ""}    </ram:SpecifiedTradeProduct>
    <ram:SpecifiedLineTradeAgreement>
      <ram:NetPriceProductTradePrice>
        <ram:ChargeAmount currencyID="{invoice.currency}">{Decimal(str(item.unit_price_net)):.2f}</ram:ChargeAmount>
      </ram:NetPriceProductTradePrice>
    </ram:SpecifiedLineTradeAgreement>
    <ram:SpecifiedLineTradeDelivery>
      <ram:BilledQuantity unitCode="{item.unit or 'C62'}">{Decimal(str(item.quantity)):.4f}</ram:BilledQuantity>
    </ram:SpecifiedLineTradeDelivery>
    <ram:SpecifiedLineTradeSettlement>
      <ram:ApplicableTradeTax>
        <ram:TypeCode>VAT</ram:TypeCode>
        <ram:CategoryCode>{cat}</ram:CategoryCode>
        <ram:RateApplicablePercent>{Decimal(str(item.vat_rate)):.2f}</ram:RateApplicablePercent>
      </ram:ApplicableTradeTax>
      <ram:SpecifiedTradeSettlementLineMonetarySummation>
        <ram:LineTotalAmount currencyID="{invoice.currency}">{Decimal(str(item.total_net)):.2f}</ram:LineTotalAmount>
      </ram:SpecifiedTradeSettlementLineMonetarySummation>
    </ram:SpecifiedLineTradeSettlement>
  </ram:IncludedSupplyChainTradeLineItem>"""

        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice
  xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
  xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
  xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">
  <rsm:ExchangedDocumentContext>
    <ram:GuidelineSpecifiedDocumentContextParameter>
      <ram:ID>urn:cen.eu:en16931:2017#compliant#urn:factur-x.eu:1p0:en16931</ram:ID>
    </ram:GuidelineSpecifiedDocumentContextParameter>
  </rsm:ExchangedDocumentContext>
  <rsm:ExchangedDocument>
    <ram:ID>{invoice.invoice_number}</ram:ID>
    <ram:TypeCode>380</ram:TypeCode>
    <ram:IssueDateTime>
      <udt:DateTimeString format="102">{inv_date}</udt:DateTimeString>
    </ram:IssueDateTime>
  </rsm:ExchangedDocument>
  <rsm:SupplyChainTradeTransaction>
    {line_items}
    <ram:ApplicableHeaderTradeAgreement>
      <ram:SellerTradeParty>
        <ram:Name>{settings.company_name}</ram:Name>
        <ram:PostalTradeAddress>
          <ram:LineOne>{settings.company_street}</ram:LineOne>
          <ram:PostcodeCode>{settings.company_zip}</ram:PostcodeCode>
          <ram:CityName>{settings.company_city}</ram:CityName>
          <ram:CountryID>{settings.company_country}</ram:CountryID>
        </ram:PostalTradeAddress>
      </ram:SellerTradeParty>
      <ram:BuyerTradeParty>
        <ram:Name>{buyer_name}</ram:Name>
      </ram:BuyerTradeParty>
    </ram:ApplicableHeaderTradeAgreement>
    <ram:ApplicableHeaderTradeDelivery/>
    <ram:ApplicableHeaderTradeSettlement>
      <ram:InvoiceCurrencyCode>{invoice.currency}</ram:InvoiceCurrencyCode>
      {vat_lines}
      <ram:SpecifiedTradePaymentTerms>
        <ram:DueDateDateTime>
          <udt:DateTimeString format="102">{due_date}</udt:DateTimeString>
        </ram:DueDateDateTime>
      </ram:SpecifiedTradePaymentTerms>
      <ram:SpecifiedTradeSettlementHeaderMonetarySummation>
        <ram:LineTotalAmount currencyID="{invoice.currency}">{invoice.subtotal_net:.2f}</ram:LineTotalAmount>
        <ram:TaxBasisTotalAmount currencyID="{invoice.currency}">{invoice.subtotal_net:.2f}</ram:TaxBasisTotalAmount>
        <ram:TaxTotalAmount currencyID="{invoice.currency}">{invoice.total_vat:.2f}</ram:TaxTotalAmount>
        <ram:GrandTotalAmount currencyID="{invoice.currency}">{invoice.total_gross:.2f}</ram:GrandTotalAmount>
        <ram:DuePayableAmount currencyID="{invoice.currency}">{invoice.total_gross:.2f}</ram:DuePayableAmount>
      </ram:SpecifiedTradeSettlementHeaderMonetarySummation>
    </ram:ApplicableHeaderTradeSettlement>
  </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>"""
        return xml.encode("utf-8")

    def generate_pdf(self, invoice) -> bytes:
        """Generate a DIN-5008-compliant PDF invoice with embedded ZUGFeRD XML."""
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm, mm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

        PAGE_W, PAGE_H = A4
        LEFT_MARGIN  = 2.5 * cm
        RIGHT_MARGIN = 2.0 * cm
        # DIN 5008 Form B: Rücksendezeile bei 40 mm, Anschrift ab 45 mm
        TOP_MARGIN   = 4.0 * cm   # story beginnt bei 40 mm
        BOT_MARGIN   = 2.5 * cm

        logo_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'logo.jpg')

        # ── Canvas-Callback: Header (Seite 1) + Footer (alle Seiten) ──
        def draw_header_footer(canvas, doc):
            canvas.saveState()

            # --- Header (nur Seite 1) ---
            if doc.page == 1:
                logo_w = 5.0 * cm
                logo_h = logo_w * (2 / 3)
                logo_x = PAGE_W - RIGHT_MARGIN - logo_w   # rechte Logo-Kante = 2 cm vom Rand
                logo_y = PAGE_H - logo_h - 0.5 * cm        # obere Logo-Kante = 0.5 cm vom Rand

                if os.path.exists(logo_path):
                    canvas.drawImage(logo_path, logo_x, logo_y,
                                     width=logo_w, height=logo_h,
                                     preserveAspectRatio=True, mask='auto')

                # Firmeninfo linksbündig mit Logo-Linker-Kante unter Logo
                info_x = logo_x + 0.5 * cm   # linker Anker = 0.5 cm rechts der Logo-Kante
                info_y = logo_y - 3 * mm
                info_lines = [
                    (f"{settings.company_name}", "Helvetica-Bold"),
                    (settings.company_street, "Helvetica"),
                    (f"{settings.company_zip} {settings.company_city}", "Helvetica"),
                ]
                if settings.company_phone:
                    info_lines.append((f"Tel.: {settings.company_phone}", "Helvetica"))
                if settings.company_email:
                    info_lines.append((settings.company_email, "Helvetica"))
                canvas.setFillColor(colors.HexColor("#444444"))
                for text, font in info_lines:
                    canvas.setFont(font, 8)
                    canvas.drawString(info_x, info_y, text)
                    info_y -= 10   # ~3.5 mm Zeilenabstand

                # "RECHNUNG" links oben
                canvas.setFont("Helvetica-Bold", 20)
                canvas.setFillColor(colors.HexColor("#1a365d"))
                canvas.drawString(LEFT_MARGIN, PAGE_H - 2.0 * cm - 16, "RECHNUNG")

            # --- Footer (alle Seiten) ---
            footer_y  = 1.5 * cm
            line_y    = footer_y + 0.5 * cm
            canvas.setStrokeColor(colors.HexColor("#cbd5e0"))
            canvas.setLineWidth(0.5)
            canvas.line(LEFT_MARGIN, line_y, PAGE_W - RIGHT_MARGIN, line_y)
            canvas.setFont("Helvetica", 7.5)
            canvas.setFillColor(colors.HexColor("#718096"))
            footer_parts = [
                settings.company_name,
                settings.company_street,
                f"{settings.company_zip} {settings.company_city}",
            ]
            if settings.company_phone:
                footer_parts.append(f"Tel.: {settings.company_phone}")
            if settings.company_email:
                footer_parts.append(settings.company_email)
            canvas.drawCentredString(PAGE_W / 2, footer_y, "  ·  ".join(footer_parts))

            canvas.restoreState()

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=LEFT_MARGIN,
            rightMargin=RIGHT_MARGIN,
            topMargin=TOP_MARGIN,
            bottomMargin=BOT_MARGIN,
        )

        styles = getSampleStyleSheet()
        story  = []

        normal_style = ParagraphStyle("normal_custom", fontSize=9, fontName="Helvetica", leading=14)
        tiny_style   = ParagraphStyle("tiny", fontSize=6.5, fontName="Helvetica",
                                      textColor=colors.HexColor("#999999"))

        # ── DIN 5008: Rücksendezeile (Story beginnt bei 40 mm = Rücksendezeile) ──
        sender_parts = [settings.company_name, settings.company_street,
                        f"{settings.company_zip} {settings.company_city}"]
        story.append(Paragraph("  ·  ".join(sender_parts), tiny_style))
        # 5 mm Spacer → Anschrift beginnt bei 45 mm (DIN 5008 Form B)
        story.append(Spacer(1, 5 * mm))

        # ── Customer address ──
        customer = invoice.customer
        if customer:
            addr_lines = []
            if customer.company_name:
                addr_lines.append(f"<b>{customer.company_name}</b>")
            if customer.salutation or customer.first_name or customer.last_name:
                name_parts = [p for p in [customer.salutation, customer.first_name, customer.last_name] if p]
                addr_lines.append(" ".join(name_parts))
            if customer.address_line1:
                addr_lines.append(customer.address_line1)
            if customer.address_line2:
                addr_lines.append(customer.address_line2)
            if customer.postal_code or customer.city:
                addr_lines.append(f"{customer.postal_code or ''} {customer.city or ''}".strip())
            if customer.country_code and customer.country_code != "DE":
                addr_lines.append(customer.country_code)
            if addr_lines:
                story.append(Paragraph("<br/>".join(addr_lines), normal_style))
        story.append(Spacer(1, 0.8 * cm))

        # ── Invoice metadata ──
        def fmt_date(d):
            if d:
                return d.strftime("%d.%m.%Y") if hasattr(d, 'strftime') else str(d)
            return ""

        meta_data = [
            ["Rechnungsnummer:", invoice.invoice_number],
            ["Rechnungsdatum:", fmt_date(invoice.invoice_date)],
            ["Fälligkeitsdatum:", fmt_date(invoice.due_date)],
        ]
        if invoice.billing_period_from and invoice.billing_period_to:
            meta_data.append([
                "Leistungszeitraum:",
                f"{fmt_date(invoice.billing_period_from)} – {fmt_date(invoice.billing_period_to)}"
            ])

        meta_table = Table(meta_data, colWidths=[4.5 * cm, 6 * cm])
        meta_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 0.6 * cm))

        story.append(Paragraph("Sehr geehrte Damen und Herren,", normal_style))
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(
            "wir erlauben uns, folgende Leistungen in Rechnung zu stellen:",
            normal_style
        ))
        story.append(Spacer(1, 4 * mm))

        # ── Items table ──
        item_headers = ["Pos.", "Beschreibung", "Menge", "Einheit", "EP netto", "MwSt.", "Gesamt netto"]
        item_data = [item_headers]

        for item in sorted(invoice.items, key=lambda x: x.position):
            try:
                from babel.numbers import format_currency as babel_fmt_currency
                price_fmt = babel_fmt_currency(item.unit_price_net, "EUR", locale="de_DE")
                total_fmt = babel_fmt_currency(item.total_net, "EUR", locale="de_DE")
            except Exception:
                price_fmt = f"{float(item.unit_price_net):.2f} €"
                total_fmt = f"{float(item.total_net):.2f} €"

            if item.additional_text:
                desc_cell = Paragraph(
                    f"{item.description}<br/><i><font size='7' color='#666666'>{item.additional_text}</font></i>",
                    ParagraphStyle("desc", fontSize=8, fontName="Helvetica", leading=11),
                )
            else:
                desc_cell = item.description
            item_data.append([
                str(item.position),
                desc_cell,
                format(Decimal(str(item.quantity)).normalize(), "f"),
                item.unit or "",
                price_fmt,
                f"{Decimal(str(item.vat_rate)):.0f}%",
                total_fmt,
            ])

        items_table = Table(
            item_data,
            colWidths=[1 * cm, 5.3 * cm, 1.2 * cm, 2.5 * cm, 2.5 * cm, 1.2 * cm, 2.5 * cm],
        )
        items_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a365d")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7fafc")]),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(items_table)
        story.append(Spacer(1, 4 * mm))

        # ── Totals ──
        try:
            from babel.numbers import format_currency as babel_fmt_currency
            def fmt_cur(v):
                return babel_fmt_currency(v, "EUR", locale="de_DE")
        except Exception:
            def fmt_cur(v):
                return f"{float(v):.2f} €"

        vat_groups: dict = {}
        for item in invoice.items:
            rate_key = str(item.vat_rate)
            if rate_key not in vat_groups:
                vat_groups[rate_key] = {
                    "rate": Decimal(str(item.vat_rate)),
                    "net": Decimal("0"),
                    "vat": Decimal("0"),
                }
            vat_groups[rate_key]["net"] += Decimal(str(item.total_net))
            vat_groups[rate_key]["vat"] += Decimal(str(item.total_vat))

        summary_data = [
            ["Zwischensumme netto:", fmt_cur(invoice.subtotal_net)],
        ]
        for group in sorted(vat_groups.values(), key=lambda x: x["rate"]):
            summary_data.append([
                f"MwSt. {group['rate']:.0f}% auf {fmt_cur(group['net'])}:",
                fmt_cur(group["vat"]),
            ])
        summary_data.append(["", ""])
        summary_data.append(["Rechnungsbetrag brutto:", fmt_cur(invoice.total_gross)])

        summary_table = Table(summary_data, colWidths=[10.5 * cm, 3 * cm], hAlign="RIGHT")
        summary_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, -1), (-1, -1), 10),
            ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#1a365d")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 5 * mm))

        # ── Payment info ──
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e0")))
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(
            f"Bitte überweisen Sie den Betrag von <b>{fmt_cur(invoice.total_gross)}</b> "
            f"bis zum <b>{fmt_date(invoice.due_date)}</b> auf folgendes Konto:",
            normal_style
        ))
        story.append(Spacer(1, 3 * mm))

        bank_info = [["Empfänger:", settings.company_name]]
        if settings.company_iban:
            bank_info.append(["IBAN:", settings.company_iban])
        if settings.company_bic:
            bank_info.append(["BIC:", settings.company_bic])
        if settings.company_bank_name:
            bank_info.append(["Bank:", settings.company_bank_name])
        bank_info.append(["Verwendungszweck:", invoice.invoice_number])

        if len(bank_info) > 1:
            bank_table = Table(bank_info, colWidths=[3.5 * cm, 10 * cm])
            bank_table.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]))
            story.append(bank_table)

        if invoice.notes:
            story.append(Spacer(1, 4 * mm))
            story.append(Paragraph(f"Hinweis: {invoice.notes}", normal_style))

        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph("Mit freundlichen Grüßen", normal_style))
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(f"<b>{settings.company_name}</b>", normal_style))

        doc.build(story, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)
        pdf_bytes = buf.getvalue()

        # Embed ZUGFeRD XML
        try:
            xml_bytes = self.build_xml(invoice)
            pdf_bytes = self._embed_zugferd_xml(pdf_bytes, xml_bytes)
        except Exception:
            import traceback
            traceback.print_exc()

        return pdf_bytes

    def _embed_zugferd_xml(self, pdf_bytes: bytes, xml_bytes: bytes) -> bytes:
        """Embed ZUGFeRD XML as attachment in PDF using pikepdf."""
        import pikepdf
        from pikepdf import Pdf, Dictionary, Array, Name, String

        in_buf = io.BytesIO(pdf_bytes)
        out_buf = io.BytesIO()

        with Pdf.open(in_buf) as pdf:
            xml_stream = pdf.make_stream(xml_bytes)
            xml_stream["/Type"] = Name("/EmbeddedFile")
            xml_stream["/Subtype"] = Name("/text#2Fxml")
            xml_stream["/Params"] = Dictionary(Size=len(xml_bytes))

            file_spec = Dictionary(
                Type=Name("/Filespec"),
                F=String("factur-x.xml"),
                UF=String("factur-x.xml"),
                AFRelationship=Name("/Data"),
                Desc=String("ZUGFeRD/Factur-X Invoice"),
                EF=Dictionary(F=xml_stream, UF=xml_stream),
            )

            if "/Names" not in pdf.Root:
                pdf.Root["/Names"] = Dictionary()
            if "/EmbeddedFiles" not in pdf.Root["/Names"]:
                pdf.Root["/Names"]["/EmbeddedFiles"] = Dictionary(
                    Names=Array()
                )

            names_array = pdf.Root["/Names"]["/EmbeddedFiles"]["/Names"]
            names_array.append(String("factur-x.xml"))
            names_array.append(file_spec)

            pdf.Root["/AF"] = Array([file_spec])

            pdf.save(out_buf)

        return out_buf.getvalue()
