#!/usr/bin/env python3
"""Export production database to JSON backup"""
import os
import json
from datetime import datetime, date

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://topgee_db_user:O2WVCmfwsukbMrCNhhreO38Fkr7jtzUp@dpg-d7pqi1e8bjmc73anuvrg-a.oregon-postgres.render.com:5432/topgee_db')

if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

import psycopg2

def json_serial(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

print("🔄 Connecting to database...")
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

backup_data = {}

# Export all tables
tables = ['investor', 'sales_rep', 'investment_transaction', 'monthly_record', 'manual_roi', 'global_revenue', 'partner_distribution']

for table in tables:
    try:
        cur.execute(f"SELECT * FROM {table}")
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        backup_data[table] = [dict(zip(columns, row)) for row in rows]
        print(f"✅ Exported {len(rows)} rows from {table}")
    except Exception as e:
        print(f"⚠️ Skipped {table}: {e}")

# Save to file
backup_file = f"/Users/sadii/Desktop/TopGee_Database_Backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(backup_file, 'w') as f:
    json.dump(backup_data, f, indent=2, default=json_serial)

print(f"\n✅ Database backup saved to: {backup_file}")
print(f"📊 Total tables: {len(backup_data)}")
print(f"📁 Backup size: {os.path.getsize(backup_file) / 1024:.2f} KB")

cur.close()
conn.close()
