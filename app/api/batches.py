from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session, joinedload
from ..database import get_db
from ..models import (Batch, RecipeIngredient, WEIGHT_CONVERSIONS, VOLUME_CONVERSIONS, 
                     BAKING_MEASUREMENTS, convert_weight, convert_volume)

router = APIRouter(prefix="/api/batches", tags=["batches-api"])

@router.get("/search")
async def search_batches(q: str = "", db: Session = Depends(get_db)):
    query = db.query(Batch).options(joinedload(Batch.recipe))
    
    if q:
        query = query.filter(Batch.recipe.has(name=q))
    
    batches = query.all()
    
    result = []
    for batch in batches:
        # Calculate cost per unit
        recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
        total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
        total_batch_cost = total_recipe_cost + batch.estimated_labor_cost
        cost_per_unit = total_batch_cost / batch.yield_amount if batch.yield_amount else 0
        
        batch_data = {
            "id": batch.id,
            "recipe_name": batch.recipe.name,
            "yield_amount": batch.yield_amount,
            "yield_unit": batch.yield_unit,
            "cost_per_unit": cost_per_unit,
            "category": batch.recipe.category.name if batch.recipe.category else None
        }
        result.append(batch_data)
    
    return result

@router.get("/all")
async def get_all_batches(db: Session = Depends(get_db)):
    batches = db.query(Batch).options(joinedload(Batch.recipe)).all()
    
    result = []
    for batch in batches:
        # Calculate cost per unit
        recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
        total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
        total_batch_cost = total_recipe_cost + batch.estimated_labor_cost
        cost_per_unit = total_batch_cost / batch.yield_amount if batch.yield_amount else 0
        
        batch_data = {
            "id": batch.id,
            "recipe_name": batch.recipe.name,
            "yield_amount": batch.yield_amount,
            "yield_unit": batch.yield_unit,
            "cost_per_unit": cost_per_unit,
            "category": batch.recipe.category.name if batch.recipe.category else None
        }
        result.append(batch_data)
    
    return result

