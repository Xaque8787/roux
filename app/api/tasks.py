from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session, joinedload
from ..database import get_db
from ..models import Task, Batch, InventoryItem, WEIGHT_CONVERSIONS, VOLUME_CONVERSIONS, BAKING_MEASUREMENTS

router = APIRouter(prefix="/api/tasks", tags=["tasks-api"])

@router.get("/{task_id}/scale_options")
async def get_task_scale_options(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).options(joinedload(Task.batch)).filter(Task.id == task_id).first()
    if not task or not task.batch:
        raise HTTPException(status_code=404, detail="Task or batch not found")
    
    scales = task.batch.get_available_scales()
    
    result = []
    for scale_key, scale_factor, scale_label in scales:
        if task.batch.yield_amount:
            yield_amount = task.batch.get_scaled_yield(scale_factor)
            yield_text = f"{yield_amount} {task.batch.yield_unit}"
        else:
            yield_text = "Variable yield"
        
        result.append({
            "key": scale_key,
            "factor": scale_factor,
            "label": scale_label,
            "yield": yield_text
        })
    
    return result

@router.get("/{task_id}/finish_requirements")
async def get_task_finish_requirements(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).options(
        joinedload(Task.batch),
        joinedload(Task.inventory_item)
    ).filter(Task.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    result = {
        "requires_made_amount": task.requires_made_amount,
        "available_units": [],
        "inventory_info": None
    }
    
    if task.requires_made_amount and task.batch:
        # Get available units for the batch
        if task.batch.yield_unit:
            # Start with the batch's yield unit
            available_units = [task.batch.yield_unit]
            
            # Add compatible units based on the yield unit type
            if task.batch.yield_unit in WEIGHT_CONVERSIONS:
                available_units.extend([unit for unit in WEIGHT_CONVERSIONS.keys() if unit != task.batch.yield_unit])
            elif task.batch.yield_unit in VOLUME_CONVERSIONS:
                available_units.extend([unit for unit in VOLUME_CONVERSIONS.keys() if unit != task.batch.yield_unit])
            
            result["available_units"] = available_units
        else:
            # Fallback to common units
            result["available_units"] = ["lb", "oz", "gal", "qt", "cup"]
    
    # Add inventory information if available
    if task.inventory_item:
        from ..routers.inventory import InventoryDayItem
        day_item = db.query(InventoryDayItem).filter(
            InventoryDayItem.day_id == task.day_id,
            InventoryDayItem.inventory_item_id == task.inventory_item.id
        ).first()
        
        if day_item:
            result["inventory_info"] = {
                "current": day_item.quantity,
                "par_level": task.inventory_item.par_level,
                "par_unit_name": task.inventory_item.par_unit_name.name if task.inventory_item.par_unit_name else "units"
            }
    
    return result