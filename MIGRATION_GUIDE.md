# Database Migration Guide

## Problem Fixed
This migration adds snapshot columns to the `tasks` table to prevent assigned employees from being removed when clicking "Update and Generate Tasks" without changing inventory values.

## What This Migration Does
Adds four new columns to the `tasks` table:
- `snapshot_quantity` (REAL) - stores inventory quantity when task was created
- `snapshot_par_level` (REAL) - stores par level when task was created
- `snapshot_override_create` (BOOLEAN) - stores override_create_task state
- `snapshot_override_no_task` (BOOLEAN) - stores override_no_task state

## How to Run the Migration

### Option 1: Using SQL Directly (Simplest)
If you have sqlite3 command-line tool installed:

```bash
sqlite3 data/food_cost.db < manual_migration.sql
```

Or run the SQL commands directly:
```bash
sqlite3 data/food_cost.db
```

Then paste these commands:
```sql
ALTER TABLE tasks ADD COLUMN snapshot_quantity REAL;
ALTER TABLE tasks ADD COLUMN snapshot_par_level REAL;
ALTER TABLE tasks ADD COLUMN snapshot_override_create BOOLEAN DEFAULT 0;
ALTER TABLE tasks ADD COLUMN snapshot_override_no_task BOOLEAN DEFAULT 0;
.quit
```

### Option 2: Using Python Script - Automatic Detection
```bash
python3 migrate_add_snapshot_columns.py
```

This will try to find your database automatically at `./data/food_cost.db`.

### Option 3: Using Python Script - Specify Database Path
```bash
python3 migrate_add_snapshot_columns.py /path/to/your/database.db
```

For example:
```bash
python3 migrate_add_snapshot_columns.py ~/Projects/food_cost/data/food_cost.db
```

### Option 4: Run from Your Project Directory
If you're in the project root where `data/` exists:
```bash
python3 migrate_add_snapshot_columns.py ./data/food_cost.db
```

## Expected Output
```
📦 Connecting to database: ./data/food_cost.db
➕ Adding column: snapshot_quantity
✅ Added column: snapshot_quantity
➕ Adding column: snapshot_par_level
✅ Added column: snapshot_par_level
➕ Adding column: snapshot_override_create
✅ Added column: snapshot_override_create
➕ Adding column: snapshot_override_no_task
✅ Added column: snapshot_override_no_task
✅ Migration complete!
```

If you run it again, you'll see:
```
📦 Connecting to database: ./data/food_cost.db
⏭️  Column already exists: snapshot_quantity
⏭️  Column already exists: snapshot_par_level
⏭️  Column already exists: snapshot_override_create
⏭️  Column already exists: snapshot_override_no_task
✅ Migration complete!
```

## Safety
- ✅ The migration checks if columns already exist before adding them
- ✅ Safe to run multiple times
- ✅ Does not delete or modify existing data
- ✅ Only adds new columns with default values

## Troubleshooting

### "Database not found" Error
Make sure you:
1. Are in the correct directory
2. The database file exists
3. Provide the correct path to the database

### Permission Denied
Make sure you have write permissions to the database file:
```bash
ls -l data/food_cost.db
```

### Database is Locked
If you get a "database is locked" error:
1. Stop the application (kill uvicorn/FastAPI process)
2. Run the migration
3. Restart the application

## After Migration
Once the migration completes successfully:
1. Restart your application
2. The task assignment persistence issue will be fixed
3. Existing tasks without snapshots will be updated on the next "Update and Generate Tasks" click
