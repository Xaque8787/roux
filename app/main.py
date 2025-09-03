from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc
from datetime import datetime, timedelta, date
from typing import Optional, List
import json

from .database import engine, get_db
from .models import Base, User, Category, Ingredient, Recipe, RecipeIngredient, Batch, Dish, DishBatchPortion, InventoryItem, InventoryDay, InventoryDayItem, Task, UtilityCost, Vendor, VendorUnit, UsageUnit, VendorUnitConversion, IngredientUsageUnit
from .auth import hash_password, verify_password, create_jwt, get_current_user, require_admin, require_manager_or_admin, require_user_or_above
from .conversion_utils import get_batch_to_par_conversion, get_available_units_for_inventory_item, get_scale_options_for_batch, preview_conversion

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def create_default_data(db: Session):
    """Create default categories and units if they don't exist"""
    
    # Default categories
    default_categories = [
        ("Proteins", "ingredient"),
        ("Vegetables", "ingredient"),
        ("Dairy", "ingredient"),
        ("Grains", "ingredient"),
        ("Spices", "ingredient"),
        ("Appetizers", "recipe"),
        ("Entrees", "recipe"),
        ("Desserts", "recipe"),
        ("Sides", "recipe"),
        ("Prep Items", "batch"),
        ("Sauces", "batch"),
        ("Appetizers", "dish"),
        ("Entrees", "dish"),
        ("Desserts", "dish"),
        ("Beverages", "dish"),
        ("Proteins", "inventory"),
        ("Vegetables", "inventory"),
        ("Prep Items", "inventory"),
        ("Supplies", "inventory"),
    ]
    
    for name, cat_type in default_categories:
        existing = db.query(Category).filter(
            and_(Category.name == name, Category.type == cat_type)
        ).first()
        if not existing:
            category = Category(name=name, type=cat_type)
            db.add(category)
    
    # Default vendor units
    default_vendor_units = [
        ("lb", "Pound"),
        ("oz", "Ounce"),
        ("gal", "Gallon"),
        ("qt", "Quart"),
        ("cup", "Cup"),
        ("kg", "Kilogram"),
        ("g", "Gram"),
        ("l", "Liter"),
        ("ml", "Milliliter"),
    ]
    
    for name, description in default_vendor_units:
        existing = db.query(VendorUnit).filter(VendorUnit.name == name).first()
        if not existing:
            vendor_unit = VendorUnit(name=name, description=description)
            db.add(vendor_unit)
    
    # Default usage units
    default_usage_units = [
        ("lb", "Pound"),
        ("oz", "Ounce"),
        ("cup", "Cup"),
        ("tbsp", "Tablespoon"),
        ("tsp", "Teaspoon"),
        ("each", "Each/Individual"),
        ("portion", "Portion"),
        ("serving", "Serving"),
        ("qt", "Quart"),
        ("gal", "Gallon"),
        ("kg", "Kilogram"),
        ("g", "Gram"),
        ("l", "Liter"),
        ("ml", "Milliliter"),
    ]
    
    for name, description in default_usage_units:
        existing = db.query(UsageUnit).filter(UsageUnit.name == name).first()
        if not existing:
            usage_unit = UsageUnit(name=name, description=description)
            db.add(usage_unit)
    
    # Default utility costs
    default_utilities = [
        ("Power", 150.0),
        ("Gas", 80.0),
        ("Water", 45.0),
    ]
    
    for name, cost in default_utilities:
        existing = db.query(UtilityCost).filter(UtilityCost.name == name).first()
        if not existing:
            utility = UtilityCost(name=name, monthly_cost=cost)
            db.add(utility)
    
    db.commit()

@app.on_event("startup")
async def startup_event():
    db = next(get_db())
    create_default_data(db)

# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "status_code": exc.status_code, "detail": exc.detail}
    )

# Root redirect
@app.get("/")
async def root():
    return RedirectResponse(url="/home")

# Setup routes
@app.get("/setup", response_class=HTMLResponse)
async def setup_form(request: Request, db: Session = Depends(get_db)):
    # Check if any admin user exists
    admin_exists = db.query(User).filter(User.role == "admin").first()
    if admin_exists:
        return RedirectResponse(url="/home")
    
    return templates.TemplateResponse("setup.html", {"request": request})

@app.post("/setup")
async def setup_admin(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    full_name: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    # Check if any admin user exists
    admin_exists = db.query(User).filter(User.role == "admin").first()
    if admin_exists:
        return RedirectResponse(url="/home")
    
    # Use username as full_name if not provided
    if not full_name or full_name.strip() == "":
        full_name = username
    
    # Create admin user
    hashed_password = hash_password(password)
    admin_user = User(
        username=username,
        full_name=full_name,
        hashed_password=hashed_password,
        role="admin"
    )
    db.add(admin_user)
    db.commit()
    
    # Create JWT token and set cookie
    token = create_jwt({"sub": username})
    response = RedirectResponse(url="/home", status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax"
    )
    return response

# Authentication routes
@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            "login.html", 
            {"request": request, "error": "Invalid username or password"}
        )
    
    if not user.is_active:
        return templates.TemplateResponse(
            "login.html", 
            {"request": request, "error": "Account is inactive"}
        )
    
    token = create_jwt({"sub": username})
    response = RedirectResponse(url="/home", status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax"
    )
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token")
    return response

