from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from ..database import get_db
from ..dependencies import require_manager_or_admin, get_current_user, require_admin
from ..models import Batch, Recipe, RecipeIngredient, Category
from ..utils.template_helpers import setup_template_filters

router = APIRouter(prefix="/batches", tags=["batches"])
templates = setup_template_filters(Jinja2Templates(directory="templates"))

@router.get("/", response_class=HTMLResponse)
async def batches_page(request: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    batches = db.query(Batch).all()
    recipes = db.query(Recipe).all()
    categories = db.query(Category).filter(Category.type == "batch").all()
    
    return templates.TemplateResponse("batches.html", {
        "request": request,
        "current_user": current_user,
        "batches": batches,
        "recipes": recipes,
        "categories": categories
    })

@router.post("/new")
async def create_batch(
    request: Request,
    recipe_id: int = Form(...),
    category_id: int = Form(None),
    variable_yield: bool = Form(False),
    yield_amount: float = Form(None),
    yield_unit: str = Form(None),
    estimated_labor_minutes: int = Form(...),
    hourly_labor_rate: float = Form(...),
    can_be_scaled: bool = Form(False),
    scale_double: bool = Form(False),
    scale_triple: bool = Form(False),
    scale_quadruple: bool = Form(False),
    scale_three_quarters: bool = Form(False),
    scale_two_thirds: bool = Form(False),
    scale_half: bool = Form(False),
    scale_quarter: bool = Form(False),
    scale_eighth: bool = Form(False),
    scale_sixteenth: bool = Form(False),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    batch = Batch(
        recipe_id=recipe_id,
        category_id=category_id if category_id else None,
        variable_yield=variable_yield,
        yield_amount=yield_amount if not variable_yield else None,
        yield_unit=yield_unit if not variable_yield else None,
        estimated_labor_minutes=estimated_labor_minutes,
        hourly_labor_rate=hourly_labor_rate,
        can_be_scaled=can_be_scaled,
        scale_double=scale_double if can_be_scaled else False,
        scale_triple=scale_triple if can_be_scaled else False,
        scale_quadruple=scale_quadruple if can_be_scaled else False,
        scale_three_quarters=scale_three_quarters if can_be_scaled else False,
        scale_two_thirds=scale_two_thirds if can_be_scaled else False,
        scale_half=scale_half if can_be_scaled else False,
        scale_quarter=scale_quarter if can_be_scaled else False,
        scale_eighth=scale_eighth if can_be_scaled else False,
        scale_sixteenth=scale_sixteenth if can_be_scaled else False
    )
    
    db.add(batch)
    db.commit()
    
    return RedirectResponse(url="/batches", status_code=302)

@router.get("/{batch_id}", response_class=HTMLResponse)
async def batch_detail(batch_id: int, request: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
    total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)

    # Get actual labor cost (falls back to estimated if no completed tasks)
    actual_labor_cost = batch.get_actual_labor_cost(db)

    # Calculate costs with estimated labor
    estimated_total_batch_cost = total_recipe_cost + batch.estimated_labor_cost
    estimated_cost_per_yield_unit = estimated_total_batch_cost / batch.yield_amount if batch.yield_amount else 0

    # Calculate costs with actual labor
    actual_total_batch_cost = total_recipe_cost + actual_labor_cost
    actual_cost_per_yield_unit = actual_total_batch_cost / batch.yield_amount if batch.yield_amount else 0

    return templates.TemplateResponse("batch_detail.html", {
        "request": request,
        "current_user": current_user,
        "batch": batch,
        "recipe_ingredients": recipe_ingredients,
        "total_recipe_cost": total_recipe_cost,
        "actual_labor_cost": actual_labor_cost,
        "actual_total_batch_cost": actual_total_batch_cost,
        "actual_cost_per_yield_unit": actual_cost_per_yield_unit,
        "estimated_total_batch_cost": estimated_total_batch_cost,
        "estimated_cost_per_yield_unit": estimated_cost_per_yield_unit
    })

@router.get("/{batch_id}/edit", response_class=HTMLResponse)
async def batch_edit_page(batch_id: int, request: Request, db: Session = Depends(get_db), current_user = Depends(require_manager_or_admin)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    recipes = db.query(Recipe).all()
    categories = db.query(Category).filter(Category.type == "batch").all()
    
    return templates.TemplateResponse("batch_edit.html", {
        "request": request,
        "current_user": current_user,
        "batch": batch,
        "recipes": recipes,
        "categories": categories
    })

@router.post("/{batch_id}/edit")
async def update_batch(
    batch_id: int,
    request: Request,
    recipe_id: int = Form(...),
    category_id: int = Form(None),
    variable_yield: bool = Form(False),
    yield_amount: float = Form(None),
    yield_unit: str = Form(None),
    estimated_labor_minutes: int = Form(...),
    hourly_labor_rate: float = Form(...),
    can_be_scaled: bool = Form(False),
    scale_double: bool = Form(False),
    scale_triple: bool = Form(False),
    scale_quadruple: bool = Form(False),
    scale_three_quarters: bool = Form(False),
    scale_two_thirds: bool = Form(False),
    scale_half: bool = Form(False),
    scale_quarter: bool = Form(False),
    scale_eighth: bool = Form(False),
    scale_sixteenth: bool = Form(False),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    batch.recipe_id = recipe_id
    batch.category_id = category_id if category_id else None
    batch.variable_yield = variable_yield
    batch.yield_amount = yield_amount if not variable_yield else None
    batch.yield_unit = yield_unit if not variable_yield else None
    batch.estimated_labor_minutes = estimated_labor_minutes
    batch.hourly_labor_rate = hourly_labor_rate
    batch.can_be_scaled = can_be_scaled
    batch.scale_double = scale_double if can_be_scaled else False
    batch.scale_triple = scale_triple if can_be_scaled else False
    batch.scale_quadruple = scale_quadruple if can_be_scaled else False
    batch.scale_three_quarters = scale_three_quarters if can_be_scaled else False
    batch.scale_two_thirds = scale_two_thirds if can_be_scaled else False
    batch.scale_half = scale_half if can_be_scaled else False
    batch.scale_quarter = scale_quarter if can_be_scaled else False
    batch.scale_eighth = scale_eighth if can_be_scaled else False
    batch.scale_sixteenth = scale_sixteenth if can_be_scaled else False
    
    db.commit()
    
    return RedirectResponse(url=f"/batches/{batch_id}", status_code=302)

@router.get("/{batch_id}/delete")
async def delete_batch(batch_id: int, db: Session = Depends(get_db), current_user = Depends(require_admin)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    db.delete(batch)
    db.commit()
    
    return RedirectResponse(url="/batches", status_code=302)