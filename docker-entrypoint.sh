#!/bin/bash
set -e

echo "=" | awk '{for(i=1;i<=60;i++)printf $0; print ""}'
echo "Food Cost Management System - Docker Entrypoint"
echo "=" | awk '{for(i=1;i<=60;i++)printf $0; print ""}'

# Check if database directory is writable
if [ ! -w "/app/data" ]; then
    echo "❌ ERROR: /app/data is not writable!"
    echo "   Please check your volume mount permissions"
    exit 1
fi

echo "✅ Data directory is writable"

# Run migrations if database exists
if [ -f "/app/data/food_cost.db" ]; then
    echo ""
    echo "📊 Existing database detected - checking for migrations..."
    python /app/run_migrations.py
else
    echo ""
    echo "ℹ️  No existing database - will be created on first access"
    echo "ℹ️  Skipping migrations (not needed for fresh database)"
fi

echo ""
echo "=" | awk '{for(i=1;i<=60;i++)printf $0; print ""}'
echo "🚀 Starting application server..."
echo "=" | awk '{for(i=1;i<=60;i++)printf $0; print ""}'
echo ""

# Start the application
exec "$@"
