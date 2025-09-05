from fastapi import APIRouter, Form, HTTPException, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..dependencies import require_manager_or_admin
from ..models import ParUnitName

router = APIRouter(prefix="/par_unit_names", tags=["par_unit_names"])

@router.post("/new")
async def create_par_unit_name(
    name: str = Form(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    par_unit_name = ParUnitName(name=name)
    db.add(par_unit_name)
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=302)