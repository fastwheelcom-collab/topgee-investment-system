# TOPGEE Investment Management System

Complete investment tracking solution with monthly revenue management, ROI distribution, partner profit sharing, and automated reporting.

## ✨ Features

### 📊 **Dashboard**
- Total investors, investment amounts, monthly revenue
- Real-time ROI distribution tracking
- Sales team earnings overview
- Partner profit distribution (Mr. Shafaqat, Mr. Shubham, Mr. Kay)

### 👥 **Investor Management**
- Add/edit/delete investors
- Assign sales representatives
- Custom ROI splits (2-3% investor + 2-3% sales)
- Individual investor profiles with complete history

### 📅 **Monthly Tracking**
- Manual monthly revenue entry per investor
- Automatic ROI calculations
- 12-month ledger view
- Month-by-month activity tracking

### 💰 **ROI Structure (5% Total)**
- **Investor Share:** 2-3% of investment (customizable)
- **Sales Rep Share:** 2-3% of investment (customizable)
- **Total:** Always 5% of investment amount

### 🤝 **Partner Profit Distribution**
- Remaining profit after ROI distribution
- Split among 3 partners (adjustable percentages)
- Monthly tracking and reports

### 📄 **Reports & Ledgers**
- Individual investor monthly ledgers (PDF download)
- Full customer base reports
- Shareable monthly statements for clients

### 💼 **Sales Team Management**
- Add/manage sales representatives
- Track investor assignments
- Commission calculations

## 🚀 Quick Start

### 1. Install Dependencies
```bash
cd ~/Desktop/TopGee_Investment_System
pip3 install -r requirements.txt
```

### 2. Run the System
```bash
python3 app.py
```

### 3. Access
```
http://localhost:5001
```

## 📖 How to Use

### Add New Investor
1. Click **"+ Add Investor"**
2. Fill in:
   - Name, category (Individual/Company)
   - Investment amount & date
   - Assign sales representative
   - Set ROI split (investor % + sales %)
3. Save

### Record Monthly Activity
1. Go to investor profile
2. Click **"+ Add Monthly Record"**
3. Select month & year
4. Enter **revenue generated** (manual entry)
5. System automatically calculates:
   - Investor ROI payment
   - Sales commission
   - Updates partner profit pool

### View Monthly Overview
- Dashboard shows current month statistics
- Partner distribution updated automatically
- All calculations happen in real-time

### Download Investor Ledger
1. Open investor profile
2. Click **"📄 Download Ledger"**
3. PDF with 12-month history generated
4. Share with client monthly

## 💡 Key Concepts

### Revenue Flow:
```
Total Revenue (Manual Entry)
    ↓
5% ROI Distribution
    ├─→ 2-3% to Investor
    └─→ 2-3% to Sales Rep
    ↓
Remaining Profit
    ├─→ 33.33% to Mr. Shafaqat
    ├─→ 33.33% to Mr. Shubham
    └─→ 33.34% to Mr. Kay
```

### Month-by-Month Tracking:
- Each investor has 12-month ledger
- Revenue entered manually each month
- ROI auto-calculated based on investor's split
- Partner distribution updates automatically

## 🔧 Database Structure

- **Investors** - Basic info, investment amount, ROI splits
- **Monthly Records** - Revenue & distributions per investor per month
- **Partner Distribution** - Monthly profit sharing calculations
- **Sales Reps** - Team management

## 📦 File Structure

```
TopGee_Investment_System/
├── app.py                 # Main application
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── data/
│   └── investments.db    # SQLite database
├── templates/            # HTML pages
├── static/css/          # Styling
└── reports/             # Generated reports (auto-created)
```

## 🎯 Benefits

✅ **No Formula Errors** - All calculations automated  
✅ **Month-by-Month** - Track 12 months of activity  
✅ **Scalable** - Add unlimited investors  
✅ **Professional Reports** - PDF ledgers for clients  
✅ **Partner Transparency** - Clear profit distribution  
✅ **Sales Tracking** - Commission per representative  
✅ **Flexible ROI** - Adjust splits per investor  

## 🔐 Data Backup

**Critical:** Backup the `data/` folder regularly!

```bash
cp -r data/ data_backup_$(date +%Y%m%d)/
```

## 📞 Support

Built for TOPGEE Capital - April 30, 2026

---

**Ready to manage your investments professionally!**
