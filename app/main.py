from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from datetime import datetime, date, timedelta
import json
from typing import List, Optional

from .database import SessionLocal, engine, get_db
from .models import Base, User, Category, Ingredient, Recipe, RecipeIngredient, Batch, Dish, DishBatchPortion, InventoryItem, InventoryDay, InventoryDayItem, Task, UtilityCost, Vendor, VendorUnit, ParUnitName
from .auth import hash_password, verify_password, create_jwt, get_current_user, require_admin, require_manager_or_admin, require_user_or_above

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def get_current_user_optional(request: Request, db: Session = Depends(get_db)):
    """Get current user if logged in, otherwise return None"""
    try:
        return get_current_user(request, db)
    except HTTPException:
        return None

@app.get("/", response_class=HTMLResponse)
async def root(request: Request, db: Session = Depends(get_db)):
    # Check if any users exist
    user_count = db.query(User).count()
    if user_count == 0:
        return RedirectResponse(url="/setup", status_code=302)
    
    # Check if user is logged in
    try:
        current_user = get_current_user(request, db)
        return RedirectResponse(url="/login", status_code=302)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=302)

@app.get("/setup", response_class=HTMLResponse)
async def setup_form(request: Request, db: Session = Depends(get_db)):
    # Check if any users exist
    user_count = db.query(User).count()
    if user_count > 0:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("setup.html", {"request": request})

@app.post("/setup")
async def setup_admin(
    request: Request,
    username: str = Form(...),
    full_name: str = Form(""),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    # Check if any users exist
    user_count = db.query(User).count()
    if user_count > 0:
        return RedirectResponse(url="/login", status_code=302)
    
    # Use username as full_name if not provided
    if not full_name.strip():
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
        ("Appetizers", "recipe"),
        ("Entrees", "recipe"),
        ("Desserts", "recipe"),
        ("Prep Items", "batch"),
        ("Sauces", "batch"),
        ("Appetizers", "dish"),
        ("Entrees", "dish"),
        ("Desserts", "dish"),
        ("Beverages", "dish"),
        ("Prep", "inventory"),
        ("Storage", "inventory")
    ]
    
    for cat_name, cat_type in default_categories:
        existing_cat = db.query(Category).filter(
            and_(Category.name == cat_name, Category.type == cat_type)
        ).first()
        if not existing_cat:
            category = Category(name=cat_name, type=cat_type)
            db.add(category)
    
    # Create default vendor units
    default_vendor_units = [
        ("lb", "Pound"),
        ("oz", "Ounce"),
        ("g", "Gram"),
        ("kg", "Kilogram"),
        ("gal", "Gallon"),
        ("qt", "Quart"),
        ("pt", "Pint"),
        ("cup", "Cup"),
        ("fl_oz", "Fluid Ounce"),
        ("l", "Liter"),
        ("ml", "Milliliter"),
        ("#10_can", "#10 Can"),
        ("#5_can", "#5 Can"),
        ("case", "Case"),
        ("bag", "Bag"),
        ("box", "Box")
    ]
    
    for unit_name, unit_desc in default_vendor_units:
        existing_unit = db.query(VendorUnit).filter(VendorUnit.name == unit_name).first()
        if not existing_unit:
            vendor_unit = VendorUnit(name=unit_name, description=unit_desc)
            db.add(vendor_unit)
    
    # Create default par unit names
    default_par_units = ["Tub", "Case", "Container", "Batch", "Portion"]
    for par_unit_name in default_par_units:
        existing_par_unit = db.query(ParUnitName).filter(ParUnitName.name == par_unit_name).first()
        if not existing_par_unit:
            par_unit = ParUnitName(name=par_unit_name)
            db.add(par_unit)
    
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
    if not user or not verify_password(password, user.hashed_password) or not user.is_active:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid username or password"
        })
    
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
    response.delete_cookie(key="access_token")
    return response

