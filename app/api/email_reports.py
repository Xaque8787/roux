from fastapi import APIRouter, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..dependencies import require_manager_or_admin
from ..models import InventoryDay, InventoryDayItem, Task, User, InventoryItem
from ..utils.email import send_email, generate_report_email_html
from datetime import datetime

router = APIRouter(prefix="/api/inventory", tags=["email_reports"])

@router.post("/{day_id}/email-report")
async def send_inventory_report_email(
    day_id: int,
    recipient_ids: List[int] = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin)
):
    """
    Send inventory report via email to selected recipients
    """
    try:
        inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
        if not inventory_day:
            raise HTTPException(status_code=404, detail="Inventory day not found")

        recipients = db.query(User).filter(
            User.id.in_(recipient_ids),
            User.email.isnot(None),
            User.is_active == True
        ).all()

        if not recipients:
            raise HTTPException(status_code=400, detail="No valid recipients found with email addresses")

        recipient_emails = [r.email for r in recipients]

        tasks = db.query(Task).filter(Task.day_id == day_id).all()
        completed_tasks = [t for t in tasks if t.finished_at is not None]

        day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == day_id).all()

        day_summary = {
            'total_tasks': len(tasks),
            'completed_tasks': len(completed_tasks),
            'total_labor_cost': sum(t.labor_cost for t in completed_tasks),
            'total_time_hours': sum(t.total_time_minutes for t in completed_tasks) / 60
        }

        task_report = {
            'tasks': []
        }
        for task in tasks:
            task_info = {
                'description': task.description or 'N/A',
                'assigned_to': task.assigned_to.full_name if task.assigned_to else 'Unassigned',
                'status': task.status,
                'time_minutes': task.total_time_minutes if task.finished_at else 0,
                'labor_cost': task.labor_cost if task.finished_at else 0
            }
            task_report['tasks'].append(task_info)

        inventory_status = {
            'items': []
        }
        for day_item in day_items:
            if day_item.inventory_item:
                quantity = day_item.quantity
                par_level = day_item.inventory_item.par_level

                if quantity < par_level * 0.25:
                    status = 'critical'
                elif quantity < par_level * 0.5:
                    status = 'warning'
                else:
                    status = 'ok'

                inventory_status['items'].append({
                    'name': day_item.inventory_item.name,
                    'current_quantity': quantity,
                    'par_level': par_level,
                    'status': status
                })

        employee_time = {}
        for task in completed_tasks:
            if task.assigned_to:
                emp_name = task.assigned_to.full_name or task.assigned_to.username
                if emp_name not in employee_time:
                    employee_time[emp_name] = 0
                employee_time[emp_name] += task.total_time_minutes

        time_analysis = {
            'employees': [
                {
                    'name': name,
                    'hours_worked': minutes / 60
                }
                for name, minutes in employee_time.items()
            ]
        }

        day_date = inventory_day.date.strftime('%B %d, %Y')

        html_body = generate_report_email_html(
            day_date=day_date,
            day_summary=day_summary,
            task_report=task_report,
            inventory_status=inventory_status,
            time_analysis=time_analysis
        )

        subject = f"Daily Operations Report - {day_date}"

        await send_email(
            to_emails=recipient_emails,
            subject=subject,
            html_body=html_body
        )

        return JSONResponse(
            content={
                "success": True,
                "message": f"Report sent successfully to {len(recipient_emails)} recipient(s)",
                "recipients_count": len(recipient_emails)
            },
            status_code=200
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")
