"""
Run once to create initial admin user.
Usage: python create_admin.py
"""
import asyncio
import sys
from app.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.core.security import get_password_hash
from sqlalchemy import select


async def create_admin():
    email = input("Admin E-Mail: ").strip()
    password = input("Admin Passwort: ").strip()
    full_name = input("Vollständiger Name [Admin]: ").strip() or "Admin"

    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            print(f"Benutzer '{email}' existiert bereits.")
            return

        user = User(
            email=email,
            hashed_password=get_password_hash(password),
            full_name=full_name,
            role=UserRole.admin,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        print(f"Admin-Benutzer '{email}' wurde erstellt.")


if __name__ == "__main__":
    asyncio.run(create_admin())
