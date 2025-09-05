from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from ..database import get_db
from ..dependencies import require_admin
from ..models import UtilityCost

router = APIRouter(prefix="/utilities", tags=["utilities"])
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def utilities_page(request: Request, db: Session = Depends(get_db), current_user = Depends(require_admin)):
    utilities = db.query(UtilityCost).all()
    
    return templates.TemplateResponse("utilities.html", {
        "request": request,
        "current_user": current_user,
        "utilities": utilities
    })

@router.post("/new")
async def create_or_update_utility(
    request: Request,
    name: str = Form(...),
    monthly_cost: float = Form(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    # Check if utility already exists
    existing_utility = db.query(UtilityCost).filter(UtilityCost.name == name).first()
    
    if existing_utility:
        # Update existing utility
        existing_utility.monthly_cost = monthly_cost
    else:
        # Create new utility
        utility = UtilityCost(name=name, monthly_cost=monthly_cost)
        db.add(utility)
    
    db.commit()
    
    return RedirectResponse(url="/utilities", status_code=302)

@router.get("/{utility_id}/delete")
async def delete_utility(utility_id: int, db: Session = Depends(get_db), current_user = Depends(require_admin)):
    utility = db.query(UtilityCost).filter(UtilityCost.id == utility_id).first()
    if not utility:
        raise HTTPException(status_code=404, detail="Utility not found")
    
    db.delete(utility)
    db.commit()
    
    return RedirectResponse(url="/utilities", status_code=302)