from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from app.api.deps import get_db, get_current_user, require_not_readonly
from app.models.user import User
from app.models.article import Article
from app.schemas.article import ArticleCreate, ArticleUpdate, ArticleResponse, ArticleImportRow
from app.services.csv_import_service import parse_csv

router = APIRouter(prefix="/articles", tags=["articles"])


@router.get("", response_model=List[ArticleResponse])
async def list_articles(
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = select(Article)

    if search:
        like = f"%{search}%"
        query = query.where(
            or_(
                Article.article_number.ilike(like),
                Article.name.ilike(like),
                Article.category.ilike(like),
            )
        )
    if is_active is not None:
        query = query.where(Article.is_active == is_active)

    query = query.order_by(Article.article_number).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return [ArticleResponse.model_validate(a) for a in result.scalars().all()]


@router.post("", response_model=ArticleResponse, status_code=status.HTTP_201_CREATED)
async def create_article(
    data: ArticleCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_not_readonly),
):
    existing = await db.execute(
        select(Article).where(Article.article_number == data.article_number)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Artikelnummer bereits vergeben")

    article = Article(**data.model_dump())
    db.add(article)
    await db.flush()
    await db.refresh(article)
    return ArticleResponse.model_validate(article)


@router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(
    article_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    return ArticleResponse.model_validate(article)


@router.put("/{article_id}", response_model=ArticleResponse)
async def update_article(
    article_id: str,
    data: ArticleUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_not_readonly),
):
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(article, field, value)

    await db.flush()
    await db.refresh(article)
    return ArticleResponse.model_validate(article)


@router.delete("/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_article(
    article_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_not_readonly),
):
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    await db.delete(article)


@router.post("/import/preview", response_model=List[ArticleImportRow])
async def preview_import(
    file: UploadFile = File(...),
    _: User = Depends(require_not_readonly),
):
    content = await file.read()
    rows = parse_csv(content)
    return rows


@router.post("/import/confirm", response_model=List[ArticleResponse])
async def confirm_import(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_not_readonly),
):
    content = await file.read()
    rows = parse_csv(content)
    valid_rows = [r for r in rows if r.is_valid]

    created = []
    for row in valid_rows:
        existing = await db.execute(
            select(Article).where(Article.article_number == row.article_number)
        )
        art = existing.scalar_one_or_none()
        if art:
            # Update existing
            art.name = row.name
            art.description = row.description
            art.unit = row.unit
            art.unit_price = row.unit_price
            art.vat_rate = row.vat_rate or art.vat_rate
            art.category = row.category
        else:
            art = Article(
                article_number=row.article_number,
                name=row.name,
                description=row.description,
                unit=row.unit,
                unit_price=row.unit_price,
                vat_rate=row.vat_rate or 19,
                category=row.category,
            )
            db.add(art)
        await db.flush()
        await db.refresh(art)
        created.append(ArticleResponse.model_validate(art))

    return created
