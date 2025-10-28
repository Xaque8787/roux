# Email Integration Troubleshooting Guide

## Common Issues and Solutions

### Issue: "Invalid `from` field" Error

**Error message:**
```
Failed to send email: Invalid `from` field. The email address needs to follow the `email@example.com` or `Name <email@example.com>` format.
```

**Cause:**
You've set `RESEND_FROM_EMAIL` to a domain name instead of a complete email address.

**❌ Wrong:**
```bash
RESEND_FROM_EMAIL=reports.pospiros.pizza
RESEND_FROM_EMAIL=pospiros.pizza
```

**✅ Correct:**
```bash
RESEND_FROM_EMAIL=reports@pospiros.pizza
RESEND_FROM_EMAIL=noreply@pospiros.pizza
RESEND_FROM_EMAIL=daily-reports@pospiros.pizza
```

**How to fix:**

1. Open your `.env` file
2. Change `RESEND_FROM_EMAIL` to include a full email address with `@`
3. The domain part (after `@`) must match your verified domain in Resend
4. Restart your application

**Example for your setup:**

If you verified `pospiros.pizza` in Resend, you can use:
- `reports@pospiros.pizza`
- `noreply@pospiros.pizza`
- `kitchen@pospiros.pizza`
- `manager@pospiros.pizza`

Any local part (before `@`) works - you don't need to create individual email accounts!

---

### Issue: "RESEND_API_KEY is not configured"

**Error message:**
```
RESEND_API_KEY is not configured in environment variables
```

**Solution:**

1. Go to https://resend.com/api-keys
2. Copy your API key (starts with `re_`)
3. Add to `.env` file:
   ```bash
   RESEND_API_KEY=re_your_actual_key_here
   ```
4. Restart application

---

### Issue: "RESEND_FROM_EMAIL is not configured"

**Error message:**
```
RESEND_FROM_EMAIL is not configured in environment variables
```

**Solution:**

1. Add to `.env` file:
   ```bash
   RESEND_FROM_EMAIL=reports@yourdomain.com
   ```
2. Make sure the domain is verified in Resend
3. Restart application

---

### Issue: "Domain not verified" or "Domain verification required"

**Error from Resend API**

**Solution:**

1. Log into https://resend.com/domains
2. Click on your domain
3. Add the DNS records shown to your DNS provider (e.g., Cloudflare)
4. Wait for DNS propagation (can take up to 24 hours, usually faster)
5. Click "Verify" in Resend dashboard

**For Cloudflare users:**

When adding DNS records to Cloudflare:
- Set the **Proxy status to "DNS only"** (gray cloud icon)
- Do NOT use "Proxied" (orange cloud) for email DNS records
- This is important for SPF, DKIM, and DMARC records

**Required DNS records (example):**
```
Type: TXT
Name: @ (or your domain)
Value: v=spf1 include:_spf.resend.com ~all

Type: TXT
Name: resend._domainkey
Value: [provided by Resend]

Type: TXT
Name: _dmarc
Value: [provided by Resend]
```

---

### Issue: "No valid recipients found"

**Error message:**
```
No valid recipients found with email addresses
```

**Solution:**

The selected employees don't have email addresses configured.

1. Go to `/employees`
2. Edit each manager/admin
3. Add their email addresses
4. Save
5. Try sending the report again

---

### Issue: Email sent but not received

**Possible causes:**

1. **Check spam/junk folder** - Most common issue!

2. **Verify email address is correct**
   - Go to `/employees`
   - Check recipient's email address for typos

3. **Check Resend delivery logs**
   - Go to https://resend.com/emails
   - Look for your sent email
   - Check delivery status
   - Look for bounce or rejection reasons

4. **Domain reputation** (for new domains)
   - New domains may have delivery issues initially
   - Send a few test emails first
   - Consider warming up your domain
   - Gmail/Outlook may delay emails from new domains

---

### Issue: "Unexpected token '<'" or HTML parsing error

**Error message:**
```
Error sending report: Unexpected token '<', "<!DOCTYPE "... is not valid JSON
```

**Cause:**
This was a bug in the original code (now fixed). The API was returning HTML instead of JSON.

**Solution:**
Make sure you're using the latest version of `app/api/email_reports.py` that returns JSONResponse objects.

---

### Testing Your Configuration

**Step 1: Verify DNS records**
```bash
# Check SPF record
dig TXT pospiros.pizza

# Check DKIM record
dig TXT resend._domainkey.pospiros.pizza

# Check DMARC record
dig TXT _dmarc.pospiros.pizza
```

**Step 2: Test email sending**

1. Create a test employee with your personal email
2. Make them a manager or admin
3. Go to an inventory report
4. Send to yourself
5. Check inbox (and spam!)

---

## Environment Variable Checklist

Your `.env` file should have:

```bash
# Required for email
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxx
RESEND_FROM_EMAIL=reports@pospiros.pizza

# Other required variables
SECRET_KEY=your-secret-key
DATABASE_URL=sqlite:///./data/food_cost.db
TZ=America/New_York  # or your timezone
```

**Verify format:**
- ✅ `RESEND_FROM_EMAIL` has `@` symbol
- ✅ Domain after `@` is verified in Resend
- ✅ `RESEND_API_KEY` starts with `re_`
- ✅ No spaces around `=` signs
- ✅ No quotes around values (unless value contains spaces)

---

## Quick Test Commands

**Check if environment variables are loaded:**
```bash
# In your application directory
python3 -c "import os; print('API Key:', os.getenv('RESEND_API_KEY')[:10] if os.getenv('RESEND_API_KEY') else 'NOT SET'); print('From Email:', os.getenv('RESEND_FROM_EMAIL'))"
```

**Expected output:**
```
API Key: re_xxxxxxx
From Email: reports@pospiros.pizza
```

---

## Still Having Issues?

1. **Check application logs** for detailed error messages
2. **Check Resend dashboard** at https://resend.com/emails for delivery status
3. **Verify DNS propagation** at https://dnschecker.org
4. **Test with Resend test domain** first: `RESEND_FROM_EMAIL=onboarding@resend.dev`

---

## For Your Specific Setup

Based on your message, here's exactly what you need:

**In Resend Dashboard:**
- Verified domain: `pospiros.pizza` ✓

**In your `.env` file:**
```bash
RESEND_FROM_EMAIL=reports@pospiros.pizza
```

**NOT:**
```bash
RESEND_FROM_EMAIL=reports.pospiros.pizza  # ❌ Missing @
```

The subdomain you set up in Cloudflare (`reports.pospiros.pizza`) is for DNS verification records, not for the email address itself. The email address uses the base domain with `@`.
