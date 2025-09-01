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