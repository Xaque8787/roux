from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from datetime import datetime, timedelta
from ..database import get_db
from ..models import Task, Batch, InventoryItem, User, WEIGHT_CONVERSIONS, VOLUME_CONVERSIONS, BAKING_MEASUREMENTS
from ..auth import get_current_user
from ..utils.datetime_utils import get_naive_local_time

router = APIRouter(prefix="/api/tasks", tags=["tasks-api"])

class EditTimeRequest(BaseModel):
    total_minutes: int
    finished_at: str

class EditAssignedEmployeesRequest(BaseModel):
    employee_ids: list[int]

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

@router.get("/{task_id}")
async def get_task_details(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "id": task.id,
        "description": task.description,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
        "total_time_minutes": task.total_time_minutes,
        "total_pause_time": task.total_pause_time,
        "status": task.status
    }

@router.put("/{task_id}/edit_time")
async def edit_task_time(
    task_id: int,
    request: EditTimeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from ..models import TaskSession

    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Only admins and managers can edit task times")

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != "completed":
        raise HTTPException(status_code=400, detail="Can only edit completed tasks")

    if not task.started_at:
        raise HTTPException(status_code=400, detail="Task has no start time")

    finished_at_dt = datetime.fromisoformat(request.finished_at)

    # Update the last session's ended_at to match the new finished_at
    # This is critical because total_time_minutes is calculated from sessions
    last_session = db.query(TaskSession).filter(
        TaskSession.task_id == task_id
    ).order_by(TaskSession.started_at.desc()).first()

    if last_session:
        # Get all sessions to determine if we need special handling for multi-session tasks
        all_sessions = db.query(TaskSession).filter(
            TaskSession.task_id == task_id
        ).order_by(TaskSession.started_at.asc()).all()

        if len(all_sessions) > 1:
            # Multi-session task: use total_minutes to calculate the last session's end time
            # Calculate time from all previous sessions (excluding the last one)
            previous_sessions_minutes = sum(
                session.duration_minutes for session in all_sessions[:-1]
            )
            # Calculate how many minutes the last session should be
            last_session_minutes = request.total_minutes - previous_sessions_minutes

            # Validate that the last session would have positive duration
            if last_session_minutes < 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Total time must be at least {previous_sessions_minutes} minutes (duration of previous sessions)"
                )

            # Calculate the end time for the last session
            # ended_at = started_at + (last_session_minutes * 60) + pause_duration
            last_session_seconds = (last_session_minutes * 60) + last_session.pause_duration
            last_session.ended_at = last_session.started_at + timedelta(seconds=last_session_seconds)

            # Also update task.finished_at to match
            task.finished_at = last_session.ended_at
        else:
            # Single session task: directly use the finished_at_dt
            # Validate against the session's start time
            if finished_at_dt <= last_session.started_at:
                raise HTTPException(status_code=400, detail="Finish time must be after start time")

            last_session.ended_at = finished_at_dt
            task.finished_at = finished_at_dt
    else:
        # No sessions exist (edge case - shouldn't happen for completed tasks)
        # Fall back to just updating task.finished_at
        if finished_at_dt <= task.started_at:
            raise HTTPException(status_code=400, detail="Finish time must be after start time")
        task.finished_at = finished_at_dt

    db.commit()

    return {
        "success": True,
        "message": "Task time updated successfully",
        "task": {
            "id": task.id,
            "started_at": task.started_at.isoformat(),
            "finished_at": task.finished_at.isoformat(),
            "total_time_minutes": task.total_time_minutes,
            "labor_cost": task.labor_cost
        }
    }

@router.put("/{task_id}/edit_assigned_employees")
async def edit_assigned_employees(
    task_id: int,
    request: EditAssignedEmployeesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Only admins and managers can edit task assignments")

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != "completed":
        raise HTTPException(status_code=400, detail="Can only edit completed tasks")

    if not request.employee_ids:
        raise HTTPException(status_code=400, detail="At least one employee must be assigned")

    employee_ids = request.employee_ids
    employees = db.query(User).filter(User.id.in_(employee_ids)).all()

    if len(employees) != len(employee_ids):
        raise HTTPException(status_code=404, detail="One or more employees not found")

    if len(employee_ids) == 1:
        task.assigned_to_id = employee_ids[0]
        task.assigned_employee_ids = None
    else:
        task.assigned_to_id = employee_ids[0]
        task.assigned_employee_ids = ",".join(str(emp_id) for emp_id in employee_ids)

    db.commit()

    return {
        "success": True,
        "message": "Task assignments updated successfully",
        "task": {
            "id": task.id,
            "assigned_to_id": task.assigned_to_id,
            "assigned_employee_ids": task.assigned_employee_ids
        }
    }