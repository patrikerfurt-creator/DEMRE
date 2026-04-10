from pydantic import BaseModel, field_serializer
from typing import Optional, List
from uuid import UUID
from decimal import Decimal
from datetime import date, datetime
from app.models.contract import ContractStatus, BillingPeriod


class ContractItemBase(BaseModel):
    article_id: Optional[UUID] = None
    quantity: Decimal = Decimal("1.000")
    override_price: Optional[Decimal] = None
    override_vat_rate: Optional[Decimal] = None
    description_override: Optional[str] = None
    billing_period: BillingPeriod = BillingPeriod.monthly
    sort_order: int = 0
    is_active: bool = True
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None


class ContractItemCreate(ContractItemBase):
    pass


class ContractItemUpdate(BaseModel):
    article_id: Optional[UUID] = None
    quantity: Optional[Decimal] = None
    override_price: Optional[Decimal] = None
    override_vat_rate: Optional[Decimal] = None
    description_override: Optional[str] = None
    billing_period: Optional[BillingPeriod] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None


class ContractItemResponse(ContractItemBase):
    id: UUID
    contract_id: UUID
    created_at: datetime
    updated_at: datetime

    @field_serializer("quantity")
    def serialize_quantity(self, value: Decimal) -> str:
        return format(value.normalize(), "f")

    model_config = {"from_attributes": True}


class ContractBase(BaseModel):
    contract_number: Optional[str] = None
    customer_id: UUID
    property_ref: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    billing_day: int = 1
    payment_terms_days: int = 14
    notes: Optional[str] = None
    status: ContractStatus = ContractStatus.active


class ContractCreate(ContractBase):
    items: List[ContractItemCreate] = []


class ContractUpdate(BaseModel):
    contract_number: Optional[str] = None
    customer_id: Optional[UUID] = None
    property_ref: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    billing_day: Optional[int] = None
    payment_terms_days: Optional[int] = None
    notes: Optional[str] = None
    status: Optional[ContractStatus] = None


class ContractResponse(ContractBase):
    id: UUID
    created_by: Optional[UUID] = None
    items: List[ContractItemResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
