"""
Migration script to add payout tracking fields to InvestmentTransaction table
Run this ONCE on production after deploying new code
"""

import os
import psycopg2
from psycopg2 import sql

# Get database URL from environment
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    print("❌ DATABASE_URL not found! Set it first.")
    print("Example: export DATABASE_URL='postgresql://user:pass@host:5432/db'")
    exit(1)

# Ensure it's in postgresql:// format
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

print(f"🔵 Connecting to database...")

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    # Add new columns to investment_transaction table
    migrations = [
        "ALTER TABLE investment_transaction ADD COLUMN IF NOT EXISTS payout_month INTEGER",
        "ALTER TABLE investment_transaction ADD COLUMN IF NOT EXISTS payout_year INTEGER",
        "ALTER TABLE investment_transaction ADD COLUMN IF NOT EXISTS source_type VARCHAR(50)"
    ]
    
    for migration in migrations:
        print(f"Running: {migration}")
        cur.execute(migration)
    
    conn.commit()
    print("✅ Migration completed successfully!")
    print("\nNew columns added:")
    print("  - payout_month (INTEGER) - Which month this payout is for")
    print("  - payout_year (INTEGER) - Which year this payout is for")
    print("  - source_type (VARCHAR) - 'Investor ROI' or 'Sales Share'")
    
except Exception as e:
    print(f"❌ Migration failed: {e}")
    import traceback
    traceback.print_exc()
finally:
    if conn:
        cur.close()
        conn.close()
