#!/usr/bin/env python3
"""
Migration Runner Script

This script automatically applies database migrations found in the /migrations folder.
It tracks applied migrations in the migrations_applied table to prevent duplicate execution.

Usage:
    python run_migrations.py

The script:
1. Ensures migrations_applied table exists
2. Scans /migrations folder for .py files
3. Checks which migrations have already been applied
4. Runs new migrations in alphabetical order
5. Records successful migrations in the database
6. Moves applied migrations to /migrations/old after execution
"""

import os
import sys
import hashlib
import sqlite3
from pathlib import Path
from datetime import datetime
import importlib.util

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.database import get_database_url

def get_db_path():
    """Extract database file path from DATABASE_URL"""
    db_url = get_database_url()
    if db_url.startswith('sqlite:///'):
        return db_url.replace('sqlite:///', '')
    return None

def calculate_checksum(file_path):
    """Calculate SHA256 checksum of a file"""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            sha256.update(chunk)
    return sha256.hexdigest()

def ensure_migrations_table(conn):
    """Ensure migrations_applied table exists"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS migrations_applied (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE NOT NULL,
            checksum TEXT,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    print("✅ Migrations table ready")

def get_applied_migrations(conn):
    """Get list of already applied migrations"""
    cursor = conn.execute("SELECT filename, checksum FROM migrations_applied")
    return {row[0]: row[1] for row in cursor.fetchall()}

def get_pending_migrations(migrations_dir, applied_migrations):
    """Get list of migrations that need to be applied"""
    if not migrations_dir.exists():
        return []

    all_migrations = sorted([
        f for f in migrations_dir.glob('*.py')
        if f.name != '__init__.py' and not f.name.startswith('.')
    ])

    pending = []
    for migration_file in all_migrations:
        filename = migration_file.name
        checksum = calculate_checksum(migration_file)

        if filename not in applied_migrations:
            pending.append((migration_file, checksum))
        elif applied_migrations[filename] != checksum:
            print(f"⚠️  Warning: Migration {filename} has been modified since it was applied!")
            print(f"   Skipping to prevent inconsistencies.")

    return pending

def run_migration(migration_file, conn):
    """Execute a migration file"""
    print(f"\n▶️  Applying migration: {migration_file.name}")

    try:
        # Load the migration module
        spec = importlib.util.spec_from_file_location(
            f"migration_{migration_file.stem}",
            migration_file
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Check if migration has an 'upgrade' function
        if hasattr(module, 'upgrade'):
            module.upgrade(conn)
        else:
            # If no upgrade function, execute the file as SQL
            with open(migration_file, 'r') as f:
                sql = f.read()
                # Execute SQL (handle multiple statements)
                conn.executescript(sql)

        conn.commit()
        print(f"✅ Successfully applied: {migration_file.name}")
        return True

    except Exception as e:
        conn.rollback()
        print(f"❌ Failed to apply migration {migration_file.name}: {e}")
        return False

def record_migration(conn, filename, checksum):
    """Record a successfully applied migration"""
    conn.execute(
        "INSERT INTO migrations_applied (filename, checksum, applied_at) VALUES (?, ?, ?)",
        (filename, checksum, datetime.now())
    )
    conn.commit()

def move_migration_to_old(migration_file, old_dir):
    """Move applied migration to old directory"""
    try:
        old_dir.mkdir(parents=True, exist_ok=True)
        destination = old_dir / migration_file.name
        migration_file.rename(destination)
        print(f"📁 Moved to old: {migration_file.name}")
    except Exception as e:
        print(f"⚠️  Could not move {migration_file.name} to old: {e}")

def main():
    print("=" * 60)
    print("Database Migration Runner")
    print("=" * 60)

    # Get database path
    db_path = get_db_path()
    if not db_path:
        print("❌ Could not determine database path")
        sys.exit(1)

    print(f"📊 Database: {db_path}")

    # Check if database exists
    db_exists = os.path.exists(db_path)
    if not db_exists:
        print("ℹ️  Database does not exist yet - will be created by application")
        print("ℹ️  Skipping migrations (no migrations needed for fresh database)")
        sys.exit(0)

    # Connect to database
    conn = sqlite3.connect(db_path)

    try:
        # Ensure migrations table exists
        ensure_migrations_table(conn)

        # Get migrations directory
        migrations_dir = project_root / 'migrations'
        old_dir = migrations_dir / 'old'

        # Get applied and pending migrations
        applied_migrations = get_applied_migrations(conn)
        pending_migrations = get_pending_migrations(migrations_dir, applied_migrations)

        if not pending_migrations:
            print("\n✅ No pending migrations - database is up to date")
            return

        print(f"\n📋 Found {len(pending_migrations)} pending migration(s)")

        # Apply each pending migration
        for migration_file, checksum in pending_migrations:
            success = run_migration(migration_file, conn)

            if success:
                # Record the migration
                record_migration(conn, migration_file.name, checksum)
                # Move to old directory
                move_migration_to_old(migration_file, old_dir)
            else:
                print(f"\n❌ Migration failed, stopping execution")
                sys.exit(1)

        print("\n" + "=" * 60)
        print("✅ All migrations applied successfully")
        print("=" * 60)

    finally:
        conn.close()

if __name__ == '__main__':
    main()
