from fastapi import APIRouter, Form, HTTPException, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..dependencies import require_manager_or_admin, get_current_user
from ..models import Category

router = APIRouter(prefix="/categories", tags=["categories"])

@router.post("/new")
async def create_category(
    name: str = Form(...),
    type: str = Form(...),
    icon: str = Form("🔘"),
    color: str = Form("#6c757d"),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    category = Category(name=name, type=type, icon=icon, color=color)
    db.add(category)
    db.commit()
    
    # Redirect back to the appropriate page based on type
    redirect_urls = {
        "ingredient": "/ingredients",
        "recipe": "/recipes",
        "batch": "/batches",
        "dish": "/dishes",
        "inventory": "/inventory"
    }
    
    return RedirectResponse(url=redirect_urls.get(type, "/home"), status_code=302)