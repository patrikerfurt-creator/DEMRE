#!/bin/bash
set -e

echo "Waiting for database..."
until python -c "
import psycopg2
import os
import time
try:
    conn = psycopg2.connect(
        host='db',
        port=5432,
        dbname='demre',
        user='demre',
        password='demre_secret',
        connect_timeout=3
    )
    conn.close()
    print('Database ready')
except Exception as e:
    print(f'Database not ready: {e}')
    exit(1)
"; do
    echo "Waiting..."
    sleep 2
done

echo "Running migrations..."
# If tables already exist but alembic_version is missing, stamp as head to avoid re-running
python - <<'EOF'
import psycopg2, sys
conn = psycopg2.connect(host='db', port=5432, dbname='demre', user='demre', password='demre_secret')
cur = conn.cursor()
cur.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='users')")
tables_exist = cur.fetchone()[0]
cur.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='alembic_version')")
alembic_exists = cur.fetchone()[0]
if alembic_exists:
    cur.execute("SELECT version_num FROM alembic_version")
    row = cur.fetchone()
    already_stamped = row is not None
else:
    already_stamped = False
conn.close()
# Exit code 2 = tables exist but not stamped (need stamp), 0 = run normally
if tables_exist and not already_stamped:
    sys.exit(2)
sys.exit(0)
EOF
EXIT_CODE=$?
if [ $EXIT_CODE -eq 2 ]; then
    echo "Tables already exist, stamping migration as head..."
    alembic stamp head
else
    alembic upgrade head
fi

echo "Creating default admin if needed..."
python init_db.py 2>/dev/null || true

echo "Starting server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