@router.get("/{batch_id}/portion_units")
async def get_batch_portion_units(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Get recipe ingredients to determine usage type
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
    
    # Determine usage type from ingredients
    usage_type = None
    for ri in recipe_ingredients:
        if ri.ingredient and ri.ingredient.usage_type:
            usage_type = ri.ingredient.usage_type
            break
    
    # Get available units based on usage type
    available_units = []
    
    if usage_type == 'weight':
        available_units.extend(list(WEIGHT_CONVERSIONS.keys()))
    elif usage_type == 'volume':
        available_units.extend(list(VOLUME_CONVERSIONS.keys()))
    else:
        # Default to both if we can't determine
        available_units.extend(list(WEIGHT_CONVERSIONS.keys()))
        available_units.extend(list(VOLUME_CONVERSIONS.keys()))
    
    # Add baking measurements if any ingredient supports them
    for ri in recipe_ingredients:
        if ri.ingredient and ri.ingredient.has_baking_conversion:
            available_units.extend(list(BAKING_MEASUREMENTS.keys()))
            break
    
    # Remove duplicates and format response
    available_units = list(set(available_units))
    
    result = []
    for unit in available_units:
        result.append({
            "id": unit,
            "name": unit
        })
    
    return result

@router.get("/{batch_id}/cost_per_unit/{unit}")
async def get_batch_cost_per_unit(batch_id: int, unit: str, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    if batch.variable_yield:
        return {
            "batch_id": batch_id,
            "unit": unit,
            "expected_cost_per_unit": 0,
            "actual_cost_per_unit": 0,
            "error": "Variable yield batches cannot provide cost per unit"
        }
    
    # Calculate base costs
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
    total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
    
    # Expected cost (with estimated labor)
    expected_total_cost = total_recipe_cost + batch.estimated_labor_cost
    expected_cost_per_yield_unit = expected_total_cost / batch.yield_amount if batch.yield_amount else 0
    
    # Actual cost (with most recent actual labor)
    actual_total_cost = total_recipe_cost + batch.get_actual_labor_cost(db)
    actual_cost_per_yield_unit = actual_total_cost / batch.yield_amount if batch.yield_amount else 0
    
    # Convert to requested unit if different from yield unit
    expected_cost_per_unit = expected_cost_per_yield_unit
    actual_cost_per_unit = actual_cost_per_yield_unit
    
    if unit != batch.yield_unit:
        # Determine usage type from ingredients
        usage_type = None
        for ri in recipe_ingredients:
            if ri.ingredient and ri.ingredient.usage_type:
                usage_type = ri.ingredient.usage_type
                break
        
        try:
            if usage_type == 'weight' and batch.yield_unit in WEIGHT_CONVERSIONS and unit in WEIGHT_CONVERSIONS:
                conversion_factor = convert_weight(1, batch.yield_unit, unit)
                expected_cost_per_unit = expected_cost_per_yield_unit / conversion_factor
                actual_cost_per_unit = actual_cost_per_yield_unit / conversion_factor
            elif usage_type == 'volume' and batch.yield_unit in VOLUME_CONVERSIONS and unit in VOLUME_CONVERSIONS:
                conversion_factor = convert_volume(1, batch.yield_unit, unit)
                expected_cost_per_unit = expected_cost_per_yield_unit / conversion_factor
                actual_cost_per_unit = actual_cost_per_yield_unit / conversion_factor
            elif batch.yield_unit in WEIGHT_CONVERSIONS and unit in WEIGHT_CONVERSIONS:
                conversion_factor = convert_weight(1, batch.yield_unit, unit)
                expected_cost_per_unit = expected_cost_per_yield_unit / conversion_factor
                actual_cost_per_unit = actual_cost_per_yield_unit / conversion_factor
            elif batch.yield_unit in VOLUME_CONVERSIONS and unit in VOLUME_CONVERSIONS:
                conversion_factor = convert_volume(1, batch.yield_unit, unit)
                expected_cost_per_unit = expected_cost_per_yield_unit / conversion_factor
                actual_cost_per_unit = actual_cost_per_yield_unit / conversion_factor
        except ValueError:
            # Conversion failed, use original values
            pass
    
    return {
        "batch_id": batch_id,
        "unit": unit,
        "expected_cost_per_unit": round(expected_cost_per_unit, 4),
        "actual_cost_per_unit": round(actual_cost_per_unit, 4)
    }

@router.get("/{batch_id}/available_units")
async def get_batch_available_units(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Get recipe ingredients to determine usage type
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
    
    # Determine usage type from ingredients
    usage_type = None
    for ri in recipe_ingredients:
        if ri.ingredient and ri.ingredient.usage_type:
            usage_type = ri.ingredient.usage_type
            break
    
    # Get available units based on usage type
    available_units = []
    
    if usage_type == 'weight':
        available_units.extend(list(WEIGHT_CONVERSIONS.keys()))
    elif usage_type == 'volume':
        available_units.extend(list(VOLUME_CONVERSIONS.keys()))
    else:
        # Default to both if we can't determine
        available_units.extend(list(WEIGHT_CONVERSIONS.keys()))
        available_units.extend(list(VOLUME_CONVERSIONS.keys()))
    
    # Add baking measurements if any ingredient supports them
    for ri in recipe_ingredients:
        if ri.ingredient and ri.ingredient.has_baking_conversion:
            available_units.extend(list(BAKING_MEASUREMENTS.keys()))
            break
    
    # Remove duplicates
    available_units = list(set(available_units))
    
    return available_units

@router.get("/{batch_id}/recipe_cost")
async def get_batch_recipe_cost(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Calculate total recipe cost
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
    total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
    
    return {
        "batch_id": batch_id,
        "recipe_name": batch.recipe.name,
        "total_recipe_cost": total_recipe_cost,
        "estimated_labor_cost": batch.estimated_labor_cost,
        "actual_labor_cost": batch.get_actual_labor_cost(db)
    }