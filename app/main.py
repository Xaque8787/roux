# Food Cost Management System - Updated with working setup
from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from datetime import datetime, timedelta, date
from typing import Optional, List
import os

from .database import SessionLocal, engine, Base
from .models import *
from .auth import *
from .schemas import *

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_setup_required(db: Session):
    """Check if initial setup is required"""
    user_count = db.query(User).count()
    return user_count == 0

@app.get("/", response_class=RedirectResponse)
async def root():
    return RedirectResponse(url="/home", status_code=307)

@app.get("/setup", response_class=HTMLResponse)
async def setup_form(request: Request, db: Session = Depends(get_db)):
    if not check_setup_required(db):
        return RedirectResponse(url="/home", status_code=307)
    return templates.TemplateResponse("setup.html", {"request": request})

@app.post("/setup")
async def create_admin_user(
    request: Request,
    username: str = Form(...),
    full_name: str = Form(""),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    if not check_setup_required(db):
        return RedirectResponse(url="/home", status_code=307)
    
    try:
        # Use username as full_name if not provided
        if not full_name or full_name.strip() == "":
            full_name = username
        
        # Create admin user
        hashed_password = hash_password(password)
        admin_user = User(
            username=username,
            hashed_password=hashed_password,
            full_name=full_name,
            role="admin",
            is_admin=True,
            is_user=True,
            hourly_wage=15.0
        )
        db.add(admin_user)
        
        # Create default categories
        categories = [
            Category(name="Proteins", type="ingredient"),
            Category(name="Vegetables", type="ingredient"),
            Category(name="Dairy", type="ingredient"),
            Category(name="Grains", type="ingredient"),
            Category(name="Spices", type="ingredient"),
            Category(name="Appetizers", type="dish"),
            Category(name="Entrees", type="dish"),
            Category(name="Desserts", type="dish"),
            Category(name="Beverages", type="dish"),
            Category(name="Sauces", type="recipe"),
            Category(name="Soups", type="recipe"),
            Category(name="Salads", type="recipe"),
            Category(name="Prep Items", type="inventory"),
            Category(name="Finished Goods", type="inventory")
        ]
        
        for category in categories:
            db.add(category)
        
        # Create vendor units
        vendor_units = [
            VendorUnit(name="lb", description="Pound"),
            VendorUnit(name="oz", description="Ounce"),
            VendorUnit(name="gal", description="Gallon"),
            VendorUnit(name="qt", description="Quart"),
            VendorUnit(name="pt", description="Pint"),
            VendorUnit(name="fl oz", description="Fluid Ounce"),
            VendorUnit(name="kg", description="Kilogram"),
            VendorUnit(name="g", description="Gram"),
            VendorUnit(name="L", description="Liter"),
            VendorUnit(name="mL", description="Milliliter")
        ]
        
        for unit in vendor_units:
            db.add(unit)
        
        # Create usage units
        usage_units = [
            UsageUnit(name="cup"),
            UsageUnit(name="tbsp"),
            UsageUnit(name="tsp"),
            UsageUnit(name="oz"),
            UsageUnit(name="lb"),
            UsageUnit(name="each"),
            UsageUnit(name="piece"),
            UsageUnit(name="slice"),
            UsageUnit(name="clove"),
            UsageUnit(name="bunch"),
            UsageUnit(name="head"),
            UsageUnit(name="can"),
            UsageUnit(name="bottle"),
            UsageUnit(name="bag"),
            UsageUnit(name="box"),
            UsageUnit(name="gal"),
            UsageUnit(name="qt"),
            UsageUnit(name="pt"),
            UsageUnit(name="fl oz")
        ]
        
        for unit in usage_units:
            db.add(unit)
        
        # Commit to get IDs
        db.commit()
        
        # Create vendor unit conversions
        # Get the units we just created
        lb_unit = db.query(VendorUnit).filter(VendorUnit.name == "lb").first()
        oz_unit = db.query(VendorUnit).filter(VendorUnit.name == "oz").first()
        gal_unit = db.query(VendorUnit).filter(VendorUnit.name == "gal").first()
        qt_unit = db.query(VendorUnit).filter(VendorUnit.name == "qt").first()
        pt_unit = db.query(VendorUnit).filter(VendorUnit.name == "pt").first()
        fl_oz_unit = db.query(VendorUnit).filter(VendorUnit.name == "fl oz").first()
        
        # Get usage units
        cup_usage = db.query(UsageUnit).filter(UsageUnit.name == "cup").first()
        tbsp_usage = db.query(UsageUnit).filter(UsageUnit.name == "tbsp").first()
        tsp_usage = db.query(UsageUnit).filter(UsageUnit.name == "tsp").first()
        oz_usage = db.query(UsageUnit).filter(UsageUnit.name == "oz").first()
        lb_usage = db.query(UsageUnit).filter(UsageUnit.name == "lb").first()
        gal_usage = db.query(UsageUnit).filter(UsageUnit.name == "gal").first()
        qt_usage = db.query(UsageUnit).filter(UsageUnit.name == "qt").first()
        pt_usage = db.query(UsageUnit).filter(UsageUnit.name == "pt").first()
        fl_oz_usage = db.query(UsageUnit).filter(UsageUnit.name == "fl oz").first()
        
        # Create conversions
        conversions = []
        
        # Pound conversions
        if lb_unit and oz_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=lb_unit.id, usage_unit_id=oz_usage.id, conversion_factor=16))
        if lb_unit and lb_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=lb_unit.id, usage_unit_id=lb_usage.id, conversion_factor=1))
        if lb_unit and cup_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=lb_unit.id, usage_unit_id=cup_usage.id, conversion_factor=2))  # Approximate for flour
        
        # Ounce conversions
        if oz_unit and oz_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=oz_unit.id, usage_unit_id=oz_usage.id, conversion_factor=1))
        if oz_unit and tbsp_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=oz_unit.id, usage_unit_id=tbsp_usage.id, conversion_factor=2))
        if oz_unit and tsp_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=oz_unit.id, usage_unit_id=tsp_usage.id, conversion_factor=6))
        
        # Gallon conversions
        if gal_unit and gal_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=gal_unit.id, usage_unit_id=gal_usage.id, conversion_factor=1))
        if gal_unit and qt_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=gal_unit.id, usage_unit_id=qt_usage.id, conversion_factor=4))
        if gal_unit and pt_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=gal_unit.id, usage_unit_id=pt_usage.id, conversion_factor=8))
        if gal_unit and cup_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=gal_unit.id, usage_unit_id=cup_usage.id, conversion_factor=16))
        if gal_unit and fl_oz_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=gal_unit.id, usage_unit_id=fl_oz_usage.id, conversion_factor=128))
        
        # Quart conversions
        if qt_unit and qt_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=qt_unit.id, usage_unit_id=qt_usage.id, conversion_factor=1))
        if qt_unit and pt_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=qt_unit.id, usage_unit_id=pt_usage.id, conversion_factor=2))
        if qt_unit and cup_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=qt_unit.id, usage_unit_id=cup_usage.id, conversion_factor=4))
        if qt_unit and fl_oz_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=qt_unit.id, usage_unit_id=fl_oz_usage.id, conversion_factor=32))
        
        # Pint conversions
        if pt_unit and pt_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=pt_unit.id, usage_unit_id=pt_usage.id, conversion_factor=1))
        if pt_unit and cup_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=pt_unit.id, usage_unit_id=cup_usage.id, conversion_factor=2))
        if pt_unit and fl_oz_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=pt_unit.id, usage_unit_id=fl_oz_usage.id, conversion_factor=16))
        
        # Fluid ounce conversions
        if fl_oz_unit and fl_oz_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=fl_oz_unit.id, usage_unit_id=fl_oz_usage.id, conversion_factor=1))
        if fl_oz_unit and tbsp_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=fl_oz_unit.id, usage_unit_id=tbsp_usage.id, conversion_factor=2))
        if fl_oz_unit and tsp_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=fl_oz_unit.id, usage_unit_id=tsp_usage.id, conversion_factor=6))
        
        # Add all conversions
        for conversion in conversions:
            db.add(conversion)
        
        db.commit()
        
        # Redirect to login page after successful setup
        return RedirectResponse(url="/login", status_code=303)
        
    except Exception as e:
        db.rollback()
        return templates.TemplateResponse("setup.html", {
            "request": request, 
            "error": f"Error creating admin user: {str(e)}"
        })

