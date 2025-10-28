import os
import resend
from typing import List

resend.api_key = os.getenv("RESEND_API_KEY")

async def send_email(
    to_emails: List[str],
    subject: str,
    html_body: str,
    from_email: str = None
) -> dict:
    """
    Send an email using Resend API

    Args:
        to_emails: List of recipient email addresses
        subject: Email subject line
        html_body: HTML content of the email
        from_email: Sender email address (defaults to RESEND_FROM_EMAIL env var)

    Returns:
        dict: Response from Resend API

    Raises:
        Exception: If RESEND_API_KEY is not configured or email sending fails
    """
    if not resend.api_key:
        raise Exception("RESEND_API_KEY is not configured in environment variables")

    if not from_email:
        from_email = os.getenv("RESEND_FROM_EMAIL")
        if not from_email:
            raise Exception("RESEND_FROM_EMAIL is not configured in environment variables")

    if not to_emails or len(to_emails) == 0:
        raise Exception("At least one recipient email address is required")

    try:
        params = {
            "from": from_email,
            "to": to_emails,
            "subject": subject,
            "html": html_body,
        }

        response = resend.Emails.send(params)
        return response
    except Exception as e:
        raise Exception(f"Failed to send email: {str(e)}")


def generate_report_email_html(
    day_date: str,
    day_summary: dict,
    task_report: dict,
    inventory_status: dict,
    time_analysis: dict
) -> str:
    """
    Generate HTML email content for daily report

    Args:
        day_date: Date of the report (formatted string)
        day_summary: Summary data for the day
        task_report: Task completion data
        inventory_status: Current inventory status
        time_analysis: Time tracking and analysis data

    Returns:
        str: HTML content for the email
    """
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily Report - {day_date}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f4f4f4;
            margin: 0;
            padding: 0;
        }}
        .container {{
            max-width: 800px;
            margin: 20px auto;
            background-color: #ffffff;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
            font-weight: 600;
        }}
        .header p {{
            margin: 5px 0 0 0;
            opacity: 0.9;
            font-size: 16px;
        }}
        .content {{
            padding: 30px;
        }}
        .section {{
            margin-bottom: 30px;
        }}
        .section h2 {{
            color: #667eea;
            font-size: 20px;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e0e0e0;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .summary-card {{
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 6px;
            border-left: 4px solid #667eea;
        }}
        .summary-card h3 {{
            margin: 0 0 5px 0;
            font-size: 14px;
            color: #666;
            font-weight: 500;
        }}
        .summary-card p {{
            margin: 0;
            font-size: 24px;
            font-weight: 600;
            color: #333;
        }}
        .table-container {{
            overflow-x: auto;
            margin-top: 15px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e0e0e0;
        }}
        th {{
            background-color: #f8f9fa;
            font-weight: 600;
            color: #555;
        }}
        tr:hover {{
            background-color: #f8f9fa;
        }}
        .status-badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 500;
        }}
        .status-completed {{
            background-color: #d4edda;
            color: #155724;
        }}
        .status-in-progress {{
            background-color: #fff3cd;
            color: #856404;
        }}
        .status-pending {{
            background-color: #d1ecf1;
            color: #0c5460;
        }}
        .status-critical {{
            background-color: #f8d7da;
            color: #721c24;
        }}
        .status-warning {{
            background-color: #fff3cd;
            color: #856404;
        }}
        .status-ok {{
            background-color: #d4edda;
            color: #155724;
        }}
        .footer {{
            background-color: #f8f9fa;
            padding: 20px 30px;
            text-align: center;
            color: #666;
            font-size: 14px;
        }}
        .footer p {{
            margin: 5px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Daily Operations Report</h1>
            <p>{day_date}</p>
        </div>

        <div class="content">
            <!-- Day Summary Section -->
            <div class="section">
                <h2>📊 Day Summary</h2>
                <div class="summary-grid">
                    <div class="summary-card">
                        <h3>Total Tasks</h3>
                        <p>{day_summary.get('total_tasks', 0)}</p>
                    </div>
                    <div class="summary-card">
                        <h3>Completed Tasks</h3>
                        <p>{day_summary.get('completed_tasks', 0)}</p>
                    </div>
                    <div class="summary-card">
                        <h3>Total Labor Cost</h3>
                        <p>${day_summary.get('total_labor_cost', 0):.2f}</p>
                    </div>
                    <div class="summary-card">
                        <h3>Total Time Logged</h3>
                        <p>{day_summary.get('total_time_hours', 0):.1f} hrs</p>
                    </div>
                </div>
            </div>

            <!-- Task Report Section -->
            <div class="section">
                <h2>✅ Task Report</h2>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Task</th>
                                <th>Assigned To</th>
                                <th>Status</th>
                                <th>Time</th>
                                <th>Labor Cost</th>
                            </tr>
                        </thead>
                        <tbody>
"""

    for task in task_report.get('tasks', []):
        status_class = {
            'completed': 'status-completed',
            'in_progress': 'status-in-progress',
            'not_started': 'status-pending'
        }.get(task.get('status', 'pending'), 'status-pending')

        html += f"""
                            <tr>
                                <td>{task.get('description', 'N/A')}</td>
                                <td>{task.get('assigned_to', 'Unassigned')}</td>
                                <td><span class="status-badge {status_class}">{task.get('status', 'Pending').replace('_', ' ').title()}</span></td>
                                <td>{task.get('time_minutes', 0)} min</td>
                                <td>${task.get('labor_cost', 0):.2f}</td>
                            </tr>
"""

    html += """
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Inventory Status Section -->
            <div class="section">
                <h2>📦 Inventory Status</h2>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Item</th>
                                <th>Current</th>
                                <th>Par Level</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
"""

    for item in inventory_status.get('items', []):
        status = item.get('status', 'ok')
        status_class = {
            'critical': 'status-critical',
            'warning': 'status-warning',
            'ok': 'status-ok'
        }.get(status, 'status-ok')

        status_text = {
            'critical': 'Critical',
            'warning': 'Low',
            'ok': 'Good'
        }.get(status, 'Good')

        html += f"""
                            <tr>
                                <td>{item.get('name', 'N/A')}</td>
                                <td>{item.get('current_quantity', 0):.1f}</td>
                                <td>{item.get('par_level', 0):.1f}</td>
                                <td><span class="status-badge {status_class}">{status_text}</span></td>
                            </tr>
"""

    html += """
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Time Analysis Section -->
            <div class="section">
                <h2>⏱️ Time Analysis</h2>
                <div class="summary-grid">
"""

    for employee in time_analysis.get('employees', []):
        html += f"""
                    <div class="summary-card">
                        <h3>{employee.get('name', 'Unknown')}</h3>
                        <p>{employee.get('hours_worked', 0):.1f} hrs</p>
                    </div>
"""

    html += """
                </div>
            </div>
        </div>

        <div class="footer">
            <p><strong>Food Cost Management System</strong></p>
            <p>This is an automated report. Please do not reply to this email.</p>
        </div>
    </div>
</body>
</html>
"""

    return html
