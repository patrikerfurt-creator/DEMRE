from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from decimal import Decimal
from datetime import date, datetime
from app.models.payment_run import RunType, RunStatus


class PaymentRunResponse(BaseModel):
    id: UUID
    run_type: RunType
    status: RunStatus
    triggered_by: Optional[UUID] = None
    period_from: Optional[date] = None
    period_to: Optional[date] = None
    invoice_count: Optional[int] = None
    total_amount: Optional[Decimal] = None
    file_path: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SepaExportRequest(BaseModel):
    invoice_ids: List[UUID]
    execution_date: Optional[date] = None


class DatevExportRequest(BaseModel):
    period_from: date
    period_to: date
    invoice_ids: Optional[List[UUID]] = None
