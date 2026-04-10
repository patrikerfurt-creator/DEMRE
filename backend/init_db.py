"""
Initialize database: create default admin if not exists.
Called from start.sh after alembic migrations.
"""
import asyncio
import sys
from app.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.core.security import get_password_hash
from sqlalchemy import select


async def create_default_admin():
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(User).where(User.email == "admin@demre.de"))
        if existing.scalar_one_or_none():
            print("Default admin already exists.")
            return

        user = User(
            email="admin@demre.de",
            hashed_password=get_password_hash("admin123"),
            full_name="Administrator",
            role=UserRole.admin,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        print("Default admin created:")
        print("  Email:    admin@demre.de")
        print("  Password: admin123")
        print("  IMPORTANT: Change the password immediately after first login!")


if __name__ == "__main__":
    asyncio.run(create_default_admin())
