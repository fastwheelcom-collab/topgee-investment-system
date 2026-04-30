#!/usr/bin/env python3
"""
Migrate investor data from old spreadsheet to new system
"""
from app import app, db, Investor, SalesRep
from datetime import datetime

# Client data from old spreadsheet
clients_data = [
    # Individual Clients
    ("Mohd. Uncle", "Individual", 1000000, 2.5, 2.5, "2025-11-25"),
    ("Nickunj", "Individual", 1000000, 3.0, 2.0, "2025-12-22"),
    ("Harsh", "Individual", 550000, 3.5, 1.5, "2025-11-21"),
    ("Hamza", "Individual", 300000, 3.2, 1.8, "2026-01-01"),
    ("Sammar Shabir", "Individual", 450000, 2.2, 2.8, "2026-01-01"),
    ("Abid", "Individual", 300000, 3.0, 2.0, "2026-01-01"),
    ("Ahsan", "Individual", 850000, 4.0, 1.0, "2026-01-01"),
    ("Sumit", "Individual", 400000, 2.0, 3.0, "2026-01-01"),
    ("Abhishek", "Individual", 100000, 2.0, 3.0, "2026-01-01"),
    ("Nishant", "Individual", 500000, 3.0, 2.0, "2026-01-01"),
    ("Vijay", "Individual", 500000, 3.0, 2.0, "2026-01-01"),
    ("Mr. Tanveer", "Individual", 126000, 3.0, 2.0, "2026-01-01"),
    ("Mr. Kamran", "Individual", 107000, 3.0, 2.0, "2026-01-01"),
    ("Zeeshan Bhai", "Individual", 100000, 5.0, 0.0, "2026-01-01"),
    ("Shah Sahib", "Individual", 70000, 2.5, 2.5, "2026-01-01"),
    ("Sonia", "Individual", 38000, 5.0, 0.0, "2026-01-01"),
    ("Faizan Basharat", "Individual", 74000, 4.0, 1.0, "2026-01-01"),
    ("Hammad Razaq", "Individual", 60000, 4.0, 1.0, "2026-05-01"),
    ("Sundas Amir", "Individual", 200000, 5.0, 0.0, "2026-04-01"),
    
    # Company Clients
    ("Riasat (Trade Marketing)", "Company", 2707073, 5.0, 0.0, "2026-01-01"),
    ("Fast Wheel", "Company", 635370, 5.0, 0.0, "2026-01-01"),
    ("Shubham's Sister", "Company", 759414, 5.0, 0.0, "2025-12-01"),
    ("Top G", "Company", 1915987, 5.0, 0.0, "2026-02-01"),
]

with app.app_context():
    print("\n" + "="*60)
    print("🔄 MIGRATING DATA FROM OLD SPREADSHEET")
    print("="*60 + "\n")
    
    # Get sales reps
    sales_reps = SalesRep.query.all()
    if not sales_reps:
        print("❌ No sales reps found. Run app.py first to initialize database.")
        exit(1)
    
    # Clear existing investors (fresh start)
    existing_count = Investor.query.count()
    if existing_count > 0:
        print(f"⚠️  Found {existing_count} existing investors. Clearing...")
        Investor.query.delete()
        db.session.commit()
        print("✅ Cleared existing data\n")
    
    # Add investors
    print("📋 Adding investors:")
    print("-" * 60)
    
    added = 0
    for name, category, investment, inv_roi, sales_roi, date_str in clients_data:
        # Assign sales rep (rotate through available reps)
        sales_rep = sales_reps[added % len(sales_reps)]
        
        investor = Investor(
            name=name,
            category=category,
            investment_amount=investment,
            investment_date=datetime.strptime(date_str, '%Y-%m-%d'),
            sales_rep_id=sales_rep.id,
            investor_roi_percent=inv_roi,
            sales_roi_percent=sales_roi,
            status='Active'
        )
        
        db.session.add(investor)
        added += 1
        
        print(f"  {added:2d}. {name:30} | {category:10} | {investment:>12,.0f} AED | {inv_roi}% / {sales_roi}%")
    
    db.session.commit()
    
    print("-" * 60)
    print(f"\n✅ Successfully migrated {added} investors!")
    
    # Summary
    total_investment = sum(c[2] for c in clients_data)
    individual_count = len([c for c in clients_data if c[1] == 'Individual'])
    company_count = len([c for c in clients_data if c[1] == 'Company'])
    
    print("\n📊 Summary:")
    print(f"  • Total Investors: {added}")
    print(f"  • Individual: {individual_count}")
    print(f"  • Company: {company_count}")
    print(f"  • Total Investment: {total_investment:,.0f} AED")
    print(f"  • Sales Reps: {len(sales_reps)}")
    
    print("\n" + "="*60)
    print("✅ MIGRATION COMPLETE!")
    print("="*60)
    print("\n📊 Access dashboard: http://localhost:5001\n")
