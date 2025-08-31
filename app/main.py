from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_
from datetime import datetime, date, timedelta
import json
from typing import List, Optional

from .database import engine, get_db
from .models import Base, User, Category, Ingredient, Recipe, RecipeIngredient, Batch, Dish, DishBatchPortion, InventoryItem, InventoryDay, InventoryDayItem, Task, UtilityCost, Vendor, UsageUnit, IngredientUsageUnit, VendorUnit, VendorUnitConversion
from .auth import hash_password, verify_password, create_jwt, get_current_user, require_admin, require_manager_or_admin, require_user_or_above

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Helper function to check if setup is needed
def needs_setup(db: Session):
    return db.query(User).count() == 0

# Helper function to create default categories
def create_default_categories(db: Session):
    """Create default categories if they don't exist"""
    default_categories = [
        ("Proteins", "ingredient"),
        ("Vegetables", "ingredient"),
        ("Dairy", "ingredient"),
        ("Grains", "ingredient"),
        ("Spices", "ingredient"),
        ("Oils", "ingredient"),
        ("Appetizers", "dish"),
        ("Entrees", "dish"),
        ("Desserts", "dish"),
        ("Beverages", "dish"),
        ("Prep Items", "recipe"),
        ("Sauces", "recipe"),
        ("Sides", "recipe"),
        ("Dry Storage", "inventory"),
        ("Cold Storage", "inventory"),
        ("Freezer", "inventory"),
        ("Cleaning", "inventory")
    ]
    
    for name, cat_type in default_categories:
        existing = db.query(Category).filter(Category.name == name, Category.type == cat_type).first()
        if not existing:
            category = Category(name=name, type=cat_type)
            db.add(category)
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error creating categories: {e}")

def create_default_units(db: Session):
    """Create default vendor and usage units if they don't exist"""
    default_vendor_units = [
        ("lb", "Pound"),
        ("oz", "Ounce"),
        ("gal", "Gallon"),
        ("qt", "Quart"),
        ("pt", "Pint"),
        ("fl oz", "Fluid Ounce"),
        ("kg", "Kilogram"),
        ("g", "Gram"),
        ("L", "Liter"),
        ("mL", "Milliliter")
    ]
    
    for name, description in default_vendor_units:
        existing = db.query(VendorUnit).filter(VendorUnit.name == name).first()
        if not existing:
            unit = VendorUnit(name=name, description=description)
            db.add(unit)
    
    default_usage_units = [
        "lb", "oz", "kg", "g",
        "gal", "qt", "pt", "cup", "fl oz", "tbsp", "tsp", "mL", "L",
        "each", "piece", "slice", "clove", "head", "bunch", "can", "jar", "bottle", "bag", "box"
    ]
    
    for name in default_usage_units:
        existing = db.query(UsageUnit).filter(UsageUnit.name == name).first()
        if not existing:
            unit = UsageUnit(name=name)
            db.add(unit)
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error creating units: {e}")
    
    # Create default conversions
    conversions = [
        # Weight conversions
        ("lb", "lb", 1.0),
        ("lb", "oz", 16.0),
        ("oz", "oz", 1.0),
        ("oz", "lb", 1/16.0),
        ("kg", "kg", 1.0),
        ("kg", "g", 1000.0),
        ("g", "g", 1.0),
        ("g", "kg", 1/1000.0),
        
        # Volume conversions
        ("gal", "gal", 1.0),
        ("gal", "qt", 4.0),
        ("gal", "pt", 8.0),
        ("gal", "cup", 16.0),
        ("gal", "tbsp", 256.0),
        ("gal", "tsp", 768.0),
        ("qt", "qt", 1.0),
        ("qt", "pt", 2.0),
        ("qt", "cup", 4.0),
        ("qt", "tbsp", 64.0),
        ("qt", "tsp", 192.0),
        ("pt", "pt", 1.0),
        ("pt", "cup", 2.0),
        ("pt", "tbsp", 32.0),
        ("pt", "tsp", 96.0),
        ("L", "L", 1.0),
        ("L", "mL", 1000.0),
        ("mL", "mL", 1.0),
        ("mL", "L", 1/1000.0),
    ]
    
    for vendor_unit_name, usage_unit_name, factor in conversions:
        vendor_unit = db.query(VendorUnit).filter(VendorUnit.name == vendor_unit_name).first()
        usage_unit = db.query(UsageUnit).filter(UsageUnit.name == usage_unit_name).first()
        
        if vendor_unit and usage_unit:
            existing = db.query(VendorUnitConversion).filter(
                and_(
                    VendorUnitConversion.vendor_unit_id == vendor_unit.id,
                    VendorUnitConversion.usage_unit_id == usage_unit.id
                )
            ).first()
            
            if not existing:
                conversion = VendorUnitConversion(
                    vendor_unit_id=vendor_unit.id,
                    usage_unit_id=usage_unit.id,
                    conversion_factor=factor
                )
                db.add(conversion)
    
    db.commit()

# Routes
@app.get("/", response_class=HTMLResponse)
async def root(request: Request, db: Session = Depends(get_db)):
    if needs_setup(db):
        return RedirectResponse(url="/setup", status_code=302)
    
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    
    return RedirectResponse(url="/home", status_code=302)

