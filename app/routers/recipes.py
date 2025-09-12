from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import json
from ..database import get_db
from ..dependencies import require_manager_or_admin, get_current_user, require_admin
from ..models import Recipe, Category, RecipeIngredient

router = APIRouter(prefix="/recipes", tags=["recipes"])
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def recipes_page(request: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    recipes = db.query(Recipe).all()
    categories = db.query(Category).filter(Category.type == "recipe").all()
    
    return templates.TemplateResponse("recipes.html", {
        "request": request,
        "current_user": current_user,
        "recipes": recipes,
        "categories": categories
    })

@router.post("/new")
async def create_recipe(
    request: Request,
    name: str = Form(...),
    instructions: str = Form(""),
    category_id: int = Form(...),
    ingredients_data: str = Form(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    recipe = Recipe(
        name=name,
        instructions=instructions if instructions else None,
        category_id=category_id
    )
    
    db.add(recipe)
    db.flush()  # Get the recipe ID
    
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
    
    db.commit()
    
    return RedirectResponse(url="/recipes", status_code=302)

@router.get("/{recipe_id}", response_class=HTMLResponse)
async def recipe_detail(recipe_id: int, request: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
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

@router.get("/{recipe_id}/edit", response_class=HTMLResponse)
async def recipe_edit_page(recipe_id: int, request: Request, db: Session = Depends(get_db), current_user = Depends(require_manager_or_admin)):
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

@router.post("/{recipe_id}/edit")
async def update_recipe(
    recipe_id: int,
    request: Request,
    name: str = Form(...),
    instructions: str = Form(""),
    category_id: int = Form(...),
    ingredients_data: str = Form(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    recipe.name = name
    recipe.instructions = instructions if instructions else None
    recipe.category_id = category_id
    
    # Remove existing ingredients
    db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).delete()
    
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
    
    db.commit()
    
    return RedirectResponse(url=f"/recipes/{recipe_id}", status_code=302)

@router.get("/{recipe_id}/delete")
async def delete_recipe(recipe_id: int, db: Session = Depends(get_db), current_user = Depends(require_admin)):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    # Delete recipe ingredients first
    db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).delete()
    
    db.delete(recipe)
    db.commit()
    
    return RedirectResponse(url="/recipes", status_code=302)