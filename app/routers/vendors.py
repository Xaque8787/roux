from fastapi import APIRouter, Form, HTTPException, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..dependencies import require_manager_or_admin
from ..models import Vendor

router = APIRouter(prefix="/vendors", tags=["vendors"])

@router.post("/new")
async def create_vendor(
    name: str = Form(...),
    contact_info: str = Form(""),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    vendor = Vendor(
        name=name,
        contact_info=contact_info if contact_info else None
    )
    db.add(vendor)
    db.commit()
    
    return RedirectResponse(url="/ingredients", status_code=302)