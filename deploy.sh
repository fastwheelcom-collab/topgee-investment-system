#!/bin/bash
set -e

echo "🔵 Step 1: Running database migration..."
cd ~/Desktop/TopGee_Investment_System
export DATABASE_URL='postgresql://topgee_db_user:O2WVCmfwsukbMrCNhhreO38Fkr7jtzUp@dpg-d7pqi1e8bjmc73anuvrg-a.oregon-postgres.render.com:5432/topgee_db'
python migrate_payout_tracking.py

echo ""
echo "✅ Migration complete!"
echo ""
echo "🔵 Step 2: Committing changes..."
git add .
git commit -m "feat: Payout tracking system with automatic ledger linking

- Add payout_month, payout_year, source_type to InvestmentTransaction
- Auto-link Investor/Sales Payouts to 12-Month ROI Ledger
- Real-time paid/unpaid status tracking (✅ PAID / ⚠️ PARTIAL / ❌ UNPAID)
- Enhanced Capital Transactions UI with month/year selection
- Visual payment breakdown in ledger
- Add Investor Payouts and Sales Payouts dashboard cards"

echo ""
echo "🔵 Step 3: Pushing to GitHub (auto-deploys to Render)..."
git push origin main

echo ""
echo "✅ Deployment initiated!"
echo "🌐 Live site: https://topgee-investment-system.onrender.com"
echo "⏱️  Wait 2-3 minutes for Render deployment to complete"
