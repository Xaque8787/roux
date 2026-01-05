#!/usr/bin/env python3
"""
Migration: Add three-quarters and two-thirds scaling columns to batches table.
"""

def upgrade(conn):
    """Add scale_three_quarters and scale_two_thirds columns to batches table"""
    print("Adding three-quarters and two-thirds batch scaling columns...")

    # Add scale_three_quarters column
    try:
        conn.execute("ALTER TABLE batches ADD COLUMN scale_three_quarters BOOLEAN DEFAULT 0")
        print("✓ Added scale_three_quarters column to batches table")
    except Exception as e:
        if "duplicate column name" in str(e).lower():
            print("⊘ scale_three_quarters column already exists")
        else:
            raise e

    # Add scale_two_thirds column
    try:
        conn.execute("ALTER TABLE batches ADD COLUMN scale_two_thirds BOOLEAN DEFAULT 0")
        print("✓ Added scale_two_thirds column to batches table")
    except Exception as e:
        if "duplicate column name" in str(e).lower():
            print("⊘ scale_two_thirds column already exists")
        else:
            raise e

if __name__ == "__main__":
    import sys
    import os
    import sqlite3
    from pathlib import Path

    # Add parent directory to path
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

    from app.database import get_database_url

    print("=" * 60)
    print("Migration: Add three-quarters and two-thirds scaling")
    print("=" * 60)

    # Get database path
    db_url = get_database_url()
    if db_url.startswith('sqlite:///'):
        db_path = db_url.replace('sqlite:///', '')
    else:
        print("❌ Could not determine database path")
        sys.exit(1)

    print(f"📊 Database: {db_path}")

    # Connect and run migration
    conn = sqlite3.connect(db_path)
    try:
        upgrade(conn)
        conn.commit()
        print("=" * 60)
        print("✅ Migration complete!")
        print("=" * 60)
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        sys.exit(1)
    finally:
        conn.close()
