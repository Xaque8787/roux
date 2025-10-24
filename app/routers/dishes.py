from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import json
from ..database import get_db
from ..dependencies import require_manager_or_admin, get_current_user, require_admin
from ..models import Dish, Category, DishBatchPortion, DishIngredientPortion, Batch
from ..utils.template_helpers import setup_template_filters

router = APIRouter(prefix="/dishes", tags=["dishes"])
templates = setup_template_filters(Jinja2Templates(directory="templates"))

@router.get("/", response_class=HTMLResponse)
async def dishes_page(request: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    dishes = db.query(Dish).all()
    categories = db.query(Category).filter(Category.type == "dish").all()
    
    return templates.TemplateResponse("dishes.html", {
        "request": request,
        "current_user": current_user,
        "dishes": dishes,
        "categories": categories
    })

@router.post("/new")
async def create_dish(
    request: Request,
    name: str = Form(...),
    category_id: int = Form(None),
    sale_price: float = Form(...),
    description: str = Form(""),
    batch_portions_data: str = Form(...),
    ingredient_portions_data: str = Form(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    dish = Dish(
        name=name,
        category_id=category_id if category_id else None,
        sale_price=sale_price,
        description=description if description else None
    )
    
    db.add(dish)
    db.flush()  # Get the dish ID
    
    # Parse and add batch portions
    try:
        batch_portions = json.loads(batch_portions_data)
        for portion_data in batch_portions:
            dish_batch_portion = DishBatchPortion(
                dish_id=dish.id,
                batch_id=portion_data['batch_id'],
                portion_size=portion_data.get('portion_size'),
                portion_unit=portion_data.get('unit'),
                use_recipe_portion=portion_data.get('use_recipe_portion', False),
                recipe_portion_percent=portion_data.get('recipe_portion_percent')
            )
            db.add(dish_batch_portion)
    except (json.JSONDecodeError, KeyError) as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid batch portions data")
    
    # Parse and add ingredient portions
    try:
        ingredient_portions = json.loads(ingredient_portions_data)
        for portion_data in ingredient_portions:
            dish_ingredient_portion = DishIngredientPortion(
                dish_id=dish.id,
                ingredient_id=portion_data['ingredient_id'],
                quantity=portion_data['quantity'],
                unit=portion_data['unit']
            )
            db.add(dish_ingredient_portion)
    except (json.JSONDecodeError, KeyError) as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid ingredient portions data")
    
    db.commit()
    
    return RedirectResponse(url="/dishes", status_code=302)

@router.get("/{dish_id}", response_class=HTMLResponse)
async def dish_detail(dish_id: int, request: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    dish_batch_portions = db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).all()
    dish_ingredient_portions = db.query(DishIngredientPortion).filter(DishIngredientPortion.dish_id == dish_id).all()
    
    # Calculate costs dynamically for each portion
    expected_recipe_cost = sum(portion.get_recipe_cost(db) for portion in dish_batch_portions)
    expected_labor_cost = sum(portion.get_labor_cost(db, 'estimated') for portion in dish_batch_portions)
    ingredient_cost = sum(portion.cost for portion in dish_ingredient_portions)
    expected_total_cost = expected_recipe_cost + expected_labor_cost + ingredient_cost
    
    actual_recipe_cost = sum(portion.get_recipe_cost(db) for portion in dish_batch_portions)
    actual_labor_cost = sum(portion.get_labor_cost(db, 'actual') for portion in dish_batch_portions)
    actual_total_cost = actual_recipe_cost + actual_labor_cost + ingredient_cost
    
    week_recipe_cost = sum(portion.get_recipe_cost(db) for portion in dish_batch_portions)
    week_labor_cost = sum(portion.get_labor_cost(db, 'week_avg') for portion in dish_batch_portions)
    actual_total_cost_week = week_recipe_cost + week_labor_cost + ingredient_cost
    
    month_recipe_cost = sum(portion.get_recipe_cost(db) for portion in dish_batch_portions)
    month_labor_cost = sum(portion.get_labor_cost(db, 'month_avg') for portion in dish_batch_portions)
    actual_total_cost_month = month_recipe_cost + month_labor_cost + ingredient_cost
    
    all_time_recipe_cost = sum(portion.get_recipe_cost(db) for portion in dish_batch_portions)
    all_time_labor_cost = sum(portion.get_labor_cost(db, 'all_time_avg') for portion in dish_batch_portions)
    actual_total_cost_all_time = all_time_recipe_cost + all_time_labor_cost + ingredient_cost
    
    # Calculate profits and margins
    expected_profit = dish.sale_price - expected_total_cost
    expected_profit_margin = (expected_profit / dish.sale_price * 100) if dish.sale_price > 0 else 0
    
    actual_profit = dish.sale_price - actual_total_cost
    actual_profit_margin = (actual_profit / dish.sale_price * 100) if dish.sale_price > 0 else 0
    
    actual_profit_week = dish.sale_price - actual_total_cost_week
    actual_profit_margin_week = (actual_profit_week / dish.sale_price * 100) if dish.sale_price > 0 else 0
    
    actual_profit_month = dish.sale_price - actual_total_cost_month
    actual_profit_margin_month = (actual_profit_month / dish.sale_price * 100) if dish.sale_price > 0 else 0
    
    actual_profit_all_time = dish.sale_price - actual_total_cost_all_time
    actual_profit_margin_all_time = (actual_profit_all_time / dish.sale_price * 100) if dish.sale_price > 0 else 0
    
    return templates.TemplateResponse("dish_detail.html", {
        "request": request,
        "current_user": current_user,
        "dish": dish,
        "dish_batch_portions": dish_batch_portions,
        "dish_ingredient_portions": dish_ingredient_portions,
        "ingredient_cost": ingredient_cost,
        "expected_total_cost": expected_total_cost,
        "expected_recipe_cost": expected_recipe_cost,
        "expected_labor_cost": expected_labor_cost,
        "actual_total_cost": actual_total_cost,
        "actual_recipe_cost": actual_recipe_cost,
        "actual_labor_cost": actual_labor_cost,
        "week_recipe_cost": week_recipe_cost,
        "week_labor_cost": week_labor_cost,
        "actual_total_cost_week": actual_total_cost_week,
        "month_recipe_cost": month_recipe_cost,
        "month_labor_cost": month_labor_cost,
        "actual_total_cost_month": actual_total_cost_month,
        "all_time_recipe_cost": all_time_recipe_cost,
        "all_time_labor_cost": all_time_labor_cost,
        "actual_total_cost_all_time": actual_total_cost_all_time,
        "expected_profit": expected_profit,
        "expected_profit_margin": expected_profit_margin,
        "actual_profit": actual_profit,
        "actual_profit_margin": actual_profit_margin,
        "actual_profit_week": actual_profit_week,
        "actual_profit_margin_week": actual_profit_margin_week,
        "actual_profit_month": actual_profit_month,
        "actual_profit_margin_month": actual_profit_margin_month,
        "actual_profit_all_time": actual_profit_all_time,
        "actual_profit_margin_all_time": actual_profit_margin_all_time,
        "db": db
    })

@router.get("/{dish_id}/edit", response_class=HTMLResponse)
async def dish_edit_page(dish_id: int, request: Request, db: Session = Depends(get_db), current_user = Depends(require_manager_or_admin)):
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    categories = db.query(Category).filter(Category.type == "dish").all()
    dish_batch_portions = db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).all()
    dish_ingredient_portions = db.query(DishIngredientPortion).filter(DishIngredientPortion.dish_id == dish_id).all()
    
    return templates.TemplateResponse("dish_edit.html", {
        "request": request,
        "current_user": current_user,
        "dish": dish,
        "categories": categories,
        "dish_batch_portions": dish_batch_portions,
        "dish_ingredient_portions": dish_ingredient_portions,
        "db": db
    })

@router.post("/{dish_id}/edit")
async def update_dish(
    dish_id: int,
    request: Request,
    name: str = Form(...),
    category_id: int = Form(None),
    sale_price: float = Form(...),
    description: str = Form(""),
    batch_portions_data: str = Form(...),
    ingredient_portions_data: str = Form(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    dish.name = name
    dish.category_id = category_id if category_id else None
    dish.sale_price = sale_price
    dish.description = description if description else None
    
    # Remove existing batch portions
    db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).delete()
    
    # Remove existing ingredient portions
    db.query(DishIngredientPortion).filter(DishIngredientPortion.dish_id == dish_id).delete()
    
    # Parse and add new batch portions
    try:
        batch_portions = json.loads(batch_portions_data)
        for portion_data in batch_portions:
            dish_batch_portion = DishBatchPortion(
                dish_id=dish.id,
                batch_id=portion_data['batch_id'],
                portion_size=portion_data.get('portion_size'),
                portion_unit=portion_data.get('unit'),
                use_recipe_portion=portion_data.get('use_recipe_portion', False),
                recipe_portion_percent=portion_data.get('recipe_portion_percent')
            )
            db.add(dish_batch_portion)
    except (json.JSONDecodeError, KeyError) as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid batch portions data")
    
    # Parse and add new ingredient portions
    try:
        ingredient_portions = json.loads(ingredient_portions_data)
        for portion_data in ingredient_portions:
            dish_ingredient_portion = DishIngredientPortion(
                dish_id=dish.id,
                ingredient_id=portion_data['ingredient_id'],
                quantity=portion_data['quantity'],
                unit=portion_data['unit']
            )
            db.add(dish_ingredient_portion)
    except (json.JSONDecodeError, KeyError) as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid ingredient portions data")
    
    db.commit()
    
    return RedirectResponse(url=f"/dishes/{dish_id}", status_code=302)

@router.get("/{dish_id}/delete")
async def delete_dish(dish_id: int, db: Session = Depends(get_db), current_user = Depends(require_admin)):
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    # Delete dish batch portions first
    db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).delete()
    
    # Delete dish ingredient portions
    db.query(DishIngredientPortion).filter(DishIngredientPortion.dish_id == dish_id).delete()
    
    db.delete(dish)
    db.commit()
    
    return RedirectResponse(url="/dishes", status_code=302)