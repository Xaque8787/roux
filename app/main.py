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

@app.get("/ingredients/{ingredient_id}/edit", response_class=HTMLResponse)
async def ingredient_edit(ingredient_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    categories = db.query(Category).filter(Category.type == "ingredient").all()
    vendors = db.query(Vendor).all()
    vendor_units = db.query(VendorUnit).all()
    
    return templates.TemplateResponse("ingredient_edit.html", {
        "request": request,
        "current_user": current_user,
        "ingredient": ingredient,
        "categories": categories,
        "vendors": vendors,
        "vendor_units": vendor_units,
        "existing_conversions": {}  # Simplified for now
    })

@app.post("/ingredients/{ingredient_id}/edit")
async def update_ingredient(
    ingredient_id: int,
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
    
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    # Update ingredient fields
    ingredient.name = name
    ingredient.usage_type = usage_type
    ingredient.category_id = category_id if category_id else None
    ingredient.vendor_id = vendor_id if vendor_id else None
    ingredient.purchase_type = purchase_type
    ingredient.purchase_unit_name = purchase_unit_name
    ingredient.net_weight_volume_item = net_weight_volume_item
    ingredient.net_unit = net_unit
    ingredient.purchase_total_cost = purchase_total_cost
    ingredient.breakable_case = breakable_case
    ingredient.items_per_case = items_per_case
    ingredient.net_weight_volume_case = net_weight_volume_case
    ingredient.has_baking_conversion = has_baking_conversion
    ingredient.baking_measurement_unit = baking_measurement_unit if has_baking_conversion else None
    ingredient.baking_weight_amount = baking_weight_amount if has_baking_conversion else None
    ingredient.baking_weight_unit = baking_weight_unit if has_baking_conversion else None
    
    db.commit()
    return RedirectResponse(url=f"/ingredients/{ingredient_id}", status_code=302)

@app.get("/ingredients/{ingredient_id}/delete")
async def delete_ingredient(ingredient_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    db.delete(ingredient)
    db.commit()
    return RedirectResponse(url="/ingredients", status_code=302)

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

@app.get("/recipes/{recipe_id}/edit", response_class=HTMLResponse)
async def recipe_edit(recipe