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
