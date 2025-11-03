#!/usr/bin/env python3
"""
Manual migration script to add triple and quadruple scaling columns to batches table.
Run this from the project root directory: python supabase/migrations/apply_triple_quadruple.py
"""

import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.database import engine
from sqlalchemy import text

def apply_migration():
    print("Applying migration: Add triple and quadruple batch scaling columns")
    print("-" * 60)

    with engine.connect() as conn:
        # Add scale_triple column
        try:
            conn.execute(text("ALTER TABLE batches ADD COLUMN scale_triple BOOLEAN DEFAULT 0"))
            conn.commit()
            print("✓ Added scale_triple column to batches table")
        except Exception as e:
            if "duplicate column name" in str(e).lower():
                print("⊘ scale_triple column already exists")
            else:
                print(f"✗ Error adding scale_triple: {e}")

        # Add scale_quadruple column
        try:
            conn.execute(text("ALTER TABLE batches ADD COLUMN scale_quadruple BOOLEAN DEFAULT 0"))
            conn.commit()
            print("✓ Added scale_quadruple column to batches table")
        except Exception as e:
            if "duplicate column name" in str(e).lower():
                print("⊘ scale_quadruple column already exists")
            else:
                print(f"✗ Error adding scale_quadruple: {e}")

    print("-" * 60)
    print("Migration complete!")

if __name__ == "__main__":
    apply_migration()
