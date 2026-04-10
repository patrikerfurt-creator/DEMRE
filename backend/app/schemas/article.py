from pydantic import BaseModel, field_validator
from typing import Optional, List
from uuid import UUID
from decimal import Decimal
from datetime import datetime


class ArticleBase(BaseModel):
    article_number: str
    name: str
    description: Optional[str] = None
    unit: Optional[str] = None
    unit_price: Decimal
    vat_rate: Decimal = Decimal("19.00")
    category: Optional[str] = None
    is_active: bool = True


class ArticleCreate(ArticleBase):
    pass


class ArticleUpdate(BaseModel):
    article_number: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    unit_price: Optional[Decimal] = None
    vat_rate: Optional[Decimal] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None


class ArticleResponse(ArticleBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ArticleImportRow(BaseModel):
    row_number: int
    article_number: str
    name: str
    description: Optional[str] = None
    unit: Optional[str] = None
    unit_price: Optional[Decimal] = None
    vat_rate: Optional[Decimal] = None
    category: Optional[str] = None
    errors: List[str] = []
    is_valid: bool = True
