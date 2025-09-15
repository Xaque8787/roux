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
        "inventory_info": None,
        "use_par_unit": False,
        "par_unit_name": None,
        "par_unit_equals_info": None
    }
    
    # Check if this task has an inventory item with par unit settings
    if task.requires_made_amount and task.inventory_item:
        item = task.inventory_item
        
        # If inventory item has par unit settings, use par unit logic
        if item.par_unit_name and item.par_unit_equals_type:
            result["use_par_unit"] = True
            result["par_unit_name"] = item.par_unit_name.name
            
            # Add par unit equals information for display
            if item.par_unit_equals_type == "par_unit_itself":
                result["par_unit_equals_info"] = {
                    "type": "par_unit_itself",
                    "description": f"Each {item.par_unit_name.name} = 1 {item.par_unit_name.name}"
                }
            elif item.par_unit_equals_type == "custom" and item.par_unit_equals_amount and item.par_unit_equals_unit:
                result["par_unit_equals_info"] = {
                    "type": "custom",
                    "amount": item.par_unit_equals_amount,
                    "unit": item.par_unit_equals_unit,
                    "description": f"Each {item.par_unit_name.name} = {item.par_unit_equals_amount} {item.par_unit_equals_unit}"
                }
            elif item.par_unit_equals_type == "auto" and item.batch and not item.batch.variable_yield:
                auto_amount = item.par_unit_equals_calculated
                if auto_amount:
                    result["par_unit_equals_info"] = {
                        "type": "auto",
                        "amount": auto_amount,
                        "unit": item.batch.yield_unit,
                        "description": f"Each {item.par_unit_name.name} = {auto_amount} {item.batch.yield_unit}"
                    }
    
    # Add inventory information if available
    if task.inventory_item:
        from ..models import InventoryDayItem
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