# Quick Start Guide - Email Reports

## Step 1: Run Database Migration

```bash
cd /path/to/project
python migrations/add_employee_email.py
```

Answer "yes" when prompted.

## Step 2: Get Resend API Key

1. Go to https://resend.com
2. Sign up for free account (3,000 emails/month free)
3. Get your API key from dashboard

## Step 3: Configure Environment

Add to your `.env` file:

```bash
RESEND_API_KEY=re_your_actual_api_key_here
RESEND_FROM_EMAIL=onboarding@resend.dev
```

**Note**: Use `onboarding@resend.dev` for testing, or verify your own domain.

## Step 4: Install Dependencies & Restart

```bash
# If using Docker:
docker-compose down
docker-compose build
docker-compose up -d

# If running bare metal:
pip install -r requirements.txt
# Restart your application
```

## Step 5: Add Employee Emails

1. Go to `/employees`
2. Edit manager/admin users
3. Add their email addresses
4. Save

## Step 6: Send Your First Report

1. Go to `/inventory`
2. Click on a finalized day
3. Click "Email Report" button
4. Select recipients
5. Click "Send Report"
6. Check email inbox!

## That's It!

Your email reporting system is now live and ready to use.

## Troubleshooting

**Error: "RESEND_API_KEY is not configured"**
- Solution: Add the key to `.env` and restart

**Error: "No valid recipients found"**
- Solution: Make sure employees have emails and are active

**Email not received?**
- Check spam folder
- Verify email address is correct
- Check Resend dashboard for delivery logs

## Support

See `EMAIL_INTEGRATION_README.md` for detailed documentation.
