"""
Migration: Add Email Field to Users Table

This migration adds an optional email field to the users table to enable
email notifications for reports and other communication features.

Changes:
1. Adds 'email' column to users table (nullable, to allow existing users without emails)

Run this migration before deploying the email notification feature.

Usage:
    python migrations/add_employee_email.py

Environment Variables:
    DATABASE_URL - Database connection string (defaults to ./data/food_cost.db)
"""

import sqlite3
import os
from datetime import datetime

# Database path - auto-detect or use environment variable
def get_database_path():
    # Try DATABASE_URL from environment first
    db_url = os.getenv("DATABASE_URL", "")
    if db_url and "sqlite" in db_url:
        # Extract path from sqlite:///path format
        db_path = db_url.replace("sqlite:///", "").replace("sqlite://", "")
        if os.path.exists(db_path):
            return db_path

    # Detect if we're in a Docker container
    is_docker = os.path.exists('/.dockerenv') or os.path.exists('/app')

    if is_docker:
        # Docker container paths
        possible_paths = [
            "/app/data/food_cost.db",
            "/home/app/data/food_cost.db",
        ]
        print("🐳 Detected Docker environment")
    else:
        # Local development paths (PyCharm/local testing)
        possible_paths = [
            "./data/food_cost.db",
            "./data/database.db",
            "../data/food_cost.db",
            "../data/database.db",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "food_cost.db"),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "database.db"),
        ]
        print("💻 Detected local development environment")

    for path in possible_paths:
        if os.path.exists(path):
            abs_path = os.path.abspath(path)
            print(f"✓ Found database at: {abs_path}")
            return abs_path

    # If no existing database found, use default based on environment
    if is_docker:
        default_path = "/app/data/food_cost.db"
    else:
        default_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "food_cost.db")

    print(f"⚠️  No existing database found, will use: {default_path}")
    return default_path

DB_PATH = get_database_path()

def migrate():
    """Run the migration"""
    print(f"Starting migration...")
    print(f"Database: {DB_PATH}")

    # Check if database file exists
    if not os.path.exists(DB_PATH):
        print(f"\n❌ Error: Database file not found at {DB_PATH}")
        print("\nPlease ensure:")
        print("  1. Your application has been run at least once to create the database")
        print("  2. You're running this script from the correct directory")
        print("  3. Or set DATABASE_URL environment variable to point to your database")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check what tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        existing_tables = [row[0] for row in cursor.fetchall()]
        print(f"\nExisting tables in database: {', '.join(existing_tables) if existing_tables else 'None'}")

        if 'users' not in existing_tables:
            print(f"\n❌ Error: 'users' table does not exist in the database")
            print("\nThis could mean:")
            print("  1. The database has not been initialized yet")
            print("  2. You're connecting to the wrong database file")
            print("  3. The table might have a different name")
            print(f"\nAvailable tables: {', '.join(existing_tables) if existing_tables else 'None'}")
            return

        # Step 1: Add email column to users table
        print("\n1. Adding email column to users table...")
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'email' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN email TEXT")
            print("   ✓ Added email column")
        else:
            print("   - email column already exists")

        # Step 2: Add index on email for faster lookups
        print("\n2. Adding index on email column...")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_users_email'")
        if not cursor.fetchone():
            cursor.execute("CREATE INDEX idx_users_email ON users(email)")
            print("   ✓ Created index on email column")
        else:
            print("   - Index already exists")

        conn.commit()
        print("\n✅ Migration completed successfully!")
        print("\nNext steps:")
        print("1. Deploy the updated application code with email field support")
        print("2. Update user records with email addresses via the admin interface")
        print("3. Configure SMTP settings in .env to enable email notifications")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    import sys

    # Allow manual database path specification
    if len(sys.argv) > 1:
        manual_db_path = sys.argv[1]
        if os.path.exists(manual_db_path):
            DB_PATH = manual_db_path
            print(f"Using manually specified database: {DB_PATH}")
        else:
            print(f"❌ Error: Specified database file not found: {manual_db_path}")
            sys.exit(1)

    # Confirmation prompt
    print("=" * 70)
    print("DATABASE MIGRATION: Add Email Field to Users")
    print("=" * 70)
    print("\nThis migration will:")
    print("  1. Add email column to users table")
    print("  2. Create an index on the email column")
    print(f"\nDatabase path: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"\n❌ Database file not found!")
        print(f"\nSearched locations:")
        for path in ["./data/food_cost.db", "./data/database.db", "../data/food_cost.db"]:
            exists = "✓" if os.path.exists(path) else "✗"
            print(f"  {exists} {path}")
        print(f"\nUsage: python {sys.argv[0]} /path/to/your/database.db")
        sys.exit(1)

    print("\n⚠️  IMPORTANT: Backup your database before proceeding!")
    print(f"  Backup command: cp {DB_PATH} {DB_PATH}.backup_$(date +%Y%m%d_%H%M%S)")

    response = input("\nDo you want to continue? (yes/no): ")
    if response.lower() in ['yes', 'y']:
        migrate()
    else:
        print("Migration cancelled.")
