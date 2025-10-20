# Quick Fix: Database Not Found Error

## Problem

When running the migration, you see:
```
❌ Migration failed: no such table: inventory_days
```

This means the migration script couldn't find your database file or the database doesn't have the expected tables.

## Solution

### Option 1: Specify Database Path Manually

Run the migration with the full path to your database:

```bash
# Replace with your actual database path
python migrations/add_day_timestamps_and_timezone.py /home/spiros-zach/Projects/food_cost/data/food_cost.db
```

### Option 2: Set DATABASE_URL Environment Variable

```bash
# Set the environment variable
export DATABASE_URL="sqlite:///path/to/your/database.db"

# Then run the migration
python migrations/add_day_timestamps_and_timezone.py
```

### Option 3: Run from Project Directory

Make sure you're running the script from your project root directory where the `data` folder exists:

```bash
cd /home/spiros-zach/Projects/food_cost
python migrations/add_day_timestamps_and_timezone.py
```

## Finding Your Database

If you're not sure where your database is, try:

```bash
# Find all .db files in your project
find /home/spiros-zach/Projects/food_cost -name "*.db" 2>/dev/null
```

Common locations:
- `./data/food_cost.db`
- `./data/database.db`
- `/app/data/food_cost.db` (in Docker)

## Verify Database Tables

Once you find your database, check what tables exist:

```bash
sqlite3 /path/to/your/database.db ".tables"
```

You should see tables like:
- `inventory_days`
- `tasks`
- `users`
- `batches`
- etc.

If you don't see `inventory_days`, your database hasn't been initialized yet. Run your application first to create the tables.

## Still Having Issues?

The updated migration script now:
1. ✅ Auto-detects common database locations
2. ✅ Shows which tables exist in your database
3. ✅ Accepts manual database path as argument
4. ✅ Provides helpful error messages

Try running it again - it will now tell you exactly what's wrong and where it's looking for the database.
