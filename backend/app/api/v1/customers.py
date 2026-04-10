from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from app.api.deps import get_db, get_current_user, require_not_readonly
from app.models.user import User
from app.models.customer import Customer
from app.schemas.customer import CustomerCreate, CustomerUpdate, CustomerResponse, CustomerListResponse, CustomerImportRow
from app.services.csv_import_service import parse_customers_csv
from app.core.number_generator import generate_customer_number

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=CustomerListResponse)
async def list_customers(
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = select(Customer)

    if search:
        like = f"%{search}%"
        query = query.where(
            or_(
                Customer.customer_number.ilike(like),
                Customer.company_name.ilike(like),
                Customer.first_name.ilike(like),
                Customer.last_name.ilike(like),
                Customer.email.ilike(like),
                Customer.city.ilike(like),
            )
        )
    if is_active is not None:
        query = query.where(Customer.is_active == is_active)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()

    query = query.order_by(Customer.customer_number).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = [CustomerResponse.model_validate(c) for c in result.scalars().all()]

    return CustomerListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    data: CustomerCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_not_readonly),
):
    if not data.customer_number:
        data.customer_number = await generate_customer_number(db)
    else:
        existing = await db.execute(
            select(Customer).where(Customer.customer_number == data.customer_number)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Kundennummer bereits vergeben")

    customer = Customer(**data.model_dump())
    db.add(customer)
    await db.flush()
    await db.refresh(customer)
    return CustomerResponse.model_validate(customer)


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden")
    return CustomerResponse.model_validate(customer)


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: str,
    data: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_not_readonly),
):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)

    await db.flush()
    await db.refresh(customer)
    return CustomerResponse.model_validate(customer)


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
    customer_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_not_readonly),
):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden")
    await db.delete(customer)


@router.post("/import/preview", response_model=List[CustomerImportRow])
async def preview_customer_import(
    file: UploadFile = File(...),
    _: User = Depends(require_not_readonly),
):
    content = await file.read()
    return parse_customers_csv(content)


@router.post("/import/confirm", response_model=List[CustomerResponse])
async def confirm_customer_import(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_not_readonly),
):
    content = await file.read()
    rows = parse_customers_csv(content)
    valid_rows = [r for r in rows if r.is_valid]

    created = []
    for row in valid_rows:
        if not row.customer_number:
            row.customer_number = await generate_customer_number(db)
        existing = await db.execute(
            select(Customer).where(Customer.customer_number == row.customer_number)
        )
        customer = existing.scalar_one_or_none()
        row_data = row.model_dump(exclude={"row_number", "errors", "is_valid"})
        if customer:
            for field, value in row_data.items():
                if value is not None:
                    setattr(customer, field, value)
        else:
            customer = Customer(**row_data)
            db.add(customer)
        await db.flush()
        await db.refresh(customer)
        created.append(CustomerResponse.model_validate(customer))

    return created
