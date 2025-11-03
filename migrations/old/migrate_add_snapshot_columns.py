"""
Migration script to add snapshot columns to tasks table
Run this once to update existing databases with the new columns

Usage:
    python3 migrate_add_snapshot_columns.py [path/to/database.db]

If no path is provided, will try to detect the database automatically.
"""
import sqlite3
import os
import sys

def get_database_path():
    """Get the database path matching the logic in app/database.py"""
    # Check if path was provided as argument
    if len(sys.argv) > 1:
        return sys.argv[1]

    if os.path.exists('/app') and os.path.exists('/home/app'):
        # Docker environment
        return '/app/data/food_cost.db'
    else:
        # Bare metal environment
        return './data/food_cost.db'

def migrate():
    db_path = get_database_path()

    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        print("\n💡 Usage: python3 migrate_add_snapshot_columns.py [path/to/database.db]")
        print("   Example: python3 migrate_add_snapshot_columns.py ./data/food_cost.db")
        return

    print(f"📦 Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if columns already exist
    cursor.execute("PRAGMA table_info(tasks)")
    columns = {row[1] for row in cursor.fetchall()}

    columns_to_add = {
        'snapshot_quantity': 'REAL',
        'snapshot_par_level': 'REAL',
        'snapshot_override_create': 'BOOLEAN DEFAULT 0',
        'snapshot_override_no_task': 'BOOLEAN DEFAULT 0'
    }

    for column_name, column_type in columns_to_add.items():
        if column_name not in columns:
            try:
                print(f"➕ Adding column: {column_name}")
                cursor.execute(f"ALTER TABLE tasks ADD COLUMN {column_name} {column_type}")
                conn.commit()
                print(f"✅ Added column: {column_name}")
            except sqlite3.OperationalError as e:
                print(f"❌ Error adding column {column_name}: {e}")
        else:
            print(f"⏭️  Column already exists: {column_name}")

    conn.close()
    print("✅ Migration complete!")

if __name__ == "__main__":
    migrate()
