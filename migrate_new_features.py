#!/usr/bin/env python3
"""
Migration script for new features:
- Add GlobalRevenue table
- Transaction types now support: Deposit, Withdrawal, Investor Payout, Sales Payout
"""

import os
import sys

# Set PostgreSQL connection from environment
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    print("⚠️ DATABASE_URL not set! This script is for production PostgreSQL only.")
    print("For local SQLite, the app will auto-create tables on first run.")
    sys.exit(1)

# Fix postgres:// → postgresql://
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

import psycopg2

print("🔧 Running migration for new dashboard features...")
print(f"📦 Database: {DATABASE_URL[:60]}...")

try:
    # Connect to database
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    # 1. Check if GlobalRevenue table exists
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'global_revenue'
        );
    """)
    table_exists = cur.fetchone()[0]
    
    if not table_exists:
        print("📊 Creating GlobalRevenue table...")
        cur.execute("""
            CREATE TABLE global_revenue (
                id SERIAL PRIMARY KEY,
                total_revenue DOUBLE PRECISION DEFAULT 0,
                input_mode VARCHAR(20) DEFAULT 'amount',
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Insert default record
        cur.execute("""
            INSERT INTO global_revenue (total_revenue, input_mode)
            VALUES (0, 'amount');
        """)
        print("✅ GlobalRevenue table created with default row")
    else:
        print("ℹ️ GlobalRevenue table already exists")
    
    # 2. Verify InvestmentTransaction table supports new transaction types
    # (PostgreSQL allows any string values in VARCHAR columns, so no schema change needed)
    cur.execute("""
        SELECT COUNT(*) FROM investment_transaction
        WHERE transaction_type IN ('Investor Payout', 'Sales Payout');
    """)
    payout_count = cur.fetchone()[0]
    print(f"ℹ️ Found {payout_count} payout transactions (Investor Payout, Sales Payout)")
    
    # Commit changes
    conn.commit()
    
    print("\n✅ Migration completed successfully!")
    print("\n📋 Summary:")
    print("   - GlobalRevenue table created (total revenue tracking)")
    print("   - Transaction types now support: Deposit, Withdrawal, Investor Payout, Sales Payout")
    print("\n🎯 Next steps:")
    print("   1. Deploy updated app.py")
    print("   2. Set Total Revenue Generated from dashboard")
    print("   3. Use new payout transaction types for ROI distributions")
    
except Exception as e:
    print(f"\n❌ Migration failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    if 'cur' in locals():
        cur.close()
    if 'conn' in locals():
        conn.close()