# Home page
@app.get("/home", response_class=HTMLResponse)
async def home(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("home.html", {
        "request": request,
        "current_user": current_user
    })

# Employee management routes
@app.get("/employees", response_class=HTMLResponse)
async def employees_page(request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    employees = db.query(User).all()
    return templates.TemplateResponse("employees.html", {
        "request": request,
        "current_user": current_user,
        "employees": employees
    })

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
    # Check if username already exists
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        employees = db.query(User).all()
        return templates.TemplateResponse("employees.html", {
            "request": request,
            "current_user": current_user,
            "employees": employees,
            "error": "Username already exists"
        })
    
    hashed_password = hash_password(password)
    employee = User(
        username=username,
        full_name=full_name,
        hashed_password=hashed_password,
        hourly_wage=hourly_wage,
        work_schedule=work_schedule,
        role=role
    )
    db.add(employee)
    db.commit()
    
    return RedirectResponse(url="/employees", status_code=302)

@app.get("/employees/{employee_id}", response_class=HTMLResponse)
async def employee_detail(
    request: Request,
    employee_id: int,
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
    request: Request,
    employee_id: int,
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
    request: Request,
    employee_id: int,
    full_name: str = Form(...),
    username: str = Form(...),
    password: Optional[str] = Form(None),
    hourly_wage: float = Form(...),
    work_schedule: str = Form(""),
    role: str = Form("user"),
    is_active: Optional[str] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Check if username is taken by another user
    existing = db.query(User).filter(
        and_(User.username == username, User.id != employee_id)
    ).first()
    if existing:
        return templates.TemplateResponse("employee_edit.html", {
            "request": request,
            "current_user": current_user,
            "employee": employee,
            "error": "Username already exists"
        })
    
    employee.full_name = full_name
    employee.username = username
    employee.hourly_wage = hourly_wage
    employee.work_schedule = work_schedule
    employee.role = role
    employee.is_active = is_active is not None
    
    if password and password.strip():
        employee.hashed_password = hash_password(password)
    
    db.commit()
    return RedirectResponse(url=f"/employees/{employee_id}", status_code=302)

# Ingredient management routes
@app.get("/ingredients", response_class=HTMLResponse)
async def ingredients_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ingredients = db.query(Ingredient).options(
        joinedload(Ingredient.category),
        joinedload(Ingredient.vendor),
        joinedload(Ingredient.vendor_unit),
        joinedload(Ingredient.usage_units).joinedload(IngredientUsageUnit.usage_unit)
    ).all()
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
    purchase_type: str = Form("single"),
    purchase_unit_name: str = Form(...),
    vendor_unit_id: int = Form(...),
    purchase_weight_volume: float = Form(...),
    purchase_total_cost: float = Form(...),
    breakable_case: Optional[str] = Form(None),
    items_per_case: Optional[int] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    # Calculate item weight for cases
    item_weight_volume = None
    if purchase_type == "case" and items_per_case:
        item_weight_volume = purchase_weight_volume / items_per_case
    
    ingredient = Ingredient(
        name=name,
        category_id=category_id if category_id else None,
        vendor_id=vendor_id if vendor_id else None,
        purchase_type=purchase_type,
        purchase_unit_name=purchase_unit_name,
        vendor_unit_id=vendor_unit_id,
        purchase_weight_volume=purchase_weight_volume,
        purchase_total_cost=purchase_total_cost,
        breakable_case=breakable_case is not None,
        items_per_case=items_per_case,
        item_weight_volume=item_weight_volume
    )
    db.add(ingredient)
    db.flush()  # Get the ID
    
    # Process usage units
    form_data = await request.form()
    for key, value in form_data.items():
        if key.startswith("conversion_") and value:
            usage_unit_id = int(key.split("_")[1])
            conversion_factor = float(value)
            
            # Calculate price per usage unit
            price_per_usage_unit = purchase_total_cost / (purchase_weight_volume * conversion_factor)
            
            ingredient_usage_unit = IngredientUsageUnit(
                ingredient_id=ingredient.id,
                usage_unit_id=usage_unit_id,
                conversion_factor=conversion_factor,
                price_per_usage_unit=price_per_usage_unit
            )
            db.add(ingredient_usage_unit)
    
    db.commit()
    return RedirectResponse(url="/ingredients", status_code=302)

@app.get("/ingredients/{ingredient_id}", response_class=HTMLResponse)
async def ingredient_detail(
    request: Request,
    ingredient_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ingredient = db.query(Ingredient).options(
        joinedload(Ingredient.category),
        joinedload(Ingredient.vendor),
        joinedload(Ingredient.vendor_unit),
        joinedload(Ingredient.usage_units).joinedload(IngredientUsageUnit.usage_unit)
    ).filter(Ingredient.id == ingredient_id).first()
    
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    return templates.TemplateResponse("ingredient_detail.html", {
        "request": request,
        "current_user": current_user,
        "ingredient": ingredient
    })

@app.get("/ingredients/{ingredient_id}/edit", response_class=HTMLResponse)
async def ingredient_edit_form(
    request: Request,
    ingredient_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    ingredient = db.query(Ingredient).options(
        joinedload(Ingredient.category),
        joinedload(Ingredient.vendor),
        joinedload(Ingredient.vendor_unit),
        joinedload(Ingredient.usage_units).joinedload(IngredientUsageUnit.usage_unit)
    ).filter(Ingredient.id == ingredient_id).first()
    
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    categories = db.query(Category).filter(Category.type == "ingredient").all()
    vendors = db.query(Vendor).all()
    vendor_units = db.query(VendorUnit).all()
    usage_units = db.query(UsageUnit).all()
    
    # Create existing conversions dict
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

# Recipe management routes
@app.get("/recipes", response_class=HTMLResponse)
async def recipes_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    recipes = db.query(Recipe).options(joinedload(Recipe.category)).all()
    categories = db.query(Category).filter(Category.type == "recipe").all()
    
    return templates.TemplateResponse("recipes.html", {
        "request": request,
        "current_user": current_user,
        "recipes": recipes,
        "categories": categories
    })

@app.post("/recipes/new")
async def create_recipe(
    request: Request,
    name: str = Form(...),
    instructions: Optional[str] = Form(None),
    category_id: Optional[int] = Form(None),
    ingredients_data: str = Form("[]"),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    recipe = Recipe(
        name=name,
        instructions=instructions,
        category_id=category_id if category_id else None
    )
    db.add(recipe)
    db.flush()  # Get the ID
    
    # Process ingredients
    ingredients = json.loads(ingredients_data)
    for ing_data in ingredients:
        # Get the price per usage unit from ingredient
        ingredient_usage_unit = db.query(IngredientUsageUnit).filter(
            and_(
                IngredientUsageUnit.ingredient_id == ing_data["ingredient_id"],
                IngredientUsageUnit.usage_unit_id == ing_data["usage_unit_id"]
            )
        ).first()
        
        if ingredient_usage_unit:
            cost = ing_data["quantity"] * ingredient_usage_unit.price_per_usage_unit
            
            recipe_ingredient = RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_id=ing_data["ingredient_id"],
                usage_unit_id=ing_data["usage_unit_id"],
                quantity=ing_data["quantity"],
                cost=cost
            )
            db.add(recipe_ingredient)
    
    db.commit()
    return RedirectResponse(url="/recipes", status_code=302)

@app.get("/recipes/{recipe_id}", response_class=HTMLResponse)
async def recipe_detail(
    request: Request,
    recipe_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    recipe = db.query(Recipe).options(joinedload(Recipe.category)).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    recipe_ingredients = db.query(RecipeIngredient).options(
        joinedload(RecipeIngredient.ingredient).joinedload(Ingredient.category),
        joinedload(RecipeIngredient.usage_unit)
    ).filter(RecipeIngredient.recipe_id == recipe_id).all()
    
    total_cost = sum(ri.cost for ri in recipe_ingredients)
    
    return templates.TemplateResponse("recipe_detail.html", {
        "request": request,
        "current_user": current_user,
        "recipe": recipe,
        "recipe_ingredients": recipe_ingredients,
        "total_cost": total_cost
    })

@app.get("/recipes/{recipe_id}/edit", response_class=HTMLResponse)
async def recipe_edit_form(
    request: Request,
    recipe_id: int,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    recipe = db.query(Recipe).options(joinedload(Recipe.category)).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    recipe_ingredients = db.query(RecipeIngredient).options(
        joinedload(RecipeIngredient.ingredient),
        joinedload(RecipeIngredient.usage_unit)
    ).filter(RecipeIngredient.recipe_id == recipe_id).all()
    
    categories = db.query(Category).filter(Category.type == "recipe").all()
    
    return templates.TemplateResponse("recipe_edit.html", {
        "request": request,
        "current_user": current_user,
        "recipe": recipe,
        "recipe_ingredients": recipe_ingredients,
        "categories": categories
    })

# Batch management routes
@app.get("/batches", response_class=HTMLResponse)
async def batches_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    batches = db.query(Batch).options(
        joinedload(Batch.recipe).joinedload(Recipe.category),
        joinedload(Batch.yield_unit)
    ).all()
    recipes = db.query(Recipe).all()
    usage_units = db.query(UsageUnit).all()
    
    return templates.TemplateResponse("batches.html", {
        "request": request,
        "current_user": current_user,
        "batches": batches,
        "recipes": recipes,
        "usage_units": usage_units
    })

@app.post("/batches/new")
async def create_batch(
    request: Request,
    recipe_id: int = Form(...),
    is_variable: Optional[str] = Form(None),
    yield_amount: Optional[float] = Form(None),
    yield_unit_id: Optional[int] = Form(None),
    estimated_labor_minutes: int = Form(...),
    hourly_labor_rate: float = Form(16.75),
    can_be_scaled: Optional[str] = Form(None),
    scale_double: Optional[str] = Form(None),
    scale_half: Optional[str] = Form(None),
    scale_quarter: Optional[str] = Form(None),
    scale_eighth: Optional[str] = Form(None),
    scale_sixteenth: Optional[str] = Form(None),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    batch = Batch(
        recipe_id=recipe_id,
        is_variable=is_variable is not None,
        yield_amount=yield_amount,
        yield_unit_id=yield_unit_id,
        estimated_labor_minutes=estimated_labor_minutes,
        hourly_labor_rate=hourly_labor_rate,
        can_be_scaled=can_be_scaled is not None,
        scale_double=scale_double is not None,
        scale_half=scale_half is not None,
        scale_quarter=scale_quarter is not None,
        scale_eighth=scale_eighth is not None,
        scale_sixteenth=scale_sixteenth is not None
    )
    db.add(batch)
    db.commit()
    
    return RedirectResponse(url="/batches", status_code=302)

@app.get("/batches/{batch_id}", response_class=HTMLResponse)
async def batch_detail(
    request: Request,
    batch_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    batch = db.query(Batch).options(
        joinedload(Batch.recipe).joinedload(Recipe.category),
        joinedload(Batch.yield_unit)
    ).filter(Batch.id == batch_id).first()
    
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    recipe_ingredients = db.query(RecipeIngredient).options(
        joinedload(RecipeIngredient.ingredient).joinedload(Ingredient.category),
        joinedload(RecipeIngredient.usage_unit)
    ).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
    
    total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
    total_batch_cost = total_recipe_cost + (batch.estimated_labor_cost or 0)
    cost_per_yield_unit = total_batch_cost / batch.yield_amount if batch.yield_amount else 0
    
    return templates.TemplateResponse("batch_detail.html", {
        "request": request,
        "current_user": current_user,
        "batch": batch,
        "recipe_ingredients": recipe_ingredients,
        "total_recipe_cost": total_recipe_cost,
        "total_batch_cost": total_batch_cost,
        "cost_per_yield_unit": cost_per_yield_unit
    })

@app.get("/batches/{batch_id}/edit", response_class=HTMLResponse)
async def batch_edit_form(
    request: Request,
    batch_id: int,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    batch = db.query(Batch).options(
        joinedload(Batch.recipe),
        joinedload(Batch.yield_unit)
    ).filter(Batch.id == batch_id).first()
    
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

# Dish management routes
@app.get("/dishes", response_class=HTMLResponse)
async def dishes_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    dishes = db.query(Dish).options(joinedload(Dish.category)).all()
    categories = db.query(Category).filter(Category.type == "dish").all()
    
    return templates.TemplateResponse("dishes.html", {
        "request": request,
        "current_user": current_user,
        "dishes": dishes,
        "categories": categories
    })

@app.post("/dishes/new")
async def create_dish(
    request: Request,
    name: str = Form(...),
    category_id: Optional[int] = Form(None),
    sale_price: float = Form(...),
    description: Optional[str] = Form(None),
    batch_portions_data: str = Form("[]"),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    dish = Dish(
        name=name,
        category_id=category_id if category_id else None,
        sale_price=sale_price,
        description=description
    )
    db.add(dish)
    db.flush()  # Get the ID
    
    # Process batch portions
    batch_portions = json.loads(batch_portions_data)
    for portion_data in batch_portions:
        dish_batch_portion = DishBatchPortion(
            dish_id=dish.id,
            batch_id=portion_data["batch_id"],
            portion_unit_id=portion_data["portion_unit_id"],
            portion_size=portion_data["portion_size"],
            expected_cost=portion_data["estimated_cost"]
        )
        db.add(dish_batch_portion)
    
    db.commit()
    return RedirectResponse(url="/dishes", status_code=302)

@app.get("/dishes/{dish_id}", response_class=HTMLResponse)
async def dish_detail(
    request: Request,
    dish_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    dish = db.query(Dish).options(joinedload(Dish.category)).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    dish_batch_portions = db.query(DishBatchPortion).options(
        joinedload(DishBatchPortion.batch).joinedload(Batch.recipe).joinedload(Recipe.category),
        joinedload(DishBatchPortion.portion_unit)
    ).filter(DishBatchPortion.dish_id == dish_id).all()
    
    expected_total_cost = sum(portion.expected_cost or 0 for portion in dish_batch_portions)
    actual_total_cost = sum(portion.actual_cost or 0 for portion in dish_batch_portions)
    
    expected_profit = dish.sale_price - expected_total_cost
    expected_profit_margin = (expected_profit / dish.sale_price * 100) if dish.sale_price > 0 else 0
    
    actual_profit = dish.sale_price - actual_total_cost
    actual_profit_margin = (actual_profit / dish.sale_price * 100) if dish.sale_price > 0 else 0
    
    # Calculate week/month/all-time averages (placeholder for now)
    actual_total_cost_week = actual_total_cost
    actual_profit_week = actual_profit
    actual_profit_margin_week = actual_profit_margin
    
    actual_total_cost_month = actual_total_cost
    actual_profit_month = actual_profit
    actual_profit_margin_month = actual_profit_margin
    
    actual_total_cost_all_time = actual_total_cost
    actual_profit_all_time = actual_profit
    actual_profit_margin_all_time = actual_profit_margin
    
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
        "actual_profit_margin": actual_profit_margin,
        "actual_total_cost_week": actual_total_cost_week,
        "actual_profit_week": actual_profit_week,
        "actual_profit_margin_week": actual_profit_margin_week,
        "actual_total_cost_month": actual_total_cost_month,
        "actual_profit_month": actual_profit_month,
        "actual_profit_margin_month": actual_profit_margin_month,
        "actual_total_cost_all_time": actual_total_cost_all_time,
        "actual_profit_all_time": actual_profit_all_time,
        "actual_profit_margin_all_time": actual_profit_margin_all_time
    })

@app.get("/dishes/{dish_id}/edit", response_class=HTMLResponse)
async def dish_edit_form(
    request: Request,
    dish_id: int,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    dish = db.query(Dish).options(joinedload(Dish.category)).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    dish_batch_portions = db.query(DishBatchPortion).options(
        joinedload(DishBatchPortion.batch).joinedload(Batch.recipe),
        joinedload(DishBatchPortion.portion_unit)
    ).filter(DishBatchPortion.dish_id == dish_id).all()
    
    categories = db.query(Category).filter(Category.type == "dish").all()
    
    return templates.TemplateResponse("dish_edit.html", {
        "request": request,
        "current_user": current_user,
        "dish": dish,
        "dish_batch_portions": dish_batch_portions,
        "categories": categories
    })

# Inventory management routes
@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inventory_items = db.query(InventoryItem).options(
        joinedload(InventoryItem.category),
        joinedload(InventoryItem.batch).joinedload(Batch.recipe),
        joinedload(InventoryItem.par_unit_equals_unit)
    ).all()
    
    inventory_days = db.query(InventoryDay).options(
        joinedload(InventoryDay.tasks)
    ).order_by(desc(InventoryDay.date)).limit(10).all()
    
    categories = db.query(Category).filter(Category.type == "inventory").all()
    batches = db.query(Batch).options(
        joinedload(Batch.recipe),
        joinedload(Batch.yield_unit)
    ).all()
    usage_units = db.query(UsageUnit).all()
    employees = db.query(User).filter(User.is_active == True).all()
    
    return templates.TemplateResponse("inventory.html", {
        "request": request,
        "current_user": current_user,
        "inventory_items": inventory_items,
        "inventory_days": inventory_days,
        "categories": categories,
        "batches": batches,
        "usage_units": usage_units,
        "employees": employees,
        "today": date.today().isoformat()
    })

@app.post("/inventory/items/new")
async def create_inventory_item(
    request: Request,
    name: str = Form(...),
    category_id: Optional[int] = Form(None),
    par_level: float = Form(...),
    par_unit_equals_amount: float = Form(1.0),
    par_unit_equals_unit_id: int = Form(...),
    batch_id: Optional[int] = Form(None),
    manual_conversion_factor: Optional[float] = Form(None),
    conversion_notes: Optional[str] = Form(None),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    inventory_item = InventoryItem(
        name=name,
        category_id=category_id if category_id else None,
        par_level=par_level,
        par_unit_equals_amount=par_unit_equals_amount,
        par_unit_equals_unit_id=par_unit_equals_unit_id,
        batch_id=batch_id if batch_id else None,
        manual_conversion_factor=manual_conversion_factor,
        conversion_notes=conversion_notes
    )
    db.add(inventory_item)
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=302)

@app.get("/inventory/items/{item_id}/edit", response_class=HTMLResponse)
async def inventory_item_edit_form(
    request: Request,
    item_id: int,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    item = db.query(InventoryItem).options(
        joinedload(InventoryItem.category),
        joinedload(InventoryItem.batch).joinedload(Batch.recipe),
        joinedload(InventoryItem.par_unit_equals_unit)
    ).filter(InventoryItem.id == item_id).first()
    
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    categories = db.query(Category).filter(Category.type == "inventory").all()
    batches = db.query(Batch).options(
        joinedload(Batch.recipe),
        joinedload(Batch.yield_unit)
    ).all()
    usage_units = db.query(UsageUnit).all()
    
    return templates.TemplateResponse("inventory_item_edit.html", {
        "request": request,
        "current_user": current_user,
        "item": item,
        "categories": categories,
        "batches": batches,
        "usage_units": usage_units
    })

@app.post("/inventory/day/new")
async def create_inventory_day(
    request: Request,
    date: date = Form(...),
    employee_ids: List[int] = Form([]),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    # Check if day already exists
    existing_day = db.query(InventoryDay).filter(InventoryDay.date == date).first()
    if existing_day:
        return RedirectResponse(url=f"/inventory/day/{existing_day.id}", status_code=302)
    
    # Create new inventory day
    inventory_day = InventoryDay(
        date=date,
        employees_working=",".join(map(str, employee_ids))
    )
    db.add(inventory_day)
    db.flush()  # Get the ID
    
    # Create inventory day items for all inventory items
    inventory_items = db.query(InventoryItem).all()
    for item in inventory_items:
        day_item = InventoryDayItem(
            day_id=inventory_day.id,
            inventory_item_id=item.id,
            quantity=0.0  # Default to 0, will be updated by user
        )
        db.add(day_item)
    
    db.commit()
    return RedirectResponse(url=f"/inventory/day/{inventory_day.id}", status_code=302)

@app.get("/inventory/day/{day_id}", response_class=HTMLResponse)
async def inventory_day_detail(
    request: Request,
    day_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    inventory_day_items = db.query(InventoryDayItem).options(
        joinedload(InventoryDayItem.inventory_item).joinedload(InventoryItem.category),
        joinedload(InventoryDayItem.inventory_item).joinedload(InventoryItem.batch).joinedload(Batch.recipe),
        joinedload(InventoryDayItem.inventory_item).joinedload(InventoryItem.par_unit_equals_unit)
    ).filter(InventoryDayItem.day_id == day_id).all()
    
    tasks = db.query(Task).options(
        joinedload(Task.assigned_to),
        joinedload(Task.batch).joinedload(Batch.recipe),
        joinedload(Task.inventory_item),
        joinedload(Task.made_unit)
    ).filter(Task.day_id == day_id).all()
    
    employees = db.query(User).filter(User.is_active == True).all()
    
    return templates.TemplateResponse("inventory_day.html", {
        "request": request,
        "current_user": current_user,
        "inventory_day": inventory_day,
        "inventory_day_items": inventory_day_items,
        "tasks": tasks,
        "employees": employees
    })

@app.post("/inventory/day/{day_id}/update")
async def update_inventory_day(
    day_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or Admin access required")
    
    # Get the inventory day
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    if inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Cannot update finalized day")
    
    # Get form data
    form_data = await request.form()
    
    # Update global notes
    inventory_day.global_notes = form_data.get("global_notes", "")
    
    # Update inventory quantities and overrides
    inventory_items = db.query(InventoryItem).all()
    
    for item in inventory_items:
        # Get quantity
        quantity_key = f"item_{item.id}"
        if quantity_key in form_data:
            quantity = float(form_data[quantity_key])
            
            # Find or create inventory day item
            day_item = db.query(InventoryDayItem).filter(
                InventoryDayItem.day_id == day_id,
                InventoryDayItem.inventory_item_id == item.id
            ).first()
            
            if not day_item:
                day_item = InventoryDayItem(
                    day_id=day_id,
                    inventory_item_id=item.id,
                    quantity=quantity
                )
                db.add(day_item)
            else:
                day_item.quantity = quantity
            
            # Update overrides
            override_create_key = f"override_create_{item.id}"
            override_no_task_key = f"override_no_task_{item.id}"
            
            day_item.override_create_task = override_create_key in form_data
            day_item.override_no_task = override_no_task_key in form_data
    
    # Generate tasks based on inventory levels
    generate_inventory_tasks(db, inventory_day)
    
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=303)

def generate_inventory_tasks(db: Session, inventory_day: InventoryDay):
    """Generate tasks for items that are below par or have overrides"""
    
    # Get all inventory day items
    day_items = db.query(InventoryDayItem).filter(
        InventoryDayItem.day_id == inventory_day.id
    ).all()
    
    # Get working employees
    working_employee_ids = []
    if inventory_day.employees_working:
        working_employee_ids = [int(id.strip()) for id in inventory_day.employees_working.split(',') if id.strip()]
    
    for day_item in day_items:
        item = day_item.inventory_item
        
        # Check if task should be created
        should_create_task = False
        
        if day_item.override_no_task:
            # Explicitly no task
            continue
        elif day_item.override_create_task:
            # Force create task
            should_create_task = True
        elif day_item.quantity <= item.par_level:
            # Below or at par level
            should_create_task = True
        
        if should_create_task and item.batch:
            # Check if task already exists for this item today
            existing_task = db.query(Task).filter(
                Task.day_id == inventory_day.id,
                Task.inventory_item_id == item.id,
                Task.auto_generated == True
            ).first()
            
            if not existing_task:
                # Create new task
                task_description = f"Make {item.name} (Below par: {day_item.quantity}/{item.par_level})"
                
                # Assign to first working employee or leave unassigned
                assigned_to_id = working_employee_ids[0] if working_employee_ids else None
                
                new_task = Task(
                    day_id=inventory_day.id,
                    assigned_to_id=assigned_to_id,
                    description=task_description,
                    auto_generated=True,
                    batch_id=item.batch_id,
                    inventory_item_id=item.id,
                    requires_manual_made=item.batch.is_variable if item.batch else False
                )
                
                db.add(new_task)

@app.post("/inventory/day/{day_id}/finalize")
async def finalize_inventory_day(
    day_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    if inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Day already finalized")
    
    inventory_day.finalized = True
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=303)

# Utility management routes
@app.get("/utilities", response_class=HTMLResponse)
async def utilities_page(request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    utilities = db.query(UtilityCost).all()
    return templates.TemplateResponse("utilities.html", {
        "request": request,
        "current_user": current_user,
        "utilities": utilities
    })

@app.post("/utilities/new")
async def create_or_update_utility(
    request: Request,
    name: str = Form(...),
    monthly_cost: float = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    # Check if utility already exists
    existing = db.query(UtilityCost).filter(UtilityCost.name == name).first()
    if existing:
        existing.monthly_cost = monthly_cost
        existing.last_updated = datetime.utcnow()
    else:
        utility = UtilityCost(name=name, monthly_cost=monthly_cost)
        db.add(utility)
    
    db.commit()
    return RedirectResponse(url="/utilities", status_code=302)

# Category management
@app.post("/categories/new")
async def create_category(
    request: Request,
    name: str = Form(...),
    type: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    category = Category(name=name, type=type)
    db.add(category)
    db.commit()
    
    # Redirect back to the appropriate page
    redirect_map = {
        "ingredient": "/ingredients",
        "recipe": "/recipes",
        "batch": "/batches",
        "dish": "/dishes",
        "inventory": "/inventory"
    }
    return RedirectResponse(url=redirect_map.get(type, "/home"), status_code=302)

# Vendor management
@app.post("/vendors/new")
async def create_vendor(
    request: Request,
    name: str = Form(...),
    contact_info: Optional[str] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    vendor = Vendor(name=name, contact_info=contact_info)
    db.add(vendor)
    db.commit()
    return RedirectResponse(url="/ingredients", status_code=302)

@app.post("/vendor_units/new")
async def create_vendor_unit(
    request: Request,
    name: str = Form(...),
    description: Optional[str] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    vendor_unit = VendorUnit(name=name, description=description)
    db.add(vendor_unit)
    db.commit()
    return RedirectResponse(url="/ingredients", status_code=302)

@app.post("/usage_units/new")
async def create_usage_unit(
    request: Request,
    name: str = Form(...),
    description: Optional[str] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    usage_unit = UsageUnit(name=name, description=description)
    db.add(usage_unit)
    db.commit()
    return RedirectResponse(url="/ingredients", status_code=302)

# API Routes
@app.get("/api/ingredients/all")
async def get_all_ingredients(db: Session = Depends(get_db)):
    ingredients = db.query(Ingredient).options(
        joinedload(Ingredient.category),
        joinedload(Ingredient.usage_units).joinedload(IngredientUsageUnit.usage_unit)
    ).all()
    
    return [
        {
            "id": ing.id,
            "name": ing.name,
            "category": ing.category.name if ing.category else None,
            "usage_units": [
                {
                    "usage_unit_id": iu.usage_unit_id,
                    "usage_unit_name": iu.usage_unit.name,
                    "conversion_factor": iu.conversion_factor,
                    "price_per_usage_unit": iu.price_per_usage_unit
                }
                for iu in ing.usage_units
            ]
        }
        for ing in ingredients
    ]

@app.get("/api/recipes/{recipe_id}/usage_units")
async def get_recipe_usage_units(recipe_id: int, db: Session = Depends(get_db)):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    # Get all usage units from recipe ingredients
    recipe_ingredients = db.query(RecipeIngredient).options(
        joinedload(RecipeIngredient.ingredient).joinedload(Ingredient.usage_units).joinedload(IngredientUsageUnit.usage_unit)
    ).filter(RecipeIngredient.recipe_id == recipe_id).all()
    
    usage_units = set()
    for ri in recipe_ingredients:
        for iu in ri.ingredient.usage_units:
            usage_units.add((iu.usage_unit.id, iu.usage_unit.name))
    
    return [
        {"id": unit_id, "name": unit_name}
        for unit_id, unit_name in sorted(usage_units, key=lambda x: x[1])
    ]

@app.get("/api/batches/all")
async def get_all_batches(db: Session = Depends(get_db)):
    batches = db.query(Batch).options(
        joinedload(Batch.recipe).joinedload(Recipe.category),
        joinedload(Batch.yield_unit)
    ).all()
    
    result = []
    for batch in batches:
        # Calculate cost per unit
        recipe_ingredients = db.query(RecipeIngredient).filter(
            RecipeIngredient.recipe_id == batch.recipe_id
        ).all()
        total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
        total_batch_cost = total_recipe_cost + (batch.estimated_labor_cost or 0)
        cost_per_unit = total_batch_cost / batch.yield_amount if batch.yield_amount else 0
        
        result.append({
            "id": batch.id,
            "recipe_name": batch.recipe.name,
            "category": batch.recipe.category.name if batch.recipe.category else None,
            "yield_amount": batch.yield_amount,
            "yield_unit": batch.yield_unit.name if batch.yield_unit else "",
            "yield_unit_id": batch.yield_unit_id,
            "cost_per_unit": cost_per_unit,
            "is_variable": batch.is_variable
        })
    
    return result

@app.get("/api/batches/search")
async def search_batches(q: str, db: Session = Depends(get_db)):
    batches = db.query(Batch).options(
        joinedload(Batch.recipe).joinedload(Recipe.category),
        joinedload(Batch.yield_unit)
    ).join(Recipe).filter(
        Recipe.name.ilike(f"%{q}%")
    ).all()
    
    result = []
    for batch in batches:
        # Calculate cost per unit
        recipe_ingredients = db.query(RecipeIngredient).filter(
            RecipeIngredient.recipe_id == batch.recipe_id
        ).all()
        total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
        total_batch_cost = total_recipe_cost + (batch.estimated_labor_cost or 0)
        cost_per_unit = total_batch_cost / batch.yield_amount if batch.yield_amount else 0
        
        result.append({
            "id": batch.id,
            "recipe_name": batch.recipe.name,
            "category": batch.recipe.category.name if batch.recipe.category else None,
            "yield_amount": batch.yield_amount,
            "yield_unit": batch.yield_unit.name if batch.yield_unit else "",
            "yield_unit_id": batch.yield_unit_id,
            "cost_per_unit": cost_per_unit,
            "is_variable": batch.is_variable
        })
    
    return result

@app.get("/api/batches/{batch_id}/available_units")
async def get_batch_available_units(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(Batch).options(
        joinedload(Batch.recipe),
        joinedload(Batch.yield_unit)
    ).filter(Batch.id == batch_id).first()
    
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Get usage units from recipe ingredients
    recipe_ingredients = db.query(RecipeIngredient).options(
        joinedload(RecipeIngredient.ingredient).joinedload(Ingredient.usage_units).joinedload(IngredientUsageUnit.usage_unit)
    ).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
    
    usage_units = set()
    for ri in recipe_ingredients:
        for iu in ri.ingredient.usage_units:
            usage_units.add((iu.usage_unit.id, iu.usage_unit.name))
    
    return [
        {"id": unit_id, "name": unit_name}
        for unit_id, unit_name in sorted(usage_units, key=lambda x: x[1])
    ]

@app.get("/api/batches/{batch_id}/cost_per_unit/{unit_id}")
async def get_batch_cost_per_unit(batch_id: int, unit_id: int, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Calculate total batch cost
    recipe_ingredients = db.query(RecipeIngredient).filter(
        RecipeIngredient.recipe_id == batch.recipe_id
    ).all()
    total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
    total_batch_cost = total_recipe_cost + (batch.estimated_labor_cost or 0)
    
    # For now, assume 1:1 conversion - this would need proper conversion logic
    cost_per_unit = total_batch_cost / batch.yield_amount if batch.yield_amount else 0
    
    return {
        "expected_cost_per_unit": cost_per_unit,
        "total_batch_cost": total_batch_cost,
        "yield_amount": batch.yield_amount
    }

@app.get("/api/batches/{batch_id}/labor_stats")
async def get_batch_labor_stats(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Get completed tasks for this batch
    completed_tasks = db.query(Task).options(
        joinedload(Task.assigned_to)
    ).filter(
        and_(Task.batch_id == batch_id, Task.status == "completed")
    ).order_by(desc(Task.finished_at)).all()
    
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
    
    # Calculate statistics
    most_recent = completed_tasks[0]
    all_costs = [task.labor_cost for task in completed_tasks]
    
    # Filter by time periods
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    week_tasks = [task for task in completed_tasks if task.finished_at >= week_ago]
    month_tasks = [task for task in completed_tasks if task.finished_at >= month_ago]
    
    week_costs = [task.labor_cost for task in week_tasks]
    month_costs = [task.labor_cost for task in month_tasks]
    
    return {
        "task_count": len(completed_tasks),
        "most_recent_cost": most_recent.labor_cost,
        "most_recent_date": most_recent.finished_at.strftime('%Y-%m-%d'),
        "average_week": sum(week_costs) / len(week_costs) if week_costs else 0,
        "average_month": sum(month_costs) / len(month_costs) if month_costs else 0,
        "average_all_time": sum(all_costs) / len(all_costs),
        "week_task_count": len(week_tasks),
        "month_task_count": len(month_tasks)
    }

@app.get("/api/inventory/batch/{batch_id}/available_units")
async def get_inventory_batch_available_units(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Create a temporary inventory item to use the conversion utility
    temp_item = InventoryItem(batch_id=batch_id)
    units = get_available_units_for_inventory_item(db, temp_item)
    
    return units

@app.get("/api/inventory/conversion_preview")
async def get_inventory_conversion_preview(
    batch_id: int,
    unit_id: int,
    manual_factor: Optional[float] = None,
    db: Session = Depends(get_db)
):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Create a temporary inventory item
    temp_item = InventoryItem(
        batch_id=batch_id,
        par_unit_equals_unit_id=unit_id,
        manual_conversion_factor=manual_factor
    )
    
    preview = preview_conversion(db, batch, temp_item, 1.0)
    return preview

@app.get("/api/usage_units/all")
async def get_all_usage_units(db: Session = Depends(get_db)):
    units = db.query(UsageUnit).order_by(UsageUnit.name).all()
    return [{"id": unit.id, "name": unit.name} for unit in units]

@app.get("/api/vendor_units/{vendor_unit_id}/conversions")
async def get_vendor_unit_conversions(vendor_unit_id: int, db: Session = Depends(get_db)):
    conversions = db.query(VendorUnitConversion).options(
        joinedload(VendorUnitConversion.usage_unit)
    ).filter(VendorUnitConversion.vendor_unit_id == vendor_unit_id).all()
    
    return {
        str(conv.usage_unit_id): conv.conversion_factor
        for conv in conversions
    }

@app.get("/api/tasks/{task_id}/finish_requirements")
async def get_task_finish_requirements(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).options(
        joinedload(Task.batch).joinedload(Batch.recipe),
        joinedload(Task.batch).joinedload(Batch.yield_unit),
        joinedload(Task.inventory_item).joinedload(InventoryItem.par_unit_equals_unit)
    ).filter(Task.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    requirements = {
        "requires_manual_made": False,
        "scale_options": [],
        "expected_yield": None,
        "batch_unit_name": None,
        "made_unit_id": None,
        "made_unit_name": None,
        "conversion_preview": None
    }
    
    if task.batch:
        if task.batch.is_variable:
            # Variable yield batch - requires manual input
            requirements["requires_manual_made"] = True
            requirements["made_unit_id"] = task.batch.yield_unit_id
            requirements["made_unit_name"] = task.batch.yield_unit.name if task.batch.yield_unit else "units"
        elif task.batch.can_be_scaled:
            # Scalable batch - show scale options
            requirements["scale_options"] = get_scale_options_for_batch(task.batch)
            requirements["batch_unit_name"] = task.batch.yield_unit.name if task.batch.yield_unit else "units"
        else:
            # Fixed batch - automatic calculation
            requirements["expected_yield"] = task.batch.yield_amount
            requirements["batch_unit_name"] = task.batch.yield_unit.name if task.batch.yield_unit else "units"
            
            # Show conversion preview if inventory item is linked
            if task.inventory_item:
                preview = preview_conversion(db, task.batch, task.inventory_item, task.batch.yield_amount)
                if preview["available"]:
                    requirements["conversion_preview"] = preview["preview_text"]
    
    return requirements

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)