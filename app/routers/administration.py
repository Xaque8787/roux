from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from ..database import get_db
from ..dependencies import require_admin, get_current_user
from ..schemas import UserOut
from ..utils.backup import create_backup, cleanup_old_backups, list_backups, get_backup_dir
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/administration", response_class=HTMLResponse)
async def administration_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(require_admin)
):
    backups = list_backups()

    return templates.TemplateResponse("administration.html", {
        "request": request,
        "user": current_user,
        "backups": backups
    })

@router.post("/administration/backup")
async def create_database_backup(
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(require_admin)
):
    result = create_backup()

    if result["success"]:
        deleted_count = cleanup_old_backups(keep_count=7)

        return JSONResponse({
            "success": True,
            "message": f"Backup created successfully: {result['filename']}",
            "filename": result["filename"],
            "size_mb": round(result["size"] / (1024 * 1024), 2),
            "deleted_old_backups": deleted_count
        })
    else:
        raise HTTPException(status_code=500, detail=f"Backup failed: {result['error']}")

@router.get("/administration/backups")
async def get_backups_list(
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(require_admin)
):
    backups = list_backups()
    return JSONResponse({"backups": backups})

@router.get("/administration/backup/download/{filename}")
async def download_backup(
    filename: str,
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(require_admin)
):
    if not filename.startswith("backup_") or not filename.endswith(".db"):
        raise HTTPException(status_code=400, detail="Invalid backup filename")

    backup_dir = get_backup_dir()
    backup_path = Path(backup_dir) / filename

    if not backup_path.exists():
        raise HTTPException(status_code=404, detail="Backup file not found")

    return FileResponse(
        path=str(backup_path),
        filename=filename,
        media_type="application/octet-stream"
    )