@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, db: Session = Depends(get_db)):
    if check_setup_required(db):
        return RedirectResponse(url="/setup", status_code=307)
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    if check_setup_required(db):
        return RedirectResponse(url="/setup", status_code=307)
    
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {
            "request": request, 
            "error": "Invalid username or password"
        })
    
    if not user.is_active:
        return templates.TemplateResponse("login.html", {
            "request": request, 
            "error": "Account is deactivated"
        })
    
    # Create JWT token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_jwt(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    # Create response and set cookie
    response = RedirectResponse(url="/home", status_code=303)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax"
    )
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key="access_token")
    return response

@app.get("/home", response_class=HTMLResponse)
async def home(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("home.html", {
        "request": request,
        "current_user": current_user
    })

# Ingredients routes
@app.get("/ingredients", response_class=HTMLResponse)
async def ingredients_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ingredients = db.query(Ingredient).all()
    categories = db.query(Category).filter(Category.type == "ingredient").all()
    vendors = db.query(Vendor).all()
    vendor_units = db.query(VendorUnit).all()
    usage_units = db.query(UsageUnit).all()
    
    return templates.TemplateResponse("ingredients.html", {
        "request": request,
        "current_user": current_user,
        "ingredients": ingredients,
        "categories": categories,
        "vendors": vendors,
        "vendor_units": vendor_units,
        "usage_units": usage_units
    })

@app.post("/ingredients/new")
async def create_ingredient(
    request: Request,
    name: str = Form(...),
    category_id: Optional[int] = Form(None),
    vendor_id: Optional[int] = Form(None),
    vendor_unit_id: Optional[int] = Form(None),
    purchase_type: str = Form(...),
    purchase_unit_name: str = Form(...),
    purchase_weight_volume: float = Form(...),
    purchase_total_cost: float = Form(...),
    breakable_case: bool = Form(False),
    items_per_case: Optional[int] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    try:
        # Create ingredient
        ingredient = Ingredient(
            name=name,
            category_id=category_id if category_id else None,
            vendor_id=vendor_id if vendor_id else None,
            vendor_unit_id=vendor_unit_id if vendor_unit_id else None,
            purchase_type=purchase_type,
            purchase_unit_name=purchase_unit_name,
            purchase_weight_volume=purchase_weight_volume,
            purchase_total_cost=purchase_total_cost,
            breakable_case=breakable_case,
            items_per_case=items_per_case if purchase_type == 'case' else None
        )
        db.add(ingredient)
        db.flush()  # Get the ID
        
        # Add usage unit conversions
        form_data = await request.form()
        for key, value in form_data.items():
            if key.startswith('conversion_') and value:
                usage_unit_id = int(key.split('_')[1])
                conversion_factor = float(value)
                
                usage_conversion = IngredientUsageUnit(
                    ingredient_id=ingredient.id,
                    usage_unit_id=usage_unit_id,
                    conversion_factor=conversion_factor
                )
                db.add(usage_conversion)
        
        db.commit()
        return RedirectResponse(url="/ingredients", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/ingredients/{ingredient_id}", response_class=HTMLResponse)
async def ingredient_detail(ingredient_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    usage_units = db.query(IngredientUsageUnit).filter(IngredientUsageUnit.ingredient_id == ingredient_id).all()
    
    return templates.TemplateResponse("ingredient_detail.html", {
        "request": request,
        "current_user": current_user,
        "ingredient": ingredient,
        "usage_units": usage_units
    })

# Recipes routes
@app.get("/recipes", response_class=HTMLResponse)
async def recipes_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    recipes = db.query(Recipe).all()
    categories = db.query(Category).filter(Category.type == "recipe").all()
    
    return templates.TemplateResponse("recipes.html", {
        "request": request,
        "current_user": current_user,
        "recipes": recipes,
        "categories": categories
    })

@app.get("/recipes/{recipe_id}", response_class=HTMLResponse)
async def recipe_detail(recipe_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).all()
    total_cost = sum(ri.cost for ri in recipe_ingredients)
    
    return templates.TemplateResponse("recipe_detail.html", {
        "request": request,
        "current_user": current_user,
        "recipe": recipe,
        "recipe_ingredients": recipe_ingredients,
        "total_cost": total_cost
    })

# Batches routes
@app.get("/batches", response_class=HTMLResponse)
async def batches_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    batches = db.query(Batch).all()
    recipes = db.query(Recipe).all()
    usage_units = db.query(UsageUnit).all()
    
    return templates.TemplateResponse("batches.html", {
        "request": request,
        "current_user": current_user,
        "batches": batches,
        "recipes": recipes,
        "usage_units": usage_units
    })

@app.get("/batches/{batch_id}", response_class=HTMLResponse)
async def batch_detail(batch_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
    total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
    total_batch_cost = total_recipe_cost + batch.estimated_labor_cost
    cost_per_yield_unit = total_batch_cost / batch.yield_amount if batch.yield_amount > 0 else 0
    
    return templates.TemplateResponse("batch_detail.html", {
        "request": request,
        "current_user": current_user,
        "batch": batch,
        "recipe_ingredients": recipe_ingredients,
        "total_recipe_cost": total_recipe_cost,
        "total_batch_cost": total_batch_cost,
        "cost_per_yield_unit": cost_per_yield_unit
    })

# Dishes routes
@app.get("/dishes", response_class=HTMLResponse)
async def dishes_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    dishes = db.query(Dish).all()
    categories = db.query(Category).filter(Category.type == "dish").all()
    
    return templates.TemplateResponse("dishes.html", {
        "request": request,
        "current_user": current_user,
        "dishes": dishes,
        "categories": categories
    })

@app.get("/dishes/{dish_id}", response_class=HTMLResponse)
async def dish_detail(dish_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    dish_batch_portions = db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).all()
    
    # Calculate costs
    expected_total_cost = 0
    actual_total_cost = 0
    
    for portion in dish_batch_portions:
        # Calculate expected cost (using estimated labor)
        recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == portion.batch.recipe_id).all()
        recipe_cost = sum(ri.cost for ri in recipe_ingredients)
        total_batch_cost = recipe_cost + portion.batch.estimated_labor_cost
        cost_per_unit = total_batch_cost / portion.batch.yield_amount if portion.batch.yield_amount > 0 else 0
        portion.expected_cost = portion.portion_size * cost_per_unit
        expected_total_cost += portion.expected_cost
        
        # For now, actual cost equals expected cost (will be updated with real labor data later)
        portion.actual_cost = portion.expected_cost
        actual_total_cost += portion.actual_cost
    
    expected_profit = dish.sale_price - expected_total_cost
    expected_profit_margin = (expected_profit / dish.sale_price * 100) if dish.sale_price > 0 else 0
    actual_profit = dish.sale_price - actual_total_cost
    actual_profit_margin = (actual_profit / dish.sale_price * 100) if dish.sale_price > 0 else 0
    
    return templates.TemplateResponse("dish_detail.html", {
        "request": request,
        "current_user": current_user,
        "dish": dish,
        "dish_batch_portions": dish_batch_portions,
        "expected_total_cost": expected_total_cost,
        "actual_total_cost": actual_total_cost,
        "expected_profit": expected_profit,
        "expected_profit_margin": expected_profit_margin,
        "actual_profit": actual_profit,
        "actual_profit_margin": actual_profit_margin
    })

# Inventory routes
@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inventory_items = db.query(InventoryItem).all()
    categories = db.query(Category).filter(Category.type == "inventory").all()
    batches = db.query(Batch).all()
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Get current day (today's inventory day if exists)
    today = date.today()
    current_day = db.query(InventoryDay).filter(InventoryDay.date == today).first()
    
    # Get recent finalized days (last 30 days)
    thirty_days_ago = today - timedelta(days=30)
    finalized_days = db.query(InventoryDay).filter(
        InventoryDay.finalized == True,
        InventoryDay.date >= thirty_days_ago
    ).order_by(InventoryDay.date.desc()).limit(10).all()
    
    return templates.TemplateResponse("inventory.html", {
        "request": request,
        "current_user": current_user,
        "inventory_items": inventory_items,
        "categories": categories,
        "batches": batches,
        "employees": employees,
        "current_day": current_day,
        "finalized_days": finalized_days,
        "today_date": today.isoformat()
    })

# Employees routes (admin only)
@app.get("/employees", response_class=HTMLResponse)
async def employees_page(request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    employees = db.query(User).all()
    
    return templates.TemplateResponse("employees.html", {
        "request": request,
        "current_user": current_user,
        "employees": employees
    })

# Utilities routes (admin only)
@app.get("/utilities", response_class=HTMLResponse)
async def utilities_page(request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    utilities = db.query(UtilityCost).all()
    
    return templates.TemplateResponse("utilities.html", {
        "request": request,
        "current_user": current_user,
        "utilities": utilities
    })

# API routes for AJAX functionality
@app.get("/api/ingredients/all")
async def get_all_ingredients(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ingredients = db.query(Ingredient).all()
    result = []
    
    for ingredient in ingredients:
        usage_units = db.query(IngredientUsageUnit).filter(IngredientUsageUnit.ingredient_id == ingredient.id).all()
        
        ingredient_data = {
            "id": ingredient.id,
            "name": ingredient.name,
            "category": ingredient.category.name if ingredient.category else None,
            "usage_units": [
                {
                    "usage_unit_id": iu.usage_unit_id,
                    "usage_unit_name": iu.usage_unit.name,
                    "price_per_usage_unit": iu.price_per_usage_unit
                }
                for iu in usage_units
            ]
        }
        result.append(ingredient_data)
    
    return result

@app.get("/api/batches/all")
async def get_all_batches(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    batches = db.query(Batch).all()
    result = []
    
    for batch in batches:
        # Calculate batch cost
        recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
        recipe_cost = sum(ri.cost for ri in recipe_ingredients)
        total_cost = recipe_cost + batch.estimated_labor_cost
        cost_per_unit = total_cost / batch.yield_amount if batch.yield_amount > 0 else 0
        
        batch_data = {
            "id": batch.id,
            "recipe_name": batch.recipe.name,
            "yield_amount": batch.yield_amount,
            "yield_unit": batch.yield_unit.name if batch.yield_unit else "",
            "yield_unit_id": batch.yield_unit_id,
            "cost_per_unit": cost_per_unit,
            "category": batch.recipe.category.name if batch.recipe.category else None
        }
        result.append(batch_data)
    
    return result

@app.get("/api/batches/search")
async def search_batches(q: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    batches = db.query(Batch).join(Recipe).filter(Recipe.name.ilike(f"%{q}%")).all()
    result = []
    
    for batch in batches:
        # Calculate batch cost
        recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
        recipe_cost = sum(ri.cost for ri in recipe_ingredients)
        total_cost = recipe_cost + batch.estimated_labor_cost
        cost_per_unit = total_cost / batch.yield_amount if batch.yield_amount > 0 else 0
        
        batch_data = {
            "id": batch.id,
            "recipe_name": batch.recipe.name,
            "yield_amount": batch.yield_amount,
            "yield_unit": batch.yield_unit.name if batch.yield_unit else "",
            "yield_unit_id": batch.yield_unit_id,
            "cost_per_unit": cost_per_unit,
            "category": batch.recipe.category.name if batch.recipe.category else None
        }
        result.append(batch_data)
    
    return result

@app.get("/api/vendor_units/{vendor_unit_id}/conversions")
async def get_vendor_unit_conversions(vendor_unit_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conversions = db.query(VendorUnitConversion).filter(VendorUnitConversion.vendor_unit_id == vendor_unit_id).all()
    result = {}
    
    for conversion in conversions:
        result[conversion.usage_unit_id] = conversion.conversion_factor
    
    return result

# Categories route
@app.post("/categories/new")
async def create_category(
    name: str = Form(...),
    type: str = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    try:
        category = Category(name=name, type=type)
        db.add(category)
        db.commit()
        
        # Redirect back to the appropriate page based on type
        if type == "ingredient":
            return RedirectResponse(url="/ingredients", status_code=303)
        elif type == "recipe":
            return RedirectResponse(url="/recipes", status_code=303)
        elif type == "dish":
            return RedirectResponse(url="/dishes", status_code=303)
        elif type == "inventory":
            return RedirectResponse(url="/inventory", status_code=303)
        else:
            return RedirectResponse(url="/home", status_code=303)
            
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# Vendors route
@app.post("/vendors/new")
async def create_vendor(
    name: str = Form(...),
    contact_info: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    try:
        vendor = Vendor(name=name, contact_info=contact_info)
        db.add(vendor)
        db.commit()
        return RedirectResponse(url="/ingredients", status_code=303)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# Vendor Units route
@app.post("/vendor_units/new")
async def create_vendor_unit(
    name: str = Form(...),
    description: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    try:
        vendor_unit = VendorUnit(name=name, description=description)
        db.add(vendor_unit)
        db.commit()
        return RedirectResponse(url="/ingredients", status_code=303)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# Usage Units route
@app.post("/usage_units/new")
async def create_usage_unit(
    name: str = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    try:
        usage_unit = UsageUnit(name=name)
        db.add(usage_unit)
        db.commit()
        return RedirectResponse(url="/ingredients", status_code=303)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# Employee routes
@app.post("/employees/new")
async def create_employee(
    request: Request,
    full_name: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    hourly_wage: float = Form(...),
    work_schedule: str = Form(""),
    role: str = Form("user"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    try:
        # Check if username already exists
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            employees = db.query(User).all()
            return templates.TemplateResponse("employees.html", {
                "request": request,
                "current_user": current_user,
                "employees": employees,
                "error": "Username already exists"
            })
        
        # Create new employee
        hashed_password = hash_password(password)
        employee = User(
            username=username,
            hashed_password=hashed_password,
            full_name=full_name,
            hourly_wage=hourly_wage,
            work_schedule=work_schedule,
            role=role,
            is_admin=(role == "admin"),
            is_user=True
        )
        db.add(employee)
        db.commit()
        return RedirectResponse(url="/employees", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/employees/{employee_id}", response_class=HTMLResponse)
async def employee_detail(
    employee_id: int, 
    request: Request, 
    current_user: User = Depends(require_admin), 
    db: Session = Depends(get_db)
):
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    return templates.TemplateResponse("employee_detail.html", {
        "request": request,
        "current_user": current_user,
        "employee": employee
    })

@app.get("/employees/{employee_id}/edit", response_class=HTMLResponse)
async def employee_edit_form(
    employee_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    return templates.TemplateResponse("employee_edit.html", {
        "request": request,
        "current_user": current_user,
        "employee": employee
    })

@app.post("/employees/{employee_id}/edit")
async def update_employee(
    employee_id: int,
    request: Request,
    full_name: str = Form(...),
    username: str = Form(...),
    password: str = Form(""),
    hourly_wage: float = Form(...),
    work_schedule: str = Form(""),
    role: str = Form("user"),
    is_active: bool = Form(False),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    try:
        employee = db.query(User).filter(User.id == employee_id).first()
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        # Check if username is taken by another user
        existing_user = db.query(User).filter(User.username == username, User.id != employee_id).first()
        if existing_user:
            return templates.TemplateResponse("employee_edit.html", {
                "request": request,
                "current_user": current_user,
                "employee": employee,
                "error": "Username already exists"
            })
        
        # Update employee
        employee.full_name = full_name
        employee.username = username
        employee.hourly_wage = hourly_wage
        employee.work_schedule = work_schedule
        employee.role = role
        employee.is_admin = (role == "admin")
        employee.is_active = is_active
        
        # Update password if provided
        if password and password.strip():
            employee.hashed_password = hash_password(password)
        
        db.commit()
        return RedirectResponse(url=f"/employees/{employee_id}", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/employees/{employee_id}/delete")
async def deactivate_employee(
    employee_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    try:
        employee = db.query(User).filter(User.id == employee_id).first()
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        # Don't allow deactivating yourself
        if employee.id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
        
        employee.is_active = False
        db.commit()
        return RedirectResponse(url="/employees", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
# Error handlers
@app.exception_handler(401)
async def unauthorized_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/"):
        raise exc
    return RedirectResponse(url="/login", status_code=303)

@app.exception_handler(403)
async def forbidden_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse("error.html", {
        "request": request,
        "status_code": 403,
        "detail": "Access forbidden"
    }, status_code=403)

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse("error.html", {
        "request": request,
        "status_code": 404,
        "detail": "Page not found"
    }, status_code=404)

# Additional missing routes
@app.post("/recipes/new")
async def create_recipe(
    request: Request,
    name: str = Form(...),
    category_id: Optional[int] = Form(None),
    instructions: str = Form(""),
    ingredients_data: str = Form(""),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    try:
        import json
        
        # Create recipe
        recipe = Recipe(
            name=name,
            category_id=category_id if category_id else None,
            instructions=instructions
        )
        db.add(recipe)
        db.flush()  # Get the ID
        
        # Add ingredients if provided
        if ingredients_data:
            ingredients = json.loads(ingredients_data)
            for ingredient_data in ingredients:
                recipe_ingredient = RecipeIngredient(
                    recipe_id=recipe.id,
                    ingredient_id=ingredient_data['ingredient_id'],
                    usage_unit_id=ingredient_data['usage_unit_id'],
                    quantity=ingredient_data['quantity']
                )
                db.add(recipe_ingredient)
        
        db.commit()
        return RedirectResponse(url="/recipes", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/recipes/{recipe_id}/edit", response_class=HTMLResponse)
async def recipe_edit_form(
    recipe_id: int,
    request: Request,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    categories = db.query(Category).filter(Category.type == "recipe").all()
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).all()
    
    return templates.TemplateResponse("recipe_edit.html", {
        "request": request,
        "current_user": current_user,
        "recipe": recipe,
        "categories": categories,
        "recipe_ingredients": recipe_ingredients
    })

@app.post("/recipes/{recipe_id}/edit")
async def update_recipe(
    recipe_id: int,
    request: Request,
    name: str = Form(...),
    category_id: Optional[int] = Form(None),
    instructions: str = Form(""),
    ingredients_data: str = Form(""),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    try:
        import json
        
        recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")
        
        # Update recipe
        recipe.name = name
        recipe.category_id = category_id if category_id else None
        recipe.instructions = instructions
        
        # Remove existing ingredients
        db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).delete()
        
        # Add new ingredients
        if ingredients_data:
            ingredients = json.loads(ingredients_data)
            for ingredient_data in ingredients:
                recipe_ingredient = RecipeIngredient(
                    recipe_id=recipe.id,
                    ingredient_id=ingredient_data['ingredient_id'],
                    usage_unit_id=ingredient_data['usage_unit_id'],
                    quantity=ingredient_data['quantity']
                )
                db.add(recipe_ingredient)
        
        db.commit()
        return RedirectResponse(url=f"/recipes/{recipe_id}", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/recipes/{recipe_id}/delete")
async def delete_recipe(
    recipe_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    try:
        recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")
        
        # Delete recipe ingredients first
        db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).delete()
        
        # Delete recipe
        db.delete(recipe)
        db.commit()
        return RedirectResponse(url="/recipes", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/batches/new")
async def create_batch(
    request: Request,
    recipe_id: int = Form(...),
    yield_amount: float = Form(...),
    yield_unit_id: int = Form(...),
    estimated_labor_minutes: int = Form(...),
    hourly_labor_rate: float = Form(...),
    can_be_scaled: bool = Form(False),
    scale_double: bool = Form(False),
    scale_half: bool = Form(False),
    scale_quarter: bool = Form(False),
    scale_eighth: bool = Form(False),
    scale_sixteenth: bool = Form(False),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    try:
        batch = Batch(
            recipe_id=recipe_id,
            yield_amount=yield_amount,
            yield_unit_id=yield_unit_id,
            estimated_labor_minutes=estimated_labor_minutes,
            hourly_labor_rate=hourly_labor_rate,
            can_be_scaled=can_be_scaled,
            scale_double=scale_double,
            scale_half=scale_half,
            scale_quarter=scale_quarter,
            scale_eighth=scale_eighth,
            scale_sixteenth=scale_sixteenth
        )
        db.add(batch)
        db.commit()
        return RedirectResponse(url="/batches", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/batches/{batch_id}/edit", response_class=HTMLResponse)
async def batch_edit_form(
    batch_id: int,
    request: Request,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    recipes = db.query(Recipe).all()
    usage_units = db.query(UsageUnit).all()
    
    return templates.TemplateResponse("batch_edit.html", {
        "request": request,
        "current_user": current_user,
        "batch": batch,
        "recipes": recipes,
        "usage_units": usage_units
    })

@app.post("/batches/{batch_id}/edit")
async def update_batch(
    batch_id: int,
    request: Request,
    recipe_id: int = Form(...),
    yield_amount: float = Form(...),
    yield_unit_id: int = Form(...),
    estimated_labor_minutes: int = Form(...),
    hourly_labor_rate: float = Form(...),
    can_be_scaled: bool = Form(False),
    scale_double: bool = Form(False),
    scale_half: bool = Form(False),
    scale_quarter: bool = Form(False),
    scale_eighth: bool = Form(False),
    scale_sixteenth: bool = Form(False),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    try:
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        
        # Update batch
        batch.recipe_id = recipe_id
        batch.yield_amount = yield_amount
        batch.yield_unit_id = yield_unit_id
        batch.estimated_labor_minutes = estimated_labor_minutes
        batch.hourly_labor_rate = hourly_labor_rate
        batch.can_be_scaled = can_be_scaled
        batch.scale_double = scale_double
        batch.scale_half = scale_half
        batch.scale_quarter = scale_quarter
        batch.scale_eighth = scale_eighth
        batch.scale_sixteenth = scale_sixteenth
        
        db.commit()
        return RedirectResponse(url=f"/batches/{batch_id}", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/batches/{batch_id}/delete")
async def delete_batch(
    batch_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    try:
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        
        # Delete related dish batch portions first
        db.query(DishBatchPortion).filter(DishBatchPortion.batch_id == batch_id).delete()
        
        # Delete batch
        db.delete(batch)
        db.commit()
        return RedirectResponse(url="/batches", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/dishes/new")
async def create_dish(
    request: Request,
    name: str = Form(...),
    category_id: Optional[int] = Form(None),
    sale_price: float = Form(...),
    description: str = Form(""),
    batch_portions_data: str = Form(""),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    try:
        import json
        
        # Create dish
        dish = Dish(
            name=name,
            category_id=category_id if category_id else None,
            sale_price=sale_price,
            description=description
        )
        db.add(dish)
        db.flush()  # Get the ID
        
        # Add batch portions if provided
        if batch_portions_data:
            batch_portions = json.loads(batch_portions_data)
            for portion_data in batch_portions:
                dish_batch_portion = DishBatchPortion(
                    dish_id=dish.id,
                    batch_id=portion_data['batch_id'],
                    portion_size=portion_data['portion_size'],
                    portion_unit_id=portion_data['portion_unit_id']
                )
                db.add(dish_batch_portion)
        
        db.commit()
        return RedirectResponse(url="/dishes", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/dishes/{dish_id}/edit", response_class=HTMLResponse)
async def dish_edit_form(
    dish_id: int,
    request: Request,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    categories = db.query(Category).filter(Category.type == "dish").all()
    dish_batch_portions = db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).all()
    
    return templates.TemplateResponse("dish_edit.html", {
        "request": request,
        "current_user": current_user,
        "dish": dish,
        "categories": categories,
        "dish_batch_portions": dish_batch_portions
    })

@app.post("/dishes/{dish_id}/edit")
async def update_dish(
    dish_id: int,
    request: Request,
    name: str = Form(...),
    category_id: Optional[int] = Form(None),
    sale_price: float = Form(...),
    description: str = Form(""),
    batch_portions_data: str = Form(""),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    try:
        import json
        
        dish = db.query(Dish).filter(Dish.id == dish_id).first()
        if not dish:
            raise HTTPException(status_code=404, detail="Dish not found")
        
        # Update dish
        dish.name = name
        dish.category_id = category_id if category_id else None
        dish.sale_price = sale_price
        dish.description = description
        
        # Remove existing batch portions
        db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).delete()
        
        # Add new batch portions
        if batch_portions_data:
            batch_portions = json.loads(batch_portions_data)
            for portion_data in batch_portions:
                dish_batch_portion = DishBatchPortion(
                    dish_id=dish.id,
                    batch_id=portion_data['batch_id'],
                    portion_size=portion_data['portion_size'],
                    portion_unit_id=portion_data['portion_unit_id']
                )
                db.add(dish_batch_portion)
        
        db.commit()
        return RedirectResponse(url=f"/dishes/{dish_id}", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/dishes/{dish_id}/delete")
async def delete_dish(
    dish_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    try:
        dish = db.query(Dish).filter(Dish.id == dish_id).first()
        if not dish:
            raise HTTPException(status_code=404, detail="Dish not found")
        
        # Delete dish batch portions first
        db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).delete()
        
        # Delete dish
        db.delete(dish)
        db.commit()
        return RedirectResponse(url="/dishes", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/ingredients/{ingredient_id}/edit", response_class=HTMLResponse)
async def ingredient_edit_form(
    ingredient_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    categories = db.query(Category).filter(Category.type == "ingredient").all()
    vendors = db.query(Vendor).all()
    vendor_units = db.query(VendorUnit).all()
    usage_units = db.query(UsageUnit).all()
    
    # Get existing conversions
    existing_conversions = {}
    for iu in ingredient.usage_units:
        existing_conversions[iu.usage_unit_id] = iu.conversion_factor
    
    return templates.TemplateResponse("ingredient_edit.html", {
        "request": request,
        "current_user": current_user,
        "ingredient": ingredient,
        "categories": categories,
        "vendors": vendors,
        "vendor_units": vendor_units,
        "usage_units": usage_units,
        "existing_conversions": existing_conversions
    })

@app.post("/ingredients/{ingredient_id}/edit")
async def update_ingredient(
    ingredient_id: int,
    request: Request,
    name: str = Form(...),
    category_id: Optional[int] = Form(None),
    vendor_id: Optional[int] = Form(None),
    vendor_unit_id: Optional[int] = Form(None),
    purchase_type: str = Form(...),
    purchase_unit_name: str = Form(...),
    purchase_weight_volume: float = Form(...),
    purchase_total_cost: float = Form(...),
    breakable_case: bool = Form(False),
    items_per_case: Optional[int] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    try:
        ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
        if not ingredient:
            raise HTTPException(status_code=404, detail="Ingredient not found")
        
        # Update ingredient
        ingredient.name = name
        ingredient.category_id = category_id if category_id else None
        ingredient.vendor_id = vendor_id if vendor_id else None
        ingredient.vendor_unit_id = vendor_unit_id if vendor_unit_id else None
        ingredient.purchase_type = purchase_type
        ingredient.purchase_unit_name = purchase_unit_name
        ingredient.purchase_weight_volume = purchase_weight_volume
        ingredient.purchase_total_cost = purchase_total_cost
        ingredient.breakable_case = breakable_case
        ingredient.items_per_case = items_per_case if purchase_type == 'case' else None
        
        # Remove existing usage unit conversions
        db.query(IngredientUsageUnit).filter(IngredientUsageUnit.ingredient_id == ingredient_id).delete()
        
        # Add new usage unit conversions
        form_data = await request.form()
        for key, value in form_data.items():
            if key.startswith('conversion_') and value:
                usage_unit_id = int(key.split('_')[1])
                conversion_factor = float(value)
                
                usage_conversion = IngredientUsageUnit(
                    ingredient_id=ingredient.id,
                    usage_unit_id=usage_unit_id,
                    conversion_factor=conversion_factor
                )
                db.add(usage_conversion)
        
        db.commit()
        return RedirectResponse(url=f"/ingredients/{ingredient_id}", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/ingredients/{ingredient_id}/delete")
async def delete_ingredient(
    ingredient_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    try:
        ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
        if not ingredient:
            raise HTTPException(status_code=404, detail="Ingredient not found")
        
        # Delete usage unit conversions first
        db.query(IngredientUsageUnit).filter(IngredientUsageUnit.ingredient_id == ingredient_id).delete()
        
        # Delete recipe ingredients
        db.query(RecipeIngredient).filter(RecipeIngredient.ingredient_id == ingredient_id).delete()
        
        # Delete ingredient
        db.delete(ingredient)
        db.commit()
        return RedirectResponse(url="/ingredients", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/inventory/new_item")
async def create_inventory_item(
    request: Request,
    name: str = Form(...),
    category_id: Optional[int] = Form(None),
    batch_id: Optional[int] = Form(None),
    par_level: float = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    try:
        inventory_item = InventoryItem(
            name=name,
            category_id=category_id if category_id else None,
            batch_id=batch_id if batch_id else None,
            par_level=par_level
        )
        db.add(inventory_item)
        db.commit()
        return RedirectResponse(url="/inventory", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/inventory/new_day")
async def create_inventory_day(
    request: Request,
    date: str = Form(...),
    employees_working: List[str] = Form(...),
    global_notes: str = Form(""),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    try:
        from datetime import datetime
        
        # Parse date
        inventory_date = datetime.strptime(date, '%Y-%m-%d').date()
        
        # Check if day already exists
        existing_day = db.query(InventoryDay).filter(InventoryDay.date == inventory_date).first()
        if existing_day:
            return RedirectResponse(url=f"/inventory/day/{existing_day.id}", status_code=303)
        
        # Create inventory day
        inventory_day = InventoryDay(
            date=inventory_date,
            employees_working=','.join(employees_working),
            global_notes=global_notes
        )
        db.add(inventory_day)
        db.flush()  # Get the ID
        
        # Create inventory day items for all inventory items
        inventory_items = db.query(InventoryItem).all()
        for item in inventory_items:
            day_item = InventoryDayItem(
                day_id=inventory_day.id,
                inventory_item_id=item.id,
                quantity=0
            )
            db.add(day_item)
        
        db.commit()
        return RedirectResponse(url=f"/inventory/day/{inventory_day.id}", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/inventory/day/{day_id}", response_class=HTMLResponse)
async def inventory_day_detail(
    day_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    inventory_day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == day_id).all()
    tasks = db.query(Task).filter(Task.day_id == day_id).all()
    employees = db.query(User).filter(User.is_active == True).all()
    
    return templates.TemplateResponse("inventory_day.html", {
        "request": request,
        "current_user": current_user,
        "inventory_day": inventory_day,
        "inventory_day_items": inventory_day_items,
        "tasks": tasks,
        "employees": employees
    })

@app.get("/inventory/items/{item_id}/edit", response_class=HTMLResponse)
async def inventory_item_edit_form(
    item_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    categories = db.query(Category).filter(Category.type == "inventory").all()
    batches = db.query(Batch).all()
    
    return templates.TemplateResponse("inventory_item_edit.html", {
        "request": request,
        "current_user": current_user,
        "item": item,
        "categories": categories,
        "batches": batches
    })

@app.post("/inventory/items/{item_id}/edit")
async def update_inventory_item(
    item_id: int,
    request: Request,
    name: str = Form(...),
    category_id: Optional[int] = Form(None),
    batch_id: Optional[int] = Form(None),
    par_level: float = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    try:
        item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Inventory item not found")
        
        # Update item
        item.name = name
        item.category_id = category_id if category_id else None
        item.batch_id = batch_id if batch_id else None
        item.par_level = par_level
        
        db.commit()
        return RedirectResponse(url="/inventory", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/inventory/items/{item_id}/delete")
async def delete_inventory_item(
    item_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    try:
        item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Inventory item not found")
        
        # Delete related day items first
        db.query(InventoryDayItem).filter(InventoryDayItem.inventory_item_id == item_id).delete()
        
        # Delete tasks related to this item
        db.query(Task).filter(Task.inventory_item_id == item_id).delete()
        
        # Delete item
        db.delete(item)
        db.commit()
        return RedirectResponse(url="/inventory", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/utilities/new")
async def create_utility(
    request: Request,
    name: str = Form(...),
    monthly_cost: float = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    try:
        # Check if utility already exists
        existing_utility = db.query(UtilityCost).filter(UtilityCost.name == name).first()
        if existing_utility:
            # Update existing
            existing_utility.monthly_cost = monthly_cost
            existing_utility.last_updated = datetime.utcnow()
        else:
            # Create new
            utility = UtilityCost(name=name, monthly_cost=monthly_cost)
            db.add(utility)
        
        db.commit()
        return RedirectResponse(url="/utilities", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/utilities/{utility_id}/delete")
async def delete_utility(
    utility_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    try:
        utility = db.query(UtilityCost).filter(UtilityCost.id == utility_id).first()
        if not utility:
            raise HTTPException(status_code=404, detail="Utility not found")
        
        db.delete(utility)
        db.commit()
        return RedirectResponse(url="/utilities", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# Additional API routes for recipe functionality
@app.get("/api/recipes/{recipe_id}/usage_units")
async def get_recipe_usage_units(
    recipe_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).all()
    usage_unit_ids = set()
    
    for ri in recipe_ingredients:
        usage_unit_ids.add(ri.usage_unit_id)
    
    usage_units = db.query(UsageUnit).filter(UsageUnit.id.in_(usage_unit_ids)).all()
    
    return [{"id": unit.id, "name": unit.name} for unit in usage_units]

@app.get("/api/batches/{batch_id}/portion_units")
async def get_batch_portion_units(
    batch_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Get recipe ingredients and their usage units
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
    usage_unit_ids = set()
    
    for ri in recipe_ingredients:
        usage_unit_ids.add(ri.usage_unit_id)
    
    # Always include the batch yield unit
    if batch.yield_unit_id:
        usage_unit_ids.add(batch.yield_unit_id)
    
    usage_units = db.query(UsageUnit).filter(UsageUnit.id.in_(usage_unit_ids)).all()
    
    return [{"id": unit.id, "name": unit.name} for unit in usage_units]

@app.get("/api/batches/{batch_id}/cost_per_unit/{unit_id}")
async def get_batch_cost_per_unit(
    batch_id: int,
    unit_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Calculate total batch cost
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
    recipe_cost = sum(ri.cost for ri in recipe_ingredients)
    total_cost = recipe_cost + batch.estimated_labor_cost
    
    # Calculate cost per yield unit
    cost_per_yield_unit = total_cost / batch.yield_amount if batch.yield_amount > 0 else 0
    
    # If requesting yield unit, return directly
    if unit_id == batch.yield_unit_id:
        return {"expected_cost_per_unit": cost_per_yield_unit}
    
    # Otherwise, need to convert from yield unit to requested unit
    # For now, return the yield unit cost (conversion logic can be added later)
    return {"expected_cost_per_unit": cost_per_yield_unit}

@app.get("/api/batches/{batch_id}/labor_stats")
async def get_batch_labor_stats(
    batch_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from datetime import datetime, timedelta
    
    # Get completed tasks for this batch
    completed_tasks = db.query(Task).filter(
        Task.batch_id == batch_id,
        Task.finished_at.isnot(None)
    ).order_by(Task.finished_at.desc()).all()
    
    if not completed_tasks:
        return {
            "task_count": 0,
            "most_recent_cost": 0,
            "most_recent_date": None,
            "average_week": 0,
            "average_month": 0,
            "average_all_time": 0,
            "week_task_count": 0,
            "month_task_count": 0
        }
    
    # Calculate stats
    most_recent = completed_tasks[0]
    week_ago = datetime.utcnow() - timedelta(days=7)
    month_ago = datetime.utcnow() - timedelta(days=30)
    
    week_tasks = [t for t in completed_tasks if t.finished_at >= week_ago]
    month_tasks = [t for t in completed_tasks if t.finished_at >= month_ago]
    
    return {
        "task_count": len(completed_tasks),
        "most_recent_cost": most_recent.labor_cost,
        "most_recent_date": most_recent.finished_at.strftime('%Y-%m-%d'),
        "average_week": sum(t.labor_cost for t in week_tasks) / len(week_tasks) if week_tasks else 0,
        "average_month": sum(t.labor_cost for t in month_tasks) / len(month_tasks) if month_tasks else 0,
        "average_all_time": sum(t.labor_cost for t in completed_tasks) / len(completed_tasks),
        "week_task_count": len(week_tasks),
        "month_task_count": len(month_tasks)
    }