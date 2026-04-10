from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from app.api.deps import get_db, get_current_user, require_not_readonly
from app.models.user import User
from app.models.creditor import Creditor
from app.models.incoming_invoice import IncomingInvoice
from app.schemas.creditor import CreditorCreate, CreditorUpdate, CreditorResponse, CreditorListResponse
from app.core.number_generator import generate_creditor_number

router = APIRouter(prefix="/creditors", tags=["creditors"])


@router.get("", response_model=CreditorListResponse)
async def list_creditors(
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = select(Creditor)
    if search:
        like = f"%{search}%"
        query = query.where(
            or_(
                Creditor.creditor_number.ilike(like),
                Creditor.company_name.ilike(like),
                Creditor.first_name.ilike(like),
                Creditor.last_name.ilike(like),
                Creditor.email.ilike(like),
                Creditor.city.ilike(like),
            )
        )
    if is_active is not None:
        query = query.where(Creditor.is_active == is_active)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()

    query = query.order_by(Creditor.creditor_number).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = [CreditorResponse.model_validate(c) for c in result.scalars().all()]
    return CreditorListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=CreditorResponse, status_code=status.HTTP_201_CREATED)
async def create_creditor(
    data: CreditorCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_not_readonly),
):
    creditor_number = await generate_creditor_number(db)
    creditor = Creditor(creditor_number=creditor_number, **data.model_dump())
    db.add(creditor)
    await db.flush()
    await db.refresh(creditor)
    return CreditorResponse.model_validate(creditor)


@router.get("/{creditor_id}", response_model=CreditorResponse)
async def get_creditor(
    creditor_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Creditor).where(Creditor.id == creditor_id))
    creditor = result.scalar_one_or_none()
    if not creditor:
        raise HTTPException(status_code=404, detail="Kreditor nicht gefunden")
    return CreditorResponse.model_validate(creditor)


@router.put("/{creditor_id}", response_model=CreditorResponse)
async def update_creditor(
    creditor_id: str,
    data: CreditorUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_not_readonly),
):
    result = await db.execute(select(Creditor).where(Creditor.id == creditor_id))
    creditor = result.scalar_one_or_none()
    if not creditor:
        raise HTTPException(status_code=404, detail="Kreditor nicht gefunden")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(creditor, field, value)
    await db.flush()
    await db.refresh(creditor)
    return CreditorResponse.model_validate(creditor)


@router.delete("/{creditor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_creditor(
    creditor_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_not_readonly),
):
    result = await db.execute(select(Creditor).where(Creditor.id == creditor_id))
    creditor = result.scalar_one_or_none()
    if not creditor:
        raise HTTPException(status_code=404, detail="Kreditor nicht gefunden")

    # Block deletion if open invoices exist
    inv_result = await db.execute(
        select(func.count()).where(IncomingInvoice.creditor_id == creditor.id)
    )
    if inv_result.scalar() > 0:
        raise HTTPException(
            status_code=409,
            detail="Kreditor hat Eingangsrechnungen und kann nicht gelöscht werden"
        )
    await db.delete(creditor)
