# Quick Fix for "no such column: tasks.snapshot_quantity" Error

## The Fastest Solution

**Stop your application first**, then run ONE of these commands:

### Using sqlite3 (Recommended - Fastest)
```bash
cd /home/spiros-zach/Projects/food_cost
sqlite3 data/food_cost.db < manual_migration.sql
```

### Using Python Script
```bash
cd /home/spiros-zach/Projects/food_cost
python3 migrate_add_snapshot_columns.py data/food_cost.db
```

### Manual SQL Commands
```bash
cd /home/spiros-zach/Projects/food_cost
sqlite3 data/food_cost.db
```
Then paste:
```sql
ALTER TABLE tasks ADD COLUMN snapshot_quantity REAL;
ALTER TABLE tasks ADD COLUMN snapshot_par_level REAL;
ALTER TABLE tasks ADD COLUMN snapshot_override_create BOOLEAN DEFAULT 0;
ALTER TABLE tasks ADD COLUMN snapshot_override_no_task BOOLEAN DEFAULT 0;
.quit
```

## Then Restart Your Application
```bash
# If using uvicorn directly
uvicorn app.main:app --reload

# If using docker
docker-compose restart

# If using start.sh
./start.sh
```

## That's It!
The error should be gone and task assignments will now persist correctly.
