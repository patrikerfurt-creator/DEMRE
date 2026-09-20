from typing import Optional
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class AppSetting(Base, TimestampMixin):
    """Ueber die Oberflaeche aenderbare Einstellungen (Firmendaten).

    Liegt bewusst in der Datenbank und nicht in einer .env-Datei: Der
    Backend-Container hat kein Volume auf /app, jede dort geschriebene Datei
    ist nach dem naechsten `docker compose up -d --build` verloren.
    Die Datenbank liegt dagegen im Volume `pgdata` und uebersteht Updates.
    """

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(Text)
