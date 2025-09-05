from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from ..database import get_db
from ..dependencies import get_current_user
from ..models import User

router = APIRouter(tags=["home"])
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/home", status_code=302)

@router.get("/home", response_class=HTMLResponse)
async def home(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("home.html", {
        "request": request,
        "current_user": current_user
    })