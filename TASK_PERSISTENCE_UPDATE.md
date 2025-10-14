# Task Assignment Persistence Fix - Complete Guide

## What Was Fixed
Fixed the issue where assigned employees were removed from tasks when clicking "Update and Generate Tasks" multiple times without changing inventory values.

## Files Changed
1. **app/models.py** - Added 4 snapshot columns to Task model
2. **app/routers/inventory.py** - Updated task generation logic to compare inventory snapshots

## Required: Database Migration

Your existing database needs to be updated with 4 new columns. Choose the easiest method for you:

---

## 🚀 Quick Start (Pick One Method)

### Method 1: SQLite Command (Fastest ⚡)
```bash
cd /home/spiros-zach/Projects/food_cost
sqlite3 data/food_cost.db < manual_migration.sql
```

### Method 2: Python Script
```bash
cd /home/spiros-zach/Projects/food_cost
python3 migrate_add_snapshot_columns.py data/food_cost.db
```

### Method 3: Manual SQL
```bash
cd /home/spiros-zach/Projects/food_cost
sqlite3 data/food_cost.db
```
Then paste these lines:
```sql
ALTER TABLE tasks ADD COLUMN snapshot_quantity REAL;
ALTER TABLE tasks ADD COLUMN snapshot_par_level REAL;
ALTER TABLE tasks ADD COLUMN snapshot_override_create BOOLEAN DEFAULT 0;
ALTER TABLE tasks ADD COLUMN snapshot_override_no_task BOOLEAN DEFAULT 0;
.quit
```

---

## After Running Migration

1. **Restart your application**
2. **Test the fix:**
   - Create/open an inventory day
   - Generate tasks
   - Assign employees to tasks
   - Click "Update and Generate Tasks" again (without changing inventory)
   - ✅ Employees should still be assigned!

## How It Works Now

### Before Fix ❌
```
Inventory: Pizza (Qty: 1, Par: 2)
Click "Generate" → Task created, assign Zach
Click "Generate" again → Task deleted & recreated, Zach removed ❌
```

### After Fix ✅
```
Inventory: Pizza (Qty: 1, Par: 2)
Click "Generate" → Task created, assign Zach, snapshot saved (qty:1, par:2)
Click "Generate" again → Inventory compared with snapshot, no change detected
                        → Task preserved, Zach still assigned ✅
Change Qty to 0 → Inventory changed, task updated (expected behavior)
```

## Protection Rules

The system now follows these rules:

1. **Started Tasks** - Never modified, even if inventory changes
2. **Completed Tasks** - Never modified
3. **Not Started Tasks** - Only updated if inventory values change
4. **Force Regenerate** - Bypasses comparison, recreates all tasks

## Troubleshooting

### "Database is locked"
- Stop your application first
- Run the migration
- Restart the application

### "Permission denied"
- Check file permissions: `ls -l data/food_cost.db`
- Make sure you own the file or have write access

### "Column already exists"
- This is fine! The migration is safe to run multiple times
- Your database is already up-to-date

### Still seeing the error after migration?
- Make sure you restarted the application
- Verify columns were added: `sqlite3 data/food_cost.db ".schema tasks"`
- Check that you're running the application from the correct directory

## Files Included

- `migrate_add_snapshot_columns.py` - Python migration script
- `manual_migration.sql` - SQL migration script
- `MIGRATION_GUIDE.md` - Detailed migration instructions
- `QUICK_FIX.md` - Fast reference guide

## Questions?

If you encounter any issues, check:
1. Is the application stopped before migration?
2. Is the database path correct?
3. Do you have write permissions?
4. Did you restart the application after migration?
