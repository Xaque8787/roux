# Database Migrations

This folder contains database migration scripts that are automatically applied when the application starts.

## How It Works

1. **Automatic Execution**: When the Docker container starts, the `docker-entrypoint.sh` script runs `run_migrations.py`
2. **Tracking**: Applied migrations are recorded in the `migrations_applied` table
3. **One-Time Execution**: Each migration runs only once, tracked by filename and checksum
4. **Archive**: After a migration is applied, it's moved to `migrations/old/` for reference

## For Existing Users

If you're upgrading from a previous version:
- Your existing database will continue to work
- The `migrations_applied` table will be created automatically
- No manual intervention needed

## Creating a New Migration

1. Create a Python file in this folder with a timestamp prefix:
   ```
   migrations/20250103_add_new_feature.py
   ```

2. Choose one of two approaches:

### Approach 1: Using an upgrade() function (Recommended)
```python
def upgrade(conn):
    """
    Apply the migration

    Args:
        conn: sqlite3 database connection
    """
    conn.execute("""
        ALTER TABLE users ADD COLUMN phone_number TEXT
    """)
```

### Approach 2: Raw SQL
```sql
-- migrations/20250103_add_new_feature.py
ALTER TABLE users ADD COLUMN phone_number TEXT;

CREATE TABLE IF NOT EXISTS new_table (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);
```

## Naming Convention

Use timestamp prefixes to ensure migrations run in order:
- Format: `YYYYMMDD_description.py`
- Example: `20250103_add_user_phone.py`
- Example: `20250104120000_create_audit_log.py`

## Best Practices

1. **Idempotent**: Use `IF EXISTS` / `IF NOT EXISTS` clauses
2. **Descriptive Names**: Clearly describe what the migration does
3. **Test First**: Test migrations on a copy of your database
4. **Small Changes**: Keep migrations focused on one logical change
5. **Document**: Add comments explaining complex migrations

## Running Migrations Manually

If you need to run migrations manually (outside Docker):

```bash
python3 run_migrations.py
```

## Migration History

All previously applied migrations are stored in `migrations/old/` for reference.
