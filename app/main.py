from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import os

from .database import SessionLocal, engine, Base
from .models import (
    User, Category, VendorUnit, ParUnitName, Vendor, Ingredient, Recipe, 
    RecipeIngredient, Batch, Dish, DishBatchPortion, InventoryItem, 
    InventoryDay, InventoryDayItem, Task, UtilityCost
)
from .auth import hash_password, verify_password, create_jwt, get_current_user

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def has_admin_user(db: Session):
    """Check if there's at least one admin user in the database"""
    admin_user = db.query(User).filter(User.role == "admin").first()
    return admin_user is not None

@app.get("/")
async def root(request: Request, db: Session = Depends(get_db)):
    if not has_admin_user(db):
        return RedirectResponse(url="/setup", status_code=302)
    return RedirectResponse(url="/home", status_code=302)

@app.get("/setup", response_class=HTMLResponse)
async def setup_form(request: Request, db: Session = Depends(get_db)):
    if has_admin_user(db):
        return RedirectResponse(url="/home", status_code=302)
    return templates.TemplateResponse("setup.html", {"request": request})

@app.post("/setup")
async def setup_admin(
    request: Request,
    username: str = Form(...),
    full_name: str = Form(None),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    print(f"Setup attempt - Username: {username}, Full name: {full_name}")
    
    if has_admin_user(db):
        return RedirectResponse(url="/home", status_code=302)
    
    # Validate input
    if not username or not password:
        return templates.TemplateResponse("setup.html", {
            "request": request,
            "error": "Username and password are required"
        })
    
    if len(password) < 4:
        return templates.TemplateResponse("setup.html", {
            "request": request,
            "error": "Password must be at least 4 characters long"
        })
    
    try:
        # Create admin user
        hashed_password = hash_password(password)
        admin_user = User(
            username=username,
            full_name=full_name or username,
            hashed_password=hashed_password,
            role="admin",
            is_admin=True,
            is_active=True,
            hourly_wage=20.0
        )
        db.add(admin_user)
        
        # Create default categories
        default_categories = [
            ("Proteins", "ingredient"),
            ("Vegetables", "ingredient"),
            ("Dairy", "ingredient"),
            ("Grains", "ingredient"),
            ("Spices", "ingredient"),
            ("Appetizers", "dish"),
            ("Entrees", "dish"),
            ("Desserts", "dish"),
            ("Beverages", "dish"),
            ("Prep Items", "recipe"),
            ("Sauces", "recipe"),
            ("Sides", "recipe"),
            ("General", "inventory")
        ]
        
        for name, cat_type in default_categories:
            existing_category = db.query(Category).filter(
                Category.name == name, 
                Category.type == cat_type
            ).first()
            if not existing_category:
                category = Category(name=name, type=cat_type)
                db.add(category)
        
        # Create default vendor units
        default_vendor_units = [
            ("lb", "Pound"),
            ("oz", "Ounce"),
            ("gal", "Gallon"),
            ("qt", "Quart"),
            ("pt", "Pint"),
            ("cup", "Cup"),
            ("fl_oz", "Fluid Ounce"),
            ("l", "Liter"),
            ("ml", "Milliliter"),
            ("g", "Gram"),
            ("kg", "Kilogram"),
            ("each", "Each"),
            ("dozen", "Dozen"),
            ("case", "Case")
        ]
        
        for name, description in default_vendor_units:
            existing_unit = db.query(VendorUnit).filter(VendorUnit.name == name).first()
            if not existing_unit:
                vendor_unit = VendorUnit(name=name, description=description)
                db.add(vendor_unit)
        
        # Create default par unit names
        default_par_units = [
            "Tub",
            "Case",
            "Container",
            "Bag",
            "Box",
            "Bottle",
            "Can",
            "Package"
        ]
        
        for name in default_par_units:
            existing_par = db.query(ParUnitName).filter(ParUnitName.name == name).first()
            if not existing_par:
                par_unit = ParUnitName(name=name)
                db.add(par_unit)
        
        db.commit()
        print("Setup completed successfully, redirecting to login")
        return RedirectResponse(url="/login", status_code=302)
        
    except Exception as e:
        print(f"Setup error: {str(e)}")
        db.rollback()
        return templates.TemplateResponse("setup.html", {
            "request": request,
            "error": f"Setup failed: {str(e)}"
        })

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
    print(f"Login attempt - Username: {username}")
    
    # Validate input
    if not username or not password:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Username and password are required"
        })
    
    # Find user
    user = db.query(User).filter(User.username == username).first()
    print(f"User found: {user is not None}")
    
    if not user:
        print("User not found in database")
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid username or password"
        })
    
    print(f"User active: {user.is_active}")
    if not user.is_active:
        print("User account is inactive")
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Account is inactive"
        })
    
    # Verify password
    print("Verifying password...")
    if not verify_password(password, user.hashed_password):
        print("Password verification failed")
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid username or password"
        })
    
    print("Login successful, creating JWT...")
    
    # Create JWT token
    access_token_expires = timedelta(minutes=30)
    access_token = create_jwt(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    print("JWT cookie set, redirecting to /home")
    
    # Create response and set cookie
    response = RedirectResponse(url="/home", status_code=302)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax"
    )
    
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(key="access_token")
    return response

