# Payout Tracking System Update

## 🎯 What's New

### 1. **Capital Transactions Enhancement**
- **4 transaction types** with smart tracking:
  - Deposit
  - Withdrawal
  - **Investor Payout** (auto-deducted from Investor ROI pool)
  - **Sales Payout** (auto-deducted from Sales Share pool)

### 2. **Automatic Payout Linking**
- When recording an Investor Payout or Sales Payout:
  - System asks for **month & year** the payout is for
  - Transaction is **automatically linked** to that month in the 12-Month ROI Ledger
  - Real-time tracking of paid vs unpaid ROI

### 3. **12-Month ROI Ledger Updates**
- **Paid Status Indicators**:
  - ✅ **PAID** (green) - Full ROI paid for the month
  - ⚠️ **PARTIAL** (yellow) - Partial payment made
  - ❌ **UNPAID** (red) - No payment yet
- **Payout Details** shown inline:
  - Date of each payout
  - Amount paid
  - Payment percentage
  - Notes

### 4. **Enhanced Transaction Table**
- New "For Month" column showing which month each payout is for
- Visual badges for transaction types
- Better organization of capital movements

### 5. **Dashboard Cards**
- **Investor Payouts** card (green) - Total paid to investors
- **Sales Payouts** card (orange) - Total paid to sales team

---

## 🚀 Deployment Steps

### Step 1: Run Database Migration

```bash
cd ~/Desktop/TopGee_Investment_System

# Set database URL (production)
export DATABASE_URL='postgresql://topgee_db_user:O2WVCmfwsukbMrCNhhreO38Fkr7jtzUp@dpg-d7pqi1e8bjmc73anuvrg-a.oregon-postgres.render.com:5432/topgee_db'

# Run migration
python migrate_payout_tracking.py
```

**Expected output:**
```
🔵 Connecting to database...
Running: ALTER TABLE investment_transaction ADD COLUMN IF NOT EXISTS payout_month INTEGER
Running: ALTER TABLE investment_transaction ADD COLUMN IF NOT EXISTS payout_year INTEGER
Running: ALTER TABLE investment_transaction ADD COLUMN IF NOT EXISTS source_type VARCHAR(50)
✅ Migration completed successfully!

New columns added:
  - payout_month (INTEGER) - Which month this payout is for
  - payout_year (INTEGER) - Which year this payout is for
  - source_type (VARCHAR) - 'Investor ROI' or 'Sales Share'
```

### Step 2: Deploy to Render

```bash
# Commit changes
git add .
git commit -m "feat: Add payout tracking system with automatic ledger linking"

# Push to GitHub (auto-deploys to Render)
git push origin main
```

### Step 3: Verify Deployment

1. **Wait 2-3 minutes** for Render deployment
2. Visit: https://topgee-investment-system.onrender.com
3. Login (admin/admin123)
4. Go to any investor profile
5. Click **+ Add Transaction**
6. Select **"Investor Payout"** → Month/Year fields should appear
7. Test the flow

---

## 📋 How to Use (Admin)

### Adding a Payout

1. Go to **Investor Profile**
2. Click **+ Add Transaction** in Capital Transactions section
3. Select transaction type:
   - **Investor Payout** (for investor ROI share)
   - **Sales Payout** (for sales team share)
4. **NEW:** Select **month & year** this payout is for
5. Enter amount, date, notes
6. Upload payment evidence (optional)
7. Click **Save Transaction**

**Result:**
- Transaction appears in Capital Transactions table
- Automatically links to the selected month in 12-Month ROI Ledger
- Ledger shows paid status (✅ PAID / ⚠️ PARTIAL / ❌ UNPAID)
- Payment details appear under the month

### Viewing Paid/Unpaid Status

Go to **12-Month ROI Ledger - 2026** section:

- **Green rows** = Fully paid months
- **Yellow rows** = Partially paid months
- **White rows** = Unpaid months
- **Payment breakdown** shown for each month:
  - Expected: 15,000 AED
  - Paid: 10,000 AED (67%)
  - • 05-May: 5,000 AED - First installment
  - • 15-May: 5,000 AED - Second installment

---

## 🎨 Visual Changes

### Capital Transactions Section

**Before:**
- Deposit
- Withdrawal

**After:**
- Deposit
- Withdrawal
- **Investor Payout** (with month/year tracking)
- **Sales Payout** (with month/year tracking)

### 12-Month ROI Ledger

**Before:**
- Just manual ROI entries
- No payment tracking

**After:**
- ✅ **PAID** / ⚠️ **PARTIAL** / ❌ **UNPAID** badges
- Inline payout details
- Real-time payment progress
- Linked transactions

### Dashboard Cards (New)

