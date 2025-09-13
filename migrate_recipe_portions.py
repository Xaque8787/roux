#!/usr/bin/env python3
"""
Database migration script to add recipe portion columns to dish_batch_portions table.
Run this script to update your existing database with the new columns.
"""

import sqlite3
import os
import sys

def migrate_database():
    # Get database path from environment or use default
    database_url = os.getenv("DATABASE_URL", "sqlite:///./food_cost.db")
    
    # Extract the file path from the database URL
    if database_url.startswith("sqlite:///"):
        db_path = database_url.replace("sqlite:///", "")
    else:
        print("Error: This script only works with SQLite databases")
        sys.exit(1)
    
    # Check if database file exists
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        sys.exit(1)
    
    print(f"Migrating database: {db_path}")
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(dish_batch_portions)")
        columns = [row[1] for row in cursor.fetchall()]
        
        migrations_needed = []
        
        if 'use_recipe_portion' not in columns:
            migrations_needed.append("ALTER TABLE dish_batch_portions ADD COLUMN use_recipe_portion BOOLEAN DEFAULT FALSE")
        
        if 'recipe_portion_percent' not in columns:
            migrations_needed.append("ALTER TABLE dish_batch_portions ADD COLUMN recipe_portion_percent REAL")
        
        if not migrations_needed:
            print("✅ Database is already up to date!")
            return
        
        # Execute migrations
        for migration in migrations_needed:
            print(f"Executing: {migration}")
            cursor.execute(migration)
        
        # Commit changes
        conn.commit()
        print(f"✅ Successfully added {len(migrations_needed)} column(s) to dish_batch_portions table")
        
        # Verify the changes
        cursor.execute("PRAGMA table_info(dish_batch_portions)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"📋 Current columns in dish_batch_portions: {', '.join(columns)}")
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("🔧 Food Cost Management - Database Migration")
    print("Adding recipe portion columns to dish_batch_portions table...")
    print()
    
    migrate_database()
    
    print()
    print("🎉 Migration completed successfully!")
    print("You can now use the recipe portion feature in dishes.")