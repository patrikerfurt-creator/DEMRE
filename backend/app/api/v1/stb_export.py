import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.deps import require_admin
from app.config import settings
from app.models.user import User

router = APIRouter(prefix="/stb-export", tags=["stb-export"])

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def _export_dir() -> str:
    d = settings.stb_export_dir
    if d:
        os.makedirs(d, exist_ok=True)
    return d


def _list_files() -> list[str]:
    d = _export_dir()
    if not d or not os.path.isdir(d):
        return []
    return sorted(
        f for f in os.listdir(d)
        if os.path.isfile(os.path.join(d, f))
        and os.path.splitext(f)[1].lower() in ALLOWED_EXTENSIONS
    )


@router.get("/count", summary="Anzahl ausstehender STB-Exportdateien")
async def get_stb_export_count(_: User = Depends(require_admin)):
    return {"count": len(_list_files())}


@router.get("/files", summary="Liste der ausstehenden STB-Exportdateien")
async def list_stb_export_files(_: User = Depends(require_admin)):
    return {"files": _list_files()}


@router.get("/files/{filename}", summary="Einzelne STB-Exportdatei herunterladen")
async def download_stb_file(filename: str, _: User = Depends(require_admin)):
    export_dir = _export_dir()
    if not export_dir:
        raise HTTPException(status_code=404, detail="STB_EXPORT_DIR nicht konfiguriert")
    safe_name = os.path.basename(filename)
    filepath = os.path.join(export_dir, safe_name)
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    return FileResponse(filepath, filename=safe_name)


@router.delete("/files/{filename}", status_code=204, summary="STB-Exportdatei nach erfolgreichem Download löschen")
async def delete_stb_file(filename: str, _: User = Depends(require_admin)):
    export_dir = _export_dir()
    if not export_dir:
        raise HTTPException(status_code=404, detail="STB_EXPORT_DIR nicht konfiguriert")
    safe_name = os.path.basename(filename)
    filepath = os.path.join(export_dir, safe_name)
    if os.path.isfile(filepath):
        os.remove(filepath)
