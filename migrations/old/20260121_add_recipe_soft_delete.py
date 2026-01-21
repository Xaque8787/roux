"""
Migration: Add soft delete support to recipes

# Summary
Adds soft delete functionality to recipes table to preserve historical data
while hiding deleted recipes from active use.

# Changes Made

1. New Columns
   - `recipes.deleted` (BOOLEAN, default FALSE)
     - Marks recipes as deleted without removing them from database
     - Allows historical batches/tasks to still reference recipe data
     - Enables undo/restore functionality

2. Benefits
   - Historical inventory reports remain intact
   - Old tasks/batches show "(removed)" indicator for deleted recipes
   - Accidental deletions can be restored
   - Clean separation between active and archived recipes

# Usage
   - Active recipes: WHERE deleted = FALSE (or deleted = 0)
   - Show all including deleted: No filter
   - Deleted only: WHERE deleted = TRUE (or deleted = 1)
"""


def upgrade(conn):
    """Add deleted column to recipes table"""

    print("Adding soft delete support to recipes table...")

    # Check if column already exists
    cursor = conn.execute("PRAGMA table_info(recipes)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'deleted' not in columns:
        # Add deleted column with default FALSE
        conn.execute("""
            ALTER TABLE recipes
            ADD COLUMN deleted BOOLEAN DEFAULT 0 NOT NULL
        """)
        print("  ✓ Added 'deleted' column to recipes table")
    else:
        print("  ℹ Column 'deleted' already exists, skipping")

    conn.commit()
    print("✅ Soft delete migration completed successfully!")
