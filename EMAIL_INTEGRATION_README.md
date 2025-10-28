# Email Report Integration - Implementation Summary

This document describes the email reporting feature that has been integrated into the Food Cost Management System.

## Overview

The system now supports sending daily inventory reports via email using Resend (https://resend.com), a modern email service for developers.

## What Was Implemented

### 1. Database Changes

**Migration Script**: `migrations/add_employee_email.py`
- Adds `email` column to the `users` table (nullable)
- Creates an index on the email column for faster lookups
- **Action Required**: Run this migration before using the feature

```bash
python migrations/add_employee_email.py
```

### 2. Employee Email Management

Email fields have been added to all employee management interfaces:

- **Employee Creation Form** (`/employees`): Optional email field
- **Employee Edit Form** (`/employees/{id}/edit`): Edit email addresses
- **Employee Detail View** (`/employees/{id}`): Display email with mailto link
- **Admin Setup Wizard** (`/setup`): Email field for initial admin user

### 3. Email Service Integration

**New Files**:
- `app/utils/email.py`: Core email functionality using Resend
  - `send_email()`: Send emails to multiple recipients
  - `generate_report_email_html()`: Generate beautiful HTML email templates

**Dependencies**:
- Added `resend==0.8.0` to `requirements.txt`

### 4. Report Email Functionality

**New API Endpoint**: `/api/inventory/{day_id}/email-report`
- POST endpoint to send daily reports
- Requires manager or admin permissions
- Accepts list of recipient employee IDs
- Generates comprehensive HTML report

**Frontend Components**:
- Email Report button on inventory report page
- Modal dialog to select recipients
- Shows only active managers/admins with email addresses
- Select All / Deselect All functionality
- Real-time sending status with spinner

### 5. Email Report Content

The email includes four main sections:

1. **Day Summary**
   - Total tasks
   - Completed tasks
   - Total labor cost
   - Total time logged

2. **Task Report**
   - List of all tasks with status
   - Assigned employees
   - Time spent per task
   - Labor cost per task

3. **Inventory Status**
   - Current quantity vs. par levels
   - Status indicators (Critical, Low, Good)
   - Color-coded alerts

4. **Time Analysis**
   - Hours worked per employee
   - Summary cards for each team member

## Setup Instructions

### 1. Sign Up for Resend

1. Go to https://resend.com
2. Create a free account (3,000 emails/month free)
3. Get your API key from the dashboard
4. Verify your domain (or use their test domain for development)

### 2. Configure Environment Variables

Add these variables to your `.env` file:

```bash
# Email Configuration (Resend)
RESEND_API_KEY=re_your_actual_api_key_here
RESEND_FROM_EMAIL=reports@yourdomain.com
```

**Note**: For testing, you can use Resend's test email format:
```bash
RESEND_FROM_EMAIL=onboarding@resend.dev
```

### 3. Run Database Migration

```bash
# Make sure you're in the project directory
cd /path/to/project

# Run the migration
python migrations/add_employee_email.py

# Confirm when prompted
```

### 4. Add Employee Emails

1. Log in as an admin
2. Go to Employee Management (`/employees`)
3. Edit existing employees or create new ones
4. Add email addresses for managers and admins who should receive reports

### 5. Test Email Reports

1. Navigate to Inventory page
2. View a finalized inventory day report
3. Click "Email Report" button
4. Select recipients from the modal
5. Click "Send Report"
6. Check recipient inboxes

## Usage

### Sending a Daily Report

1. **Navigate to Report**: Go to `/inventory` and click on a finalized day to view its report
2. **Open Email Modal**: Click the "Email Report" button (top right)
3. **Select Recipients**: Check the boxes next to managers/admins who should receive the report
4. **Send**: Click "Send Report" button
5. **Confirmation**: You'll see a success message with the number of recipients

### Who Can Send Reports?

- Only managers and admins can send email reports
- Regular users do not have access to this feature

### Who Can Receive Reports?

- Only active employees with the role of "manager" or "admin"
- Only employees who have an email address configured
- Inactive employees are excluded automatically

## Email Template Design

The email report features:

- Modern, responsive HTML design
- Professional gradient header
- Organized sections with icons
- Color-coded status badges
- Mobile-friendly layout
- Clean typography and spacing
- Summary cards with key metrics
- Data tables for detailed information

## Security Considerations

- Email addresses are stored in plaintext (standard practice)
- Only managers/admins can trigger email sends
- Resend API key is stored securely in environment variables
- Email sending is logged in application
- Failed sends return clear error messages

## Troubleshooting

### "RESEND_API_KEY is not configured"

**Solution**: Add `RESEND_API_KEY` to your `.env` file and restart the application.

### "RESEND_FROM_EMAIL is not configured"

**Solution**: Add `RESEND_FROM_EMAIL` to your `.env` file and restart the application.

### "No valid recipients found"

**Solution**: Ensure selected employees have email addresses and are active.

### Email not received

**Possible causes**:
1. Check spam/junk folder
2. Verify email address is correct in employee profile
3. Confirm Resend domain is verified (for production)
4. Check Resend dashboard for delivery status

### Migration fails

**Solution**:
1. Ensure database file exists and is accessible
2. Check you're running from the correct directory
3. Verify database path in error message
4. Manually specify database path: `python migrations/add_employee_email.py /path/to/database.db`

## Cost Considerations

### Resend Free Tier
- 3,000 emails per month
- 100 emails per day
- Perfect for small to medium restaurants

### When to Upgrade
- If sending reports to 5+ people daily: ~150 emails/month (well within free tier)
- If sending multiple reports per day: May approach limits
- Paid plan starts at $20/month for 50,000 emails

## Future Enhancements

Possible improvements for later:

1. **Scheduled Reports**: Automatically send reports at end of day
2. **Custom Templates**: Let admins customize email content
3. **Report History**: Track who received which reports
4. **PDF Attachments**: Include PDF version of report
5. **Weekly Summaries**: Aggregate weekly performance reports
6. **Alert Emails**: Send alerts for critical inventory levels
7. **Reply-to Configuration**: Set custom reply-to addresses

## Technical Details

### Files Modified

1. `app/models.py`: Added `email` column to User model
2. `app/routers/auth.py`: Updated setup wizard
3. `app/routers/employees.py`: Added email handling to forms
4. `templates/setup.html`: Email field in setup form
5. `templates/employees.html`: Email field in create form
6. `templates/employee_edit.html`: Email field in edit form
7. `templates/employee_detail.html`: Display email address
8. `templates/inventory_report.html`: Email button and modal
9. `requirements.txt`: Added resend package
10. `.env.example`: Added email configuration examples

### Files Created

1. `migrations/add_employee_email.py`: Database migration script
2. `app/utils/email.py`: Email service utilities
3. `app/api/email_reports.py`: Email report API endpoint
4. `EMAIL_INTEGRATION_README.md`: This documentation file

### API Endpoints

**POST** `/api/inventory/{day_id}/email-report`
- **Auth**: Requires manager or admin role
- **Input**: Form data with `recipient_ids` (list of integers)
- **Output**: JSON with success status and recipient count
- **Errors**: 400 (bad request), 404 (not found), 500 (server error)

## Support

If you encounter issues:

1. Check this documentation
2. Verify environment variables are set correctly
3. Ensure database migration was run successfully
4. Check Resend dashboard for delivery logs
5. Review application logs for error messages

## Conclusion

The email reporting feature is now fully integrated and ready to use. Simply configure your Resend account, run the migration, add employee emails, and start sending professional daily reports!
