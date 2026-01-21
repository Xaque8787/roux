from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import json
from ..database import get_db
from ..dependencies import require_manager_or_admin, get_current_user, require_admin
from ..models import Recipe, Category, RecipeIngredient, RecipeBatchPortion
from ..utils.template_helpers import setup_template_filters
from ..utils.slugify import generate_unique_slug

router = APIRouter(prefix="/recipes", tags=["recipes"])
templates = setup_template_filters(Jinja2Templates(directory="templates"))

@router.get("/", response_class=HTMLResponse)
async def recipes_page(request: Request, show_deleted: bool = False, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    if show_deleted:
        recipes = db.query(Recipe).all()
    else:
        recipes = db.query(Recipe).filter(Recipe.deleted == False).all()

    categories = db.query(Category).filter(Category.type == "recipe").all()

    return templates.TemplateResponse("recipes.html", {
        "request": request,
        "current_user": current_user,
        "recipes": recipes,
        "categories": categories,
        "show_deleted": show_deleted
    })

@router.post("/new")
async def create_recipe(
    request: Request,
    name: str = Form(...),
    instructions: str = Form(""),
    category_id: int = Form(None),
    ingredients_data: str = Form(...),
    batch_portions_data: str = Form("[]"),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    slug = generate_unique_slug(db, Recipe, name)

    recipe = Recipe(
        name=name,
        slug=slug,
        instructions=instructions if instructions else None,
        category_id=category_id if category_id else None
    )

    db.add(recipe)
    db.flush()

    # Parse and add ingredients
    try:
        ingredients = json.loads(ingredients_data)
        for ingredient_data in ingredients:
            recipe_ingredient = RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_id=ingredient_data['ingredient_id'],
                unit=ingredient_data['unit'],
                quantity=ingredient_data['quantity']
            )
            db.add(recipe_ingredient)
    except (json.JSONDecodeError, KeyError) as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid ingredients data")

    # Parse and add batch portions
    try:
        batch_portions = json.loads(batch_portions_data)
        for batch_data in batch_portions:
            recipe_batch_portion = RecipeBatchPortion(
                recipe_id=recipe.id,
                batch_id=batch_data['batch_id'],
                portion_size=batch_data.get('portion_size'),
                portion_unit=batch_data.get('unit'),
                use_recipe_portion=batch_data.get('use_recipe_portion', False),
                recipe_portion_percent=batch_data.get('recipe_portion_percent')
            )
            db.add(recipe_batch_portion)
    except (json.JSONDecodeError, KeyError) as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid batch portions data")

    db.commit()

    return RedirectResponse(url=f"/recipes/{slug}", status_code=302)

@router.get("/{slug}", response_class=HTMLResponse)
async def recipe_detail(slug: str, request: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    recipe = db.query(Recipe).filter(Recipe.slug == slug).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe.id).all()
    recipe_batch_portions = db.query(RecipeBatchPortion).filter(RecipeBatchPortion.recipe_id == recipe.id).all()

    ingredients_cost = sum(ri.cost for ri in recipe_ingredients)
    batch_portions_cost = sum(rbp.get_total_cost(db) for rbp in recipe_batch_portions)
    total_cost = ingredients_cost + batch_portions_cost

    return templates.TemplateResponse("recipe_detail.html", {
        "request": request,
        "current_user": current_user,
        "recipe": recipe,
        "recipe_ingredients": recipe_ingredients,
        "recipe_batch_portions": recipe_batch_portions,
        "total_cost": total_cost,
        "db": db
    })

@router.get("/{slug}/edit", response_class=HTMLResponse)
async def recipe_edit_page(slug: str, request: Request, db: Session = Depends(get_db), current_user = Depends(require_manager_or_admin)):
    recipe = db.query(Recipe).filter(Recipe.slug == slug).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    categories = db.query(Category).filter(Category.type == "recipe").all()
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe.id).all()
    recipe_batch_portions = db.query(RecipeBatchPortion).filter(RecipeBatchPortion.recipe_id == recipe.id).all()

    return templates.TemplateResponse("recipe_edit.html", {
        "request": request,
        "current_user": current_user,
        "recipe": recipe,
        "categories": categories,
        "recipe_ingredients": recipe_ingredients,
        "recipe_batch_portions": recipe_batch_portions,
        "db": db
    })

@router.post("/{slug}/edit")
async def update_recipe(
    slug: str,
    request: Request,
    name: str = Form(...),
    instructions: str = Form(""),
    category_id: int = Form(None),
    ingredients_data: str = Form(...),
    batch_portions_data: str = Form("[]"),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    recipe = db.query(Recipe).filter(Recipe.slug == slug).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    if recipe.name != name:
        recipe.slug = generate_unique_slug(db, Recipe, name, exclude_id=recipe.id)

    recipe.name = name
    recipe.instructions = instructions if instructions else None
    recipe.category_id = category_id if category_id else None

    # Remove existing ingredients
    db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe.id).delete()

    # Parse and add new ingredients
    try:
        ingredients = json.loads(ingredients_data)
        for ingredient_data in ingredients:
            recipe_ingredient = RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_id=ingredient_data['ingredient_id'],
                unit=ingredient_data['unit'],
                quantity=ingredient_data['quantity']
            )
            db.add(recipe_ingredient)
    except (json.JSONDecodeError, KeyError) as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid ingredients data")

    # Remove existing batch portions
    db.query(RecipeBatchPortion).filter(RecipeBatchPortion.recipe_id == recipe.id).delete()

    # Parse and add new batch portions
    try:
        batch_portions = json.loads(batch_portions_data)
        for batch_data in batch_portions:
            recipe_batch_portion = RecipeBatchPortion(
                recipe_id=recipe.id,
                batch_id=batch_data['batch_id'],
                portion_size=batch_data.get('portion_size'),
                portion_unit=batch_data.get('unit'),
                use_recipe_portion=batch_data.get('use_recipe_portion', False),
                recipe_portion_percent=batch_data.get('recipe_portion_percent')
            )
            db.add(recipe_batch_portion)
    except (json.JSONDecodeError, KeyError) as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid batch portions data")

    db.commit()

    return RedirectResponse(url=f"/recipes/{recipe.slug}", status_code=302)

@router.get("/{slug}/delete")
async def delete_recipe(slug: str, db: Session = Depends(get_db), current_user = Depends(require_admin)):
    recipe = db.query(Recipe).filter(Recipe.slug == slug).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    recipe.deleted = True
    db.commit()

    return RedirectResponse(url="/recipes", status_code=302)

@router.get("/{slug}/restore")
async def restore_recipe(slug: str, db: Session = Depends(get_db), current_user = Depends(require_admin)):
    recipe = db.query(Recipe).filter(Recipe.slug == slug).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    recipe.deleted = False
    db.commit()

    return RedirectResponse(url="/recipes?show_deleted=true", status_code=302)