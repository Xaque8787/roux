from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import markdown
from ..dependencies import get_current_user
from ..utils.template_helpers import setup_template_filters

router = APIRouter(prefix="/guides", tags=["guides"])
templates = setup_template_filters(Jinja2Templates(directory="templates"))

DOCS_DIR = Path(__file__).parent.parent.parent / "docs"

DOC_FILES = {
    "ingredients": {
        "title": "Managing Ingredients",
        "file": "ingredients.md",
        "description": "Complete guide to setting up and managing ingredients"
    },
    "recipes": {
        "title": "Creating Recipes",
        "file": "recipes.md",
        "description": "Detailed instructions for building recipes"
    },
    "batches": {
        "title": "Production Batches",
        "file": "batches.md",
        "description": "Comprehensive guide to production batches"
    },
    "dishes": {
        "title": "Menu Items (Dishes)",
        "file": "dishes.md",
        "description": "Everything about creating and costing dishes"
    },
    "inventory": {
        "title": "Daily Inventory",
        "file": "inventory.md",
        "description": "Complete inventory management system"
    }
}

@router.get("", response_class=HTMLResponse)
async def docs_index(request: Request, current_user: dict = Depends(get_current_user)):
    """Documentation index page listing all available guides"""
    return templates.TemplateResponse(
        "docs_index.html",
        {
            "request": request,
            "current_user": current_user,
            "doc_files": DOC_FILES
        }
    )

@router.get("/{doc_name}", response_class=HTMLResponse)
async def view_doc(
    doc_name: str,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """View a specific documentation page"""
    if doc_name not in DOC_FILES:
        raise HTTPException(status_code=404, detail="Documentation not found")

    doc_info = DOC_FILES[doc_name]
    doc_path = DOCS_DIR / doc_info["file"]

    if not doc_path.exists():
        raise HTTPException(status_code=404, detail="Documentation file not found")

    with open(doc_path, 'r', encoding='utf-8') as f:
        markdown_content = f.read()

    html_content = markdown.markdown(
        markdown_content,
        extensions=['tables', 'fenced_code', 'codehilite', 'toc']
    )

    return templates.TemplateResponse(
        "docs_view.html",
        {
            "request": request,
            "current_user": current_user,
            "title": doc_info["title"],
            "content": html_content,
            "doc_name": doc_name,
            "doc_files": DOC_FILES
        }
    )
