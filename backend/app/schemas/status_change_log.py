from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class ChangedByShort(BaseModel):
    id: UUID
    full_name: str
    email: str
    model_config = {"from_attributes": True}


class StatusChangeLogResponse(BaseModel):
    id: UUID
    entity_type: str
    entity_id: UUID
    from_status: str
    to_status: str
    changed_by_id: UUID
    changed_by: Optional[ChangedByShort] = None
    changed_at: datetime
    note: Optional[str] = None
    model_config = {"from_attributes": True}