@app.get("/home", response_class=HTMLResponse)
async def home(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("home.html", {
        "request": request,
        "current_user": current_user
    })

# Employee Management Routes
@app.get("/employees", response_class=HTMLResponse)
async def employees_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Check if username already exists
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    hashed_password = hash_password(password)
    employee = User(
        username=username,
        full_name=full_name,
        hashed_password=hashed_password,
        hourly_wage=hourly_wage,
        work_schedule=work_schedule,
        role=role,
        is_admin=(role == "admin"),
        is_active=True
    )
    
    db.add(employee)
    db.commit()
    
    return RedirectResponse(url="/employees", status_code=302)

# Ingredients Management Routes
@app.get("/ingredients", response_class=HTMLResponse)
async def ingredients_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ingredients = db.query(Ingredient).all()
    categories = db.query(Category).filter(Category.type == "ingredient").all()
    vendors = db.query(Vendor).all()
    vendor_units = db.query(VendorUnit).all()
    
    return templates.TemplateResponse("ingredients.html", {
        "request": request,
        "current_user": current_user,
        "ingredients": ingredients,
        "categories": categories,
        "vendors": vendors,
        "vendor_units": vendor_units
    })

@app.post("/ingredients/new")
async def create_ingredient(
    request: Request,
    name: str = Form(...),
    usage_type: str = Form(...),
    category_id: int = Form(None),
    vendor_id: int = Form(None),
    purchase_type: str = Form(...),
    purchase_unit_name: str = Form(...),
    net_weight_volume_item: float = Form(...),
    net_unit: str = Form(...),
    purchase_total_cost: float = Form(...),
    breakable_case: bool = Form(False),
    items_per_case: int = Form(None),
    net_weight_volume_case: float = Form(None),
    has_baking_conversion: bool = Form(False),
    baking_measurement_unit: str = Form(None),
    baking_weight_amount: float = Form(None),
    baking_weight_unit: str = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    ingredient = Ingredient(
        name=name,
        usage_type=usage_type,
        category_id=category_id if category_id else None,
        vendor_id=vendor_id if vendor_id else None,
        purchase_type=purchase_type,
        purchase_unit_name=purchase_unit_name,
        net_weight_volume_item=net_weight_volume_item,
        net_unit=net_unit,
        purchase_total_cost=purchase_total_cost,
        breakable_case=breakable_case,
        items_per_case=items_per_case,
        net_weight_volume_case=net_weight_volume_case,
        has_baking_conversion=has_baking_conversion,
        baking_measurement_unit=baking_measurement_unit if has_baking_conversion else None,
        baking_weight_amount=baking_weight_amount if has_baking_conversion else None,
        baking_weight_unit=baking_weight_unit if has_baking_conversion else None
    )
    
    db.add(ingredient)
    db.commit()
    
    return RedirectResponse(url="/ingredients", status_code=302)

@app.get("/ingredients/{ingredient_id}", response_class=HTMLResponse)
async def ingredient_detail(ingredient_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    return templates.TemplateResponse("ingredient_detail.html", {
        "request": request,
        "current_user": current_user,
        "ingredient": ingredient
    })

# Recipes Management Routes
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

# Batches Management Routes
@app.get("/batches", response_class=HTMLResponse)
async def batches_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    batches = db.query(Batch).all()
    recipes = db.query(Recipe).all()
    
    return templates.TemplateResponse("batches.html", {
        "request": request,
        "current_user": current_user,
        "batches": batches,
        "recipes": recipes
    })

@app.get("/batches/{batch_id}", response_class=HTMLResponse)
async def batch_detail(batch_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
    total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
    total_batch_cost = total_recipe_cost + batch.estimated_labor_cost
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

# Dishes Management Routes
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
    expected_total_cost = sum(portion.expected_cost for portion in dish_batch_portions)
    actual_total_cost = sum(portion.actual_cost for portion in dish_batch_portions)
    
    expected_profit = dish.sale_price - expected_total_cost
    actual_profit = dish.sale_price - actual_total_cost
    expected_profit_margin = (expected_profit / dish.sale_price * 100) if dish.sale_price > 0 else 0
    actual_profit_margin = (actual_profit / dish.sale_price * 100) if dish.sale_price > 0 else 0
    
    return templates.TemplateResponse("dish_detail.html", {
        "request": request,
        "current_user": current_user,
        "dish": dish,
        "dish_batch_portions": dish_batch_portions,
        "expected_total_cost": expected_total_cost,
        "actual_total_cost": actual_total_cost,
        "expected_profit": expected_profit,
        "actual_profit": actual_profit,
        "expected_profit_margin": expected_profit_margin,
        "actual_profit_margin": actual_profit_margin,
        "actual_total_cost_week": actual_total_cost,  # Simplified for now
        "actual_profit_week": actual_profit,
        "actual_profit_margin_week": actual_profit_margin,
        "actual_total_cost_month": actual_total_cost,
        "actual_profit_month": actual_profit,
        "actual_profit_margin_month": actual_profit_margin,
        "actual_total_cost_all_time": actual_total_cost,
        "actual_profit_all_time": actual_profit,
        "actual_profit_margin_all_time": actual_profit_margin
    })

# Inventory Management Routes
@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inventory_items = db.query(InventoryItem).all()
    categories = db.query(Category).filter(Category.type == "inventory").all()
    par_unit_names = db.query(ParUnitName).all()
    batches = db.query(Batch).all()
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Get current day if exists
    today = datetime.now().date()
    current_day = db.query(InventoryDay).filter(
        InventoryDay.date == today,
        InventoryDay.finalized == False
    ).first()
    
    # Get recent finalized days
    thirty_days_ago = datetime.now().date() - timedelta(days=30)
    finalized_days = db.query(InventoryDay).filter(
        InventoryDay.finalized == True,
        InventoryDay.date >= thirty_days_ago
    ).order_by(InventoryDay.date.desc()).limit(10).all()
    
    return templates.TemplateResponse("inventory.html", {
        "request": request,
        "current_user": current_user,
        "inventory_items": inventory_items,
        "categories": categories,
        "par_unit_names": par_unit_names,
        "batches": batches,
        "employees": employees,
        "current_day": current_day,
        "finalized_days": finalized_days,
        "today_date": today.isoformat()
    })

# Utilities Management Routes (Admin only)
@app.get("/utilities", response_class=HTMLResponse)
async def utilities_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    utilities = db.query(UtilityCost).all()
    
    return templates.TemplateResponse("utilities.html", {
        "request": request,
        "current_user": current_user,
        "utilities": utilities
    })

@app.post("/utilities/new")
async def create_utility(
    request: Request,
    name: str = Form(...),
    monthly_cost: float = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Check if utility already exists, update if it does
    existing_utility = db.query(UtilityCost).filter(UtilityCost.name == name).first()
    if existing_utility:
        existing_utility.monthly_cost = monthly_cost
        existing_utility.last_updated = datetime.utcnow()
    else:
        utility = UtilityCost(
            name=name,
            monthly_cost=monthly_cost
        )
        db.add(utility)
    
    db.commit()
    return RedirectResponse(url="/utilities", status_code=302)

# Category creation route
@app.post("/categories/new")
async def create_category(
    request: Request,
    name: str = Form(...),
    type: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or Admin access required")
    
    # Check if category already exists
    existing_category = db.query(Category).filter(
        Category.name == name,
        Category.type == type
    ).first()
    
    if not existing_category:
        category = Category(name=name, type=type)
        db.add(category)
        db.commit()
    
    # Redirect back to the appropriate page
    redirect_map = {
        "ingredient": "/ingredients",
        "recipe": "/recipes",
        "dish": "/dishes",
        "inventory": "/inventory"
    }
    
    return RedirectResponse(url=redirect_map.get(type, "/home"), status_code=302)

# Vendor creation route
@app.post("/vendors/new")
async def create_vendor(
    request: Request,
    name: str = Form(...),
    contact_info: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    vendor = Vendor(name=name, contact_info=contact_info)
    db.add(vendor)
    db.commit()
    
    return RedirectResponse(url="/ingredients", status_code=302)

# Par Unit Name creation route
@app.post("/par_unit_names/new")
async def create_par_unit_name(
    request: Request,
    name: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or Admin access required")
    
    par_unit = ParUnitName(name=name)
    db.add(par_unit)
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=302)

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("error.html", {
        "request": request,
        "status_code": exc.status_code,
        "detail": exc.detail
    })