```
💸 Investor Payouts          🤝 Sales Payouts
   125,000 AED                  75,000 AED
   8 payout(s)                  8 payout(s)
```

---

## 🔧 Technical Changes

### Database Model Updates

**InvestmentTransaction:**
- Added `payout_month` (INTEGER)
- Added `payout_year` (INTEGER)
- Added `source_type` (VARCHAR) - "Investor ROI" or "Sales Share"

### Backend Logic

**`investor_detail()` route:**
- Fetches payout transactions for current year
- Builds ledger with paid/unpaid status
- Calculates payment progress (paid vs expected)
- Passes payout details to template

**`add_transaction()` route:**
- Accepts payout_month and payout_year for payout types
- Auto-sets source_type based on transaction type
- Links transaction to specific month

**`edit_transaction()` route:**
- Updated to handle payout fields
- Clears payout fields for non-payout transactions

### Frontend Updates

**investor_detail.html:**
- Dynamic payout fields (show/hide based on type)
- Month/Year selectors for payouts
- Enhanced ledger table with paid status
- JavaScript toggle for payout fields
- Color-coded rows (green/yellow/white)

---

## 📊 Example Workflow

### Scenario: Paying Investor ROI for April 2026

1. **Expected ROI:** 15,000 AED (based on capital)
2. **Admin action:** Add Investor Payout
   - Amount: 15,000 AED
   - For Month: April
   - For Year: 2026
   - Date: 05-May-2026
   - Evidence: bank_transfer.pdf
3. **System behavior:**
   - Transaction saved in Capital Transactions
   - April row in ledger turns **green** (✅ PAID)
   - Shows: "Paid: 15,000 AED (100%)"
   - Displays: "• 05-May: 15,000 AED"

### Scenario: Partial Payment

1. **Expected ROI:** 20,000 AED
2. **Admin pays:** 12,000 AED (first installment)
3. **Ledger shows:**
   - Row color: **yellow** (⚠️ PARTIAL)
   - "Paid: 12,000 AED (60%)"
   - Remaining: 8,000 AED unpaid
4. **Admin pays:** 8,000 AED (second installment)
5. **Ledger updates:**
   - Row color: **green** (✅ PAID)
   - "Paid: 20,000 AED (100%)"
   - Shows both payments

---

## 🔒 Data Integrity

- **Automatic source tracking:** Investor Payout → "Investor ROI", Sales Payout → "Sales Share"
- **Month validation:** Can only select months 1-12
- **Real-time recalculation:** Status updates instantly when payouts added
- **Payment evidence:** Optional file uploads for audit trail
- **Non-destructive:** Old monthly records unaffected

---

## 🛡️ Backward Compatibility

- ✅ Existing InvestmentTransaction records unaffected (new columns default to NULL)
- ✅ Old deposits/withdrawals continue to work
- ✅ Manual ROI entries still supported
- ✅ All existing routes and views functional

---

## 📝 Notes

- **Payout month/year:** Only visible when transaction type is "Investor Payout" or "Sales Payout"
- **Paid status:** Auto-calculated with 5% tolerance (accounts for rounding)
- **Multiple payouts:** Supported - system sums all payouts for the month
- **Evidence files:** Stored as base64 in database (same as contracts)

---

## 🎉 Benefits

1. **Transparency:** Investors see exactly what's paid vs owed
2. **Automation:** No manual tracking of paid/unpaid months
3. **Accuracy:** Real-time status updates
4. **Audit Trail:** Payment evidence uploads
5. **Flexibility:** Support partial payments
6. **Professional:** Clean UI with color-coded status

---

## 🆘 Troubleshooting

**Migration fails:**
```bash
# Verify database connection
echo $DATABASE_URL

# Check existing columns
psql $DATABASE_URL -c "\d investment_transaction"
```

**Payout fields not showing:**
- Clear browser cache (Ctrl+Shift+R)
- Check JavaScript console for errors
- Verify transaction type is "Investor Payout" or "Sales Payout"

**Paid status not updating:**
- Check payout_month and payout_year are set correctly
- Verify amount matches expected ROI (within 5%)
- Look at Capital Transactions table for the payout record

---

## 📞 Support

Issues? Check:
1. Migration script output
2. Render deployment logs
3. Browser console (F12)
4. Database column existence

**Render Logs:**
```
Dashboard → topgee-investment-system → Logs
```

**Database Check:**
```bash
psql $DATABASE_URL
\d investment_transaction
SELECT payout_month, payout_year, source_type FROM investment_transaction LIMIT 5;
```

---

**Update completed:** May 5, 2026  
**Version:** 2.0 - Payout Tracking System  
**Status:** Ready for deployment ✅
