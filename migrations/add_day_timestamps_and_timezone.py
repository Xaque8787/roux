"""
Migration: Add Day Timestamps and Convert to Local Timezone

This migration does three things:
1. Adds started_at and finalized_at columns to inventory_days table
2. Converts all existing UTC timestamps to local timezone (configurable via TZ env var)
3. Updates the datetime handling throughout the application

Run this migration before deploying the timezone-aware code changes.

Usage:
    python migrations/add_day_timestamps_and_timezone.py

Environment Variables:
    TZ - Target timezone for conversion (e.g., 'America/New_York', 'America/Chicago')
         Defaults to 'UTC' if not set
"""

import sqlite3
import os
from datetime import datetime, timedelta
import zoneinfo

# Database path
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "database.db")

# Get timezone offset
TZ_NAME = os.getenv('TZ', 'UTC')
try:
    TIMEZONE = zoneinfo.ZoneInfo(TZ_NAME)
except zoneinfo.ZoneInfoNotFoundError:
    print(f"Warning: Timezone '{TZ_NAME}' not found, using UTC")
    TIMEZONE = zoneinfo.ZoneInfo('UTC')

def get_utc_offset_hours():
    """Calculate the UTC offset for the configured timezone"""
    now = datetime.now(TIMEZONE)
    offset = now.utcoffset()
    if offset is None:
        return 0
    return offset.total_seconds() / 3600

def migrate():
    """Run the migration"""
    print(f"Starting migration...")
    print(f"Database: {DB_PATH}")
    print(f"Target Timezone: {TZ_NAME}")

    utc_offset_hours = get_utc_offset_hours()
    print(f"UTC Offset: {utc_offset_hours:+.1f} hours")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Step 1: Add new columns to inventory_days
        print("\n1. Adding started_at and finalized_at columns to inventory_days...")
        cursor.execute("PRAGMA table_info(inventory_days)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'started_at' not in columns:
            cursor.execute("ALTER TABLE inventory_days ADD COLUMN started_at DATETIME")
            print("   ✓ Added started_at column")
        else:
            print("   - started_at column already exists")

        if 'finalized_at' not in columns:
            cursor.execute("ALTER TABLE inventory_days ADD COLUMN finalized_at DATETIME")
            print("   ✓ Added finalized_at column")
        else:
            print("   - finalized_at column already exists")

        # Step 2: Populate started_at with created_at for existing days
        print("\n2. Populating started_at for existing inventory days...")
        cursor.execute("""
            UPDATE inventory_days
            SET started_at = created_at
            WHERE started_at IS NULL AND created_at IS NOT NULL
        """)
        print(f"   ✓ Updated {cursor.rowcount} records")

        # Step 3: Convert timestamps in all tables
        print(f"\n3. Converting timestamps from UTC to {TZ_NAME}...")

        # Tables and their datetime columns
        tables_to_convert = {
            'users': ['created_at'],
            'ingredients': ['created_at'],
            'recipes': ['created_at'],
            'batches': ['created_at'],
            'dishes': ['created_at'],
            'inventory_items': ['created_at'],
            'inventory_days': ['created_at', 'started_at', 'finalized_at'],
            'janitorial_tasks': ['created_at'],
            'tasks': ['created_at', 'started_at', 'finished_at', 'paused_at'],
            'inventory_snapshots': ['last_updated']
        }

        for table, columns in tables_to_convert.items():
            # Check if table exists
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            if not cursor.fetchone():
                print(f"   - Skipping {table} (table does not exist)")
                continue

            for col in columns:
                # Check if column exists
                cursor.execute(f"PRAGMA table_info({table})")
                table_columns = [c[1] for c in cursor.fetchall()]
                if col not in table_columns:
                    print(f"   - Skipping {table}.{col} (column does not exist)")
                    continue

                # Convert timestamps using SQLite's datetime function
                # This converts from UTC to local time
                cursor.execute(f"""
                    UPDATE {table}
                    SET {col} = datetime({col}, '{utc_offset_hours:+.0f} hours')
                    WHERE {col} IS NOT NULL
                """)
                affected = cursor.rowcount
                if affected > 0:
                    print(f"   ✓ Converted {affected} records in {table}.{col}")

        conn.commit()
        print("\n✅ Migration completed successfully!")
        print("\nNext steps:")
        print("1. Deploy the updated application code with timezone support")
        print("2. Set the TZ environment variable in your docker-compose.yml")
        print("3. Restart the application")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    # Confirmation prompt
    print("=" * 70)
    print("DATABASE MIGRATION: Add Day Timestamps and Timezone Conversion")
    print("=" * 70)
    print("\nThis migration will:")
    print("  1. Add started_at and finalized_at columns to inventory_days")
    print("  2. Convert all UTC timestamps to local timezone")
    print(f"\nTarget timezone: {TZ_NAME}")
    print(f"Database path: {DB_PATH}")
    print("\n⚠️  IMPORTANT: Backup your database before proceeding!")

    response = input("\nDo you want to continue? (yes/no): ")
    if response.lower() in ['yes', 'y']:
        migrate()
    else:
        print("Migration cancelled.")
