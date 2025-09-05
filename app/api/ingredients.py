from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Ingredient, WEIGHT_CONVERSIONS, VOLUME_CONVERSIONS, BAKING_MEASUREMENTS

router = APIRouter(prefix="/api/ingredients", tags=["ingredients-api"])

@router.get("/all")
async def get_all_ingredients(db: Session = Depends(get_db)):
    ingredients = db.query(Ingredient).all()
    result = []
    
    for ingredient in ingredients:
        available_units = ingredient.get_available_units()
        
        ingredient_data = {
            "id": ingredient.id,
            "name": ingredient.name,
            "category": ingredient.category.name if ingredient.category else None,
            "available_units": available_units
        }
        result.append(ingredient_data)
    
    return result

@router.get("/{ingredient_id}/cost_per_unit/{unit}")
async def get_ingredient_cost_per_unit(ingredient_id: int, unit: str, db: Session = Depends(get_db)):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    cost_per_unit = ingredient.get_cost_per_unit(unit)
    
    return {
        "ingredient_id": ingredient_id,
        "unit": unit,
        "cost_per_unit": cost_per_unit
    }