from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from datetime import date
from app.api.deps import get_db, get_current_user, require_not_readonly
from app.models.user import User
from app.models.contract import Contract, ContractItem, ContractStatus
from app.core.number_generator import generate_contract_number
from app.schemas.contract import (
    ContractCreate, ContractUpdate, ContractResponse,
    ContractItemCreate, ContractItemUpdate, ContractItemResponse
)

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.get("", response_model=List[ContractResponse])
async def list_contracts(
    customer_id: Optional[str] = Query(None),
    status: Optional[ContractStatus] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = select(Contract).options(selectinload(Contract.items))

    if customer_id:
        query = query.where(Contract.customer_id == customer_id)
    if status:
        query = query.where(Contract.status == status)

    query = query.order_by(Contract.contract_number).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return [ContractResponse.model_validate(c) for c in result.scalars().all()]


@router.post("", response_model=ContractResponse, status_code=201)
async def create_contract(
    data: ContractCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_not_readonly),
):
    if not data.contract_number:
        data.contract_number = await generate_contract_number(db)
    else:
        existing = await db.execute(
            select(Contract).where(Contract.contract_number == data.contract_number)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Abo-Nr. bereits vergeben")

    contract_data = data.model_dump(exclude={"items"})
    contract_data["created_by"] = current_user.id
    contract = Contract(**contract_data)
    db.add(contract)
    await db.flush()

    for item_data in data.items:
        item = ContractItem(contract_id=contract.id, **item_data.model_dump())
        db.add(item)

    await db.flush()
    result = await db.execute(
        select(Contract).options(selectinload(Contract.items)).where(Contract.id == contract.id)
    )
    contract = result.scalar_one()
    return ContractResponse.model_validate(contract)


@router.get("/{contract_id}", response_model=ContractResponse)
async def get_contract(
    contract_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Contract).options(selectinload(Contract.items)).where(Contract.id == contract_id)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Vertrag nicht gefunden")
    return ContractResponse.model_validate(contract)


@router.put("/{contract_id}", response_model=ContractResponse)
async def update_contract(
    contract_id: str,
    data: ContractUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_not_readonly),
):
    result = await db.execute(
        select(Contract).options(selectinload(Contract.items)).where(Contract.id == contract_id)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Vertrag nicht gefunden")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(contract, field, value)

    await db.flush()
    await db.refresh(contract)
    return ContractResponse.model_validate(contract)


@router.delete("/{contract_id}", status_code=204)
async def delete_contract(
    contract_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_not_readonly),
):
    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Vertrag nicht gefunden")
    await db.delete(contract)


@router.post("/{contract_id}/terminate", response_model=ContractResponse)
async def terminate_contract(
    contract_id: str,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_not_readonly),
):
    result = await db.execute(
        select(Contract).options(selectinload(Contract.items)).where(Contract.id == contract_id)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Vertrag nicht gefunden")

    contract.status = ContractStatus.terminated
    if end_date:
        contract.end_date = end_date
    elif not contract.end_date:
        contract.end_date = date.today()

    await db.flush()
    await db.refresh(contract)
    return ContractResponse.model_validate(contract)


# Contract items endpoints
@router.post("/{contract_id}/items", response_model=ContractItemResponse, status_code=201)
async def add_contract_item(
    contract_id: str,
    data: ContractItemCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_not_readonly),
):
    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Vertrag nicht gefunden")

    item = ContractItem(contract_id=contract_id, **data.model_dump())
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return ContractItemResponse.model_validate(item)


@router.put("/{contract_id}/items/{item_id}", response_model=ContractItemResponse)
async def update_contract_item(
    contract_id: str,
    item_id: str,
    data: ContractItemUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_not_readonly),
):
    result = await db.execute(
        select(ContractItem).where(
            ContractItem.id == item_id,
            ContractItem.contract_id == contract_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Position nicht gefunden")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)

    await db.flush()
    await db.refresh(item)
    return ContractItemResponse.model_validate(item)


@router.delete("/{contract_id}/items/{item_id}", status_code=204)
async def delete_contract_item(
    contract_id: str,
    item_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_not_readonly),
):
    result = await db.execute(
        select(ContractItem).where(
            ContractItem.id == item_id,
            ContractItem.contract_id == contract_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Position nicht gefunden")
    await db.delete(item)