@app.get("/home", response_class=HTMLResponse)
async def home(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("home.html", {
        "request": request,
        "current_user": current_user
    })

# Ingredients
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
    category_id: Optional[int] = Form(None),
    vendor_id: Optional[int] = Form(None),
    vendor_unit_id: Optional[int] = Form(None),
    purchase_type: str = Form(...),
    purchase_unit_name: str = Form(...),
    net_weight_volume_item: float = Form(...),
    net_unit: str = Form(...),
    purchase_total_cost: float = Form(...),
    breakable_case: bool = Form(False),
    items_per_case: Optional[int] = Form(None),
    net_weight_volume_case: Optional[float] = Form(None),
    has_baking_conversion: bool = Form(False),
    baking_measurement_unit: Optional[str] = Form(None),
    baking_weight_amount: Optional[float] = Form(None),
    baking_weight_unit: Optional[str] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    # Calculate net_weight_volume_case if not provided
    if purchase_type == "case" and items_per_case and not net_weight_volume_case:
        net_weight_volume_case = net_weight_volume_item * items_per_case
    
    ingredient = Ingredient(
        name=name,
        usage_type=usage_type,
        category_id=category_id if category_id else None,
        vendor_id=vendor_id if vendor_id else None,
        vendor_unit_id=vendor_unit_id if vendor_unit_id else None,
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
async def ingredient_detail(
    ingredient_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    return templates.TemplateResponse("ingredient_detail.html", {
        "request": request,
        "current_user": current_user,
        "ingredient": ingredient
    })

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
    
    return templates.TemplateResponse("ingredient_edit.html", {
        "request": request,
        "current_user": current_user,
        "ingredient": ingredient,
        "categories": categories,
        "vendors": vendors,
        "vendor_units": vendor_units
    })

@app.post("/ingredients/{ingredient_id}/edit")
async def update_ingredient(
    ingredient_id: int,
    request: Request,
    name: str = Form(...),
    usage_type: str = Form(...),
    category_id: Optional[int] = Form(None),
    vendor_id: Optional[int] = Form(None),
    vendor_unit_id: Optional[int] = Form(None),
    purchase_type: str = Form(...),
    purchase_unit_name: str = Form(...),
    net_weight_volume_item: float = Form(...),
    net_unit: str = Form(...),
    purchase_total_cost: float = Form(...),
    breakable_case: bool = Form(False),
    items_per_case: Optional[int] = Form(None),
    net_weight_volume_case: Optional[float] = Form(None),
    has_baking_conversion: bool = Form(False),
    baking_measurement_unit: Optional[str] = Form(None),
    baking_weight_amount: Optional[float] = Form(None),
    baking_weight_unit: Optional[str] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    # Calculate net_weight_volume_case if not provided
    if purchase_type == "case" and items_per_case and not net_weight_volume_case:
        net_weight_volume_case = net_weight_volume_item * items_per_case
    
    ingredient.name = name
    ingredient.usage_type = usage_type
    ingredient.category_id = category_id if category_id else None
    ingredient.vendor_id = vendor_id if vendor_id else None
    ingredient.vendor_unit_id = vendor_unit_id if vendor_unit_id else None
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
async def delete_ingredient(
    ingredient_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    db.delete(ingredient)
    db.commit()
    
    return RedirectResponse(url="/ingredients", status_code=302)

# API endpoint for ingredient cost per unit
@app.get("/api/ingredients/{ingredient_id}/cost_per_unit/{unit}")
async def get_ingredient_cost_per_unit(
    ingredient_id: int,
    unit: str,
    db: Session = Depends(get_db)
):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    cost_per_unit = ingredient.get_cost_per_unit(unit)
    return {"cost_per_unit": cost_per_unit}

# API endpoint for all ingredients with available units
@app.get("/api/ingredients/all")
async def get_all_ingredients(db: Session = Depends(get_db)):
    ingredients = db.query(Ingredient).all()
    result = []
    
    for ingredient in ingredients:
        ingredient_data = {
            "id": ingredient.id,
            "name": ingredient.name,
            "category": ingredient.category.name if ingredient.category else None,
            "available_units": ingredient.get_available_units()
        }
        result.append(ingredient_data)
    
    return result

# Recipes
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

@app.post("/recipes/new")
async def create_recipe(
    request: Request,
    name: str = Form(...),
    instructions: str = Form(""),
    category_id: Optional[int] = Form(None),
    ingredients_data: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    recipe = Recipe(
        name=name,
        instructions=instructions if instructions else None,
        category_id=category_id if category_id else None
    )
    db.add(recipe)
    db.flush()  # Get the recipe ID
    
    # Parse ingredients data
    ingredients = json.loads(ingredients_data)
    for ingredient_data in ingredients:
        recipe_ingredient = RecipeIngredient(
            recipe_id=recipe.id,
            ingredient_id=ingredient_data["ingredient_id"],
            unit=ingredient_data["unit"],
            quantity=ingredient_data["quantity"]
        )
        db.add(recipe_ingredient)
    
    db.commit()
    
    return RedirectResponse(url="/recipes", status_code=302)

@app.get("/recipes/{recipe_id}", response_class=HTMLResponse)
async def recipe_detail(
    recipe_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
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
    instructions: str = Form(""),
    category_id: Optional[int] = Form(None),
    ingredients_data: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    recipe.name = name
    recipe.instructions = instructions if instructions else None
    recipe.category_id = category_id if category_id else None
    
    # Delete existing recipe ingredients
    db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).delete()
    
    # Add new recipe ingredients
    ingredients = json.loads(ingredients_data)
    for ingredient_data in ingredients:
        recipe_ingredient = RecipeIngredient(
            recipe_id=recipe.id,
            ingredient_id=ingredient_data["ingredient_id"],
            unit=ingredient_data["unit"],
            quantity=ingredient_data["quantity"]
        )
        db.add(recipe_ingredient)
    
    db.commit()
    
    return RedirectResponse(url=f"/recipes/{recipe_id}", status_code=302)

@app.get("/recipes/{recipe_id}/delete")
async def delete_recipe(
    recipe_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    # Delete recipe ingredients first
    db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).delete()
    db.delete(recipe)
    db.commit()
    
    return RedirectResponse(url="/recipes", status_code=302)

# API endpoint for recipe available units
@app.get("/api/recipes/{recipe_id}/available_units")
async def get_recipe_available_units(
    recipe_id: int,
    db: Session = Depends(get_db)
):
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).all()
    
    all_units = set()
    for ri in recipe_ingredients:
        if ri.ingredient:
            all_units.update(ri.ingredient.get_available_units())
    
    return list(all_units)

# Batches
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

@app.post("/batches/new")
async def create_batch(
    request: Request,
    recipe_id: int = Form(...),
    variable_yield: bool = Form(False),
    yield_amount: Optional[float] = Form(None),
    yield_unit: Optional[str] = Form(None),
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
        variable_yield=variable_yield,
        yield_amount=yield_amount if not variable_yield else None,
        yield_unit=yield_unit if not variable_yield else None,
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
async def batch_detail(
    batch_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
    total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
    total_batch_cost = total_recipe_cost + batch.estimated_labor_cost
    
    cost_per_yield_unit = 0
    if not batch.variable_yield and batch.yield_amount and batch.yield_amount > 0:
        cost_per_yield_unit = total_batch_cost / batch.yield_amount
    
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
    batch_id: int,
    request: Request,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    recipes = db.query(Recipe).all()
    
    return templates.TemplateResponse("batch_edit.html", {
        "request": request,
        "current_user": current_user,
        "batch": batch,
        "recipes": recipes
    })

@app.post("/batches/{batch_id}/edit")
async def update_batch(
    batch_id: int,
    request: Request,
    recipe_id: int = Form(...),
    variable_yield: bool = Form(False),
    yield_amount: Optional[float] = Form(None),
    yield_unit: Optional[str] = Form(None),
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
    batch.variable_yield = variable_yield
    batch.yield_amount = yield_amount if not variable_yield else None
    batch.yield_unit = yield_unit if not variable_yield else None
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
async def delete_batch(
    batch_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    db.delete(batch)
    db.commit()
    
    return RedirectResponse(url="/batches", status_code=302)

# API endpoints for batches
@app.get("/api/batches/all")
async def get_all_batches(db: Session = Depends(get_db)):
    batches = db.query(Batch).all()
    result = []
    
    for batch in batches:
        # Calculate cost per unit
        recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
        total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
        total_batch_cost = total_recipe_cost + batch.estimated_labor_cost
        
        cost_per_unit = 0
        if not batch.variable_yield and batch.yield_amount and batch.yield_amount > 0:
            cost_per_unit = total_batch_cost / batch.yield_amount
        
        batch_data = {
            "id": batch.id,
            "recipe_name": batch.recipe.name,
            "category": batch.recipe.category.name if batch.recipe.category else None,
            "yield_amount": batch.yield_amount,
            "yield_unit": batch.yield_unit,
            "cost_per_unit": cost_per_unit,
            "variable_yield": batch.variable_yield
        }
        result.append(batch_data)
    
    return result

@app.get("/api/batches/search")
async def search_batches(q: str, db: Session = Depends(get_db)):
    batches = db.query(Batch).join(Recipe).filter(
        or_(
            Recipe.name.ilike(f"%{q}%"),
            Recipe.category.has(Category.name.ilike(f"%{q}%"))
        )
    ).all()
    
    result = []
    for batch in batches:
        # Calculate cost per unit
        recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
        total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
        total_batch_cost = total_recipe_cost + batch.estimated_labor_cost
        
        cost_per_unit = 0
        if not batch.variable_yield and batch.yield_amount and batch.yield_amount > 0:
            cost_per_unit = total_batch_cost / batch.yield_amount
        
        batch_data = {
            "id": batch.id,
            "recipe_name": batch.recipe.name,
            "category": batch.recipe.category.name if batch.recipe.category else None,
            "yield_amount": batch.yield_amount,
            "yield_unit": batch.yield_unit,
            "cost_per_unit": cost_per_unit,
            "variable_yield": batch.variable_yield
        }
        result.append(batch_data)
    
    return result

@app.get("/api/batches/{batch_id}/available_units")
async def get_batch_available_units(
    batch_id: int,
    db: Session = Depends(get_db)
):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Get all units from recipe ingredients
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
    
    all_units = set()
    for ri in recipe_ingredients:
        if ri.ingredient:
            all_units.update(ri.ingredient.get_available_units())
    
    # Add batch yield unit if it exists
    if batch.yield_unit:
        all_units.add(batch.yield_unit)
    
    return list(all_units)

@app.get("/api/batches/{batch_id}/labor_stats")
async def get_batch_labor_stats(
    batch_id: int,
    db: Session = Depends(get_db)
):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Get completed tasks for this batch
    completed_tasks = db.query(Task).filter(
        Task.batch_id == batch_id,
        Task.finished_at.isnot(None)
    ).all()
    
    if not completed_tasks:
        return {
            "task_count": 0,
            "most_recent_cost": batch.estimated_labor_cost,
            "most_recent_date": None,
            "average_week": batch.estimated_labor_cost,
            "average_month": batch.estimated_labor_cost,
            "average_all_time": batch.estimated_labor_cost,
            "week_task_count": 0,
            "month_task_count": 0
        }
    
    # Most recent task
    most_recent = max(completed_tasks, key=lambda t: t.finished_at)
    
    # Time-based filtering
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    week_tasks = [t for t in completed_tasks if t.finished_at >= week_ago]
    month_tasks = [t for t in completed_tasks if t.finished_at >= month_ago]
    
    return {
        "task_count": len(completed_tasks),
        "most_recent_cost": most_recent.labor_cost,
        "most_recent_date": most_recent.finished_at.strftime('%Y-%m-%d'),
        "average_week": sum(t.labor_cost for t in week_tasks) / len(week_tasks) if week_tasks else batch.estimated_labor_cost,
        "average_month": sum(t.labor_cost for t in month_tasks) / len(month_tasks) if month_tasks else batch.estimated_labor_cost,
        "average_all_time": sum(t.labor_cost for t in completed_tasks) / len(completed_tasks),
        "week_task_count": len(week_tasks),
        "month_task_count": len(month_tasks)
    }

# Dishes
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

@app.post("/dishes/new")
async def create_dish(
    request: Request,
    name: str = Form(...),
    category_id: Optional[int] = Form(None),
    sale_price: float = Form(...),
    description: str = Form(""),
    batch_portions_data: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    dish = Dish(
        name=name,
        category_id=category_id if category_id else None,
        sale_price=sale_price,
        description=description if description else None
    )
    db.add(dish)
    db.flush()  # Get the dish ID
    
    # Parse batch portions data
    batch_portions = json.loads(batch_portions_data)
    for portion_data in batch_portions:
        dish_batch_portion = DishBatchPortion(
            dish_id=dish.id,
            batch_id=portion_data["batch_id"],
            portion_size=portion_data["portion_size"],
            portion_unit=portion_data["portion_unit_name"]
        )
        db.add(dish_batch_portion)
    
    db.commit()
    
    return RedirectResponse(url="/dishes", status_code=302)

@app.get("/dishes/{dish_id}", response_class=HTMLResponse)
async def dish_detail(
    dish_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    dish_batch_portions = db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).all()
    
    # Calculate costs
    expected_total_cost = sum(portion.expected_cost for portion in dish_batch_portions)
    actual_total_cost = sum(portion.actual_cost for portion in dish_batch_portions)
    actual_total_cost_week = sum(portion.actual_cost_week_avg for portion in dish_batch_portions)
    actual_total_cost_month = sum(portion.actual_cost_month_avg for portion in dish_batch_portions)
    actual_total_cost_all_time = sum(portion.actual_cost_all_time_avg for portion in dish_batch_portions)
    
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
        "expected_total_cost": expected_total_cost,
        "actual_total_cost": actual_total_cost,
        "actual_total_cost_week": actual_total_cost_week,
        "actual_total_cost_month": actual_total_cost_month,
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
        "actual_profit_margin_all_time": actual_profit_margin_all_time
    })

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
    batch_portions_data: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    dish.name = name
    dish.category_id = category_id if category_id else None
    dish.sale_price = sale_price
    dish.description = description if description else None
    
    # Delete existing batch portions
    db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).delete()
    
    # Add new batch portions
    batch_portions = json.loads(batch_portions_data)
    for portion_data in batch_portions:
        dish_batch_portion = DishBatchPortion(
            dish_id=dish.id,
            batch_id=portion_data["batch_id"],
            portion_size=portion_data["portion_size"],
            portion_unit=portion_data["portion_unit_name"]
        )
        db.add(dish_batch_portion)
    
    db.commit()
    
    return RedirectResponse(url=f"/dishes/{dish_id}", status_code=302)

@app.get("/dishes/{dish_id}/delete")
async def delete_dish(
    dish_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    # Delete dish batch portions first
    db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).delete()
    db.delete(dish)
    db.commit()
    
    return RedirectResponse(url="/dishes", status_code=302)

# Inventory
@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inventory_items = db.query(InventoryItem).all()
    categories = db.query(Category).filter(Category.type == "inventory").all()
    batches = db.query(Batch).all()
    par_unit_names = db.query(ParUnitName).all()
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Get current day
    today = date.today()
    current_day = db.query(InventoryDay).filter(
        InventoryDay.date == today,
        InventoryDay.finalized == False
    ).first()
    
    # Get recent finalized days
    thirty_days_ago = today - timedelta(days=30)
    finalized_days = db.query(InventoryDay).filter(
        InventoryDay.date >= thirty_days_ago,
        InventoryDay.finalized == True
    ).order_by(InventoryDay.date.desc()).limit(10).all()
    
    return templates.TemplateResponse("inventory.html", {
        "request": request,
        "current_user": current_user,
        "inventory_items": inventory_items,
        "categories": categories,
        "batches": batches,
        "par_unit_names": par_unit_names,
        "employees": employees,
        "current_day": current_day,
        "finalized_days": finalized_days,
        "today_date": today.isoformat()
    })

@app.post("/inventory/new_item")
async def create_inventory_item(
    request: Request,
    name: str = Form(...),
    par_unit_name_id: Optional[int] = Form(None),
    par_level: float = Form(...),
    batch_id: Optional[int] = Form(None),
    par_unit_equals_type: Optional[str] = Form(None),
    par_unit_equals_amount: Optional[float] = Form(None),
    par_unit_equals_unit: Optional[str] = Form(None),
    category_id: Optional[int] = Form(None),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    inventory_item = InventoryItem(
        name=name,
        par_unit_name_id=par_unit_name_id if par_unit_name_id else None,
        par_level=par_level,
        batch_id=batch_id if batch_id else None,
        par_unit_equals_type=par_unit_equals_type,
        par_unit_equals_amount=par_unit_equals_amount,
        par_unit_equals_unit=par_unit_equals_unit,
        category_id=category_id if category_id else None
    )
    
    db.add(inventory_item)
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=302)

@app.post("/inventory/new_day")
async def create_inventory_day(
    request: Request,
    date: str = Form(...),
    employees_working: List[str] = Form([]),
    global_notes: str = Form(""),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    inventory_date = datetime.strptime(date, "%Y-%m-%d").date()
    
    # Check if day already exists
    existing_day = db.query(InventoryDay).filter(InventoryDay.date == inventory_date).first()
    if existing_day:
        return RedirectResponse(url=f"/inventory/day/{existing_day.id}", status_code=302)
    
    inventory_day = InventoryDay(
        date=inventory_date,
        employees_working=",".join(employees_working) if employees_working else "",
        global_notes=global_notes if global_notes else None
    )
    db.add(inventory_day)
    db.flush()  # Get the day ID
    
    # Create inventory day items for all inventory items
    inventory_items = db.query(InventoryItem).all()
    for item in inventory_items:
        inventory_day_item = InventoryDayItem(
            day_id=inventory_day.id,
            inventory_item_id=item.id,
            quantity=0.0
        )
        db.add(inventory_day_item)
    
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{inventory_day.id}", status_code=302)

@app.get("/inventory/day/{day_id}", response_class=HTMLResponse)
async def inventory_day_page(
    day_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    inventory_day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == day_id).all()
    tasks = db.query(Task).filter(Task.day_id == day_id).order_by(Task.id).all()
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
    global_notes: str = Form(""),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day or inventory_day.finalized:
        raise HTTPException(status_code=404, detail="Inventory day not found or finalized")
    
    inventory_day.global_notes = global_notes if global_notes else None
    
    # Get form data
    form_data = await request.form()
    
    # Update inventory quantities and overrides
    inventory_day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == day_id).all()
    for item in inventory_day_items:
        quantity_key = f"item_{item.inventory_item.id}"
        override_create_key = f"override_create_{item.inventory_item.id}"
        override_no_task_key = f"override_no_task_{item.inventory_item.id}"
        
        if quantity_key in form_data:
            item.quantity = float(form_data[quantity_key])
        
        item.override_create_task = override_create_key in form_data
        item.override_no_task = override_no_task_key in form_data
    
    # Delete existing auto-generated tasks
    db.query(Task).filter(Task.day_id == day_id, Task.auto_generated == True).delete()
    
    # Generate new tasks based on inventory levels
    for item in inventory_day_items:
        should_create_task = False
        
        if item.override_create_task:
            should_create_task = True
        elif not item.override_no_task and item.quantity <= item.inventory_item.par_level:
            should_create_task = True
        
        if should_create_task:
            task = Task(
                day_id=day_id,
                inventory_item_id=item.inventory_item.id,
                batch_id=item.inventory_item.batch_id,
                description=f"Prep {item.inventory_item.name}",
                auto_generated=True
            )
            db.add(task)
    
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/new")
async def create_manual_task(
    day_id: int,
    request: Request,
    assigned_to_ids: List[str] = Form([]),
    inventory_item_id: Optional[int] = Form(None),
    description: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day or inventory_day.finalized:
        raise HTTPException(status_code=404, detail="Inventory day not found or finalized")
    
    # Create tasks for each assigned employee or one unassigned task
    if assigned_to_ids:
        for assigned_to_id in assigned_to_ids:
            task = Task(
                day_id=day_id,
                assigned_to_id=int(assigned_to_id),
                inventory_item_id=inventory_item_id if inventory_item_id else None,
                description=description,
                auto_generated=False
            )
            # Set batch_id from inventory item if available
            if inventory_item_id:
                inventory_item = db.query(InventoryItem).filter(InventoryItem.id == inventory_item_id).first()
                if inventory_item and inventory_item.batch_id:
                    task.batch_id = inventory_item.batch_id
            db.add(task)
    else:
        # Create unassigned task
        task = Task(
            day_id=day_id,
            inventory_item_id=inventory_item_id if inventory_item_id else None,
            description=description,
            auto_generated=False
        )
        # Set batch_id from inventory item if available
        if inventory_item_id:
            inventory_item = db.query(InventoryItem).filter(InventoryItem.id == inventory_item_id).first()
            if inventory_item and inventory_item.batch_id:
                task.batch_id = inventory_item.batch_id
        db.add(task)
    
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/assign")
async def assign_task(
    day_id: int,
    task_id: int,
    assigned_to_id: int = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.assigned_to_id = assigned_to_id
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/start")
async def start_task(
    day_id: int,
    task_id: int,
    current_user: User = Depends(require_user_or_above),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.started_at:
        raise HTTPException(status_code=400, detail="Task already started")
    
    task.started_at = datetime.utcnow()
    task.is_paused = False
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/start_with_scale")
async def start_task_with_scale(
    day_id: int,
    task_id: int,
    selected_scale: str = Form(...),
    current_user: User = Depends(require_user_or_above),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.started_at:
        raise HTTPException(status_code=400, detail="Task already started")
    
    # Set scale information
    scale_factors = {
        'full': 1.0,
        'double': 2.0,
        'half': 0.5,
        'quarter': 0.25,
        'eighth': 0.125,
        'sixteenth': 0.0625
    }
    
    task.selected_scale = selected_scale
    task.scale_factor = scale_factors.get(selected_scale, 1.0)
    task.started_at = datetime.utcnow()
    task.is_paused = False
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/pause")
async def pause_task(
    day_id: int,
    task_id: int,
    current_user: User = Depends(require_user_or_above),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not task.started_at or task.finished_at:
        raise HTTPException(status_code=400, detail="Task not in progress")
    
    task.paused_at = datetime.utcnow()
    task.is_paused = True
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/resume")
async def resume_task(
    day_id: int,
    task_id: int,
    current_user: User = Depends(require_user_or_above),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not task.is_paused or not task.paused_at:
        raise HTTPException(status_code=400, detail="Task not paused")
    
    # Add pause time to total
    pause_duration = (datetime.utcnow() - task.paused_at).total_seconds()
    task.total_pause_time += int(pause_duration)
    task.paused_at = None
    task.is_paused = False
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/finish")
async def finish_task(
    day_id: int,
    task_id: int,
    current_user: User = Depends(require_user_or_above),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not task.started_at or task.finished_at:
        raise HTTPException(status_code=400, detail="Task not started or already finished")
    
    task.finished_at = datetime.utcnow()
    task.is_paused = False
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/finish_with_amount")
async def finish_task_with_amount(
    day_id: int,
    task_id: int,
    made_amount: float = Form(...),
    made_unit: str = Form(...),
    current_user: User = Depends(require_user_or_above),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not task.started_at or task.finished_at:
        raise HTTPException(status_code=400, detail="Task not started or already finished")
    
    task.made_amount = made_amount
    task.made_unit = made_unit
    task.finished_at = datetime.utcnow()
    task.is_paused = False
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.get("/inventory/day/{day_id}/tasks/{task_id}", response_class=HTMLResponse)
async def task_detail(
    day_id: int,
    task_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
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

@app.post("/inventory/day/{day_id}/tasks/{task_id}/notes")
async def update_task_notes(
    day_id: int,
    task_id: int,
    notes: str = Form(""),
    current_user: User = Depends(require_user_or_above),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.notes = notes if notes else None
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}/tasks/{task_id}", status_code=302)

@app.post("/inventory/day/{day_id}/finalize")
async def finalize_inventory_day(
    day_id: int,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    inventory_day.finalized = True
    db.commit()
    
    return RedirectResponse(url=f"/inventory/reports/{day_id}", status_code=302)

@app.get("/inventory/reports/{day_id}", response_class=HTMLResponse)
async def inventory_report(
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
    name: str = Form(...),
    par_level: float = Form(...),
    batch_id: Optional[int] = Form(None),
    category_id: Optional[int] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    item.name = name
    item.par_level = par_level
    item.batch_id = batch_id if batch_id else None
    item.category_id = category_id if category_id else None
    
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=302)

@app.get("/inventory/items/{item_id}/delete")
async def delete_inventory_item(
    item_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    db.delete(item)
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=302)

# API endpoints for tasks
@app.get("/api/tasks/{task_id}/scale_options")
async def get_task_scale_options(
    task_id: int,
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task or not task.batch:
        raise HTTPException(status_code=404, detail="Task or batch not found")
    
    scales = task.batch.get_available_scales()
    result = []
    
    for scale_key, scale_factor, scale_label in scales:
        if task.batch.variable_yield:
            yield_display = "Variable"
        else:
            yield_amount = task.batch.get_scaled_yield(scale_factor)
            yield_display = f"{yield_amount} {task.batch.yield_unit}"
        
        result.append({
            "key": scale_key,
            "factor": scale_factor,
            "label": scale_label,
            "yield": yield_display
        })
    
    return result

@app.get("/api/tasks/{task_id}/finish_requirements")
async def get_task_finish_requirements(
    task_id: int,
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get available units from batch or recipe
    available_units = []
    if task.batch:
        if task.batch.variable_yield:
            # For variable yield, get units from recipe ingredients
            recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == task.batch.recipe_id).all()
            all_units = set()
            for ri in recipe_ingredients:
                if ri.ingredient:
                    all_units.update(ri.ingredient.get_available_units())
            available_units = list(all_units)
        else:
            # For fixed yield, use batch yield unit
            available_units = [task.batch.yield_unit]
    
    # Get inventory info if available
    inventory_info = None
    if task.inventory_item:
        # Get current inventory from most recent day
        latest_day_item = db.query(InventoryDayItem).filter(
            InventoryDayItem.inventory_item_id == task.inventory_item.id
        ).join(InventoryDay).order_by(InventoryDay.date.desc()).first()
        
        if latest_day_item:
            inventory_info = {
                "current": latest_day_item.quantity,
                "par_level": task.inventory_item.par_level,
                "par_unit_name": task.inventory_item.par_unit_name.name if task.inventory_item.par_unit_name else "units"
            }
    
    return {
        "available_units": available_units,
        "inventory_info": inventory_info
    }

# Employees (Admin only)
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
    role: str = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    # Check if username already exists
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    hashed_password = hash_password(password)
    employee = User(
        full_name=full_name,
        username=username,
        hashed_password=hashed_password,
        hourly_wage=hourly_wage,
        work_schedule=work_schedule,
        role=role,
        is_admin=(role == "admin"),
        is_user=True
    )
    
    db.add(employee)
    db.commit()
    
    return RedirectResponse(url="/employees", status_code=302)

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
    full_name: str = Form(...),
    username: str = Form(...),
    password: str = Form(""),
    hourly_wage: float = Form(...),
    work_schedule: str = Form(""),
    role: str = Form(...),
    is_active: bool = Form(False),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Check if username is taken by another user
    existing_user = db.query(User).filter(User.username == username, User.id != employee_id).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    employee.full_name = full_name
    employee.username = username
    if password:  # Only update password if provided
        employee.hashed_password = hash_password(password)
    employee.hourly_wage = hourly_wage
    employee.work_schedule = work_schedule
    employee.role = role
    employee.is_admin = (role == "admin")
    employee.is_active = is_active
    
    db.commit()
    
    return RedirectResponse(url=f"/employees/{employee_id}", status_code=302)

@app.get("/employees/{employee_id}/delete")
async def delete_employee(
    employee_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Don't allow deleting self
    if employee.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    # Deactivate instead of delete to preserve task history
    employee.is_active = False
    db.commit()
    
    return RedirectResponse(url="/employees", status_code=302)

# Utilities (Admin only)
@app.get("/utilities", response_class=HTMLResponse)
async def utilities_page(request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    utilities = db.query(UtilityCost).all()
    
    return templates.TemplateResponse("utilities.html", {
        "request": request,
        "current_user": current_user,
        "utilities": utilities
    })

@app.post("/utilities/new")
async def create_utility_cost(
    request: Request,
    name: str = Form(...),
    monthly_cost: float = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    # Check if utility with this name already exists
    existing_utility = db.query(UtilityCost).filter(UtilityCost.name == name).first()
    if existing_utility:
        # Update existing
        existing_utility.monthly_cost = monthly_cost
        existing_utility.last_updated = datetime.utcnow()
    else:
        # Create new
        utility = UtilityCost(
            name=name,
            monthly_cost=monthly_cost
        )
        db.add(utility)
    
    db.commit()
    
    return RedirectResponse(url="/utilities", status_code=302)

@app.post("/utilities/{utility_id}/delete")
async def delete_utility_cost(
    utility_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    utility = db.query(UtilityCost).filter(UtilityCost.id == utility_id).first()
    if not utility:
        raise HTTPException(status_code=404, detail="Utility not found")
    
    db.delete(utility)
    db.commit()
    
    return RedirectResponse(url="/utilities", status_code=302)

# Categories
@app.post("/categories/new")
async def create_category(
    request: Request,
    name: str = Form(...),
    type: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    # Check if category already exists
    existing_category = db.query(Category).filter(
        and_(Category.name == name, Category.type == type)
    ).first()
    
    if not existing_category:
        category = Category(name=name, type=type)
        db.add(category)
        db.commit()
    
    # Redirect based on type
    redirect_urls = {
        "ingredient": "/ingredients",
        "recipe": "/recipes",
        "batch": "/batches",
        "dish": "/dishes",
        "inventory": "/inventory"
    }
    
    return RedirectResponse(url=redirect_urls.get(type, "/"), status_code=302)

# Vendors
@app.post("/vendors/new")
async def create_vendor(
    request: Request,
    name: str = Form(...),
    contact_info: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    vendor = Vendor(
        name=name,
        contact_info=contact_info if contact_info else None
    )
    db.add(vendor)
    db.commit()
    
    return RedirectResponse(url="/ingredients", status_code=302)

# Par Unit Names
@app.post("/par_unit_names/new")
async def create_par_unit_name(
    request: Request,
    name: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    # Check if par unit name already exists
    existing_par_unit = db.query(ParUnitName).filter(ParUnitName.name == name).first()
    if not existing_par_unit:
        par_unit = ParUnitName(name=name)
        db.add(par_unit)
        db.commit()
    
    return RedirectResponse(url="/inventory", status_code=302)

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    current_user = get_current_user_optional(request, next(get_db()))
    return templates.TemplateResponse("error.html", {
        "request": request,
        "current_user": current_user,
        "status_code": 404,
        "detail": "Page not found"
    }, status_code=404)

@app.exception_handler(403)
async def forbidden_handler(request: Request, exc: HTTPException):
    current_user = get_current_user_optional(request, next(get_db()))
    return templates.TemplateResponse("error.html", {
        "request": request,
        "current_user": current_user,
        "status_code": 403,
        "detail": "Access forbidden"
    }, status_code=403)

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: HTTPException):
    current_user = get_current_user_optional(request, next(get_db()))
    return templates.TemplateResponse("error.html", {
        "request": request,
        "current_user": current_user,
        "status_code": 500,
        "detail": "Internal server error"
    }, status_code=500)