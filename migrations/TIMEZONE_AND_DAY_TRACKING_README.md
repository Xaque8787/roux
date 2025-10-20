# Timezone and Day Time Tracking Implementation

## Overview

This update implements two major enhancements to the application:

1. **Timezone Support**: All timestamps are now handled in your local timezone instead of UTC
2. **Day-Level Time Tracking**: Track when inventory days start and end for better shift analysis

## What Changed

### 1. New Day Timestamps

The `inventory_days` table now has two new columns:
- `started_at`: Timestamp when the inventory day was created
- `finalized_at`: Timestamp when the inventory day was finalized

These allow us to calculate:
- **Total Shift Duration**: How long from start to finish
- **Active Task Time**: Sum of all task durations
- **Off-Task Time**: Time spent between tasks or on non-tracked activities
- **Shift Efficiency**: Percentage of time spent on tracked tasks

### 2. Timezone Implementation

All datetime operations now use local timezone instead of UTC:
- New timezone utility module (`app/utils/datetime_utils.py`)
- All `datetime.utcnow()` calls replaced with `get_naive_local_time()`
- Configurable via `TZ` environment variable

### 3. Enhanced Report

The inventory report now shows:

**Old Display:**
```
634 min - Total Time Logged
634 min - Completed Task Time
10.6 hrs - Total Hours
```

**New Display:**
```
Shift Summary
├─ Total Shift Duration: 8.5 hrs (510 min)
├─ Active Task Time: 6.3 hrs (378 min)
├─ Off-Task Time: 2.2 hrs (132 min)
└─ Shift Efficiency: 74%

Task Time Breakdown
├─ Total Task Time: 378 min
└─ Completed Task Time: 350 min
```

## Migration Steps

### Step 1: Backup Your Database

**CRITICAL**: Before proceeding, backup your database!

```bash
# Navigate to your project directory
cd /path/to/project

# Create backup
cp data/food_cost.db data/food_cost.db.backup_$(date +%Y%m%d_%H%M%S)
```

### Step 2: Set Your Timezone

Edit your `.env` file to set your timezone:

```bash
# For Eastern Time
TZ=America/New_York

# For Central Time
TZ=America/Chicago

# For Mountain Time
TZ=America/Denver

# For Pacific Time
TZ=America/Los_Angeles
```

Full list of timezones: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones

### Step 3: Run the Migration Script

The migration script will:
1. Add the new `started_at` and `finalized_at` columns
2. Populate `started_at` with existing `created_at` values
3. Convert all UTC timestamps to your local timezone

```bash
# Make sure TZ is set in your environment
export TZ=America/New_York

# Run the migration
python migrations/add_day_timestamps_and_timezone.py
```

The script will show a confirmation prompt. Review carefully and type `yes` to proceed.

### Step 4: Restart the Application

After migration completes successfully:

```bash
# If using Docker Compose
docker-compose down
docker-compose up -d

# The TZ variable is already configured in docker-compose.yml
```

## Verification

### Test 1: Check Timezone

After restart, create a new inventory day or task and verify the timestamps match your local time (not UTC).

### Test 2: Check Day Tracking

1. Create a new inventory day - `started_at` should be set automatically
2. Work on some tasks
3. Finalize the day - `finalized_at` should be set automatically
4. View the report - you should see the new "Shift Summary" section

### Test 3: Historical Data

Review an old report (from before migration) and verify:
- Timestamps now show in local time (should be 4-8 hours different from before depending on your timezone)
- Times should now match what time it actually was when tasks were performed

## Important Notes

### Historical Data

**Before Migration:**
- All timestamps were stored in UTC (e.g., 17:24 actually meant 5:24 PM UTC)

**After Migration:**
- All timestamps are converted to local time (e.g., 17:24 becomes 13:24 for Eastern Time)
- Historical reports will now show correct local times

### Old Inventory Days

Inventory days created before this update:
- `started_at` will be set to the `created_at` timestamp
- `finalized_at` will be NULL (since they were finalized before this field existed)
- Reports will show task times but NOT shift duration/efficiency

### New Inventory Days

Inventory days created after this update:
- `started_at` is set when day is created
- `finalized_at` is set when day is finalized
- Reports will show full shift analysis

## Troubleshooting

### Migration Failed

If the migration fails:
1. Restore from backup: `cp data/food_cost.db.backup_XXXXXX data/food_cost.db`
2. Check the error message
3. Verify TZ environment variable is set correctly
4. Try again or contact support

### Times Look Wrong

If timestamps don't look right:
1. Verify `TZ` in `.env` file
2. Check `TZ` in `docker-compose.yml`
3. Restart the application
4. Verify with: `docker-compose exec food-cost-app printenv TZ`

### Shift Duration Not Showing

If reports don't show shift duration:
- This only works for days finalized AFTER the migration
- Old days won't have `finalized_at` timestamps
- Create a new inventory day to see the feature

## Technical Details

### Files Modified

- `app/utils/datetime_utils.py` - New timezone utility functions
- `app/models.py` - Added columns, replaced datetime calls
- `app/auth.py` - Updated JWT expiry to use local time
- `app/sse.py` - Updated SSE timestamps
- `app/main.py` - Updated statistics calculations
- `app/routers/inventory.py` - Updated all datetime operations, added shift metrics
- `templates/inventory_report.html` - Enhanced report display
- `docker-compose.yml` - Added TZ environment variable
- `.env` - Added TZ configuration

### Migration Script

Location: `migrations/add_day_timestamps_and_timezone.py`

The script uses SQLite's `datetime()` function to adjust timestamps:
```sql
UPDATE tasks
SET started_at = datetime(started_at, '+X hours')
WHERE started_at IS NOT NULL
```

Where X is your UTC offset (negative for western timezones).

### Timezone Configuration

The `TZ` environment variable is read at runtime to determine the local timezone. Changes require an application restart to take effect.

## Benefits

### Better Time Tracking
- See actual shift duration, not just task time
- Identify inefficiencies (high off-task time)
- Calculate true shift efficiency

### Accurate Timestamps
- All times now display in your local timezone
- No more mental math converting UTC to local time
- Historical data is corrected

### Labor Cost Accuracy
- Better understanding of total labor hours
- More accurate cost per shift calculations
- Identify opportunities to optimize workflows

## Questions?

If you encounter issues or have questions about this update, please refer to:
- This README
- The migration script comments
- The project documentation
