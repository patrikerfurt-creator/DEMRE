from typing import List, Optional
from uuid import UUID
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, extract
from sqlalchemy.orm import selectinload

from app.models.contract import Contract, ContractItem, ContractStatus, BillingPeriod
from app.models.invoice import Invoice, InvoiceItem, InvoiceStatus
from app.models.article import Article
from app.core.number_generator import generate_invoice_number


class InvoiceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_invoices_for_period(
        self,
        period_from: date,
        period_to: date,
        contract_ids: Optional[List[UUID]] = None,
        auto_issue: bool = False,
        generated_by: Optional[UUID] = None,
        generation_run_id: Optional[UUID] = None,
    ) -> List[UUID]:
        """
        Generate one invoice per contract item for all active contracts in the given period.
        Returns list of created invoice IDs.
        """
        query = (
            select(Contract)
            .options(
                selectinload(Contract.items).selectinload(ContractItem.article)
            )
            .where(Contract.status == ContractStatus.active)
        )

        if contract_ids:
            query = query.where(Contract.id.in_(contract_ids))

        query = query.where(
            (Contract.start_date == None) | (Contract.start_date <= period_to)
        ).where(
            (Contract.end_date == None) | (Contract.end_date >= period_from)
        )

        result = await self.db.execute(query)
        contracts = result.scalars().all()

        invoice_ids = []
        for contract in contracts:
            ids = await self._generate_invoices_for_contract(
                contract=contract,
                period_from=period_from,
                period_to=period_to,
                auto_issue=auto_issue,
                generated_by=generated_by,
                generation_run_id=generation_run_id,
            )
            invoice_ids.extend(ids)

        return invoice_ids

    async def _generate_invoices_for_contract(
        self,
        contract: Contract,
        period_from: date,
        period_to: date,
        auto_issue: bool = False,
        generated_by: Optional[UUID] = None,
        generation_run_id: Optional[UUID] = None,
    ) -> List[UUID]:
        """Creates one invoice per active contract item."""

        # Filter active items by validity dates
        candidate_items = [
            item for item in contract.items
            if item.is_active
            and (item.valid_from is None or item.valid_from <= period_to)
            and (item.valid_until is None or item.valid_until >= period_from)
        ]

        if not candidate_items:
            return []

        current_year = period_to.year

        # For annual items: find which article_ids were already billed this year
        annual_billed_article_ids: set = set()
        if any(item.billing_period == BillingPeriod.annual for item in candidate_items):
            billed_result = await self.db.execute(
                select(InvoiceItem.article_id)
                .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
                .where(Invoice.contract_id == contract.id)
                .where(extract("year", Invoice.invoice_date) == current_year)
                .where(Invoice.status != InvoiceStatus.cancelled)
                .where(InvoiceItem.article_id.isnot(None))
            )
            annual_billed_article_ids = {row[0] for row in billed_result.all()}

        # For non-annual items: find which article_ids were already billed for this exact period
        period_billed_article_ids: set = set()
        if any(item.billing_period != BillingPeriod.annual for item in candidate_items):
            period_result = await self.db.execute(
                select(InvoiceItem.article_id)
                .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
                .where(Invoice.contract_id == contract.id)
                .where(Invoice.billing_period_from == period_from)
                .where(Invoice.billing_period_to == period_to)
                .where(Invoice.status != InvoiceStatus.cancelled)
                .where(InvoiceItem.article_id.isnot(None))
            )
            period_billed_article_ids = {row[0] for row in period_result.all()}

        invoice_date = date(period_to.year, period_to.month, 1)
        due_date = invoice_date + timedelta(days=contract.payment_terms_days)

        invoice_ids = []
        for contract_item in sorted(candidate_items, key=lambda x: x.sort_order):
            # Skip annual items already billed this year
            if contract_item.billing_period == BillingPeriod.annual:
                if contract_item.article_id in annual_billed_article_ids:
                    continue
            # Skip non-annual items already billed for this exact period
            elif contract_item.article_id and contract_item.article_id in period_billed_article_ids:
                continue

            invoice_id = await self._create_single_item_invoice(
                contract=contract,
                contract_item=contract_item,
                invoice_date=invoice_date,
                due_date=due_date,
                period_from=period_from,
                period_to=period_to,
                current_year=current_year,
                auto_issue=auto_issue,
                generated_by=generated_by,
                generation_run_id=generation_run_id,
            )
            invoice_ids.append(invoice_id)

            # Track newly billed annual items to avoid duplicates within the same run
            if contract_item.billing_period == BillingPeriod.annual and contract_item.article_id:
                annual_billed_article_ids.add(contract_item.article_id)

        return invoice_ids

    async def _create_single_item_invoice(
        self,
        contract: Contract,
        contract_item: ContractItem,
        invoice_date: date,
        due_date: date,
        period_from: date,
        period_to: date,
        current_year: int,
        auto_issue: bool = False,
        generated_by: Optional[UUID] = None,
        generation_run_id: Optional[UUID] = None,
    ) -> UUID:
        price, vat_rate, description, unit = self.get_effective_price(contract_item)
        quantity = contract_item.quantity

        # Annual items: use 01.01.–31.12. as service period and append to description
        if contract_item.billing_period == BillingPeriod.annual:
            item_period_from = date(current_year, 1, 1)
            item_period_to = date(current_year, 12, 31)
            description = (
                f"{description} "
                f"({item_period_from.strftime('%d.%m.%Y')} – {item_period_to.strftime('%d.%m.%Y')})"
            )
        else:
            item_period_from = period_from
            item_period_to = period_to

        line_net = (price * quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        line_vat = (line_net * vat_rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        line_gross = line_net + line_vat

        invoice_number = await generate_invoice_number(self.db)
        invoice = Invoice(
            invoice_number=invoice_number,
            contract_id=contract.id,
            customer_id=contract.customer_id,
            invoice_date=invoice_date,
            due_date=due_date,
            billing_period_from=item_period_from,
            billing_period_to=item_period_to,
            status=InvoiceStatus.issued if auto_issue else InvoiceStatus.draft,
            currency="EUR",
            subtotal_net=line_net,
            total_vat=line_vat,
            total_gross=line_gross,
            generated_by=generated_by,
            generation_run_id=generation_run_id,
        )
        self.db.add(invoice)
        await self.db.flush()

        inv_item = InvoiceItem(
            invoice_id=invoice.id,
            article_id=contract_item.article_id,
            position=1,
            description=description,
            quantity=quantity,
            unit=unit,
            unit_price_net=price,
            vat_rate=vat_rate,
            total_net=line_net,
            total_vat=line_vat,
            total_gross=line_gross,
        )
        self.db.add(inv_item)
        await self.db.flush()

        return invoice.id

    def get_effective_price(
        self, contract_item: ContractItem
    ) -> tuple[Decimal, Decimal, str, Optional[str]]:
        article = contract_item.article

        if contract_item.override_price is not None:
            price = contract_item.override_price
        elif article:
            price = article.unit_price
        else:
            price = Decimal("0.00")

        if contract_item.override_vat_rate is not None:
            vat_rate = contract_item.override_vat_rate
        elif article:
            vat_rate = article.vat_rate
        else:
            vat_rate = Decimal("19.00")

        if contract_item.description_override:
            description = contract_item.description_override
        elif article:
            description = article.name
        else:
            description = "Leistung"

        unit = article.unit if article else None

        return price, vat_rate, description, unit
