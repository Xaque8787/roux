from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Recipe, RecipeIngredient, WEIGHT_CONVERSIONS, VOLUME_CONVERSIONS, BAKING_MEASUREMENTS

router = APIRouter(prefix="/api/recipes", tags=["recipes-api"])

@router.get("/{recipe_id}/available_units")
async def get_recipe_available_units(recipe_id: int, db: Session = Depends(get_db)):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    # Get recipe ingredients to determine available units
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).all()
    
    available_units = set()
    
    for ri in recipe_ingredients:
        if ri.ingredient:
            # Add units based on ingredient usage type
            if ri.ingredient.usage_type == 'weight':
                available_units.update(WEIGHT_CONVERSIONS.keys())
            elif ri.ingredient.usage_type == 'volume':
                available_units.update(VOLUME_CONVERSIONS.keys())
            
            # Add baking measurements if ingredient supports them
            if ri.ingredient.has_baking_conversion:
                available_units.update(BAKING_MEASUREMENTS.keys())
    
    return list(available_units)