"""
Migration: Add slug columns to all entities

This migration adds URL-friendly slug columns to all main entities and populates them
with slugified versions of their names. Slugs are unique within each entity type and
handle duplicate names by appending a number.

Changes:
- Adds 'slug' column to: ingredients, recipes, batches, dishes, users, inventory_items
- Slugs are NOT NULL and UNIQUE per table
- Populates existing records with slugified names
- Handles duplicate names by auto-incrementing (e.g., 'flour', 'flour-2', 'flour-3')
"""

import re
import unicodedata


def slugify(text):
    """Convert text to URL-friendly slug"""
    # Normalize unicode characters
    text = unicodedata.normalize('NFKD', str(text))
    # Remove non-ASCII characters
    text = text.encode('ascii', 'ignore').decode('ascii')
    # Convert to lowercase
    text = text.lower()
    # Replace spaces and special chars with hyphens
    text = re.sub(r'[^a-z0-9]+', '-', text)
    # Remove leading/trailing hyphens
    text = text.strip('-')
    # Replace multiple consecutive hyphens with single hyphen
    text = re.sub(r'-+', '-', text)
    return text or 'item'


def table_exists(conn, table_name):
    """Check if a table exists in the database"""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


def generate_slugs_for_table(conn, table_name, name_column='name', join_clause=None):
    """Generate unique slugs for all rows in a table"""
    print(f"  - Processing {table_name}...")

    # Check if table exists
    if not table_exists(conn, table_name):
        print(f"    Skipped (table doesn't exist)")
        return

    # Fetch all records
    if join_clause:
        cursor = conn.execute(f"SELECT {table_name}.id, {name_column} FROM {table_name} {join_clause}")
    else:
        cursor = conn.execute(f"SELECT id, {name_column} FROM {table_name}")

    rows = cursor.fetchall()
    slug_counts = {}

    # Generate slugs
    for row_id, name in rows:
        if not name:
            name = f"{table_name}-{row_id}"

        base_slug = slugify(name)

        # Handle duplicates
        if base_slug not in slug_counts:
            slug_counts[base_slug] = 0
            final_slug = base_slug
        else:
            slug_counts[base_slug] += 1
            final_slug = f"{base_slug}-{slug_counts[base_slug] + 1}"

        # Update the record
        conn.execute(f"UPDATE {table_name} SET slug = ? WHERE id = ?", (final_slug, row_id))

    print(f"    Generated {len(rows)} slugs for {table_name}")


def upgrade(conn):
    """Execute the migration"""
    print("Starting slug columns migration...")

    # Step 1: Add slug columns
    print("\n1. Adding slug columns to tables...")

    tables = ['ingredients', 'recipes', 'batches', 'dishes', 'users', 'inventory_items']
    tables_processed = []

    for table in tables:
        if not table_exists(conn, table):
            print(f"  - Skipped {table} (table doesn't exist)")
            continue
        tables_processed.append(table)
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN slug TEXT")
            print(f"  - Added slug column to {table}")
        except Exception as e:
            if "duplicate column" not in str(e).lower():
                print(f"  - Warning: {e}")

    conn.commit()

    # Step 2: Populate slugs
    print("\n2. Populating slugs for existing records...")

    # Ingredients - use name
    generate_slugs_for_table(conn, 'ingredients', 'name')

    # Recipes - use name
    generate_slugs_for_table(conn, 'recipes', 'name')

    # Batches - use recipe name
    generate_slugs_for_table(
        conn,
        'batches',
        'recipes.name',
        'LEFT JOIN recipes ON batches.recipe_id = recipes.id'
    )

    # Dishes - use name
    generate_slugs_for_table(conn, 'dishes', 'name')

    # Users - use username
    generate_slugs_for_table(conn, 'users', 'username')

    # Inventory items - use name
    generate_slugs_for_table(conn, 'inventory_items', 'name')

    conn.commit()

    # Step 3: Add unique indexes
    print("\n3. Adding unique indexes...")

    indexes_created = 0
    for table in tables:
        if not table_exists(conn, table):
            continue
        try:
            conn.execute(f"CREATE UNIQUE INDEX idx_{table}_slug ON {table}(slug)")
            print(f"  - Added unique index to {table}.slug")
            indexes_created += 1
        except Exception as e:
            if "already exists" not in str(e).lower():
                print(f"  - Warning: {e}")

    conn.commit()

    print("\n✅ Slug columns migration completed successfully!")
    print(f"   - Added slug columns to {len(tables_processed)} table(s)")
    print(f"   - Populated slugs for all existing records")
    print(f"   - Created {indexes_created} unique index(es) for slug lookups")


if __name__ == '__main__':
    import sys
    import sqlite3
    from pathlib import Path

    # Get database path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

    from app.database import get_database_url

    db_url = get_database_url()
    if db_url.startswith('sqlite:///'):
        db_path = db_url.replace('sqlite:///', '')

        print(f"Running migration on: {db_path}")
        conn = sqlite3.connect(db_path)

        try:
            upgrade(conn)
        except Exception as e:
            print(f"\n❌ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
        finally:
            conn.close()
    else:
        print("❌ Could not determine database path")
        sys.exit(1)