@app.get("/setup", response_class=HTMLResponse)
async def setup_get(request: Request, db: Session = Depends(get_db)):
    if not needs_setup(db):
        return RedirectResponse(url="/", status_code=302)
    
    return templates.TemplateResponse("setup.html", {"request": request})

@app.post("/setup")
async def setup_post(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    if not needs_setup(db):
        return RedirectResponse(url="/", status_code=302)
    
    hashed_password = hash_password(password)
    admin_user = User(
        username=username,
        hashed_password=hashed_password,
        full_name="Administrator",
        role="admin",
        is_admin=True,
        is_user=True
    )
    db.add(admin_user)
    db.commit()
    
    # Create default categories and units
    create_default_categories(db)
    create_default_units(db)
    
    return RedirectResponse(url="/login", status_code=302)

@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request, db: Session = Depends(get_db)):
    if needs_setup(db):
        return RedirectResponse(url="/setup", status_code=302)
    
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login_post(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    
    if not user or not verify_password(password, user.hashed_password) or not user.is_active:
        return templates.TemplateResponse("login.html", {
            "request": request, 
            "error": "Invalid username or password"
        })
    
    access_token = create_jwt(data={"sub": user.username})
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

# Employee Management (Admin only)
@app.get("/employees", response_class=HTMLResponse)
async def employees_list(request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
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
    role: str = Form(...),
    work_schedule: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
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
    
    hashed_password = hash_password(password)
    new_user = User(
        username=username,
        hashed_password=hashed_password,
        full_name=full_name,
        hourly_wage=hourly_wage,
        role=role,
        work_schedule=work_schedule,
        is_admin=(role == "admin"),
        is_user=True
    )
    db.add(new_user)
    db.commit()
    
    return RedirectResponse(url="/employees", status_code=302)

@app.get("/employees/{employee_id}", response_class=HTMLResponse)
async def employee_detail(request: Request, employee_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    return templates.TemplateResponse("employee_detail.html", {
        "request": request,
        "current_user": current_user,
        "employee": employee
    })

@app.get("/employees/{employee_id}/edit", response_class=HTMLResponse)
async def employee_edit_get(request: Request, employee_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    return templates.TemplateResponse("employee_edit.html", {
        "request": request,
        "current_user": current_user,
        "employee": employee
    })

@app.post("/employees/{employee_id}/edit")
async def employee_edit_post(
    request: Request,
    employee_id: int,
    full_name: str = Form(...),
    username: str = Form(...),
    password: str = Form(""),
    hourly_wage: float = Form(...),
    role: str = Form(...),
    work_schedule: str = Form(""),
    is_active: bool = Form(False),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Check if username is taken by another user
    existing_user = db.query(User).filter(and_(User.username == username, User.id != employee_id)).first()
    if existing_user:
        return templates.TemplateResponse("employee_edit.html", {
            "request": request,
            "current_user": current_user,
            "employee": employee,
            "error": "Username already exists"
        })
    
    employee.full_name = full_name
    employee.username = username
    employee.hourly_wage = hourly_wage
    employee.role = role
    employee.work_schedule = work_schedule
    employee.is_active = is_active
    employee.is_admin = (role == "admin")
    
    if password:
        employee.hashed_password = hash_password(password)
    
    db.commit()
    
    return RedirectResponse(url=f"/employees/{employee_id}", status_code=302)

@app.get("/employees/{employee_id}/delete")
async def employee_delete(employee_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Don't allow deleting yourself
    if employee.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    # Deactivate instead of delete to preserve task history
    employee.is_active = False
    db.commit()
    
    return RedirectResponse(url="/employees", status_code=302)

# Categories
@app.post("/categories/new")
async def create_category(
    name: str = Form(...),
    type: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    category = Category(name=name, type=type)
    db.add(category)
    db.commit()
    
    # Redirect based on type
    if type == "ingredient":
        return RedirectResponse(url="/ingredients", status_code=302)
    elif type == "recipe":
        return RedirectResponse(url="/recipes", status_code=302)
    elif type == "dish":
        return RedirectResponse(url="/dishes", status_code=302)
    elif type == "inventory":
        return RedirectResponse(url="/inventory", status_code=302)
    else:
        return RedirectResponse(url="/home", status_code=302)

# Vendors
@app.post("/vendors/new")
async def create_vendor(
    name: str = Form(...),
    contact_info: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    vendor = Vendor(name=name, contact_info=contact_info)
    db.add(vendor)
    db.commit()
    return RedirectResponse(url="/ingredients", status_code=302)

# Vendor Units
@app.post("/vendor_units/new")
async def create_vendor_unit(
    name: str = Form(...),
    description: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    vendor_unit = VendorUnit(name=name, description=description)
    db.add(vendor_unit)
    db.commit()
    return RedirectResponse(url="/ingredients", status_code=302)

@app.get("/api/vendor_units/{vendor_unit_id}/conversions")
async def get_vendor_unit_conversions(vendor_unit_id: int, db: Session = Depends(get_db)):
    conversions = db.query(VendorUnitConversion).filter(
        VendorUnitConversion.vendor_unit_id == vendor_unit_id
    ).all()
    
    result = {}
    for conv in conversions:
        result[conv.usage_unit_id] = conv.conversion_factor
    
    return result

# Usage Units
@app.post("/usage_units/new")
async def create_usage_unit(
    name: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    usage_unit = UsageUnit(name=name)
    db.add(usage_unit)
    db.commit()
    return RedirectResponse(url="/ingredients", status_code=302)

# Ingredients
@app.get("/ingredients", response_class=HTMLResponse)
async def ingredients_list(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ingredients = db.query(Ingredient).options(
        joinedload(Ingredient.category),
        joinedload(Ingredient.vendor),
        joinedload(Ingredient.vendor_unit)
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
    vendor_unit_id: Optional[int] = Form(None),
    purchase_type: str = Form(...),
    purchase_unit_name: str = Form(...),
    purchase_weight_volume: float = Form(...),
    purchase_total_cost: float = Form(...),
    breakable_case: bool = Form(False),
    items_per_case: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
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
    
    # Process usage units
    form_data = await request.form()
    usage_units = db.query(UsageUnit).all()
    
    for unit in usage_units:
        conversion_key = f"conversion_{unit.id}"
        if conversion_key in form_data and form_data[conversion_key]:
            conversion_factor = float(form_data[conversion_key])
            ingredient_usage = IngredientUsageUnit(
                ingredient_id=ingredient.id,
                usage_unit_id=unit.id,
                conversion_factor=conversion_factor
            )
            db.add(ingredient_usage)
    
    db.commit()
    return RedirectResponse(url="/ingredients", status_code=302)

@app.get("/ingredients/{ingredient_id}", response_class=HTMLResponse)
async def ingredient_detail(request: Request, ingredient_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
        "ingredient": ingredient,
        "usage_units": ingredient.usage_units
    })

@app.get("/ingredients/{ingredient_id}/edit", response_class=HTMLResponse)
async def ingredient_edit_get(request: Request, ingredient_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    ingredient = db.query(Ingredient).options(
        joinedload(Ingredient.category),
        joinedload(Ingredient.vendor),
        joinedload(Ingredient.vendor_unit),
        joinedload(Ingredient.usage_units)
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

@app.post("/ingredients/{ingredient_id}/edit")
async def ingredient_edit_post(
    request: Request,
    ingredient_id: int,
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
    
    # Update usage units - remove existing and add new ones
    db.query(IngredientUsageUnit).filter(IngredientUsageUnit.ingredient_id == ingredient_id).delete()
    
    # Process usage units
    form_data = await request.form()
    usage_units = db.query(UsageUnit).all()
    
    for unit in usage_units:
        conversion_key = f"conversion_{unit.id}"
        if conversion_key in form_data and form_data[conversion_key]:
            conversion_factor = float(form_data[conversion_key])
            ingredient_usage = IngredientUsageUnit(
                ingredient_id=ingredient.id,
                usage_unit_id=unit.id,
                conversion_factor=conversion_factor
            )
            db.add(ingredient_usage)
    
    db.commit()
    return RedirectResponse(url=f"/ingredients/{ingredient_id}", status_code=302)

@app.get("/ingredients/{ingredient_id}/delete")
async def ingredient_delete(ingredient_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    # Delete related usage units first
    db.query(IngredientUsageUnit).filter(IngredientUsageUnit.ingredient_id == ingredient_id).delete()
    
    # Delete ingredient
    db.delete(ingredient)
    db.commit()
    
    return RedirectResponse(url="/ingredients", status_code=302)

# API endpoint for ingredients
@app.get("/api/ingredients/all")
async def get_all_ingredients(db: Session = Depends(get_db)):
    try:
        ingredients = db.query(Ingredient).options(
            joinedload(Ingredient.category),
            joinedload(Ingredient.usage_units).joinedload(IngredientUsageUnit.usage_unit)
        ).all()
        
        result = []
        for ing in ingredients:
            usage_units = []
            for iu in ing.usage_units:
                usage_units.append({
                    "usage_unit_id": iu.usage_unit_id,
                    "usage_unit_name": iu.usage_unit.name,
                    "price_per_usage_unit": iu.price_per_usage_unit
                })
            
            result.append({
                "id": ing.id,
                "name": ing.name,
                "category": ing.category.name if ing.category else None,
                "usage_units": usage_units
            })
        
        return result
    except Exception as e:
        print(f"Error in get_all_ingredients: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/ingredients/search")
async def search_ingredients(q: str = "", db: Session = Depends(get_db)):
    try:
        query = db.query(Ingredient).options(
            joinedload(Ingredient.category),
            joinedload(Ingredient.usage_units).joinedload(IngredientUsageUnit.usage_unit)
        )
        
        if q:
            query = query.filter(
                or_(
                    Ingredient.name.ilike(f"%{q}%"),
                    Ingredient.category.has(Category.name.ilike(f"%{q}%"))
                )
            )
        
        ingredients = query.all()
        
        result = []
        for ing in ingredients:
            usage_units = []
            for iu in ing.usage_units:
                usage_units.append({
                    "usage_unit_id": iu.usage_unit_id,
                    "usage_unit_name": iu.usage_unit.name,
                    "price_per_usage_unit": iu.price_per_usage_unit
                })
            
            result.append({
                "id": ing.id,
                "name": ing.name,
                "category": ing.category.name if ing.category else None,
                "usage_units": usage_units
            })
        
        return result
    except Exception as e:
        print(f"Error in search_ingredients: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# Recipes
@app.get("/recipes", response_class=HTMLResponse)
async def recipes_list(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
    instructions: str = Form(""),
    category_id: Optional[int] = Form(None),
    ingredients_data: str = Form("[]"),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    # Create recipe
    recipe = Recipe(
        name=name,
        instructions=instructions,
        category_id=category_id if category_id else None
    )
    db.add(recipe)
    db.flush()  # Get the ID
    
    # Process ingredients
    try:
        ingredients = json.loads(ingredients_data)
        for ingredient_data in ingredients:
            recipe_ingredient = RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_id=ingredient_data['ingredient_id'],
                usage_unit_id=ingredient_data['usage_unit_id'],
                quantity=ingredient_data['quantity']
            )
            db.add(recipe_ingredient)
    except json.JSONDecodeError:
        pass  # No ingredients added
    
    db.commit()
    return RedirectResponse(url="/recipes", status_code=302)

@app.get("/recipes/{recipe_id}", response_class=HTMLResponse)
async def recipe_detail(request: Request, recipe_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    recipe = db.query(Recipe).options(joinedload(Recipe.category)).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    recipe_ingredients = db.query(RecipeIngredient).options(
        joinedload(RecipeIngredient.ingredient).joinedload(Ingredient.category),
        joinedload(RecipeIngredient.ingredient).joinedload(Ingredient.usage_units).joinedload(IngredientUsageUnit.usage_unit),
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
async def recipe_edit_get(request: Request, recipe_id: int, current_user: User = Depends(require_manager_or_admin), db: Session = Depends(get_db)):
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

@app.post("/recipes/{recipe_id}/edit")
async def recipe_edit_post(
    request: Request,
    recipe_id: int,
    name: str = Form(...),
    instructions: str = Form(""),
    category_id: Optional[int] = Form(None),
    ingredients_data: str = Form("[]"),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    # Update recipe
    recipe.name = name
    recipe.instructions = instructions
    recipe.category_id = category_id if category_id else None
    
    # Remove existing ingredients
    db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).delete()
    
    # Add new ingredients
    try:
        ingredients = json.loads(ingredients_data)
        for ingredient_data in ingredients:
            recipe_ingredient = RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_id=ingredient_data['ingredient_id'],
                usage_unit_id=ingredient_data['usage_unit_id'],
                quantity=ingredient_data['quantity']
            )
            db.add(recipe_ingredient)
    except json.JSONDecodeError:
        pass  # No ingredients added
    
    db.commit()
    return RedirectResponse(url=f"/recipes/{recipe_id}", status_code=302)

@app.get("/recipes/{recipe_id}/delete")
async def recipe_delete(recipe_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    # Delete recipe ingredients first
    db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).delete()
    
    # Delete recipe
    db.delete(recipe)
    db.commit()
    
    return RedirectResponse(url="/recipes", status_code=302)

@app.get("/api/recipes/{recipe_id}/usage_units")
async def get_recipe_usage_units(recipe_id: int, db: Session = Depends(get_db)):
    try:
        # Get all usage units used in this recipe's ingredients
        recipe_ingredients = db.query(RecipeIngredient).options(
            joinedload(RecipeIngredient.ingredient).joinedload(Ingredient.usage_units).joinedload(IngredientUsageUnit.usage_unit)
        ).filter(RecipeIngredient.recipe_id == recipe_id).all()
        
        usage_units = set()
        for ri in recipe_ingredients:
            for iu in ri.ingredient.usage_units:
                usage_units.add((iu.usage_unit.id, iu.usage_unit.name))
        
        result = [{"id": unit_id, "name": unit_name} for unit_id, unit_name in usage_units]
        return result
    except Exception as e:
        print(f"Error in get_recipe_usage_units: {e}")
        return []

# Batches
@app.get("/batches", response_class=HTMLResponse)
async def batches_list(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
    batch = Batch(
        recipe_id=recipe_id,
        yield_amount=yield_amount,
        yield_unit_id=yield_unit_id,
        estimated_labor_minutes=estimated_labor_minutes,
        hourly_labor_rate=hourly_labor_rate,
        can_be_scaled=can_be_scaled,
        scale_double=scale_double if can_be_scaled else False,
        scale_half=scale_half if can_be_scaled else False,
        scale_quarter=scale_quarter if can_be_scaled else False,
        scale_eighth=scale_eighth if can_be_scaled else False,
        scale_sixteenth=scale_sixteenth if can_be_scaled else False
    )
    db.add(batch)
    db.commit()
    
    return RedirectResponse(url="/batches", status_code=302)

@app.get("/batches/{batch_id}", response_class=HTMLResponse)
async def batch_detail(request: Request, batch_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    batch = db.query(Batch).options(
        joinedload(Batch.recipe).joinedload(Recipe.category),
        joinedload(Batch.yield_unit)
    ).filter(Batch.id == batch_id).first()
    
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Get recipe ingredients for cost calculation
    recipe_ingredients = db.query(RecipeIngredient).options(
        joinedload(RecipeIngredient.ingredient).joinedload(Ingredient.category),
        joinedload(RecipeIngredient.ingredient).joinedload(Ingredient.usage_units),
        joinedload(RecipeIngredient.usage_unit)
    ).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
    
    total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
    labor_cost = batch.estimated_labor_cost
    total_batch_cost = total_recipe_cost + labor_cost
    cost_per_yield_unit = total_batch_cost / batch.yield_amount if batch.yield_amount > 0 else 0
    
    return templates.TemplateResponse("batch_detail.html", {
        "request": request,
        "current_user": current_user,
        "batch": batch,
        "recipe_ingredients": recipe_ingredients,
        "total_recipe_cost": total_recipe_cost,
        "labor_cost": labor_cost,
        "total_batch_cost": total_batch_cost,
        "cost_per_yield_unit": cost_per_yield_unit
    })

@app.get("/batches/{batch_id}/edit", response_class=HTMLResponse)
async def batch_edit_get(request: Request, batch_id: int, current_user: User = Depends(require_manager_or_admin), db: Session = Depends(get_db)):
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

@app.post("/batches/{batch_id}/edit")
async def batch_edit_post(
    batch_id: int,
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
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    batch.recipe_id = recipe_id
    batch.yield_amount = yield_amount
    batch.yield_unit_id = yield_unit_id
    batch.estimated_labor_minutes = estimated_labor_minutes
    batch.hourly_labor_rate = hourly_labor_rate
    batch.can_be_scaled = can_be_scaled
    batch.scale_double = scale_double if can_be_scaled else False
    batch.scale_half = scale_half if can_be_scaled else False
    batch.scale_quarter = scale_quarter if can_be_scaled else False
    batch.scale_eighth = scale_eighth if can_be_scaled else False
    batch.scale_sixteenth = scale_sixteenth if can_be_scaled else False
    
    db.commit()
    
    return RedirectResponse(url=f"/batches/{batch_id}", status_code=302)

@app.get("/batches/{batch_id}/delete")
async def batch_delete(batch_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    db.delete(batch)
    db.commit()
    
    return RedirectResponse(url="/batches", status_code=302)

@app.get("/api/batches/search")
async def search_batches(q: str = "", db: Session = Depends(get_db)):
    try:
        query = db.query(Batch).options(
            joinedload(Batch.recipe).joinedload(Recipe.category),
            joinedload(Batch.yield_unit)
        )
        
        if q:
            query = query.filter(
                or_(
                    Batch.recipe.has(Recipe.name.ilike(f"%{q}%")),
                    Batch.recipe.has(Recipe.category.has(Category.name.ilike(f"%{q}%")))
                )
            )
        
        batches = query.all()
        
        result = []
        for batch in batches:
            # Calculate cost per unit
            recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
            total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
            labor_cost = batch.estimated_labor_cost
            total_batch_cost = total_recipe_cost + labor_cost
            cost_per_unit = total_batch_cost / batch.yield_amount if batch.yield_amount > 0 else 0
            
            result.append({
                "id": batch.id,
                "recipe_name": batch.recipe.name,
                "category": batch.recipe.category.name if batch.recipe.category else None,
                "yield_amount": batch.yield_amount,
                "yield_unit": batch.yield_unit.name if batch.yield_unit else "",
                "cost_per_unit": cost_per_unit
            })
        
        return result
    except Exception as e:
        print(f"Error in search_batches: {e}")
        return []

# API endpoint for batch search (for inventory items)
@app.get("/api/batches/all")
def get_all_batches(db: Session = Depends(get_db)):
    try:
        batches = db.query(Batch).join(Recipe).all()
        
        batch_data = []
        for batch in batches:
            # Calculate total recipe cost
            recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
            total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
            
            # Calculate estimated labor cost
            estimated_labor_cost = batch.estimated_labor_cost
            total_batch_cost = total_recipe_cost + estimated_labor_cost
            
            # Calculate cost per unit
            cost_per_unit = total_batch_cost / batch.yield_amount if batch.yield_amount > 0 else 0
            
            batch_data.append({
                "id": batch.id,
                "recipe_name": batch.recipe.name,
                "yield_amount": batch.yield_amount,
                "yield_unit": batch.yield_unit.name if batch.yield_unit else "",
                "estimated_labor_minutes": batch.estimated_labor_minutes,
                "hourly_labor_rate": batch.hourly_labor_rate,
                "cost_per_unit": cost_per_unit,
                "category": batch.recipe.category.name if batch.recipe.category else None
            })
        
        return batch_data
    except Exception as e:
        print(f"Error in get_all_batches: {e}")
        return []

@app.get("/api/batches/{batch_id}/labor_stats")
def get_batch_labor_stats(batch_id: int, db: Session = Depends(get_db)):
    try:
        from datetime import timedelta
        
        # Get all completed tasks for this batch's inventory items
        completed_tasks = db.query(Task).join(InventoryItem).filter(
            InventoryItem.batch_id == batch_id,
            Task.finished_at.isnot(None)
        ).all()
        
        if not completed_tasks:
            return {
                "most_recent_cost": 0,
                "average_week": 0,
                "average_month": 0,
                "average_year": 0,
                "task_count": 0
            }
        
        # Most recent task
        most_recent_task = max(completed_tasks, key=lambda t: t.finished_at)
        most_recent_cost = most_recent_task.labor_cost
        
        # Calculate averages for different time periods
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        year_ago = now - timedelta(days=365)
        
        week_tasks = [t for t in completed_tasks if t.finished_at >= week_ago]
        month_tasks = [t for t in completed_tasks if t.finished_at >= month_ago]
        year_tasks = [t for t in completed_tasks if t.finished_at >= year_ago]
        
        average_week = sum(t.labor_cost for t in week_tasks) / len(week_tasks) if week_tasks else 0
        average_month = sum(t.labor_cost for t in month_tasks) / len(month_tasks) if month_tasks else 0
        average_year = sum(t.labor_cost for t in year_tasks) / len(year_tasks) if year_tasks else 0
        
        return {
            "most_recent_cost": most_recent_cost,
            "average_week": average_week,
            "average_month": average_month,
            "average_year": average_year,
            "task_count": len(completed_tasks),
            "most_recent_date": most_recent_task.finished_at.strftime('%Y-%m-%d') if most_recent_task.finished_at else None
        }
    except Exception as e:
        print(f"Error in get_batch_labor_stats: {e}")
        return {
            "most_recent_cost": 0,
            "average_week": 0,
            "average_month": 0,
            "average_year": 0,
            "task_count": 0
        }

# Dishes
@app.get("/dishes", response_class=HTMLResponse)
async def dishes_list(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
    name: str = Form(...),
    category_id: Optional[int] = Form(None),
    sale_price: float = Form(...),
    description: str = Form(""),
    batch_portions_data: str = Form("[]"),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    # Create dish
    dish = Dish(
        name=name,
        category_id=category_id if category_id else None,
        sale_price=sale_price,
        description=description
    )
    db.add(dish)
    db.flush()  # Get the ID
    
    # Process batch portions
    try:
        batch_portions = json.loads(batch_portions_data)
        for portion_data in batch_portions:
            dish_batch_portion = DishBatchPortion(
                dish_id=dish.id,
                batch_id=portion_data['batch_id'],
                portion_size=portion_data['portion_size']
            )
            db.add(dish_batch_portion)
    except json.JSONDecodeError:
        pass  # No batch portions added
    
    db.commit()
    return RedirectResponse(url="/dishes", status_code=302)

@app.get("/dishes/{dish_id}", response_class=HTMLResponse)
async def dish_detail(request: Request, dish_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    dish = db.query(Dish).options(joinedload(Dish.category)).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    dish_batch_portions = db.query(DishBatchPortion).options(
        joinedload(DishBatchPortion.batch).joinedload(Batch.recipe).joinedload(Recipe.category),
        joinedload(DishBatchPortion.batch).joinedload(Batch.yield_unit),
        joinedload(DishBatchPortion.portion_unit)
    ).filter(DishBatchPortion.dish_id == dish_id).all()
    
    total_cost = sum(portion.cost for portion in dish_batch_portions)
    profit = dish.sale_price - total_cost
    profit_margin = (profit / dish.sale_price * 100) if dish.sale_price > 0 else 0
    
    return templates.TemplateResponse("dish_detail.html", {
        "request": request,
        "current_user": current_user,
        "dish": dish,
        "dish_batch_portions": dish_batch_portions,
        "total_cost": total_cost,
        "profit": profit,
        "profit_margin": profit_margin
    })

@app.get("/dishes/{dish_id}/edit", response_class=HTMLResponse)
async def dish_edit_get(request: Request, dish_id: int, current_user: User = Depends(require_manager_or_admin), db: Session = Depends(get_db)):
    dish = db.query(Dish).options(joinedload(Dish.category)).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    dish_batch_portions = db.query(DishBatchPortion).options(
        joinedload(DishBatchPortion.batch).joinedload(Batch.recipe),
        joinedload(DishBatchPortion.batch).joinedload(Batch.yield_unit)
    ).filter(DishBatchPortion.dish_id == dish_id).all()
    
    categories = db.query(Category).filter(Category.type == "dish").all()
    
    return templates.TemplateResponse("dish_edit.html", {
        "request": request,
        "current_user": current_user,
        "dish": dish,
        "dish_batch_portions": dish_batch_portions,
        "categories": categories
    })

@app.post("/dishes/{dish_id}/edit")
async def dish_edit_post(
    dish_id: int,
    name: str = Form(...),
    category_id: Optional[int] = Form(None),
    sale_price: float = Form(...),
    description: str = Form(""),
    batch_portions_data: str = Form("[]"),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
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
    try:
        batch_portions = json.loads(batch_portions_data)
        for portion_data in batch_portions:
            dish_batch_portion = DishBatchPortion(
                dish_id=dish.id,
                batch_id=portion_data['batch_id'],
                portion_size=portion_data['portion_size']
            )
            db.add(dish_batch_portion)
    except json.JSONDecodeError:
        pass  # No batch portions added
    
    db.commit()
    return RedirectResponse(url=f"/dishes/{dish_id}", status_code=302)

@app.get("/dishes/{dish_id}/delete")
async def dish_delete(dish_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    # Delete dish batch portions first
    db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).delete()
    
    # Delete dish
    db.delete(dish)
    db.commit()
    
    return RedirectResponse(url="/dishes", status_code=302)

# Inventory Management
@app.get("/inventory", response_class=HTMLResponse)
async def inventory_list(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inventory_items = db.query(InventoryItem).options(joinedload(InventoryItem.category)).all()
    categories = db.query(Category).filter(Category.type == "inventory").all()
    batches = db.query(Batch).join(Recipe).all()
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Get current day if exists
    today = date.today()
    current_day = db.query(InventoryDay).filter(InventoryDay.date == today).first()
    
    # Get recent finalized days (last 30 days)
    thirty_days_ago = today - timedelta(days=30)
    finalized_days = db.query(InventoryDay).filter(
        and_(
            InventoryDay.finalized == True,
            InventoryDay.date >= thirty_days_ago
        )
    ).order_by(InventoryDay.date.desc()).limit(10).all()
    
    return templates.TemplateResponse("inventory.html", {
        "request": request,
        "current_user": current_user,
        "inventory_items": inventory_items,
        "batches": batches,
        "categories": categories,
        "batches": batches,
        "employees": employees,
        "current_day": current_day,
        "finalized_days": finalized_days,
        "today_date": today.isoformat()
    })

@app.post("/inventory/new_item")
async def create_inventory_item(
    name: str = Form(...),
    par_level: float = Form(...),
    category_id: Optional[int] = Form(None),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    item = InventoryItem(
        name=name,
        par_level=par_level,
        category_id=category_id if category_id else None
    )
    db.add(item)
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=302)

@app.get("/inventory/items/{item_id}/edit")
async def inventory_item_edit_page(item_id: int, request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    categories = db.query(Category).filter(Category.type == "inventory").all()
    batches = db.query(Batch).join(Recipe).all()
    
    return templates.TemplateResponse("inventory_item_edit.html", {
        "request": request,
        "current_user": current_user,
        "item": item,
        "categories": categories,
        "batches": batches
    })

@app.post("/inventory/items/{item_id}/edit")
async def inventory_item_edit(item_id: int, request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    form = await request.form()
    
    item.name = form.get("name")
    item.par_level = float(form.get("par_level"))
    item.category_id = int(form.get("category_id")) if form.get("category_id") else None
    item.batch_id = int(form.get("batch_id")) if form.get("batch_id") else None
    
    db.commit()
    return RedirectResponse(url="/inventory", status_code=302)

@app.get("/inventory/items/{item_id}/delete")
async def inventory_item_delete(item_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    db.delete(item)
    db.commit()
    return RedirectResponse(url="/inventory", status_code=302)

@app.post("/inventory/new_day")
async def create_inventory_day(
    request: Request,
    date: date = Form(...),
    employees_working: List[str] = Form([]),
    global_notes: str = Form(""),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    # Check if day already exists
    existing_day = db.query(InventoryDay).filter(InventoryDay.date == date).first()
    if existing_day:
        return RedirectResponse(url=f"/inventory/day/{existing_day.id}", status_code=302)
    
    # Create new day
    inventory_day = InventoryDay(
        date=date,
        employees_working=",".join(employees_working),
        global_notes=global_notes
    )
    db.add(inventory_day)
    db.flush()  # Get the ID
    
    # Create inventory day items for all inventory items
    inventory_items = db.query(InventoryItem).all()
    batches = db.query(Batch).join(Recipe).all()
    for item in inventory_items:
        day_item = InventoryDayItem(
            day_id=inventory_day.id,
            inventory_item_id=item.id,
            quantity=0  # Default to 0, will be updated
        )
        db.add(day_item)
    
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{inventory_day.id}", status_code=302)

@app.get("/inventory/day/{day_id}", response_class=HTMLResponse)
async def inventory_day_detail(request: Request, day_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    inventory_day_items = db.query(InventoryDayItem).options(
        joinedload(InventoryDayItem.inventory_item).joinedload(InventoryItem.category)
    ).filter(InventoryDayItem.day_id == day_id).all()
    
    tasks = db.query(Task).options(joinedload(Task.assigned_to)).filter(Task.day_id == day_id).all()
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
    request: Request,
    day_id: int,
    global_notes: str = Form(""),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day or inventory_day.finalized:
        raise HTTPException(status_code=404, detail="Inventory day not found or finalized")
    
    # Update global notes
    inventory_day.global_notes = global_notes
    
    # Update inventory quantities
    form_data = await request.form()
    inventory_day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == day_id).all()
    
    for item in inventory_day_items:
        quantity_key = f"item_{item.inventory_item_id}"
        override_create_key = f"override_create_{item.inventory_item_id}"
        override_no_task_key = f"override_no_task_{item.inventory_item_id}"
        
        if quantity_key in form_data:
            item.quantity = float(form_data[quantity_key])
        
        item.override_create_task = override_create_key in form_data
        item.override_no_task = override_no_task_key in form_data
    
    # Generate tasks for below-par items
    for item in inventory_day_items:
        is_below_par = item.quantity <= item.inventory_item.par_level
        should_create_task = (is_below_par and not item.override_no_task) or item.override_create_task
        
        if should_create_task:
            # Check if task already exists
            existing_task = db.query(Task).filter(
                and_(
                    Task.day_id == day_id,
                    Task.description.like(f"%{item.inventory_item.name}%"),
                    Task.auto_generated == True
                )
            ).first()
            
            if not existing_task:
                task = Task(
                    day_id=day_id,
                    description=f"Restock {item.inventory_item.name} (below par: {item.quantity}/{item.inventory_item.par_level})",
                    auto_generated=True
                )
                db.add(task)
    
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/finalize")
async def finalize_inventory_day(day_id: int, current_user: User = Depends(require_manager_or_admin), db: Session = Depends(get_db)):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    inventory_day.finalized = True
    db.commit()
    
    return RedirectResponse(url=f"/inventory/reports/{day_id}", status_code=302)

@app.get("/inventory/reports/{day_id}", response_class=HTMLResponse)
async def inventory_report(request: Request, day_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    inventory_day_items = db.query(InventoryDayItem).options(
        joinedload(InventoryDayItem.inventory_item)
    ).filter(InventoryDayItem.day_id == day_id).all()
    
    tasks = db.query(Task).options(joinedload(Task.assigned_to)).filter(Task.day_id == day_id).all()
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Calculate statistics
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t.finished_at])
    below_par_items = len([item for item in inventory_day_items if item.quantity <= item.inventory_item.par_level])
    
    return templates.TemplateResponse("inventory_report.html", {
        "request": request,
        "current_user": current_user,
        "inventory_day": inventory_day,
        "inventory_day_items": inventory_day_items,
        "tasks": tasks,
        "employees": employees,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "below_par_items": below_par_items
    })

# Task Management
@app.post("/inventory/day/{day_id}/tasks/new")
async def create_task(
    day_id: int,
    assigned_to_id: Optional[int] = Form(None),
    description: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    task = Task(
        day_id=day_id,
        assigned_to_id=assigned_to_id if assigned_to_id else None,
        description=description,
        auto_generated=False
    )
    db.add(task)
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.get("/inventory/day/{day_id}/tasks/{task_id}", response_class=HTMLResponse)
async def task_detail(request: Request, day_id: int, task_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.query(Task).options(joinedload(Task.assigned_to)).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    employees = db.query(User).filter(User.is_active == True).all()
    
    return templates.TemplateResponse("task_detail.html", {
        "request": request,
        "current_user": current_user,
        "task": task,
        "inventory_day": inventory_day,
        "employees": employees
    })

@app.post("/inventory/day/{day_id}/tasks/{task_id}/assign")
async def assign_task(
    day_id: int, 
    task_id: int, 
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin)
):
    form = await request.form()
    assigned_to_id = form.get("assigned_to_id")
    
    if not assigned_to_id:
        return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)
    
    # Get the task
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Update assignment
    task.assigned_to_id = int(assigned_to_id)
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/start")
async def start_task(day_id: int, task_id: int, current_user: User = Depends(require_user_or_above), db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.started_at = datetime.utcnow()
    task.is_paused = False
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/pause")
async def pause_task(day_id: int, task_id: int, current_user: User = Depends(require_user_or_above), db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.started_at and not task.is_paused:
        task.paused_at = datetime.utcnow()
        task.is_paused = True
        
        # Add to total pause time if resuming from a previous pause
        if task.paused_at and task.started_at:
            pause_duration = (task.paused_at - task.started_at).total_seconds()
            task.total_pause_time += int(pause_duration)
    
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/resume")
async def resume_task(day_id: int, task_id: int, current_user: User = Depends(require_user_or_above), db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.is_paused:
        task.is_paused = False
        task.paused_at = None
    
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/finish")
async def finish_task(day_id: int, task_id: int, current_user: User = Depends(require_user_or_above), db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.finished_at = datetime.utcnow()
    task.is_paused = False
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/notes")
async def update_task_notes(
    day_id: int,
    task_id: int,
    notes: str = Form(...),
    current_user: User = Depends(require_user_or_above),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.notes = notes
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}/tasks/{task_id}", status_code=302)

# Utilities (Admin only)
@app.get("/utilities", response_class=HTMLResponse)
async def utilities_list(request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    utilities = db.query(UtilityCost).all()
    
    return templates.TemplateResponse("utilities.html", {
        "request": request,
        "current_user": current_user,
        "utilities": utilities
    })

@app.post("/utilities/new")
async def create_utility(
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

@app.post("/utilities/{utility_id}/delete")
async def delete_utility(utility_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    utility = db.query(UtilityCost).filter(UtilityCost.id == utility_id).first()
    if not utility:
        raise HTTPException(status_code=404, detail="Utility not found")
    
    db.delete(utility)
    db.commit()
    
    return RedirectResponse(url="/utilities", status_code=302)

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401 and "Location" in exc.headers:
        return RedirectResponse(url=exc.headers["Location"], status_code=302)
    
    return templates.TemplateResponse("error.html", {
        "request": request,
        "status_code": exc.status_code,
        "detail": exc.detail
    }, status_code=exc.status_code)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)