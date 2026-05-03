from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.deps import get_db, require_admin, get_current_user
from app.models.user import User, UserRole
from app.core.security import get_password_hash
from app.schemas.user import UserCreate, UserUpdate, UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=List[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.admin:
        result = await db.execute(select(User).order_by(User.full_name))
        return [UserResponse.model_validate(u) for u in result.scalars().all()]
    return [UserResponse.model_validate(current_user)]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="E-Mail-Adresse bereits vergeben",
        )

    user = User(
        email=data.email,
        full_name=data.full_name,
        role=data.role,
        is_active=data.is_active,
        hashed_password=get_password_hash(data.password),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    return UserResponse.model_validate(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    is_admin = current_user.role == UserRole.admin
    is_self = str(current_user.id) == user_id

    if not is_admin and not is_self:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Keine Berechtigung")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")

    update_data = data.model_dump(exclude_unset=True)
    if not is_admin:
        update_data.pop("role", None)
        update_data.pop("is_active", None)
    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

    for field, value in update_data.items():
        setattr(user, field, value)

    await db.flush()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if str(current_user.id) == user_id:
        raise HTTPException(status_code=400, detail="Eigenes Konto kann nicht gelöscht werden")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")

    await db.delete(user)
