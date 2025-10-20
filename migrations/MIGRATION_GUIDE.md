# Migration Guide: Updated for Local Development & Docker

## Quick Start

### For Local Development (PyCharm)

```bash
# 1. Navigate to your project directory
cd /home/spiros-zach/Projects/food_cost

# 2. Set your timezone (already in .env)
export TZ=America/Los_Angeles

# 3. Backup your database
cp data/food_cost.db data/food_cost.db.backup

# 4. Run the migration
python migrations/add_day_timestamps_and_timezone.py

# 5. Restart your application in PyCharm
```

### For Docker Deployment

```bash
# 1. Backup your database first
docker exec food-cost-app cp /app/data/food_cost.db /app/data/food_cost.db.backup

# 2. Run migration inside container
docker exec -it food-cost-app python migrations/add_day_timestamps_and_timezone.py

# 3. Restart container
docker-compose restart food-cost-app
```

## What Changed

### Environment Detection
The migration script now **automatically detects** whether you're running:
- 💻 **Local Development** (PyCharm/bare metal)
- 🐳 **Docker Container**

And searches for the database in the appropriate locations for each environment.

### Database Paths

**Local Development:**
- `./data/food_cost.db` (default)
- `./data/database.db` (fallback)
- `../data/food_cost.db` (if running from subdirectory)

**Docker:**
- `/app/data/food_cost.db` (default)
- `/home/app/data/food_cost.db` (fallback)

### Timezone Configuration

**Default timezone changed to:** `America/Los_Angeles` (Pacific Time)

This is configured in:
- `.env` - for local development
- `docker-compose.yml` - for Docker deployment

You can change this to any IANA timezone:
- `America/Los_Angeles` - Pacific Time
- `America/Denver` - Mountain Time  
- `America/Chicago` - Central Time
- `America/New_York` - Eastern Time

## What the Migration Does

1. ✅ Detects your environment (local vs Docker)
2. ✅ Finds your database file
3. ✅ Shows all tables in the database
4. ✅ Adds `started_at` column to `inventory_days`
5. ✅ Adds `finalized_at` column to `inventory_days`
6. ✅ Converts all UTC timestamps to Pacific Time
7. ✅ Updates timestamps in tables:
   - `users`
   - `ingredients`
   - `recipes`
   - `batches`
   - `dishes`
   - `inventory_items`
   - `inventory_days`
   - `janitorial_tasks`
   - `tasks`
   - `inventory_snapshots`

## Expected Output

When you run the migration, you'll see:

```
======================================================================
DATABASE MIGRATION: Add Day Timestamps and Timezone Conversion
======================================================================

This migration will:
  1. Add started_at and finalized_at columns to inventory_days
  2. Convert all UTC timestamps to local timezone

Target timezone: America/Los_Angeles
Database path: /home/spiros-zach/Projects/food_cost/data/food_cost.db

💻 Detected local development environment
✓ Found database at: /home/spiros-zach/Projects/food_cost/data/food_cost.db

⚠️  IMPORTANT: Backup your database before proceeding!
  Backup command: cp /home/spiros-zach/Projects/food_cost/data/food_cost.db ...

Do you want to continue? (yes/no): yes

Starting migration...
Database: /home/spiros-zach/Projects/food_cost/data/food_cost.db
Target Timezone: America/Los_Angeles
UTC Offset: -7.0 hours

Existing tables in database: users, categories, vendors, ingredients, ...

1. Adding started_at and finalized_at columns to inventory_days...
   ✓ Added started_at column
   ✓ Added finalized_at column

2. Populating started_at for existing inventory days...
   ✓ Updated 15 records

3. Converting timestamps from UTC to America/Los_Angeles...
   ✓ Converted 25 records in users.created_at
   ✓ Converted 150 records in tasks.started_at
   ✓ Converted 120 records in tasks.finished_at
   ...

✅ Migration completed successfully!
```

## Troubleshooting

### Database Not Found

If you see "Database file not found", the script will show you which paths it checked:

```
❌ Database file not found!

Searched locations:
  ✗ ./data/food_cost.db
  ✗ ./data/database.db
  ✗ ../data/food_cost.db
```

**Solution:** Specify the path manually:
```bash
python migrations/add_day_timestamps_and_timezone.py /path/to/your/database.db
```

### Table Not Found

If you see "no such table: inventory_days", your database hasn't been initialized.

**Solution:** Run your application first to create the tables, then run the migration.

### Wrong Timezone Offset

The script shows the UTC offset it will use. For Pacific Time, you should see:
- `-8.0 hours` (during Standard Time - Nov to Mar)
- `-7.0 hours` (during Daylight Time - Mar to Nov)

If it shows `+0.0 hours`, your TZ environment variable isn't set.

**Solution:**
```bash
export TZ=America/Los_Angeles
python migrations/add_day_timestamps_and_timezone.py
```

## Verification

After migration:

1. **Check timestamps** - Create a new task and verify the timestamp is in Pacific Time
2. **Check reports** - View an old inventory report and verify times are now correct
3. **Check shift metrics** - Finalize a new inventory day and verify shift duration appears

## Rollback

If something goes wrong:

```bash
# Restore from backup
cp data/food_cost.db.backup data/food_cost.db

# Or in Docker
docker exec food-cost-app cp /app/data/food_cost.db.backup /app/data/food_cost.db
```

Then restart the application.
