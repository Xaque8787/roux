from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from ..database import get_db
from ..dependencies import get_current_user
from ..models import User
import os
import httpx

from ..utils.template_helpers import setup_template_filters
router = APIRouter(tags=["home"])
templates = setup_template_filters(Jinja2Templates(directory="templates"))

def get_app_version():
    """Read the application version from .dockerversion file"""
    version_paths = [
        "/app/.dockerversion",
        ".dockerversion",
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".dockerversion")
    ]

    for version_file in version_paths:
        try:
            if os.path.exists(version_file):
                with open(version_file, "r") as f:
                    return f.read().strip()
        except Exception:
            continue

    return "unknown"

@router.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/home", status_code=302)

@router.get("/home", response_class=HTMLResponse)
async def home(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("home.html", {
        "request": request,
        "current_user": current_user,
        "app_version": get_app_version()
    })

@router.get("/api/version/check")
async def check_version():
    """Check if a new version is available on GitHub"""
    local_version = get_app_version()

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://raw.githubusercontent.com/Xaque8787/roux/main/.dockerversion"
            )
            if response.status_code == 200:
                github_version = response.text.strip()
                return JSONResponse({
                    "local_version": local_version,
                    "github_version": github_version,
                    "update_available": local_version != github_version
                })
    except Exception as e:
        pass

    return JSONResponse({
        "local_version": local_version,
        "github_version": None,
        "update_available": False,
        "error": "Could not fetch GitHub version"
    })