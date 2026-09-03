from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, send_from_directory, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from functools import wraps
import hashlib
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
import os
import csv
import re
import json
import requests
from datetime import datetime, timedelta

app = Flask(__name__)

# Use PostgreSQL in production, SQLite locally
database_url = os.environ.get('DATABASE_URL')
if database_url:
    # Render provides DATABASE_URL for PostgreSQL
    print(f"🔵 Using PostgreSQL: {database_url[:50]}...")
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    # Local SQLite
    print("⚠️ WARNING: DATABASE_URL not found! Using SQLite (will fail on Render)")
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data', 'investments.db')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'topgee-investment-system-2026')

print(f"✅ Database configured: {app.config['SQLALCHEMY_DATABASE_URI'][:60]}...")

db = SQLAlchemy(app)

# Inject is_admin into all templates automatically
@app.context_processor
def inject_globals():
    email = session.get('username', '')
    profile_pic = None
    if email and email != 'admin':
        try:
            u = UserAccount.query.filter_by(email=email).first()
            if u:
                profile_pic = u.profile_pic
        except Exception:
            pass
    return dict(
        is_admin=session.get('is_admin', False),
        current_user=session.get('display_name', ''),
        current_user_pic=profile_pic,
    )

# Admin credentials — login with EMAIL + PASSWORD
ADMIN_EMAIL    = 'fastwheel.com@gmail.com'
ADMIN_PASSWORD_HASH = '5a42c3a113a8bbdcea9adf4c026089eec84c4d01ba0b8f2c89a3c98b8722b864'

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Please login to access this page', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Please login as admin', 'error')
            return redirect(url_for('login'))
        if not session.get('is_admin', False):
            flash('Admin access required', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Exchange rate (fallback)
EXCHANGE_RATE = 3.67

# Exchange rate cache (updated every 24 hours)
exchange_rate_cache = {'rate': EXCHANGE_RATE, 'last_updated': None}

def get_live_exchange_rate():
    """Fixed at 3.67 AED per USD"""
    return EXCHANGE_RATE

# Partners
PARTNERS = {
    'shafaqat': 'Mr. Shafaqat',
    'shubham': 'Mr. Shubham',
    'kay': 'Mr. Kay'
}

# Countries list (standard)
COUNTRIES = [
    'Afghanistan', 'Albania', 'Algeria', 'Andorra', 'Angola', 'Argentina', 'Armenia', 'Australia', 'Austria', 'Azerbaijan',
    'Bahamas', 'Bahrain', 'Bangladesh', 'Barbados', 'Belarus', 'Belgium', 'Belize', 'Benin', 'Bhutan', 'Bolivia',
    'Bosnia and Herzegovina', 'Botswana', 'Brazil', 'Brunei', 'Bulgaria', 'Burkina Faso', 'Burundi', 'Cambodia', 'Cameroon',
    'Canada', 'Cape Verde', 'Central African Republic', 'Chad', 'Chile', 'China', 'Colombia', 'Comoros', 'Congo',
    'Costa Rica', 'Croatia', 'Cuba', 'Cyprus', 'Czech Republic', 'Denmark', 'Djibouti', 'Dominica', 'Dominican Republic',
    'Ecuador', 'Egypt', 'El Salvador', 'Equatorial Guinea', 'Eritrea', 'Estonia', 'Ethiopia', 'Fiji', 'Finland', 'France',
    'Gabon', 'Gambia', 'Georgia', 'Germany', 'Ghana', 'Greece', 'Grenada', 'Guatemala', 'Guinea', 'Guinea-Bissau', 'Guyana',
    'Haiti', 'Honduras', 'Hungary', 'Iceland', 'India', 'Indonesia', 'Iran', 'Iraq', 'Ireland', 'Israel', 'Italy', 'Jamaica',
    'Japan', 'Jordan', 'Kazakhstan', 'Kenya', 'Kiribati', 'Kosovo', 'Kuwait', 'Kyrgyzstan', 'Laos', 'Latvia', 'Lebanon',
    'Lesotho', 'Liberia', 'Libya', 'Liechtenstein', 'Lithuania', 'Luxembourg', 'Macedonia', 'Madagascar', 'Malawi', 'Malaysia',
    'Maldives', 'Mali', 'Malta', 'Marshall Islands', 'Mauritania', 'Mauritius', 'Mexico', 'Micronesia', 'Moldova', 'Monaco',
    'Mongolia', 'Montenegro', 'Morocco', 'Mozambique', 'Myanmar', 'Namibia', 'Nauru', 'Nepal', 'Netherlands', 'New Zealand',
    'Nicaragua', 'Niger', 'Nigeria', 'North Korea', 'Norway', 'Oman', 'Pakistan', 'Palau', 'Palestine', 'Panama',
    'Papua New Guinea', 'Paraguay', 'Peru', 'Philippines', 'Poland', 'Portugal', 'Qatar', 'Romania', 'Russia', 'Rwanda',
    'Saint Kitts and Nevis', 'Saint Lucia', 'Saint Vincent and the Grenadines', 'Samoa', 'San Marino', 'Sao Tome and Principe',
    'Saudi Arabia', 'Senegal', 'Serbia', 'Seychelles', 'Sierra Leone', 'Singapore', 'Slovakia', 'Slovenia', 'Solomon Islands',
    'Somalia', 'South Africa', 'South Korea', 'South Sudan', 'Spain', 'Sri Lanka', 'Sudan', 'Suriname', 'Swaziland', 'Sweden',
    'Switzerland', 'Syria', 'Taiwan', 'Tajikistan', 'Tanzania', 'Thailand', 'Timor-Leste', 'Togo', 'Tonga', 'Trinidad and Tobago',
    'Tunisia', 'Turkey', 'Turkmenistan', 'Tuvalu', 'Uganda', 'Ukraine', 'United Arab Emirates', 'United Kingdom', 'United States',
    'Uruguay', 'Uzbekistan', 'Vanuatu', 'Vatican City', 'Venezuela', 'Vietnam', 'Yemen', 'Zambia', 'Zimbabwe'
]

# ============= DATABASE MODELS =============

class SalesRep(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    email = db.Column(db.String(200))
    phone = db.Column(db.String(50))
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    investors = db.relationship('Investor', backref='sales_rep', lazy=True)

class Investor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50))  # Individual or Company
    country = db.Column(db.String(100))  # NEW: Country field
    investment_amount = db.Column(db.Float, nullable=False)
    investment_date = db.Column(db.Date, nullable=False)
    sales_rep_id = db.Column(db.Integer, db.ForeignKey('sales_rep.id'))
    
    # ROI Split
    investor_roi_percent = db.Column(db.Float, default=2.5)
    sales_roi_percent    = db.Column(db.Float, default=2.5)
    # TG % — target percentage used for ROI Pool calculation (default 5%)
    tg_percent = db.Column(db.Float, default=5.0)
    
    # Contract Management
    contract_start = db.Column(db.Date)  # NEW: Contract start date
    contract_end = db.Column(db.Date)    # NEW: Contract end date (auto-calculated as +1 year)
    contract_file = db.Column(db.Text)   # NEW: Base64 encoded contract PDF
    
    status = db.Column(db.String(50), default='Active')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    monthly_records = db.relationship('MonthlyRecord', backref='investor', lazy=True, cascade='all, delete-orphan')
    investment_transactions = db.relationship('InvestmentTransaction', backref='investor', lazy=True, cascade='all, delete-orphan')
    manual_roi_records = db.relationship('ManualROI', backref='investor', lazy=True, cascade='all, delete-orphan')
    
    @property
    def total_capital(self):
        """Total capital (initial + deposits - withdrawals)"""
        deposits = sum(t.amount for t in self.investment_transactions if t.transaction_type == 'Deposit')
        withdrawals = sum(t.amount for t in self.investment_transactions if t.transaction_type == 'Withdrawal')
        return self.investment_amount + deposits - withdrawals
    
    @property
    def total_roi_pool(self):
        """TG% of total capital (default 5%)"""
        return self.total_capital * ((self.tg_percent or 5.0) / 100)
    
    @property
    def monthly_investor_roi(self):
        """Investor's share of ROI (based on total capital)"""
        return self.total_capital * (self.investor_roi_percent / 100)
    
    @property
    def monthly_sales_roi(self):
        """Sales rep's share of ROI (based on total capital)"""
        return self.total_capital * (self.sales_roi_percent / 100)
    
    @property
    def contract_expiry_warning(self):
        """Check if contract expires in 90 days"""
        if not self.contract_end:
            return False
        days_remaining = (self.contract_end - date.today()).days
        return 0 <= days_remaining <= 90

class InvestmentTransaction(db.Model):
    """Track deposits, withdrawals, and payouts for each investor"""
    id = db.Column(db.Integer, primary_key=True)
    investor_id = db.Column(db.Integer, db.ForeignKey('investor.id'), nullable=False)
    
    transaction_type = db.Column(db.String(20), nullable=False)  # Deposit, Withdrawal, Investor Payout, Sales Payout
    amount = db.Column(db.Float, nullable=False)
    transaction_date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text)
    payment_evidence = db.Column(db.Text)  # Base64 encoded receipt/bank transfer proof
    
    # NEW: Payout tracking (for Investor Payout and Sales Payout types)
    payout_month = db.Column(db.Integer)  # Which month this payout is for (1-12)
    payout_year = db.Column(db.Integer)   # Which year this payout is for
    source_type = db.Column(db.String(50))  # 'Investor ROI' or 'Sales Share'
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class MonthlyRecord(db.Model):
    """Tracks monthly revenue and distributions per investor"""
    id = db.Column(db.Integer, primary_key=True)
    investor_id = db.Column(db.Integer, db.ForeignKey('investor.id'), nullable=False)
    
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)  # 1-12
    
    # Manual entry
    revenue_generated = db.Column(db.Float, default=0)  # Actual revenue this month
    
    # Auto-calculated
    investor_roi_paid = db.Column(db.Float, default=0)
    sales_roi_paid = db.Column(db.Float, default=0)
    
    payment_date = db.Column(db.Date)
    payment_method = db.Column(db.String(100))
    notes = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @property
    def month_name(self):
        return datetime(self.year, self.month, 1).strftime('%B %Y')

class PartnerDistribution(db.Model):
    """Monthly profit distribution to partners"""
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    
    total_revenue = db.Column(db.Float, default=0)
    total_roi_distributed = db.Column(db.Float, default=0)
    remaining_profit = db.Column(db.Float, default=0)
    
    # Partner shares (can be adjusted)
    shafaqat_percent = db.Column(db.Float, default=33.33)
    shubham_percent = db.Column(db.Float, default=33.33)
    kay_percent = db.Column(db.Float, default=33.34)
    
    shafaqat_amount = db.Column(db.Float, default=0)
    shubham_amount = db.Column(db.Float, default=0)
    kay_amount = db.Column(db.Float, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @property
    def month_name(self):
        return datetime(self.year, self.month, 1).strftime('%B %Y')


class ManualROI(db.Model):
    """Manual monthly ROI entry with automatic distribution"""
    id = db.Column(db.Integer, primary_key=True)
    investor_id = db.Column(db.Integer, db.ForeignKey('investor.id'), nullable=False)
    
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    
    total_roi_generated = db.Column(db.Float, nullable=False)
    investor_share = db.Column(db.Float, default=0)
    sales_share = db.Column(db.Float, default=0)
    
    entry_date = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @property
    def month_name(self):
        months = ['January', 'February', 'March', 'April', 'May', 'June', 
                  'July', 'August', 'September', 'October', 'November', 'December']
        return f"{months[self.month-1]} {self.year}"

class GlobalRevenue(db.Model):
    """Track total revenue generated (single row table)"""
    id = db.Column(db.Integer, primary_key=True)
    total_revenue = db.Column(db.Float, default=0)  # Total revenue generated
    input_mode = db.Column(db.String(20), default='amount')  # 'amount' or 'percentage'
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @staticmethod
    def get_instance():
        """Get or create the single instance"""
        instance = GlobalRevenue.query.first()
        if not instance:
            instance = GlobalRevenue(total_revenue=0)
            db.session.add(instance)
            db.session.commit()
        return instance


class RevenueHistory(db.Model):
    """Track monthly revenue entries with date"""
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    revenue_amount     = db.Column(db.Float, default=0)    # always in AED
    revenue_usd        = db.Column(db.Float, nullable=True) # original USD if entered in USD
    exchange_rate_used = db.Column(db.Float, nullable=True) # rate used at time of entry
    input_mode         = db.Column(db.String(20), default='amount')
    notes              = db.Column(db.Text)
    entry_date         = db.Column(db.DateTime, default=datetime.utcnow)
    # Capital snapshot for this month
    capital_aed        = db.Column(db.Float, nullable=True) # total capital AED at time of entry
    capital_usd        = db.Column(db.Float, nullable=True) # total capital USD at time of entry
    capital_pct        = db.Column(db.Float, nullable=True) # revenue as % of capital

    @property
    def month_name(self):
        return datetime(self.year, self.month, 1).strftime('%B %Y')

class UserAccount(db.Model):
    """Partner/admin accounts — login via email + password"""
    id           = db.Column(db.Integer, primary_key=True)
    email        = db.Column(db.String(200), unique=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    password_hash= db.Column(db.String(256), nullable=False)
    role         = db.Column(db.String(20), default='partner')  # 'admin' or 'partner'
    active       = db.Column(db.Boolean, default=True)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    last_login   = db.Column(db.DateTime, nullable=True)
    profile_pic  = db.Column(db.String(256), nullable=True)

class AuditLog(db.Model):
    """Track every add / edit / delete action"""
    id          = db.Column(db.Integer, primary_key=True)
    timestamp   = db.Column(db.DateTime, default=datetime.utcnow)
    username    = db.Column(db.String(80), nullable=False)   # who did it
    action      = db.Column(db.String(20), nullable=False)   # ADD / EDIT / DELETE / LOGIN / LOGOUT
    target_type = db.Column(db.String(60), nullable=False)   # Investor / Transaction / Revenue / etc.
    target_id   = db.Column(db.Integer,   nullable=True)     # id of affected record
    target_name = db.Column(db.String(200),nullable=True)    # human label e.g. investor name
    detail      = db.Column(db.Text,      nullable=True)     # extra detail / old value

# ============= TRADING ACCOUNTS =============

class TradingAccount(db.Model):
    __tablename__ = 'trading_accounts'
    id              = db.Column(db.Integer, primary_key=True)
    broker_name     = db.Column(db.String(100), nullable=False)
    account_holder  = db.Column(db.String(100))               # account holder name (broker account name)
    investor_name   = db.Column(db.String(100))               # actual investor person name
    account_number  = db.Column(db.String(60))
    deposit_via     = db.Column(db.String(30), default='Bank') # Cash, Crypto, Bank
    platform        = db.Column(db.String(40), default='MT5')  # MT5, MT4, cTrader
    symbol          = db.Column(db.String(30), default='XAUUSD')  # trading symbol
    currency        = db.Column(db.String(10), default='USD')
    total_invested  = db.Column(db.Float, default=0.0)   # total deposits
    total_withdrawn = db.Column(db.Float, default=0.0)   # total withdrawals
    current_balance = db.Column(db.Float, default=0.0)   # current balance
    notes           = db.Column(db.Text)
    is_active       = db.Column(db.Boolean, default=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    profits = db.relationship('AccountProfit', backref='account', lazy=True, cascade='all, delete-orphan')
    transactions = db.relationship('AccountTransaction', backref='account', lazy=True, cascade='all, delete-orphan')

    @property
    def total_generated(self):
        """Total profit ever generated = (current balance - capital) + total withdrawn"""
        return (self.current_balance - self.total_invested) + self.total_withdrawn

    @property
    def profit_ready(self):
        """Profit still sitting in account = total generated - already withdrawn"""
        return self.total_generated - self.total_withdrawn

    @property
    def net_profit(self):
        """Alias for profit_ready (used in summaries)"""
        return self.profit_ready

    @property
    def roi_pct(self):
        if self.total_invested and self.total_invested > 0:
            return (self.total_generated / self.total_invested) * 100
        return 0.0

    @property
    def today_profit(self):
        from datetime import date
        today = date.today()
        p = AccountProfit.query.filter_by(account_id=self.id, profit_date=today).first()
        return p.profit_amount if p else 0.0

    @property
    def week_profit(self):
        from datetime import date, timedelta
        import sqlalchemy as sa
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        try:
            total = db.session.query(db.func.sum(AccountProfit.profit_amount)).filter(
                AccountProfit.account_id == self.id,
                sa.cast(AccountProfit.profit_date, sa.Date) >= week_start,
                sa.cast(AccountProfit.profit_date, sa.Date) <= today
            ).scalar()
        except Exception:
            total = db.session.query(db.func.sum(AccountProfit.profit_amount)).filter(
                AccountProfit.account_id == self.id,
                AccountProfit.profit_date >= str(week_start),
                AccountProfit.profit_date <= str(today)
            ).scalar()
        return total or 0.0

    @property
    def month_profit(self):
        from datetime import date
        import sqlalchemy as sa
        today = date.today()
        month_start = today.replace(day=1)
        try:
            total = db.session.query(db.func.sum(AccountProfit.profit_amount)).filter(
                AccountProfit.account_id == self.id,
                sa.cast(AccountProfit.profit_date, sa.Date) >= month_start,
                sa.cast(AccountProfit.profit_date, sa.Date) <= today
            ).scalar()
        except Exception:
            total = db.session.query(db.func.sum(AccountProfit.profit_amount)).filter(
                AccountProfit.account_id == self.id,
                AccountProfit.profit_date >= str(month_start),
                AccountProfit.profit_date <= str(today)
            ).scalar()
        return total or 0.0

    @property
    def total_profit(self):
        total = db.session.query(db.func.sum(AccountProfit.profit_amount)).filter(
            AccountProfit.account_id == self.id
        ).scalar()
        return total or 0.0


class AccountProfit(db.Model):
    __tablename__ = 'account_profits'
    id             = db.Column(db.Integer, primary_key=True)
    account_id     = db.Column(db.Integer, db.ForeignKey('trading_accounts.id'), nullable=False)
    profit_date    = db.Column(db.Date, nullable=False)
    profit_amount  = db.Column(db.Float, default=0.0)
    notes          = db.Column(db.String(200))
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)


class AccountTransaction(db.Model):
    __tablename__ = 'account_transactions'
    id             = db.Column(db.Integer, primary_key=True)
    account_id     = db.Column(db.Integer, db.ForeignKey('trading_accounts.id'), nullable=False)
    txn_date       = db.Column(db.Date, nullable=False)
    txn_type       = db.Column(db.String(20), nullable=False)  # deposit / withdrawal
    amount         = db.Column(db.Float, default=0.0)
    notes          = db.Column(db.String(200))
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)


# ============= FOREX INVESTOR MODELS =============

class ForexInvestor(db.Model):
    __tablename__ = 'forex_investors'
    id                  = db.Column(db.Integer, primary_key=True)
    name                = db.Column(db.String(100), nullable=False)
    capital_usd         = db.Column(db.Float, default=0.0)       # investment in USD
    broker_pct          = db.Column(db.Float, default=0.0)       # % you take FROM broker profit
    investor_pct        = db.Column(db.Float, default=0.0)       # % you PAY TO investor per month
    broker_name         = db.Column(db.String(100), default='')  # which broker account
    sales_rep           = db.Column(db.String(100), default='')  # who brought this investor
    status              = db.Column(db.String(20), default='Active')
    notes               = db.Column(db.String(300), default='')
    contract_start      = db.Column(db.Date, nullable=True)
    trading_account_id  = db.Column(db.Integer, db.ForeignKey('trading_accounts.id'), nullable=True)
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)

    # Link to trading account
    trading_account = db.relationship('TradingAccount', backref='forex_investors', lazy=True)

    @property
    def display_name(self):
        """Use trading account holder name if linked"""
        if self.trading_account and self.trading_account.account_holder:
            return self.trading_account.account_holder
        return self.name

    @property
    def display_capital(self):
        """Use trading account total_invested if linked"""
        if self.trading_account:
            return self.trading_account.total_invested
        return self.capital_usd

    @property
    def display_broker(self):
        """Use trading account broker name if linked"""
        if self.trading_account:
            return self.trading_account.broker_name
        return self.broker_name

    @property
    def monthly_investor_due(self):
        """$ due to investor per month"""
        return round(self.display_capital * (self.investor_pct / 100), 2)

    @property
    def monthly_broker_take(self):
        """$ you take from broker per month (on investor capital)"""
        return round(self.display_capital * (self.broker_pct / 100), 2)

    @property
    def monthly_net_per_investor(self):
        """your net per month from this investor"""
        return round(self.monthly_broker_take - self.monthly_investor_due, 2)


class ForexMonthlyProfit(db.Model):
    __tablename__ = 'forex_monthly_profits'
    id              = db.Column(db.Integer, primary_key=True)
    year            = db.Column(db.Integer, nullable=False)
    month           = db.Column(db.Integer, nullable=False)
    broker_name     = db.Column(db.String(100), default='All')  # broker filter
    total_generated = db.Column(db.Float, default=0.0)          # total broker profit this month
    notes           = db.Column(db.String(300), default='')
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    MONTH_NAMES = ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

    @property
    def month_name(self):
        return self.MONTH_NAMES[self.month] if 0 < self.month <= 12 else str(self.month)


class ForexInvestorPayout(db.Model):
    __tablename__ = 'forex_investor_payouts'
    id              = db.Column(db.Integer, primary_key=True)
    investor_id     = db.Column(db.Integer, db.ForeignKey('forex_investors.id'), nullable=False)
    year            = db.Column(db.Integer, nullable=False)
    month           = db.Column(db.Integer, nullable=False)
    amount_paid     = db.Column(db.Float, default=0.0)
    paid_date       = db.Column(db.Date, nullable=True)
    notes           = db.Column(db.String(200), default='')
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    investor        = db.relationship('ForexInvestor', backref='payouts')


# ============= DATABASE INITIALIZATION =============

def audit(action, target_type, target_name='', target_id=None, detail=''):
    """Write one audit log entry for the current session user"""
    try:
        entry = AuditLog(
            username    = session.get('username', 'unknown'),
            action      = action,
            target_type = target_type,
            target_id   = target_id,
            target_name = target_name,
            detail      = detail,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception as e:
        print(f'Audit log error: {e}')

@app.before_request
def ensure_db_ready():
    """Ensure database tables exist before handling any request"""
    if not hasattr(app, '_db_initialized'):
        try:
            db.create_all()
            
            # Add sample sales reps if none exist
            if SalesRep.query.count() == 0:
                reps = [
                    SalesRep(name="John Smith", email="john@topgee.com"),
                    SalesRep(name="Sarah Johnson", email="sarah@topgee.com"),
                    SalesRep(name="Ahmed Ali", email="ahmed@topgee.com")
                ]
                for rep in reps:
                    db.session.add(rep)
                db.session.commit()
                print(f"✅ Added {len(reps)} sample sales reps")
            
            # Add new columns if missing (safe migration)
            # Safe column migrations
            migrations = [
                ('revenue_history', 'revenue_usd',        'FLOAT'),
                ('revenue_history', 'exchange_rate_used', 'FLOAT'),
                ('revenue_history', 'capital_aed',        'FLOAT'),
                ('revenue_history', 'capital_usd',        'FLOAT'),
                ('revenue_history', 'capital_pct',        'FLOAT'),
                ('investor',        'tg_percent',         'FLOAT DEFAULT 5.0'),
                ('user_account',     'profile_pic',        'VARCHAR(256)'),
                ('trading_accounts', 'account_holder',     'VARCHAR(100)'),
                ('trading_accounts', 'investor_name',      'VARCHAR(100)'),
                ('trading_accounts', 'deposit_via',        'VARCHAR(30)'),
                ('forex_investors',  'broker_name',        'VARCHAR(100) DEFAULT ""'),
                ('forex_investors',  'sales_rep',          'VARCHAR(100) DEFAULT ""'),
                ('forex_investors',  'notes',              'VARCHAR(300) DEFAULT ""'),
                ('forex_investors',  'contract_start',     'DATE'),
                ('forex_investors',  'trading_account_id', 'INTEGER'),
            ]
            for table, col, typ in migrations:
                try:
                    with db.engine.connect() as conn:
                        conn.execute(db.text(f'ALTER TABLE {table} ADD COLUMN {col} {typ}'))
                        conn.commit()
                        print(f'✅ Added {table}.{col}')
                except Exception:
                    pass  # already exists

            # Backfill: set tg_percent=5.0 only where it is NULL (won't touch custom values like 6.5)
            try:
                with db.engine.connect() as conn:
                    result = conn.execute(db.text("UPDATE investor SET tg_percent = 5.0 WHERE tg_percent IS NULL"))
                    conn.commit()
                    if result.rowcount:
                        print(f'✅ Backfilled {result.rowcount} investor(s) tg_percent NULL → 5.0')
            except Exception as bf_e:
                print(f'⚠️ tg_percent backfill skipped: {bf_e}')

            app._db_initialized = True
            print("✅ Database initialized successfully")
        except Exception as e:
            print(f"⚠️ DB init failed: {e}")
            import traceback
            traceback.print_exc()

# ============= ROUTES =============

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form['email'].strip().lower()
        password = request.form['password']
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        # Check master admin (email login)
        if email == ADMIN_EMAIL.lower() and password_hash == ADMIN_PASSWORD_HASH:
            session['logged_in']    = True
            session['is_admin']     = True
            session['username']     = 'admin'
            session['display_name'] = 'Admin'
            audit('LOGIN', 'System', email)
            flash('Login successful!', 'success')
            return redirect(url_for('home'))

        # Check UserAccount table by email
        user = UserAccount.query.filter_by(email=email, active=True).first()
        if user and user.password_hash == password_hash:
            session['logged_in']    = True
            session['is_admin']     = (user.role == 'admin')
            session['username']     = user.email
            session['display_name'] = user.display_name
            user.last_login = datetime.utcnow()
            db.session.commit()
            audit('LOGIN', 'System', email)
            flash(f'Welcome, {user.display_name}!', 'success')
            return redirect(url_for('home'))

        flash('Invalid email or password', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    audit('LOGOUT', 'System', session.get('username',''))
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))

@app.route('/profile')
@login_required
def profile():
    email = session.get('username', '')
    display_name = session.get('display_name', '')
    is_admin = session.get('is_admin', False)
    user = UserAccount.query.filter_by(email=email).first() if email != 'admin' else None
    return render_template('profile.html',
        username=email,
        display_name=display_name,
        is_admin=is_admin,
        user=user
    )

@app.route('/profile/upload-photo', methods=['POST'])
@login_required
def upload_profile_photo():
    import uuid
    email = session.get('username', '')
    user = UserAccount.query.filter_by(email=email).first()
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('profile'))
    file = request.files.get('photo')
    if not file or file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('profile'))
    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
        flash('Only JPG, PNG, GIF, WEBP allowed', 'error')
        return redirect(url_for('profile'))
    upload_dir = os.path.join(app.root_path, 'static', 'profile_pics')
    os.makedirs(upload_dir, exist_ok=True)
    filename = f'{uuid.uuid4().hex[:8]}.{ext}'
    file.save(os.path.join(upload_dir, filename))
    # Delete old pic
    if user.profile_pic:
        old_path = os.path.join(upload_dir, user.profile_pic)
        if os.path.exists(old_path):
            os.remove(old_path)
    user.profile_pic = filename
    db.session.commit()
    flash('Profile photo updated!', 'success')
    return redirect(url_for('profile'))

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current = request.form.get('current_password', '')
        new_pass = request.form.get('new_password', '')
        confirm  = request.form.get('confirm_password', '')

        current_hash = hashlib.sha256(current.encode()).hexdigest()
        email = session.get('username', '')

        # Admin password change
        if email == 'admin':
            global ADMIN_PASSWORD_HASH
            if current_hash != ADMIN_PASSWORD_HASH:
                flash('Current password is incorrect', 'error')
                return redirect(url_for('change_password'))
            if len(new_pass) < 6:
                flash('New password must be at least 6 characters', 'error')
                return redirect(url_for('change_password'))
            if new_pass != confirm:
                flash('New passwords do not match', 'error')
                return redirect(url_for('change_password'))
            ADMIN_PASSWORD_HASH = hashlib.sha256(new_pass.encode()).hexdigest()
            flash('Password changed successfully!', 'success')
            return redirect(url_for('home'))

        # Regular user password change
        user = UserAccount.query.filter_by(email=email).first()
        if not user or user.password_hash != current_hash:
            flash('Current password is incorrect', 'error')
            return redirect(url_for('change_password'))
        if len(new_pass) < 6:
            flash('New password must be at least 6 characters', 'error')
            return redirect(url_for('change_password'))
        if new_pass != confirm:
            flash('New passwords do not match', 'error')
            return redirect(url_for('change_password'))
        user.password_hash = hashlib.sha256(new_pass.encode()).hexdigest()
        db.session.commit()
        flash('Password changed successfully!', 'success')
        return redirect(url_for('home'))

    return render_template('change_password.html')

@app.route('/debug')
@login_required
def debug_check():
    """Debug route to check what's failing"""
    results = []
    
    try:
        investors = Investor.query.all()
        results.append(f"✅ Investors: {len(investors)} found")
    except Exception as e:
        results.append(f"❌ Investors query failed: {e}")
    
    try:
        sales_reps = SalesRep.query.all()
        results.append(f"✅ SalesReps: {len(sales_reps)} found")
    except Exception as e:
        results.append(f"❌ SalesReps query failed: {e}")
    
    try:
        global_revenue = GlobalRevenue.query.first()
        results.append(f"✅ GlobalRevenue: {global_revenue.total_revenue if global_revenue else 'None'}")
    except Exception as e:
        results.append(f"❌ GlobalRevenue query failed: {e}")
    
    try:
        if investors:
            test_investor = investors[0]
            total_cap = test_investor.total_capital
            results.append(f"✅ total_capital property works: {total_cap}")
    except Exception as e:
        results.append(f"❌ total_capital property failed: {e}")
    
    try:
        total_inv = sum(i.total_capital for i in investors)
        results.append(f"✅ Sum of total_capital: {total_inv}")
    except Exception as e:
        results.append(f"❌ Sum calculation failed: {e}")
    
    return "<h1>Debug Check</h1>" + "<br>".join(results)

@app.route('/home')
@login_required
def home():
    """Landing page — choose TopG It or Forex"""
    # Quick stats for both sides
    from sqlalchemy import func
    now = datetime.now()

    # TopG It stats
    topg_investors = Investor.query.filter_by(status='Active').count()
    topg_capital   = sum(i.total_capital for i in Investor.query.filter_by(status='Active').all())
    topg_monthly   = sum(i.monthly_investor_roi for i in Investor.query.filter_by(status='Active').all())

    # Forex stats
    forex_investors = ForexInvestor.query.filter_by(status='Active').count()
    forex_capital   = sum(i.capital_usd for i in ForexInvestor.query.filter_by(status='Active').all())
    forex_net       = sum(i.monthly_net_per_investor for i in ForexInvestor.query.filter_by(status='Active').all())

    return render_template('home.html',
        topg_investors=topg_investors, topg_capital=topg_capital, topg_monthly=topg_monthly,
        forex_investors=forex_investors, forex_capital=forex_capital, forex_net=forex_net,
        now=now,
    )


@app.route('/')
@login_required
def dashboard():
    """Main dashboard"""
    _prefix_re = re.compile(r'^(Mr\.?|Mrs\.?|Ms\.?|Dr\.?)\s*', re.IGNORECASE)
    def _sort_key(inv): return _prefix_re.sub('', inv.name).strip().lower()
    investors = sorted(Investor.query.all(), key=_sort_key)
    sales_reps = SalesRep.query.filter_by(active=True).all()
    
    # Current month/year
    now = datetime.now()
    current_year = now.year
    current_month = now.month
    
    # Get current month records
    current_records = MonthlyRecord.query.filter_by(year=current_year, month=current_month).all()
    
    # Calculate totals
    total_investors = len(investors)
    total_investment = sum(i.total_capital for i in investors)
    
    # Get live exchange rate
    exchange_rate = get_live_exchange_rate()
    total_investment_usd = total_investment / exchange_rate
    
    # NEW DASHBOARD METRICS
    # ROI Pool = sum of each investor's (capital × tg_percent)
    investment_roi_5_percent = sum(i.total_capital * ((i.tg_percent or 5.0) / 100) for i in investors)
    
    # Get global revenue
    global_revenue = GlobalRevenue.get_instance()
    total_revenue_generated = global_revenue.total_revenue
    
    # Gross Profit = Total Revenue - ROI Pool
    gross_profit         = total_revenue_generated - investment_roi_5_percent
    final_in_hand_profit = gross_profit

    # ROI Distribution
    total_investor_roi = sum(i.monthly_investor_roi for i in investors)
    total_sales_share  = sum(i.monthly_sales_roi    for i in investors)
    extra_profit       = max(0, investment_roi_5_percent - total_investor_roi)

    total_roi_pool       = total_investor_roi + total_sales_share
    investor_roi_percent = (total_investor_roi / total_roi_pool * 100) if total_roi_pool > 0 else 0
    sales_share_percent  = (total_sales_share  / total_roi_pool * 100) if total_roi_pool > 0 else 0

    # TG % stats
    # Weighted avg TG% by capital (not simple average)
    _tg_capital_sum = sum((i.tg_percent or 5.0) * i.total_capital for i in investors)
    _tg_total_cap   = sum(i.total_capital for i in investors)
    avg_tg_percent  = (_tg_capital_sum / _tg_total_cap) if _tg_total_cap > 0 else 5.0
    tg_breakdown   = [{'name': i.name, 'capital': i.total_capital,
                        'tg_pct': i.tg_percent or 5.0,
                        'pool_amount': i.total_capital * ((i.tg_percent or 5.0) / 100)}
                      for i in investors]

    partner_share = gross_profit / 3
    
    # Current month totals (OLD - for reference)
    monthly_revenue = sum(r.revenue_generated for r in current_records)
    monthly_roi_distributed = sum(r.investor_roi_paid + r.sales_roi_paid for r in current_records)
    sales_earnings = sum(r.sales_roi_paid for r in current_records)
    
    # Partner distribution for current month
    partner_dist = PartnerDistribution.query.filter_by(year=current_year, month=current_month).first()
    
    stats = {
        'total_investors': total_investors,
        'total_investment': total_investment,
        'total_investment_usd': total_investment_usd,
        'exchange_rate': exchange_rate,
        'investment_roi_5_percent': investment_roi_5_percent,
        'total_revenue_generated': total_revenue_generated,
        'final_in_hand_profit': final_in_hand_profit,
        'gross_profit':         gross_profit,
        'total_investor_roi': total_investor_roi,
        'total_sales_share':  total_sales_share,
        'extra_profit':         extra_profit,
        'avg_tg_percent':       avg_tg_percent,
        'tg_breakdown':         tg_breakdown,
        'investor_roi_percent': investor_roi_percent,
        'sales_share_percent':  sales_share_percent,
        'partner_shafay': partner_share,
        'partner_shubham': partner_share,
        'partner_kay': partner_share,
        'monthly_revenue': monthly_revenue,
        'monthly_roi_distributed': monthly_roi_distributed,
        'sales_earnings': sales_earnings,
        'partner_distribution': partner_dist,
        'current_month': now.strftime('%B %Y')
    }
    
    # Search functionality
    search_query = request.args.get('search', '')
    # Filter params
    filter_category = request.args.get('filter_category', '')
    filter_sales_rep = request.args.get('filter_sales_rep', '')
    filter_status = request.args.get('filter_status', '')

    if search_query or filter_category or filter_sales_rep or filter_status:
        query = Investor.query.filter_by(status='Active')
        if search_query:
            query = query.filter(
                db.or_(
                    Investor.name.ilike(f'%{search_query}%'),
                    Investor.category.ilike(f'%{search_query}%'),
                    Investor.notes.ilike(f'%{search_query}%')
                )
            )
        if filter_category:
            query = query.filter(Investor.category == filter_category)
        if filter_sales_rep:
            query = query.join(SalesRep).filter(SalesRep.name.ilike(f'%{filter_sales_rep}%'))
        if filter_status:
            query = query.filter(Investor.status == filter_status)
        investors = sorted(query.all(), key=_sort_key)
    
    # Revenue history for the month/date table
    revenue_history = RevenueHistory.query.order_by(
        RevenueHistory.year.desc(), RevenueHistory.month.desc()
    ).limit(24).all()

    return render_template('dashboard.html',
                         investors=investors,
                         sales_reps=sales_reps,
                         stats=stats,
                         current_year=current_year,
                         current_month=current_month,
                         search_query=search_query,
                         filter_category=filter_category,
                         filter_sales_rep=filter_sales_rep,
                         filter_status=filter_status,
                         revenue_history=revenue_history,
                         is_admin=session.get('is_admin', False))

@app.route('/investor/<int:investor_id>')
@login_required
def investor_detail(investor_id):
    investor = Investor.query.get_or_404(investor_id)
    now = datetime.now()
    current_year = now.year
    
    # Get manual ROI records for current year
    manual_records = ManualROI.query.filter_by(investor_id=investor.id, year=current_year).all()
    
    # Get payout transactions for current year
    payout_transactions = InvestmentTransaction.query.filter_by(
        investor_id=investor.id,
        transaction_type='Investor Payout'
    ).filter(
        InvestmentTransaction.payout_year == current_year
    ).all()
    
    # Build 12-month ledger with payout tracking + excess/advance carry-forward
    months = ['January', 'February', 'March', 'April', 'May', 'June',
              'July', 'August', 'September', 'October', 'November', 'December']
    ledger = []
    carried_excess = 0.0  # running excess carried forward from overpayments

    for month_num in range(1, 13):
        record = next((r for r in manual_records if r.month == month_num), None)
        month_payouts = [t for t in payout_transactions if t.payout_month == month_num]
        total_paid = sum(p.amount for p in month_payouts)
        expected_roi = investor.monthly_investor_roi

        if total_paid > 0:
            # Total running surplus = what was paid + any carried excess - what was due
            raw_diff = total_paid + carried_excess - expected_roi
            if raw_diff > 0.005:
                excess_after = round(raw_diff, 2)
                paid_status  = 'overpaid'
                carried_excess = raw_diff
            elif raw_diff < -0.005:
                excess_after = 0.0
                paid_status  = 'partial'
                carried_excess = 0.0
            else:
                excess_after = 0.0
                paid_status  = 'paid'
                carried_excess = 0.0
        else:
            excess_after = 0.0
            # Don't reset carry on unpaid months — excess still carries forward
            paid_status = 'unpaid'

        ledger.append({
            'month': month_num,
            'month_name': months[month_num - 1],
            'record': record,
            'payouts': month_payouts,
            'total_paid': total_paid,
            'expected_roi': expected_roi,
            'excess_after': excess_after,
            'paid_status': paid_status,
        })

    # Pass current carry to template for next-payment info
    current_carry = round(carried_excess, 2)
    
    # Get all manual ROI records for totals
    all_manual_records = ManualROI.query.filter_by(investor_id=investor.id).all()
    total_roi_generated = sum(r.total_roi_generated for r in all_manual_records)
    total_investor_share = sum(r.investor_share for r in all_manual_records)
    total_sales_share = sum(r.sales_share for r in all_manual_records)
    
    # Get transactions
    transactions = InvestmentTransaction.query.filter_by(investor_id=investor.id).order_by(
        InvestmentTransaction.transaction_date.desc()
    ).all()
    
    deposits = sum(t.amount for t in transactions if t.transaction_type == 'Deposit')
    withdrawals = sum(t.amount for t in transactions if t.transaction_type == 'Withdrawal')
    investor_payouts = sum(t.amount for t in transactions if t.transaction_type == 'Investor Payout')
    sales_payouts = sum(t.amount for t in transactions if t.transaction_type == 'Sales Payout')
    net_capital = investor.investment_amount + deposits - withdrawals
    
    # Get old monthly records (legacy)
    records = MonthlyRecord.query.filter_by(investor_id=investor.id).order_by(
        MonthlyRecord.year.desc(), MonthlyRecord.month.desc()
    ).limit(12).all()
    
    total_revenue = sum(r.revenue_generated for r in records)
    total_investor_roi = sum(r.investor_roi_paid for r in records)
    total_sales_roi = sum(r.sales_roi_paid for r in records)
    
    return render_template('investor_detail.html',
                         investor=investor,
                         ledger=ledger,
                         current_carry=round(current_carry, 2),
                         transactions=transactions,
                         deposits=deposits,
                         withdrawals=withdrawals,
                         investor_payouts=investor_payouts,
                         sales_payouts=sales_payouts,
                         net_capital=net_capital,
                         total_roi_generated=total_roi_generated,
                         total_investor_share=total_investor_share,
                         total_sales_share=total_sales_share,
                         records=records,
                         total_revenue=total_revenue,
                         total_investor_roi=total_investor_roi,
                         total_sales_roi=total_sales_roi,
                         current_year=current_year,
                         is_admin=session.get('is_admin', False),
                         exchange_rate=EXCHANGE_RATE)


@app.route('/investor/add', methods=['GET', 'POST'])
@admin_required
def add_investor():
    if request.method == 'POST':
        # Handle currency conversion
        currency = request.form.get('currency', 'AED')
        amount = float(request.form['investment_amount'])
        
        if currency == 'USD':
            investment_aed = amount * EXCHANGE_RATE
        else:
            investment_aed = amount
        
        # Contract dates (default 1 year)
        contract_start = datetime.strptime(request.form['contract_start'], '%Y-%m-%d').date() if request.form.get('contract_start') else None
        contract_end = None
        if contract_start:
            # Auto-calculate end date (1 year from start)
            from dateutil.relativedelta import relativedelta
            contract_end = contract_start + relativedelta(years=1)
        
        investor = Investor(
            name=request.form['name'],
            category=request.form['category'],
            country=request.form.get('country', ''),
            investment_amount=investment_aed,
            investment_date=datetime.strptime(request.form['investment_date'], '%Y-%m-%d'),
            sales_rep_id=int(request.form['sales_rep_id']) if request.form.get('sales_rep_id') else None,
            investor_roi_percent=float(request.form.get('investor_roi_percent', 2.5)),
            sales_roi_percent=float(request.form.get('sales_roi_percent', 0) or 0),
            tg_percent=float(request.form.get('tg_percent', 5.0)),
            contract_start=contract_start,
            contract_end=contract_end,
            status=request.form.get('status', 'Active'),
            notes=request.form.get('notes', '')
        )
        db.session.add(investor)
        db.session.commit()
        audit('ADD', 'Investor', investor.name, investor.id, f'Capital: {investment_aed:,.0f} AED, ROI: {investor.investor_roi_percent}%')
        return redirect(url_for('dashboard'))
    
    sales_reps = SalesRep.query.filter_by(active=True).all()
    return render_template('add_investor.html', sales_reps=sales_reps, countries=COUNTRIES)

@app.route('/investor/<int:investor_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_investor(investor_id):
    investor = Investor.query.get_or_404(investor_id)
    
    if request.method == 'POST':
        # Handle currency conversion
        currency = request.form.get('currency', 'AED')
        amount = float(request.form['investment_amount'])
        
        if currency == 'USD':
            investment_aed = amount * EXCHANGE_RATE
        else:
            investment_aed = amount
        
        # Contract dates
        contract_start = datetime.strptime(request.form['contract_start'], '%Y-%m-%d').date() if request.form.get('contract_start') else None
        contract_end = None
        if contract_start:
            from dateutil.relativedelta import relativedelta
            contract_end = contract_start + relativedelta(years=1)
        
        investor.name = request.form['name']
        investor.category = request.form['category']
        investor.country = request.form.get('country', '')
        investor.investment_amount = investment_aed
        investor.investment_date = datetime.strptime(request.form['investment_date'], '%Y-%m-%d')
        investor.sales_rep_id = int(request.form['sales_rep_id']) if request.form.get('sales_rep_id') else None
        investor.investor_roi_percent = float(request.form.get('investor_roi_percent', 2.5))
        investor.tg_percent           = float(request.form.get('tg_percent', 5.0))
        investor.sales_roi_percent = float(request.form.get('sales_roi_percent', 2.5))
        investor.contract_start = contract_start
        investor.contract_end = contract_end
        investor.status = request.form.get('status', 'Active')
        investor.notes = request.form.get('notes', '')
        
        db.session.commit()
        audit('EDIT', 'Investor', investor.name, investor.id, f'Capital: {investment_aed:,.0f} AED, ROI: {investor.investor_roi_percent}%')
        return redirect(url_for('investor_detail', investor_id=investor.id))
    
    sales_reps = SalesRep.query.filter_by(active=True).all()
    return render_template('edit_investor.html', investor=investor, sales_reps=sales_reps, countries=COUNTRIES)

@app.route('/investor/<int:investor_id>/delete', methods=['POST'])
@admin_required
def delete_investor(investor_id):
    investor = Investor.query.get_or_404(investor_id)
    audit('DELETE', 'Investor', investor.name, investor.id, f'Capital was: {investor.total_capital:,.0f} AED')
    db.session.delete(investor)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/monthly/<int:year>/<int:month>')
@login_required
def monthly_view(year, month):
    """Monthly overview - all investors for a specific month"""
    records = MonthlyRecord.query.filter_by(year=year, month=month).all()
    partner_dist = PartnerDistribution.query.filter_by(year=year, month=month).first()
    
    month_name = datetime(year, month, 1).strftime('%B %Y')
    
    # Calculate month totals
    total_revenue = sum(r.revenue_generated for r in records)
    total_roi = sum(r.investor_roi_paid + r.sales_roi_paid for r in records)
    remaining = total_revenue - total_roi
    
    return render_template('monthly_view.html',
                         year=year,
                         month=month,
                         month_name=month_name,
                         records=records,
                         partner_dist=partner_dist,
                         total_revenue=total_revenue,
                         total_roi=total_roi,
                         remaining=remaining)

@app.route('/monthly/record/add', methods=['POST'])
@admin_required
def add_monthly_record():
    """Add/update monthly record for an investor"""
    investor_id = int(request.form['investor_id'])
    year = int(request.form['year'])
    month = int(request.form['month'])
    revenue = float(request.form['revenue_generated'])
    
    investor = Investor.query.get_or_404(investor_id)
    
    # Check if record exists
    record = MonthlyRecord.query.filter_by(
        investor_id=investor_id,
        year=year,
        month=month
    ).first()
    
    if not record:
        record = MonthlyRecord(
            investor_id=investor_id,
            year=year,
            month=month
        )
        db.session.add(record)
    
    # Update values
    record.revenue_generated = revenue
    record.investor_roi_paid = investor.monthly_investor_roi
    record.sales_roi_paid = investor.monthly_sales_roi
    record.payment_date = datetime.strptime(request.form['payment_date'], '%Y-%m-%d') if request.form.get('payment_date') else None
    record.payment_method = request.form.get('payment_method', '')
    record.notes = request.form.get('notes', '')
    
    db.session.commit()
    
    # Recalculate partner distribution for this month
    calculate_partner_distribution(year, month)
    
    return redirect(url_for('investor_detail', investor_id=investor_id))

def calculate_partner_distribution(year, month):
    """Calculate and save partner profit distribution for a month"""
    records = MonthlyRecord.query.filter_by(year=year, month=month).all()
    
    total_revenue = sum(r.revenue_generated for r in records)
    total_roi = sum(r.investor_roi_paid + r.sales_roi_paid for r in records)
    remaining = total_revenue - total_roi
    
    # Get or create distribution record
    dist = PartnerDistribution.query.filter_by(year=year, month=month).first()
    if not dist:
        dist = PartnerDistribution(year=year, month=month)
        db.session.add(dist)
    
    dist.total_revenue = total_revenue
    dist.total_roi_distributed = total_roi
    dist.remaining_profit = remaining
    
    # Calculate partner shares
    dist.shafaqat_amount = remaining * (dist.shafaqat_percent / 100)
    dist.shubham_amount = remaining * (dist.shubham_percent / 100)
    dist.kay_amount = remaining * (dist.kay_percent / 100)
    
    db.session.commit()

@app.route('/reports/investor/<int:investor_id>/ledger')
def download_investor_ledger(investor_id):
    """Download investor monthly ledger as PDF"""
    investor = Investor.query.get_or_404(investor_id)
    records = MonthlyRecord.query.filter_by(investor_id=investor.id).order_by(
        MonthlyRecord.year.desc(), MonthlyRecord.month.desc()
    ).all()
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title = Paragraph(f"<b>Investment Ledger: {investor.name}</b>", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 0.3*inch))
    
    # Investor details
    details = f"""
    <b>Investment Amount:</b> {investor.investment_amount:,.2f} AED<br/>
    <b>Investment Date:</b> {investor.investment_date.strftime('%d-%b-%Y')}<br/>
    <b>Sales Representative:</b> {investor.sales_rep.name if investor.sales_rep else 'N/A'}<br/>
    <b>Actual ROI:</b> {investor.investor_roi_percent}% monthly
    """
    elements.append(Paragraph(details, styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Monthly records table
    data = [['Month', 'Revenue', 'Your ROI', 'Payment Date']]
    for rec in records:
        data.append([
            rec.month_name,
            f"{rec.revenue_generated:,.2f}",
            f"{rec.investor_roi_paid:,.2f}",
            rec.payment_date.strftime('%d-%b-%Y') if rec.payment_date else '-'
        ])
    
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(table)
    
    doc.build(elements)
    buffer.seek(0)
    
    return send_file(buffer, as_attachment=True, download_name=f'{investor.name}_ledger.pdf', mimetype='application/pdf')

@app.route('/sales-reps')
@login_required
def sales_reps():
    """Manage sales representatives"""
    reps = SalesRep.query.all()
    return render_template('sales_reps.html', 
                         sales_reps=reps,
                         is_admin=session.get('is_admin', False))

@app.route('/sales-rep/add', methods=['POST'])
@admin_required
def add_sales_rep():
    rep = SalesRep(
        name=request.form['name'],
        email=request.form.get('email', ''),
        phone=request.form.get('phone', '')
    )
    db.session.add(rep)
    db.session.commit()
    flash('Sales representative added successfully!', 'success')
    return redirect(url_for('sales_reps'))

@app.route('/sales-rep/<int:rep_id>/edit', methods=['POST'])
@admin_required
def edit_sales_rep(rep_id):
    rep = SalesRep.query.get_or_404(rep_id)
    rep.name = request.form['name']
    rep.email = request.form.get('email', '')
    rep.phone = request.form.get('phone', '')
    rep.active = request.form.get('active', 'true') == 'true'
    db.session.commit()
    flash(f'Sales representative "{rep.name}" updated successfully!', 'success')
    return redirect(url_for('sales_reps'))

@app.route('/sales-rep/<int:rep_id>/delete', methods=['POST'])
@admin_required
def delete_sales_rep(rep_id):
    rep = SalesRep.query.get_or_404(rep_id)
    rep_name = rep.name
    
    # Unassign all investors from this rep
    for investor in rep.investors:
        investor.sales_rep_id = None
    
    db.session.delete(rep)
    db.session.commit()
    flash(f'Sales representative "{rep_name}" deleted successfully!', 'success')
    return redirect(url_for('sales_reps'))

@app.route('/advanced-search')
@login_required
def advanced_search():
    """Advanced search with filters"""
    # Get filter parameters
    min_amount = request.args.get('min_amount', type=float)
    max_amount = request.args.get('max_amount', type=float)
    category = request.args.get('category', '')
    min_roi = request.args.get('min_roi', type=float)
    max_roi = request.args.get('max_roi', type=float)
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    sales_rep_id = request.args.get('sales_rep_id', type=int)
    
    # Start with all investors
    query = Investor.query
    
    # Apply filters
    if min_amount:
        query = query.filter(Investor.investment_amount >= min_amount)
    if max_amount:
        query = query.filter(Investor.investment_amount <= max_amount)
    if category:
        query = query.filter(Investor.category == category)
    if min_roi:
        query = query.filter(Investor.investor_roi_percent >= min_roi)
    if max_roi:
        query = query.filter(Investor.investor_roi_percent <= max_roi)
    if date_from:
        query = query.filter(Investor.investment_date >= datetime.strptime(date_from, '%Y-%m-%d'))
    if date_to:
        query = query.filter(Investor.investment_date <= datetime.strptime(date_to, '%Y-%m-%d'))
    if sales_rep_id:
        query = query.filter(Investor.sales_rep_id == sales_rep_id)
    
    investors = query.all()
    sales_reps = SalesRep.query.filter_by(active=True).all()
    
    # Calculate totals for filtered results
    total_investment = sum(i.investment_amount for i in investors)
    total_investors = len(investors)
    
    return render_template('advanced_search.html',
                         investors=investors,
                         sales_reps=sales_reps,
                         total_investment=total_investment,
                         total_investors=total_investors,
                         filters=request.args,
                         exchange_rate=EXCHANGE_RATE)

@app.route('/monthly-grid')
@login_required
def monthly_grid():
    """Monthly grid view for all investors — reads from InvestmentTransaction"""
    import re as _re
    _pfx2 = _re.compile(r'^(Mr\.?|Mrs\.?|Ms\.?|Dr\.?)\s+', _re.IGNORECASE)
    year = request.args.get('year', datetime.now().year, type=int)
    investors = sorted(Investor.query.all(), key=lambda i: _pfx2.sub('', i.name).strip().lower())

    # Pull all investor payouts for this year from InvestmentTransaction
    txns = InvestmentTransaction.query.filter(
        InvestmentTransaction.transaction_type == 'Investor Payout',
        InvestmentTransaction.payout_year == year
    ).all()

    # Build lookup: (investor_id, month) -> total amount paid
    payout_map = {}
    for t in txns:
        if not t.payout_month:
            continue
        key = (t.investor_id, t.payout_month)
        payout_map[key] = payout_map.get(key, 0) + t.amount

    # Build grid_data compatible with template
    grid_data = {}
    for investor in investors:
        months_data = {}
        for month in range(1, 13):
            amt = payout_map.get((investor.id, month))
            if amt:
                months_data[month] = type('Cell', (), {
                    'revenue_generated': amt,
                    'investor_roi_paid': amt,
                    'notes': ''
                })()
            else:
                months_data[month] = None
        grid_data[investor.id] = {
            'investor': investor,
            'months': months_data
        }

    return render_template('monthly_grid.html',
                         grid_data=grid_data,
                         year=year,
                         months=range(1, 13))

@app.route('/reports/customer/<int:investor_id>/monthly/<int:year>/<int:month>')
@login_required
def customer_monthly_report(investor_id, year, month):
    """Generate professional monthly report for customer"""
    investor = Investor.query.get_or_404(investor_id)
    record = MonthlyRecord.query.filter_by(
        investor_id=investor_id,
        year=year,
        month=month
    ).first()
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title = Paragraph(f"<b>TopGee It - Monthly Investment Report</b>", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 0.3*inch))
    
    # Header info
    month_name = datetime(year, month, 1).strftime('%B %Y')
    header_data = [
        ['Investor:', investor.name],
        ['Report Period:', month_name],
        ['Investment Amount:', f"{investor.investment_amount:,.2f} AED"],
        ['Investment Date:', investor.investment_date.strftime('%d %B %Y')],
    ]
    header_table = Table(header_data, colWidths=[2*inch, 4*inch])
    header_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Monthly performance
    if record:
        perf_data = [
            ['Monthly Performance', ''],
            ['Revenue Generated:', f"{record.revenue_generated:,.2f} AED"],
            [f'Your ROI ({investor.investor_roi_percent:.1f}%):', f"{record.investor_roi_paid:,.2f} AED"],
            ['Payment Date:', record.payment_date.strftime('%d %B %Y') if record.payment_date else 'Pending'],
            ['Payment Method:', record.payment_method or 'N/A'],
        ]
    else:
        perf_data = [
            ['Monthly Performance', ''],
            ['Status:', 'No activity recorded for this month'],
        ]
    
    perf_table = Table(perf_data, colWidths=[2*inch, 4*inch])
    perf_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 13),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('FONTSIZE', (0, 1), (-1, -1), 11),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(perf_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Footer
    footer = Paragraph("<i>Thank you for your investment with TopGee It</i>", styles['Normal'])
    elements.append(footer)
    
    doc.build(elements)
    buffer.seek(0)
    
    filename = f"TopGeeIt_{investor.name.replace(' ', '_')}_{month_name.replace(' ', '_')}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')

@app.route('/reports/dashboard')
@login_required
def reports_dashboard():
    """Full reports: investor active/paid, sales rep, revenue, month-wise"""
    report_type      = request.args.get('report_type', 'investor_active')
    date_from        = request.args.get('date_from', '')
    date_to          = request.args.get('date_to', '')
    investor_id_filt = request.args.get('investor_id', '')
    rep_id_filt      = request.args.get('rep_id', '')
    month_filt       = request.args.get('month', '')
    year_filt        = request.args.get('year', str(datetime.now().year))
    paid_filter      = request.args.get('paid_filter', '')  # '' | 'paid' | 'unpaid'

    _pfx = re.compile(r'^(Mr\.?|Mrs\.?|Ms\.?|Dr\.?)\s*', re.IGNORECASE)
    def _sk(inv): return _pfx.sub('', inv.name).strip().lower()

    all_investors   = sorted(Investor.query.all(), key=_sk)
    all_sales_reps  = SalesRep.query.filter_by(active=True).all()
    global_rev      = GlobalRevenue.get_instance()
    revenue_history = RevenueHistory.query.order_by(
        RevenueHistory.year.desc(), RevenueHistory.month.desc()).all()
    now           = datetime.now()
    exchange_rate = get_live_exchange_rate()

    MONTHS = ['January','February','March','April','May','June',
              'July','August','September','October','November','December']

    # Build per-investor row
    def build_inv_row(inv):
        txns = InvestmentTransaction.query.filter_by(investor_id=inv.id).all()
        inv_payouts   = [t for t in txns if t.transaction_type == 'Investor Payout']
        sales_payouts = [t for t in txns if t.transaction_type == 'Sales Payout']
        months_active = 0
        if inv.contract_start:
            months_active = max(0,(now.year-inv.contract_start.year)*12+(now.month-inv.contract_start.month))
        total_paid     = sum(t.amount for t in inv_payouts)
        # New outstanding logic: count months from contract start to last completed month
        # that have NO payout recorded (any amount = cleared, regardless of fixed %)
        # Untagged payouts: use total untagged amount to absorb months by value
        paid_months = set()
        for t in inv_payouts:
            if t.payout_month and t.payout_year:
                paid_months.add((t.payout_year, t.payout_month))
        untagged_amount = sum(t.amount for t in inv_payouts if not (t.payout_month and t.payout_year))
        pending_months = 0
        outstanding = 0.0
        monthly_ref = inv.monthly_investor_roi if inv.monthly_investor_roi > 0 else 1
        TRACK_FROM = (2026, 6)  # Only track outstanding from June 2026 onwards
        if inv.contract_start:
            y, m = max((inv.contract_start.year, inv.contract_start.month), TRACK_FROM)
            last_y, last_m = now.year, now.month - 1
            if last_m == 0:
                last_m = 12
                last_y -= 1
            while (y < last_y) or (y == last_y and m <= last_m):
                if (y, m) not in paid_months:
                    if untagged_amount >= monthly_ref:
                        untagged_amount -= monthly_ref  # absorb one month's worth
                    elif untagged_amount > 0:
                        untagged_amount = 0  # partial — still counts as paid
                    else:
                        pending_months += 1
                        outstanding += inv.monthly_investor_roi
                m += 1
                if m > 12:
                    m = 1
                    y += 1
        total_ever_due = inv.monthly_investor_roi * months_active
        # payout txns filtered by date
        payout_txns = []
        for t in inv_payouts:
            if date_from and str(t.transaction_date) < date_from: continue
            if date_to   and str(t.transaction_date) > date_to:   continue
            payout_txns.append(t)
        # sales payouts filtered by date
        sales_payout_txns_filtered = []
        for t in sales_payouts:
            if date_from and str(t.transaction_date) < date_from: continue
            if date_to   and str(t.transaction_date) > date_to:   continue
            sales_payout_txns_filtered.append(t)
        # month-wise breakdown
        monthly = {}
        for t in inv_payouts + sales_payouts:
            if t.payout_month and t.payout_year:
                key = (t.payout_year, t.payout_month)
                if key not in monthly:
                    monthly[key] = {'inv':0,'sales':0}
                if t.transaction_type == 'Investor Payout':
                    monthly[key]['inv'] += t.amount
                else:
                    monthly[key]['sales'] += t.amount
        return {
            'inv':             inv,
            'capital':         inv.total_capital,
            'monthly_roi':     inv.monthly_investor_roi,
            'sales_monthly':   inv.monthly_sales_roi,
            'total_paid':      total_paid,
            'total_sales_paid':         sum(t.amount for t in sales_payouts),
            'total_sales_paid_filtered': sum(t.amount for t in sales_payout_txns_filtered),
            'sales_payout_txns_filtered': sales_payout_txns_filtered,
            'total_ever_due':  total_ever_due,
            'outstanding':     outstanding,
            'pending_months':  pending_months,
            'months_active':   months_active,
            'monthly':         monthly,
            'payout_txns':     payout_txns,
            'rep_name':        inv.sales_rep.name if inv.sales_rep else '—',
            'rep_id':          inv.sales_rep_id,
        }

    all_rows = [build_inv_row(inv) for inv in all_investors]

    # Filter by single investor
    filtered_rows = [r for r in all_rows if str(r['inv'].id) == investor_id_filt] if investor_id_filt else all_rows

    # Filter by specific month/year (investor_active report)
    sel_month = int(month_filt) if month_filt else 0
    sel_year  = int(year_filt)  if year_filt  else 0
    if sel_month and sel_year and report_type == 'investor_active':
        def _investor_active_in_month(r):
            """Return True if investor's contract started on or before sel_month/sel_year"""
            cs = r['inv'].contract_start
            if not cs:
                return False
            return (cs.year, cs.month) <= (sel_year, sel_month)

        def _month_paid(r):
            """Return True if this investor has any payout tagged for sel_month/sel_year"""
            key = (sel_year, sel_month)
            return r['monthly'].get(key, {}).get('inv', 0) > 0

        # Always exclude investors not yet active in the selected month
        filtered_rows = [r for r in filtered_rows if _investor_active_in_month(r)]

        if paid_filter == 'paid':
            filtered_rows = [r for r in filtered_rows if _month_paid(r)]
        elif paid_filter == 'unpaid':
            filtered_rows = [r for r in filtered_rows if not _month_paid(r)]
        # else: show all active-in-month investors

    # Sales rep rows
    has_date_filter = bool(date_from and date_to)
    sales_rep_rows = []
    for rep in all_sales_reps:
        ri = [r for r in all_rows if r['rep_id'] == rep.id]
        sales_rep_rows.append({
            'rep':                      rep,
            'investor_count':           len(ri),
            'total_capital':            sum(r['capital'] for r in ri),
            'total_sales_monthly':      sum(r['sales_monthly'] for r in ri),
            'total_sales_paid':         sum(r['total_sales_paid'] for r in ri),
            'total_sales_paid_filtered':sum(r['total_sales_paid_filtered'] for r in ri),
            'investors':                ri,
        })
    if rep_id_filt:
        sales_rep_rows = [r for r in sales_rep_rows if str(r['rep'].id) == rep_id_filt]

    # Month-wise rows — support date range (date_from / date_to)
    yr = int(year_filt) if year_filt else now.year
    month_rows = []
    total_investment_val = sum(r['capital'] for r in all_rows)

    # Parse date range for month-wise
    mw_from = None
    mw_to   = None
    if report_type == 'monthwise':
        if date_from:
            try: mw_from = datetime.strptime(date_from, '%Y-%m-%d')
            except: pass
        if date_to:
            try: mw_to = datetime.strptime(date_to, '%Y-%m-%d')
            except: pass

    # Build month range covering the date span (or full year if no range)
    if mw_from and mw_to:
        months_to_show = []
        cur = mw_from.replace(day=1)
        end = mw_to.replace(day=1)
        while cur <= end:
            months_to_show.append((cur.year, cur.month))
            if cur.month == 12:
                cur = cur.replace(year=cur.year+1, month=1)
            else:
                cur = cur.replace(month=cur.month+1)
    else:
        months_to_show = [(yr, m) for m in range(1, 13)]

    for (y_key, m_key) in months_to_show:
        key = (y_key, m_key)
        inv_paid   = sum(r['monthly'].get(key,{}).get('inv',0)   for r in all_rows)
        sales_paid = sum(r['monthly'].get(key,{}).get('sales',0) for r in all_rows)
        rev        = next((h.revenue_amount for h in revenue_history if h.year==y_key and h.month==m_key), 0)
        partner    = rev - (total_investment_val * 0.05) if rev else 0
        month_rows.append({
            'month_name':  f"{MONTHS[m_key-1]} {y_key}",
            'month_num':   m_key,
            'year':        y_key,
            'inv_paid':    inv_paid,
            'sales_paid':  sales_paid,
            'revenue':     rev,
            'partner_share': partner,
            'has_data':    inv_paid > 0 or sales_paid > 0 or rev > 0,
        })

    # Stats
    total_investment  = sum(r['capital']     for r in all_rows)
    total_paid_all    = sum(r['total_paid']  for r in all_rows)
    total_outstanding = sum(r['outstanding'] for r in all_rows)
    total_monthly_due = sum(r['monthly_roi'] for r in all_rows)
    total_sales_paid  = sum(r['total_sales_paid'] for r in all_rows)

    # Correct ROI calculations
    total_investor_roi_mo = sum(r['monthly_roi']    for r in all_rows)  # sum of each investor's actual ROI%
    total_sales_roi_mo    = sum(r['sales_monthly']  for r in all_rows)  # sum of sales rep shares
    total_roi_pool_mo     = total_investor_roi_mo + total_sales_roi_mo  # total monthly obligation
    gross_revenue         = global_rev.total_revenue
    # Partner profit = Revenue - what we owe investors (sales share excluded)
    partner_profit        = gross_revenue - total_investor_roi_mo
    er                    = exchange_rate if exchange_rate else 3.67

    stats = {
        'total_investors':      len(all_rows),
        'individual_count':     sum(1 for r in all_rows if r['inv'].category == 'Individual'),
        'company_count':        sum(1 for r in all_rows if r['inv'].category == 'Company'),
        'total_investment':     total_investment,
        'total_investment_usd': total_investment / er,
        'total_paid':           total_paid_all,
        'total_paid_usd':       total_paid_all / er,
        'total_outstanding':    total_outstanding,
        'total_outstanding_usd':total_outstanding / er,
        'total_monthly_due':    total_monthly_due,
        'total_sales_paid':     total_sales_paid,
        'total_sales_paid_usd': total_sales_paid / er,
        'global_revenue':       gross_revenue,
        'global_revenue_usd':   gross_revenue / er,
        # Correct ROI figures
        'total_investor_roi_mo':    total_investor_roi_mo,
        'total_investor_roi_mo_usd':total_investor_roi_mo / er,
        'total_sales_roi_mo':       total_sales_roi_mo,
        'total_sales_roi_mo_usd':   total_sales_roi_mo / er,
        'total_roi_pool_mo':        total_roi_pool_mo,
        'total_roi_pool_mo_usd':    total_roi_pool_mo / er,
        'partner_profit':           partner_profit,
        'partner_profit_usd':       partner_profit / er,
        'partner_each':             partner_profit / 3,
        'partner_each_usd':         partner_profit / 3 / er,
        # Keep old key for backward compat
        'partner_share':            partner_profit,
        'global_revenue_raw':       gross_revenue,
        'exchange_rate':            er,
    }

    return render_template('reports_dashboard.html',
        report_type      = report_type,
        all_rows         = all_rows,
        filtered_rows    = filtered_rows,
        sales_rep_rows   = sales_rep_rows,
        month_rows       = month_rows,
        revenue_history  = revenue_history,
        all_investors    = all_investors,
        all_sales_reps   = all_sales_reps,
        stats            = stats,
        filters          = request.args,
        exchange_rate    = exchange_rate,
        year_filt        = yr,
        MONTHS           = MONTHS,
        has_date_filter  = has_date_filter,
        date_from        = date_from,
        date_to          = date_to,
        now              = now,
        sel_month        = sel_month,
        sel_year         = sel_year,
        paid_filter      = paid_filter,
    )

@app.route('/reports/export-csv')
@login_required
def reports_export_csv():
    """Export filtered investor_active report as CSV"""
    import csv, io
    investor_id_filt = request.args.get('investor_id', '')
    month_filt       = request.args.get('month', '')
    year_filt        = request.args.get('year', str(datetime.now().year))
    paid_filter      = request.args.get('paid_filter', '')

    MONTHS = ['January','February','March','April','May','June',
              'July','August','September','October','November','December']
    _pfx = re.compile(r'^(Mr\.?|Mrs\.?|Ms\.?|Dr\.?)\s*', re.IGNORECASE)
    def _sk(inv): return _pfx.sub('', inv.name).strip().lower()
    all_investors = sorted(Investor.query.all(), key=_sk)
    now = datetime.now()

    def build_inv_row(inv):
        txns = InvestmentTransaction.query.filter_by(investor_id=inv.id).all()
        inv_payouts = [t for t in txns if t.transaction_type == 'Investor Payout']
        months_active = 0
        if inv.contract_start:
            months_active = max(0,(now.year-inv.contract_start.year)*12+(now.month-inv.contract_start.month))
        total_paid = sum(t.amount for t in inv_payouts)
        paid_months = set()
        for t in inv_payouts:
            if t.payout_month and t.payout_year:
                paid_months.add((t.payout_year, t.payout_month))
        untagged_amount = sum(t.amount for t in inv_payouts if not (t.payout_month and t.payout_year))
        pending_months = 0
        outstanding = 0.0
        monthly_ref = inv.monthly_investor_roi if inv.monthly_investor_roi > 0 else 1
        TRACK_FROM = (2026, 6)
        monthly = {}
        for t in inv_payouts:
            if t.payout_month and t.payout_year:
                key = (t.payout_year, t.payout_month)
                monthly[key] = monthly.get(key, 0) + t.amount
        if inv.contract_start:
            y, m = max((inv.contract_start.year, inv.contract_start.month), TRACK_FROM)
            last_y, last_m = now.year, now.month - 1
            if last_m == 0: last_m = 12; last_y -= 1
            while (y < last_y) or (y == last_y and m <= last_m):
                if (y, m) not in paid_months:
                    if untagged_amount >= monthly_ref: untagged_amount -= monthly_ref
                    elif untagged_amount > 0: untagged_amount = 0
                    else: pending_months += 1; outstanding += inv.monthly_investor_roi
                m += 1
                if m > 12: m = 1; y += 1
        return {
            'inv': inv, 'capital': inv.total_capital, 'monthly_roi': inv.monthly_investor_roi,
            'total_paid': total_paid, 'outstanding': outstanding, 'pending_months': pending_months,
            'months_active': months_active, 'monthly': monthly,
            'rep_name': inv.sales_rep.name if inv.sales_rep else '—',
        }

    all_rows = [build_inv_row(inv) for inv in all_investors]
    filtered_rows = [r for r in all_rows if str(r['inv'].id) == investor_id_filt] if investor_id_filt else all_rows

    sel_month = int(month_filt) if month_filt else 0
    sel_year  = int(year_filt)  if year_filt  else 0

    if sel_month and sel_year:
        filtered_rows = [r for r in filtered_rows
                         if r['inv'].contract_start and
                         (r['inv'].contract_start.year, r['inv'].contract_start.month) <= (sel_year, sel_month)]
        if paid_filter == 'paid':
            filtered_rows = [r for r in filtered_rows if r['monthly'].get((sel_year, sel_month), 0) > 0]
        elif paid_filter == 'unpaid':
            filtered_rows = [r for r in filtered_rows if r['monthly'].get((sel_year, sel_month), 0) == 0]

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    month_label = f"{MONTHS[sel_month-1]} {sel_year}" if sel_month and sel_year else 'All Time'
    status_label = paid_filter.capitalize() if paid_filter else 'All'
    # Sort by sales rep name, then investor name
    filtered_rows.sort(key=lambda r: (r['rep_name'].lower(), r['inv'].name.lower()))

    writer.writerow([f'TopGee It — Investor Report'])
    writer.writerow([f'Period: {month_label}  |  Status: {status_label}'])
    writer.writerow([])
    writer.writerow(['#', 'Investor', 'Sales Rep', 'Capital (AED)', 'TG %', 'ROI %',
                     'Est. Monthly (AED)', 'Total Paid (AED)',
                     'Pending Months', 'Outstanding (AED)',
                     f'Paid {month_label}' if (sel_month and sel_year) else 'Month Status'])

    for idx, r in enumerate(filtered_rows, start=1):
        month_paid_amt = r['monthly'].get((sel_year, sel_month), 0) if (sel_month and sel_year) else ''
        if sel_month and sel_year:
            month_status = f"Paid ({month_paid_amt:,.0f})" if month_paid_amt > 0 else 'Unpaid'
        else:
            month_status = ''
        tg_percent = r['inv'].tg_percent or 5.0
        writer.writerow([
            idx,
            r['inv'].name,
            r['rep_name'],
            f"{r['capital']:,.0f}",
            f"{tg_percent:.1f}%",
            f"{r['inv'].investor_roi_percent}%",
            f"{r['monthly_roi']:,.0f}",
            f"{r['total_paid']:,.0f}",
            r['pending_months'],
            f"{r['outstanding']:,.0f}",
            month_status,
        ])

    total_tg  = sum((r['inv'].tg_percent or 5.0) for r in filtered_rows)
    total_roi = sum(r['inv'].investor_roi_percent for r in filtered_rows)
    writer.writerow([])
    writer.writerow(['', 'TOTAL', '',
                     f"{sum(r['capital'] for r in filtered_rows):,.0f}",
                     f"{total_tg:.1f}%",
                     f"{total_roi:.1f}%",
                     f"{sum(r['monthly_roi'] for r in filtered_rows):,.0f}",
                     f"{sum(r['total_paid'] for r in filtered_rows):,.0f}", '',
                     f"{sum(r['outstanding'] for r in filtered_rows):,.0f}", ''])

    from flask import make_response
    today = datetime.now().strftime('%Y-%m-%d')
    month_slug = f"_{MONTHS[sel_month-1]}_{sel_year}" if sel_month and sel_year else ''
    status_slug = f"_{paid_filter}" if paid_filter else ''
    filename = f"TopGeeIt_InvestorReport{month_slug}{status_slug}_{today}.csv"
    resp = make_response('\ufeff' + output.getvalue())
    resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
    resp.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


@app.route('/investor/<int:investor_id>/transaction/add', methods=['POST'])
@admin_required
def add_transaction(investor_id):
    """Add deposit, withdrawal, or payout transaction"""
    investor = Investor.query.get_or_404(investor_id)
    
    transaction_type = request.form['transaction_type']
    
    # Handle payment evidence upload
    payment_evidence = None
    file = request.files.get('payment_evidence')
    if file and file.filename:
        import base64
        file_data = file.read()
        encoded = base64.b64encode(file_data).decode('utf-8')
        payment_evidence = f"data:{file.mimetype};base64,{encoded}"
    
    # Create transaction
    transaction = InvestmentTransaction(
        investor_id=investor_id,
        transaction_type=transaction_type,
        amount=float(request.form['amount']),
        transaction_date=datetime.strptime(request.form['transaction_date'], '%Y-%m-%d').date(),
        notes=request.form.get('notes', ''),
        payment_evidence=payment_evidence
    )
    
    # For payout transactions, add payout tracking fields
    if transaction_type in ['Investor Payout', 'Sales Payout']:
        payout_month = int(request.form.get('payout_month', datetime.now().month))
        payout_year  = int(request.form.get('payout_year',  datetime.now().year))
        transaction.payout_month = payout_month
        transaction.payout_year  = payout_year
        transaction.source_type  = 'Investor ROI' if transaction_type == 'Investor Payout' else 'Sales Share'

        # ── AUTO-SYNC: upsert ManualROI ledger row for this month ──
        roi_entry = ManualROI.query.filter_by(
            investor_id=investor_id, year=payout_year, month=payout_month
        ).first()
        if roi_entry:
            # Update existing: recalculate from ALL payout transactions for this month
            db.session.add(transaction)   # add first so it's included in sum
            db.session.flush()
            month_payouts = InvestmentTransaction.query.filter_by(
                investor_id=investor_id, payout_year=payout_year, payout_month=payout_month
            ).filter(InvestmentTransaction.transaction_type.in_(['Investor Payout', 'Sales Payout'])).all()
            inv_paid   = sum(t.amount for t in month_payouts if t.transaction_type == 'Investor Payout')
            sales_paid = sum(t.amount for t in month_payouts if t.transaction_type == 'Sales Payout')
            roi_entry.investor_share = inv_paid
            roi_entry.sales_share    = sales_paid
            roi_entry.total_roi_generated = inv_paid + sales_paid
        else:
            # Create new ManualROI entry for this month
            inv_share   = transaction.amount if transaction_type == 'Investor Payout' else 0
            sales_share = transaction.amount if transaction_type == 'Sales Payout' else 0
            roi_entry = ManualROI(
                investor_id=investor_id,
                year=payout_year,
                month=payout_month,
                total_roi_generated=transaction.amount,
                investor_share=inv_share,
                sales_share=sales_share,
                notes=f"Auto-synced from {transaction_type} on {transaction.transaction_date}"
            )
            db.session.add(roi_entry)

    db.session.add(transaction)
    db.session.commit()
    audit('ADD', 'Transaction', investor.name, transaction.id,
          f'{transaction.transaction_type}: {transaction.amount:,.0f} AED on {transaction.transaction_date}')
    flash(f"{transaction.transaction_type} of {transaction.amount:,.2f} AED added and synced to ROI Ledger!", 'success')
    return redirect(url_for('investor_detail', investor_id=investor_id))

@app.route('/investor/<int:investor_id>/contract/upload', methods=['POST'])
@admin_required
def upload_contract(investor_id):
    """Upload signed contract"""
    investor = Investor.query.get_or_404(investor_id)
    
    file = request.files.get('contract_file')
    if file and file.filename:
        import base64
        # Read and encode file as base64
        file_data = file.read()
        encoded = base64.b64encode(file_data).decode('utf-8')
        
        # Store with mimetype prefix
        investor.contract_file = f"data:{file.mimetype};base64,{encoded}"
        db.session.commit()
        
        flash('Contract uploaded successfully!', 'success')
    else:
        flash('No file selected', 'error')
    
    return redirect(url_for('investor_detail', investor_id=investor_id))

@app.route('/investor/<int:investor_id>/contract/download')
@login_required
def download_contract(investor_id):
    """Download signed contract"""
    investor = Investor.query.get_or_404(investor_id)
    
    if not investor.contract_file:
        flash('No contract file available', 'error')
        return redirect(url_for('investor_detail', investor_id=investor_id))
    
    import base64
    import re
    
    # Extract base64 data
    match = re.match(r'data:(.+);base64,(.+)', investor.contract_file)
    if match:
        mimetype = match.group(1)
        encoded_data = match.group(2)
        file_data = base64.b64decode(encoded_data)
        
        buffer = BytesIO(file_data)
        buffer.seek(0)
        
        extension = 'pdf' if 'pdf' in mimetype else 'jpg'
        filename = f"{investor.name.replace(' ', '_')}_contract.{extension}"
        
        return send_file(buffer, as_attachment=True, download_name=filename, mimetype=mimetype)
    else:
        flash('Invalid contract file format', 'error')
        return redirect(url_for('investor_detail', investor_id=investor_id))

@app.route('/investor/<int:investor_id>/contract/delete', methods=['POST'])
@admin_required
def delete_contract(investor_id):
    """Delete signed contract"""
    investor = Investor.query.get_or_404(investor_id)
    
    if investor.contract_file:
        investor.contract_file = None
        db.session.commit()
        flash('Contract deleted successfully!', 'success')
    else:
        flash('No contract file to delete', 'error')
    
    return redirect(url_for('investor_detail', investor_id=investor_id))

@app.route('/investor/<int:investor_id>/contract/renew', methods=['POST'])
@admin_required
def renew_contract(investor_id):
    """Renew contract for another year"""
    investor = Investor.query.get_or_404(investor_id)
    
    if investor.contract_end:
        from dateutil.relativedelta import relativedelta
        # Extend by 1 year from current end date
        investor.contract_end = investor.contract_end + relativedelta(years=1)
        db.session.commit()
        flash(f"Contract renewed until {investor.contract_end.strftime('%d %B %Y')}", 'success')
    else:
        flash('No contract end date set', 'error')
    
    return redirect(url_for('investor_detail', investor_id=investor_id))

@app.route('/investor/<int:investor_id>/contract/dates/update', methods=['POST'])
@admin_required
def update_contract_dates(investor_id):
    """Update contract start/end dates"""
    investor = Investor.query.get_or_404(investor_id)
    
    contract_start = datetime.strptime(request.form['contract_start'], '%Y-%m-%d').date()
    
    # Auto-calculate end date (1 year from start)
    from dateutil.relativedelta import relativedelta
    contract_end = contract_start + relativedelta(years=1)
    
    investor.contract_start = contract_start
    investor.contract_end = contract_end
    db.session.commit()
    
    flash(f"Contract dates updated: {contract_start.strftime('%d %b %Y')} - {contract_end.strftime('%d %b %Y')}", 'success')
    return redirect(url_for('investor_detail', investor_id=investor_id))

@app.route('/investor/<int:investor_id>/contract/dates/delete', methods=['POST'])
@admin_required
def delete_contract_dates(investor_id):
    """Clear contract dates"""
    investor = Investor.query.get_or_404(investor_id)
    
    investor.contract_start = None
    investor.contract_end = None
    db.session.commit()
    
    flash('Contract dates cleared successfully!', 'success')
    return redirect(url_for('investor_detail', investor_id=investor_id))

@app.route('/investor/<int:investor_id>/transaction/<int:transaction_id>/edit', methods=['POST'])
@admin_required
def edit_transaction(investor_id, transaction_id):
    """Edit an existing transaction"""
    transaction = InvestmentTransaction.query.get_or_404(transaction_id)
    
    # Verify transaction belongs to this investor
    if transaction.investor_id != investor_id:
        flash('Invalid transaction', 'error')
        return redirect(url_for('investor_detail', investor_id=investor_id))
    
    # Update transaction fields
    transaction.transaction_type = request.form['transaction_type']
    transaction.amount = float(request.form['amount'])
    transaction.transaction_date = datetime.strptime(request.form['transaction_date'], '%Y-%m-%d').date()
    transaction.notes = request.form.get('notes', '')
    
    # For payout transactions, update payout tracking fields
    if transaction.transaction_type in ['Investor Payout', 'Sales Payout']:
        transaction.payout_month = int(request.form.get('payout_month', datetime.now().month))
        transaction.payout_year = int(request.form.get('payout_year', datetime.now().year))
        transaction.source_type = 'Investor ROI' if transaction.transaction_type == 'Investor Payout' else 'Sales Share'
    else:
        # Clear payout fields for non-payout transactions
        transaction.payout_month = None
        transaction.payout_year = None
        transaction.source_type = None
    
    # Handle payment evidence upload (optional - only if new file provided)
    file = request.files.get('payment_evidence')
    if file and file.filename:
        import base64
        file_data = file.read()
        encoded = base64.b64encode(file_data).decode('utf-8')
        transaction.payment_evidence = f"data:{file.mimetype};base64,{encoded}"
    
    db.session.commit()
    
    flash(f"{transaction.transaction_type} of {transaction.amount:,.2f} AED updated successfully!", 'success')
    return redirect(url_for('investor_detail', investor_id=investor_id))

@app.route('/investor/<int:investor_id>/transaction/<int:transaction_id>/delete', methods=['POST'])
@admin_required
def delete_transaction(investor_id, transaction_id):
    """Delete a transaction (for test entries)"""
    transaction = InvestmentTransaction.query.get_or_404(transaction_id)
    
    # Verify transaction belongs to this investor
    if transaction.investor_id != investor_id:
        flash('Invalid transaction', 'error')
        return redirect(url_for('investor_detail', investor_id=investor_id))
    
    tx_type   = transaction.transaction_type
    tx_amount = transaction.amount
    inv_name  = transaction.investor.name if transaction.investor else str(investor_id)
    audit('DELETE', 'Transaction', inv_name, transaction_id,
          f'{tx_type}: {tx_amount:,.0f} AED on {transaction.transaction_date}')
    db.session.delete(transaction)
    db.session.commit()
    flash(f"{tx_type} of {tx_amount:,.2f} AED deleted successfully!", 'success')
    return redirect(url_for('investor_detail', investor_id=investor_id))

@app.route('/investor/<int:investor_id>/transaction/<int:transaction_id>/evidence')
@login_required
def download_transaction_evidence(investor_id, transaction_id):
    """Download payment evidence for a transaction"""
    transaction = InvestmentTransaction.query.get_or_404(transaction_id)
    
    if not transaction.payment_evidence:
        flash('No payment evidence uploaded', 'error')
        return redirect(url_for('investor_detail', investor_id=investor_id))
    
    import base64
    import re
    
    # Extract base64 data
    match = re.match(r'data:(.+);base64,(.+)', transaction.payment_evidence)
    if match:
        mimetype = match.group(1)
        encoded_data = match.group(2)
        file_data = base64.b64decode(encoded_data)
        
        buffer = BytesIO(file_data)
        buffer.seek(0)
        
        extension = 'pdf' if 'pdf' in mimetype else 'jpg'
        filename = f"payment_evidence_{transaction.id}_{transaction.transaction_date.strftime('%Y%m%d')}.{extension}"
        
        return send_file(buffer, as_attachment=True, download_name=filename, mimetype=mimetype)
    else:
        flash('Invalid evidence file format', 'error')
        return redirect(url_for('investor_detail', investor_id=investor_id))

# Database will be initialized on first request via @app.before_request


@app.route('/investor/<int:investor_id>/manual-roi/add', methods=['POST'])
@admin_required
def add_manual_roi(investor_id):
    investor = Investor.query.get_or_404(investor_id)
    year = int(request.form['year'])
    month = int(request.form['month'])
    total_roi = float(request.form['total_roi_generated'])
    record = ManualROI.query.filter_by(investor_id=investor_id, year=year, month=month).first()
    if not record:
        record = ManualROI(investor_id=investor_id, year=year, month=month)
        db.session.add(record)
    record.total_roi_generated = total_roi
    record.notes = request.form.get('notes', '')
    five_percent = total_roi * 0.05
    investor_percentage = investor.investor_roi_percent
    sales_percentage = investor.sales_roi_percent
    total_percentage = investor_percentage + sales_percentage
    if total_percentage > 0:
        record.investor_share = five_percent * (investor_percentage / total_percentage)
        record.sales_share = five_percent * (sales_percentage / total_percentage)
    else:
        record.investor_share = five_percent * 0.5
        record.sales_share = five_percent * 0.5
    db.session.commit()
    flash(f"ROI entry added: {total_roi:,.2f} AED → Investor: {record.investor_share:,.2f} AED, Sales: {record.sales_share:,.2f} AED", 'success')
    return redirect(url_for('investor_detail', investor_id=investor_id))

@app.route('/investor/<int:investor_id>/manual-roi/delete', methods=['POST'])
@admin_required
def delete_manual_roi(investor_id):
    year = int(request.form['year'])
    month = int(request.form['month'])
    record = ManualROI.query.filter_by(investor_id=investor_id, year=year, month=month).first()
    if record:
        db.session.delete(record)
        db.session.commit()
        flash(f"ROI entry for {record.month_name} deleted successfully!", 'success')
    else:
        flash('ROI entry not found', 'error')
    return redirect(url_for('investor_detail', investor_id=investor_id))

@app.route('/revenue/edit/<int:rev_id>', methods=['POST'])
@admin_required
def edit_revenue(rev_id):
    hist = RevenueHistory.query.get_or_404(rev_id)
    input_mode    = request.form.get('input_mode', 'amount')
    input_value   = float(request.form.get('revenue_value', 0))
    rev_notes     = request.form.get('revenue_notes', '').strip()
    currency      = request.form.get('currency', 'AED')
    exchange_rate = float(request.form.get('exchange_rate', 3.67))
    new_month     = int(request.form.get('revenue_month', hist.month))
    new_year      = int(request.form.get('revenue_year',  hist.year))

    if currency == 'USD':
        amount = input_value * exchange_rate
    elif input_mode == 'percentage':
        total_investment = sum(inv.total_capital for inv in Investor.query.all())
        amount = total_investment * (input_value / 100)
    else:
        amount = input_value

    # Capital snapshot
    investors = Investor.query.all()
    cap_aed = sum(inv.total_capital for inv in investors)
    cap_usd = cap_aed / exchange_rate
    cap_pct = (amount / cap_aed * 100) if cap_aed else None

    hist.month              = new_month
    hist.year               = new_year
    hist.revenue_amount     = amount
    hist.revenue_usd        = input_value if currency == 'USD' else round(amount / exchange_rate, 2)
    hist.exchange_rate_used = exchange_rate
    hist.input_mode         = input_mode
    hist.notes              = rev_notes
    hist.entry_date         = datetime.utcnow()
    hist.capital_aed        = cap_aed
    hist.capital_usd        = cap_usd
    hist.capital_pct        = cap_pct
    db.session.commit()
    flash(f'Revenue updated for {hist.month_name}', 'success')
    return redirect(url_for('analytics_dashboard'))


@app.route('/revenue/delete/<int:rev_id>', methods=['POST'])
@admin_required
def delete_revenue(rev_id):
    hist = RevenueHistory.query.get_or_404(rev_id)
    month_name = hist.month_name
    audit('DELETE', 'Revenue', month_name, rev_id, f'{hist.revenue_amount:,.0f} AED')
    db.session.delete(hist)
    db.session.commit()
    flash(f'Revenue entry for {month_name} deleted.', 'success')
    return redirect(url_for('analytics_dashboard'))


@app.route('/revenue/update', methods=['POST'])
@admin_required
def update_global_revenue():
    """Update total revenue generated + save to monthly history"""
    global_revenue = GlobalRevenue.get_instance()
    
    input_mode    = request.form.get('input_mode', 'amount')
    input_value   = float(request.form['revenue_value'])
    currency      = request.form.get('currency', 'AED')
    exchange_rate = float(request.form.get('exchange_rate', 3.67))
    rev_month = int(request.form.get('revenue_month', datetime.now().month))
    rev_year  = int(request.form.get('revenue_year',  datetime.now().year))
    rev_notes = request.form.get('revenue_notes', '')

    investors = Investor.query.all()
    total_investment = sum(i.total_capital for i in investors)

    if currency == 'USD':
        amount = input_value * exchange_rate
        flash(f"Revenue ${input_value:,.2f} USD = {amount:,.2f} AED saved for {datetime(rev_year, rev_month, 1).strftime('%B %Y')}", 'topg_success')
    elif input_mode == 'percentage':
        amount = total_investment * (input_value / 100)
        flash(f"Revenue {input_value}% = {amount:,.2f} AED saved for {datetime(rev_year, rev_month, 1).strftime('%B %Y')}", 'topg_success')
    else:
        amount = input_value
        flash(f"Revenue {amount:,.2f} AED saved for {datetime(rev_year, rev_month, 1).strftime('%B %Y')}", 'topg_success')

    # Capital snapshot
    cap_aed = total_investment
    cap_usd = total_investment / exchange_rate if exchange_rate else None
    cap_pct = (amount / total_investment * 100) if total_investment else None

    # Update global total
    global_revenue.total_revenue = amount
    global_revenue.input_mode = input_mode

    # Save/update monthly history
    hist = RevenueHistory.query.filter_by(year=rev_year, month=rev_month).first()
    if hist:
        hist.revenue_amount     = amount
        hist.revenue_usd        = input_value if currency == 'USD' else round(amount / exchange_rate, 2)
        hist.exchange_rate_used = exchange_rate
        hist.input_mode         = input_mode
        hist.notes              = rev_notes
        hist.entry_date         = datetime.utcnow()
        hist.capital_aed        = cap_aed
        hist.capital_usd        = cap_usd
        hist.capital_pct        = cap_pct
    else:
        hist = RevenueHistory(year=rev_year, month=rev_month,
                              revenue_amount=amount,
                              revenue_usd=input_value if currency == 'USD' else round(amount / exchange_rate, 2),
                              exchange_rate_used=exchange_rate,
                              input_mode=input_mode, notes=rev_notes,
                              capital_aed=cap_aed, capital_usd=cap_usd, capital_pct=cap_pct)
        db.session.add(hist)

    db.session.commit()
    return redirect(url_for('analytics_dashboard'))

@app.route('/analytics')
@login_required
def analytics_dashboard():
    """Analytics — full business overview + investor breakdown"""
    _pfx = re.compile(r'^(Mr\.?|Mrs\.?|Ms\.?|Dr\.)\s*', re.IGNORECASE)
    def _skey(inv): return _pfx.sub('', inv.name).strip().lower()

    investors      = sorted(Investor.query.filter_by(status='Active').all(), key=_skey)
    global_revenue = GlobalRevenue.get_instance()
    now            = datetime.now()
    current_month  = now.month
    current_year   = now.year
    exchange_rate  = get_live_exchange_rate()

    # ── investor rows ──
    investor_rows      = []
    total_paid_clients = 0.0
    total_monthly_due  = 0.0
    total_investment   = 0.0
    today = date.today()

    for inv in investors:
        txns = InvestmentTransaction.query.filter_by(investor_id=inv.id).all()
        inv_payout_txns = [t for t in txns if t.transaction_type in ['Investor Payout', 'payout']]
        paid = sum(t.amount for t in inv_payout_txns)
        monthly_due = inv.monthly_investor_roi
        if inv.contract_start:
            months_elapsed = max(0, (today.year - inv.contract_start.year)*12 +
                                    (today.month - inv.contract_start.month))
        else:
            months_elapsed = 0
        # New outstanding: count closed months with no payout recorded
        # Untagged payouts: use total amount to absorb months by value
        paid_months_set = set()
        for t in inv_payout_txns:
            if t.payout_month and t.payout_year:
                paid_months_set.add((t.payout_year, t.payout_month))
        untagged_amt = sum(t.amount for t in inv_payout_txns if not (t.payout_month and t.payout_year))
        monthly_ref2 = monthly_due if monthly_due > 0 else 1
        outstanding = 0.0
        pending_count = 0
        TRACK_FROM2 = (2026, 6)  # Only track outstanding from June 2026 onwards
        if inv.contract_start:
            cy, cm = max((inv.contract_start.year, inv.contract_start.month), TRACK_FROM2)
            last_y, last_m = today.year, today.month - 1
            if last_m == 0:
                last_m = 12
                last_y -= 1
            while (cy < last_y) or (cy == last_y and cm <= last_m):
                if (cy, cm) not in paid_months_set:
                    if untagged_amt >= monthly_ref2:
                        untagged_amt -= monthly_ref2
                    elif untagged_amt > 0:
                        untagged_amt = 0
                    else:
                        pending_count += 1
                        outstanding += monthly_due
                cm += 1
                if cm > 12:
                    cm = 1
                    cy += 1
        total_ever_due = monthly_due * months_elapsed
        total_paid_clients += paid
        total_monthly_due  += monthly_due
        total_investment   += inv.total_capital
        investor_rows.append({
            'id': inv.id,
            'name': inv.name,
            'category': inv.category or 'Individual',
            'capital': inv.total_capital,
            'inv_pct': inv.investor_roi_percent,
            'sales_pct': inv.sales_roi_percent,
            'monthly_due': monthly_due,
            'total_ever_due': total_ever_due,
            'paid': paid,
            'outstanding': outstanding,
            'pending_months': pending_count,
            'rep': inv.sales_rep.name if inv.sales_rep else '—',
            'status': inv.status or 'Active',
            'contract_start': inv.contract_start,
            'contract_end': inv.contract_end,
            'months_elapsed': months_elapsed,
        })

    # ── summary stats (same as dashboard) ──
    total_investment_val      = total_investment
    investment_roi_5_percent  = sum(inv.total_capital * ((inv.tg_percent or 5.0) / 100) for inv in investors)
    total_revenue_generated   = global_revenue.total_revenue
    gross_profit              = total_revenue_generated - investment_roi_5_percent
    final_in_hand_profit      = gross_profit
    total_investor_roi        = sum(inv.monthly_investor_roi for inv in investors)
    total_sales_share         = sum(inv.monthly_sales_roi    for inv in investors)
    total_roi_pool            = total_investor_roi + total_sales_share
    investor_roi_percent      = (total_investor_roi / total_roi_pool * 100) if total_roi_pool > 0 else 0
    sales_share_percent       = (total_sales_share  / total_roi_pool * 100) if total_roi_pool > 0 else 0
    partner_share             = gross_profit / 3
    extra_profit              = max(0, investment_roi_5_percent - total_investor_roi)

    stats = {
        'total_investors':          len(investors),
        'total_investment':         total_investment_val,
        'total_investment_usd':     total_investment_val / exchange_rate,
        'exchange_rate':            exchange_rate,
        'investment_roi_5_percent': investment_roi_5_percent,
        'total_revenue_generated':  total_revenue_generated,
        'final_in_hand_profit':     final_in_hand_profit,
        'gross_profit':             gross_profit,
        'total_investor_roi':       total_investor_roi,
        'total_sales_share':        total_sales_share,
        'extra_profit':             extra_profit,
        'avg_tg_percent':           (sum((inv.tg_percent or 5.0) * inv.total_capital for inv in investors) / sum(inv.total_capital for inv in investors)) if investors and sum(inv.total_capital for inv in investors) > 0 else 5.0,
        'tg_breakdown':             [{'name': inv.name, 'capital': inv.total_capital,
                                      'tg_pct': inv.tg_percent or 5.0,
                                      'pool_amount': inv.total_capital * ((inv.tg_percent or 5.0) / 100)}
                                     for inv in investors],
        'investor_roi_percent':     investor_roi_percent,
        'sales_share_percent':      sales_share_percent,
        'partner_shafay':           partner_share,
        'partner_shubham':          partner_share,
        'partner_kay':              partner_share,
        'current_month':            now.strftime('%B %Y'),
    }

    revenue_history = RevenueHistory.query.order_by(
        RevenueHistory.year.desc(), RevenueHistory.month.desc()
    ).limit(24).all()

    # Compute total USD: use stored revenue_usd if available, else convert from AED
    total_revenue_usd = sum(
        h.revenue_usd if h.revenue_usd else h.revenue_amount / exchange_rate
        for h in revenue_history
    ) if revenue_history else total_revenue_generated / exchange_rate

    # For the card, use most recent entry's USD if it matches the global revenue
    latest = revenue_history[0] if revenue_history else None
    if latest and latest.revenue_usd and abs(latest.revenue_amount - total_revenue_generated) < 1:
        total_revenue_usd_display = latest.revenue_usd
    else:
        total_revenue_usd_display = total_revenue_generated / exchange_rate

    return render_template(
        'analytics_dashboard.html',
        investor_rows           = investor_rows,
        investor_count          = len(investor_rows),
        stats                   = stats,
        total_paid_clients      = total_paid_clients,
        total_monthly_due       = total_monthly_due,
        total_outstanding       = sum(r['outstanding'] for r in investor_rows),
        total_inv_roi_share     = total_investor_roi,
        total_sales_share       = total_sales_share,
        final_profit            = final_in_hand_profit,
        revenue_history         = revenue_history,
        total_revenue_usd       = total_revenue_usd_display,
        current_month           = current_month,
        current_year            = current_year,
        is_admin                = session.get('is_admin', False),
    )


@app.route('/theme/preview')
@login_required
def theme_preview():
    """Preview different color themes"""
    return render_template('theme_preview.html')

@app.route('/theme/set/<theme>')
@login_required
def set_theme(theme):
    """Set the active theme"""
    if theme in ['ocean', 'forest', 'royal']:
        session['theme'] = theme
        flash(f"Theme changed to {theme.title()}!", 'success')
    return redirect(request.referrer or url_for('theme_preview'))

# Initialize database tables on startup
print("📊 Initializing database...")
with app.app_context():
    try:
        db.create_all()
        print("✅ Database tables created/verified")
        
        # Ensure GlobalRevenue singleton exists
        from sqlalchemy.exc import OperationalError
        try:
            global_revenue = GlobalRevenue.query.first()
            if not global_revenue:
                global_revenue = GlobalRevenue(total_revenue=0)
                db.session.add(global_revenue)
                db.session.commit()
                print("✅ GlobalRevenue initialized")
        except OperationalError as e:
            print(f"⚠️ GlobalRevenue check failed: {e}")

        # ── Safe column migrations ──────────────────────────────────
        startup_migrations = [
            ('revenue_history', 'revenue_usd',        'FLOAT'),
            ('revenue_history', 'exchange_rate_used', 'FLOAT'),
            ('revenue_history', 'capital_aed',        'FLOAT'),
            ('revenue_history', 'capital_usd',        'FLOAT'),
            ('revenue_history', 'capital_pct',        'FLOAT'),
            ('investor',        'tg_percent',         'FLOAT DEFAULT 5.0'),
            ('user_account',    'profile_pic',        'VARCHAR(256)'),
            ('trading_accounts','account_holder',     'VARCHAR(100)'),
            ('trading_accounts','deposit_via',        'VARCHAR(30)'),
            ('trading_accounts','account_number',     'VARCHAR(60)'),
        ]
        from sqlalchemy import inspect as sa_inspect
        inspector = sa_inspect(db.engine)
        existing_tables = inspector.get_table_names()
        for tbl, col, typ in startup_migrations:
            if tbl not in existing_tables:
                continue
            existing_cols = [c['name'] for c in inspector.get_columns(tbl)]
            if col not in existing_cols:
                try:
                    with db.engine.connect() as conn:
                        conn.execute(db.text(f'ALTER TABLE {tbl} ADD COLUMN {col} {typ}'))
                        conn.commit()
                        print(f'✅ Migrated {tbl}.{col}')
                except Exception as me:
                    print(f'⚠️ Migration {tbl}.{col}: {me}')

        # ── Rename username → email in user_account ────────────────
        try:
            if 'user_account' in existing_tables:
                ua_cols = [c['name'] for c in inspector.get_columns('user_account')]
                if 'username' in ua_cols and 'email' not in ua_cols:
                    with db.engine.connect() as conn:
                        # Add email column first
                        conn.execute(db.text('ALTER TABLE user_account ADD COLUMN email VARCHAR(200)'))
                        # Copy data from username to email
                        conn.execute(db.text('UPDATE user_account SET email = username'))
                        conn.commit()
                        print('✅ Migrated user_account: added email column, copied from username')
                elif 'email' not in ua_cols:
                    with db.engine.connect() as conn:
                        conn.execute(db.text('ALTER TABLE user_account ADD COLUMN email VARCHAR(200)'))
                        conn.commit()
                        print('✅ Added email column to user_account')
        except Exception as me:
            print(f'⚠️ username→email migration: {me}')

    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        import traceback
        traceback.print_exc()

# ══════════════════════════════════════════════════
# USERS MANAGEMENT (admin only)
# ══════════════════════════════════════════════════
@app.route('/users', methods=['GET', 'POST'])
@admin_required
def users():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'create':
            email        = request.form['email'].strip().lower()
            display_name = request.form['display_name'].strip()
            password     = request.form['password']
            role         = request.form.get('role', 'partner')
            if UserAccount.query.filter_by(email=email).first():
                flash(f'Email "{email}" already exists.', 'error')
            else:
                user = UserAccount(
                    email=email,
                    display_name=display_name,
                    password_hash=hashlib.sha256(password.encode()).hexdigest(),
                    role=role,
                )
                db.session.add(user)
                db.session.commit()
                audit('ADD', 'User', display_name, user.id, f'role={role}')
                flash(f'User "{display_name}" created successfully!', 'success')
        elif action == 'toggle':
            user_id = int(request.form['user_id'])
            user = UserAccount.query.get_or_404(user_id)
            user.active = not user.active
            db.session.commit()
            status = 'enabled' if user.active else 'disabled'
            audit('EDIT', 'User', user.display_name, user.id, f'Account {status}')
            flash(f'{user.display_name} {status}.', 'success')
        elif action == 'delete':
            user_id = int(request.form['user_id'])
            user = UserAccount.query.get_or_404(user_id)
            audit('DELETE', 'User', user.display_name, user.id)
            db.session.delete(user)
            db.session.commit()
            flash('User deleted.', 'success')
        elif action == 'reset_password':
            user_id = int(request.form['user_id'])
            user = UserAccount.query.get_or_404(user_id)
            new_pw = request.form['new_password']
            user.password_hash = hashlib.sha256(new_pw.encode()).hexdigest()
            db.session.commit()
            audit('EDIT', 'User', user.display_name, user.id, 'Password reset')
            flash(f'Password reset for {user.display_name}', 'success')
        return redirect(url_for('users'))
    users = UserAccount.query.order_by(UserAccount.created_at.desc()).all()
    return render_template('users.html', accounts=users, users=users)

@app.route('/users/add', methods=['POST'])
@admin_required
def add_user():
    email        = request.form['email'].strip().lower()
    display_name = request.form['display_name'].strip()
    password     = request.form['password']
    role         = request.form.get('role', 'partner')
    if UserAccount.query.filter_by(email=email).first():
        flash(f'Email "{email}" already exists.', 'error')
        return redirect(url_for('users'))
    user = UserAccount(
        email=email,
        display_name=display_name,
        password_hash=hashlib.sha256(password.encode()).hexdigest(),
        role=role,
    )
    db.session.add(user)
    db.session.commit()
    audit('ADD', 'User', display_name, user.id, f'role={role}')
    flash(f'User "{display_name}" created successfully!', 'success')
    return redirect(url_for('users'))

@app.route('/users/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def reset_user_password(user_id):
    user = UserAccount.query.get_or_404(user_id)
    new_pw = request.form['new_password']
    user.password_hash = hashlib.sha256(new_pw.encode()).hexdigest()
    db.session.commit()
    audit('EDIT', 'User', user.display_name, user.id, 'Password reset')
    flash(f'Password reset for {user.display_name}', 'success')
    return redirect(url_for('users'))

@app.route('/users/<int:user_id>/toggle', methods=['POST'])
@admin_required
def toggle_user(user_id):
    user = UserAccount.query.get_or_404(user_id)
    user.active = not user.active
    db.session.commit()
    status = 'enabled' if user.active else 'disabled'
    audit('EDIT', 'User', user.display_name, user.id, f'Account {status}')
    flash(f'{user.display_name} {status}.', 'success')
    return redirect(url_for('users'))

@app.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    user = UserAccount.query.get_or_404(user_id)
    audit('DELETE', 'User', user.display_name, user.id)
    db.session.delete(user)
    db.session.commit()
    flash(f'User deleted.', 'success')
    return redirect(url_for('users'))

# ══════════════════════════════════════════════════
# AUDIT LOG
# ══════════════════════════════════════════════════
@app.route('/audit-log')
@admin_required
def audit_log():
    page      = request.args.get('page', 1, type=int)
    user_filt = request.args.get('username', '')
    act_filt  = request.args.get('action', '')
    type_filt = request.args.get('target_type', '')
    q = AuditLog.query.order_by(AuditLog.timestamp.desc())
    if user_filt: q = q.filter(AuditLog.username == user_filt)
    if act_filt:  q = q.filter(AuditLog.action == act_filt)
    if type_filt: q = q.filter(AuditLog.target_type == type_filt)
    logs      = q.paginate(page=page, per_page=50)
    all_users = db.session.query(AuditLog.username).distinct().all()
    all_types = db.session.query(AuditLog.target_type).distinct().all()
    return render_template('audit_log.html', logs=logs,
        all_users=all_users, all_types=all_types,
        filters=request.args)


@app.route('/investor/<int:investor_id>/roi-percent/update', methods=['POST'])
@admin_required
def update_roi_percent(investor_id):
    investor = Investor.query.get_or_404(investor_id)
    try:
        new_roi = float(request.form.get('investor_roi_percent', 2.5))
        if new_roi < 0 or new_roi > 100:
            return jsonify({'success': False, 'error': 'ROI % must be between 0 and 100'}), 400
        old_roi = investor.investor_roi_percent
        investor.investor_roi_percent = new_roi
        db.session.commit()
        audit('EDIT', 'Investor', investor.name, investor.id,
              f'Actual ROI changed: {old_roi}% → {new_roi}%')
        return jsonify({'success': True, 'investor_roi_percent': new_roi})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/investor/<int:investor_id>/tg-percent/update', methods=['POST'])
@admin_required
def update_tg_percent(investor_id):
    """Update TG % for an investor"""
    investor = Investor.query.get_or_404(investor_id)
    try:
        new_tg = float(request.form.get('tg_percent', 5.0))
        if new_tg < 0 or new_tg > 100:
            return jsonify({'success': False, 'error': 'TG % must be between 0 and 100'}), 400
        old_tg = investor.tg_percent or 5.0
        investor.tg_percent = new_tg
        db.session.commit()
        audit('EDIT', 'Investor', investor.name, investor.id,
              f'TG % changed: {old_tg}% → {new_tg}%')
        return jsonify({'success': True, 'tg_percent': new_tg,
                        'pool_amount': investor.total_capital * (new_tg / 100)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/gold')
def gold_dashboard():
    from flask import make_response
    resp = make_response(send_from_directory('static', 'gold-dashboard.html'))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

@app.route('/api/gold-history')
def gold_history_proxy():
    """Proxy historical Gold prices server-side to avoid browser CORS/rate limits."""
    sources = [
        # 1. Yahoo Finance GC=F hourly 14 days — no key, reliable, 250+ points
        {
            'url': 'https://query1.finance.yahoo.com/v8/finance/chart/GC%3DF?interval=1h&range=14d',
            'headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
            'parser': 'yahoo'
        },
        # 2. Yahoo Finance fallback 7 days
        {
            'url': 'https://query2.finance.yahoo.com/v8/finance/chart/GC%3DF?interval=1h&range=7d',
            'headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
            'parser': 'yahoo'
        },
        # 3. CoinGecko 14 days (fallback)
        {
            'url': 'https://api.coingecko.com/api/v3/coins/tether-gold/market_chart?vs_currency=usd&days=14&interval=hourly',
            'headers': {'Accept': 'application/json'},
            'parser': 'coingecko'
        },
    ]
    for src in sources:
        try:
            r = requests.get(src['url'], timeout=10, headers=src['headers'])
            if r.status_code != 200:
                continue
            data = r.json()
            prices = []
            if src['parser'] == 'yahoo':
                result = data.get('chart', {}).get('result', [])
                if result:
                    closes = result[0].get('indicators', {}).get('quote', [{}])[0].get('close', [])
                    prices = [float(p) for p in closes if p and float(p) > 100]
            elif src['parser'] == 'coingecko':
                prices = [p[1] for p in data.get('prices', []) if p[1] and p[1] > 100]
            if len(prices) >= 20:
                return jsonify({'prices': prices, 'count': len(prices), 'source': src['parser']})
        except Exception:
            continue
    return jsonify({'error': 'All history sources failed', 'prices': []}), 503

@app.route('/api/gold-price')
def gold_price_proxy():
    """Proxy live gold spot price server-side."""
    sources = [
        # 1. Yahoo Finance spot
        lambda: (__import__('requests').get(
            'https://query1.finance.yahoo.com/v8/finance/chart/GC%3DF?interval=1m&range=1d',
            headers={'User-Agent': 'Mozilla/5.0'}, timeout=6
        ).json()['chart']['result'][0]['meta']['regularMarketPrice'], 'Yahoo'),
        # 2. Coinbase
        lambda: (float(__import__('requests').get(
            'https://api.coinbase.com/v2/prices/XAU-USD/spot', timeout=6
        ).json()['data']['amount']), 'Coinbase'),
        # 3. Swissquote
        lambda: ((__import__('requests').get(
            'https://forex-data-feed.swissquote.com/public-quotes/bboquotes/instrument/XAU/USD', timeout=6
        ).json()[0]['spreadProfilePrices'][0]['bid']), 'Swissquote'),
    ]
    for src in sources:
        try:
            price, name = src()
            if price and float(price) > 100:
                return jsonify({'price': float(price), 'source': name})
        except Exception:
            continue
    return jsonify({'error': 'All price sources failed'}), 503


# ══════════════════════════════════════════════════════
# BACKUP ROUTE — exports ALL data as structured JSON
# ══════════════════════════════════════════════════════
@app.route('/backup')
@admin_required
def backup():
    return render_template('backup.html')

@app.route('/backup/download')
@admin_required
def backup_download():
    """Download full DB snapshot as structured JSON"""
    now = datetime.now()

    def fmt_date(d):
        return d.isoformat() if d else None

    # --- Investors ---
    investors = []
    for inv in Investor.query.all():
        txns = InvestmentTransaction.query.filter_by(investor_id=inv.id).all()
        investors.append({
            'id':               inv.id,
            'name':             inv.name,
            'category':         inv.category,
            'investment_amount':inv.investment_amount,
            'investor_roi_percent': inv.investor_roi_percent,
            'sales_roi_percent':    inv.sales_roi_percent,
            'contract_start':   fmt_date(inv.contract_start),
            'contract_end':     fmt_date(inv.contract_end),
            'status':           inv.status,
            'sales_rep_id':     inv.sales_rep_id,
            'transactions': [
                {
                    'id':               t.id,
                    'transaction_type': t.transaction_type,
                    'amount':           float(t.amount),
                    'payout_month':     t.payout_month,
                    'payout_year':      t.payout_year,
                    'transaction_date': fmt_date(t.transaction_date),
                    'notes':            t.notes,
                } for t in txns
            ]
        })

    # --- Sales Reps ---
    sales_reps = [
        {'id': r.id, 'name': r.name, 'email': r.email, 'active': r.active}
        for r in SalesRep.query.all()
    ]

    # --- Revenue History ---
    revenue_history = [
        {
            'id':             h.id,
            'year':           h.year,
            'month':          h.month,
            'revenue_amount': float(h.revenue_amount),
            'revenue_usd':    float(h.revenue_usd) if h.revenue_usd else None,
            'capital_aed':    float(h.capital_aed) if h.capital_aed else None,
            'capital_usd':    float(h.capital_usd) if h.capital_usd else None,
            'capital_pct':    float(h.capital_pct) if h.capital_pct else None,
            'notes':          h.notes,
            'entry_date':     fmt_date(h.entry_date),
        }
        for h in RevenueHistory.query.order_by(RevenueHistory.year, RevenueHistory.month).all()
    ]

    # --- Global Revenue ---
    global_rev = GlobalRevenue.get_instance()

    # --- ManualROI ---
    manual_roi = [
        {
            'id':                 r.id,
            'investor_id':        r.investor_id,
            'year':               r.year,
            'month':              r.month,
            'total_roi_generated':float(r.total_roi_generated),
            'investor_share':     float(r.investor_share),
            'sales_share':        float(r.sales_share),
        }
        for r in ManualROI.query.all()
    ]

    backup_data = {
        'backup_info': {
            'created_at':    now.isoformat(),
            'created_by':    'TopGee It System',
            'version':       '1.0',
            'description':   'Full database backup — investors, transactions, revenue, ROI records',
        },
        'summary': {
            'total_investors':       len(investors),
            'total_sales_reps':      len(sales_reps),
            'total_revenue_entries': len(revenue_history),
            'total_manual_roi':      len(manual_roi),
            'global_revenue_aed':    float(global_rev.total_revenue),
            'total_investment_aed':  sum(inv['investment_amount'] for inv in investors),
        },
        'investors':       investors,
        'sales_reps':      sales_reps,
        'revenue_history': revenue_history,
        'manual_roi':      manual_roi,
        'global_revenue':  {'total_revenue': float(global_rev.total_revenue)},
    }

    json_bytes = json.dumps(backup_data, indent=2, ensure_ascii=False).encode('utf-8')
    buf = BytesIO(json_bytes)
    buf.seek(0)
    filename = f'TopGeeIt_Backup_{now.strftime("%Y-%m-%d_%H-%M")}.json'
    return send_file(buf, as_attachment=True, download_name=filename, mimetype='application/json')

# ============= TRADING ACCOUNTS ROUTES =============

@app.route('/trading-accounts')
def trading_accounts():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    try:
        from sqlalchemy import case, func
        accounts = TradingAccount.query.order_by(
            TradingAccount.is_active.desc(),
            case(
                (func.coalesce(TradingAccount.account_holder, '') == '', 1),
                else_=0
            ),
            TradingAccount.account_holder,
            TradingAccount.broker_name
        ).all()
    except Exception:
        accounts = TradingAccount.query.order_by(TradingAccount.is_active.desc(), TradingAccount.broker_name).all()
    # Totals
    total_invested  = sum(a.total_invested  for a in accounts)
    total_withdrawn = sum(a.total_withdrawn for a in accounts)
    total_balance   = sum(a.current_balance for a in accounts)
    total_profit    = sum(a.net_profit      for a in accounts)  # balance - invested + withdrawn
    today_profit    = sum(a.today_profit    for a in accounts)
    week_profit     = sum(a.week_profit     for a in accounts)
    month_profit    = sum(a.month_profit    for a in accounts)
    from datetime import date
    # Group by account holder, sorted by count desc
    from collections import OrderedDict
    grouped_raw = {}
    for a in accounts:
        holder = a.account_holder or ''
        if holder not in grouped_raw:
            grouped_raw[holder] = []
        grouped_raw[holder].append(a)
    # Sort: named holders by count desc, unnamed always last
    named   = {k: v for k, v in grouped_raw.items() if k}
    unnamed = {k: v for k, v in grouped_raw.items() if not k}
    sorted_named = OrderedDict(sorted(named.items(), key=lambda x: len(x[1]), reverse=True))
    grouped = OrderedDict(**sorted_named, **unnamed)
    return render_template('trading_accounts.html',
        accounts=accounts,
        grouped=grouped,
        total_invested=total_invested,
        total_withdrawn=total_withdrawn,
        total_balance=total_balance,
        total_profit=total_profit,
        today_profit=today_profit,
        week_profit=week_profit,
        month_profit=month_profit,
        today=date.today().isoformat(),
        is_admin=session.get('is_admin', False),
        current_user=session.get('username', ''),
        current_user_pic=session.get('profile_pic'),
    )


@app.route('/trading-accounts/add', methods=['POST'])
def trading_account_add():
    if not session.get('logged_in') or not session.get('is_admin'):
        return redirect(url_for('login'))
    acc = TradingAccount(
        broker_name    = request.form['broker_name'],
        account_holder = request.form.get('account_holder', ''),
        investor_name  = request.form.get('investor_name', ''),
        account_number = request.form.get('account_number', ''),
        deposit_via    = request.form.get('deposit_via', 'Bank'),
        platform       = request.form.get('platform', 'MT5'),
        symbol         = request.form.get('symbol', 'XAUUSD'),
        currency       = request.form.get('currency', 'USD'),
        total_invested = float(request.form.get('total_invested') or 0),
        current_balance= float(request.form.get('current_balance') or 0),
        notes          = request.form.get('notes', ''),
        is_active      = True,
    )
    db.session.add(acc)
    db.session.commit()
    audit('ADD', 'TradingAccount', acc.broker_name, acc.id)
    flash(f'Account "{acc.broker_name}" added!', 'success')
    return redirect(url_for('trading_accounts'))


@app.route('/trading-accounts/<int:acc_id>/edit', methods=['POST'])
def trading_account_edit(acc_id):
    if not session.get('logged_in') or not session.get('is_admin'):
        return redirect(url_for('login'))
    acc = TradingAccount.query.get_or_404(acc_id)
    acc.broker_name    = request.form['broker_name']
    acc.account_holder = request.form.get('account_holder', '')
    acc.investor_name  = request.form.get('investor_name', '')
    acc.account_number = request.form.get('account_number', '')
    acc.deposit_via    = request.form.get('deposit_via', 'Bank')
    acc.platform       = request.form.get('platform', 'MT5')
    acc.symbol         = request.form.get('symbol', 'XAUUSD')
    acc.currency       = request.form.get('currency', 'USD')
    acc.current_balance= float(request.form.get('current_balance') or 0)
    acc.notes          = request.form.get('notes', '')
    acc.is_active      = request.form.get('is_active') == 'on'
    db.session.commit()
    audit('EDIT', 'TradingAccount', acc.broker_name, acc.id)
    flash('Account updated!', 'success')
    return redirect(url_for('trading_accounts'))


@app.route('/trading-accounts/<int:acc_id>/delete', methods=['POST'])
def trading_account_delete(acc_id):
    if not session.get('logged_in') or not session.get('is_admin'):
        return redirect(url_for('login'))
    acc = TradingAccount.query.get_or_404(acc_id)
    audit('DELETE', 'TradingAccount', acc.broker_name, acc.id)
    db.session.delete(acc)
    db.session.commit()
    flash('Account deleted.', 'success')
    return redirect(url_for('trading_accounts'))


@app.route('/trading-accounts/<int:acc_id>/profit/add', methods=['POST'])
def trading_account_profit_add(acc_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    from datetime import date
    acc = TradingAccount.query.get_or_404(acc_id)
    profit_date = request.form.get('profit_date') or date.today().isoformat()
    amount = float(request.form.get('amount') or 0)
    notes  = request.form.get('notes', '')
    # Upsert: one entry per date per account
    existing = AccountProfit.query.filter_by(
        account_id=acc_id,
        profit_date=date.fromisoformat(profit_date)
    ).first()
    if existing:
        existing.profit_amount = amount
        existing.notes = notes
    else:
        p = AccountProfit(
            account_id=acc_id,
            profit_date=date.fromisoformat(profit_date),
            profit_amount=amount,
            notes=notes,
        )
        db.session.add(p)
    db.session.commit()
    flash(f'Profit ${amount:,.2f} recorded for {profit_date}.', 'success')
    return redirect(url_for('trading_accounts'))


@app.route('/trading-accounts/<int:acc_id>/transaction/add', methods=['POST'])
def trading_account_txn_add(acc_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    from datetime import date
    acc = TradingAccount.query.get_or_404(acc_id)
    txn_type = request.form.get('txn_type')   # deposit / withdrawal
    amount   = float(request.form.get('amount') or 0)
    txn_date = request.form.get('txn_date') or date.today().isoformat()
    notes    = request.form.get('notes', '')
    txn = AccountTransaction(
        account_id=acc_id,
        txn_date=date.fromisoformat(txn_date),
        txn_type=txn_type,
        amount=amount,
        notes=notes,
    )
    db.session.add(txn)
    if txn_type == 'deposit':
        acc.total_invested  += amount
    elif txn_type == 'withdrawal':
        acc.total_withdrawn += amount
    db.session.commit()
    audit('ADD', 'AccountTransaction', f'{acc.broker_name} {txn_type} ${amount}', acc_id)
    flash(f'{txn_type.title()} of ${amount:,.2f} recorded.', 'success')
    return redirect(url_for('trading_accounts'))


@app.route('/trading-accounts/<int:acc_id>/weekly-profit/add', methods=['POST'])
def trading_account_weekly_profit_add(acc_id):
    """Enter weekly total profit → auto-split equally across Mon-Fri of that week"""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    from datetime import date, timedelta
    acc = TradingAccount.query.get_or_404(acc_id)
    week_start_str = request.form.get('week_start')   # Monday date as YYYY-MM-DD
    total_amount   = float(request.form.get('total_amount') or 0)
    new_balance    = request.form.get('current_balance')
    notes          = request.form.get('notes', '')
    if not week_start_str or total_amount == 0:
        flash('Please enter week start date and total profit.', 'danger')
        return redirect(url_for('trading_accounts'))
    monday = date.fromisoformat(week_start_str)
    # Ensure it's a Monday
    monday = monday - timedelta(days=monday.weekday())
    daily_amount = round(total_amount / 5, 2)
    # Adjust last day for rounding difference
    days_amounts = [daily_amount] * 4 + [round(total_amount - daily_amount * 4, 2)]
    for i, day_amount in enumerate(days_amounts):
        day = monday + timedelta(days=i)
        existing = AccountProfit.query.filter_by(
            account_id=acc_id,
            profit_date=day
        ).first()
        if existing:
            existing.profit_amount = day_amount
            existing.notes = f'[Weekly] {notes}' if notes else '[Weekly split]'
        else:
            p = AccountProfit(
                account_id=acc_id,
                profit_date=day,
                profit_amount=day_amount,
                notes=f'[Weekly] {notes}' if notes else '[Weekly split]',
            )
            db.session.add(p)
    db.session.commit()
    flash(f'Weekly profit ${total_amount:,.2f} split across Mon–Fri (${daily_amount:,.2f}/day) recorded!', 'success')
    return redirect(url_for('trading_accounts'))


@app.route('/trading-accounts/<int:acc_id>/profit/<int:profit_id>/delete', methods=['POST'])
def trading_account_profit_delete(acc_id, profit_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    p = AccountProfit.query.get_or_404(profit_id)
    db.session.delete(p)
    db.session.commit()
    flash('Profit entry deleted.', 'success')
    return redirect(url_for('trading_account_detail', acc_id=acc_id))


@app.route('/trading-accounts/<int:acc_id>/transaction/<int:txn_id>/edit', methods=['POST'])
def trading_account_txn_edit(acc_id, txn_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    from datetime import date
    acc = TradingAccount.query.get_or_404(acc_id)
    txn = AccountTransaction.query.get_or_404(txn_id)
    new_amount = float(request.form.get('amount') or txn.amount)
    new_date   = request.form.get('txn_date') or txn.txn_date.isoformat()
    new_notes  = request.form.get('notes', '')
    # Reverse old, apply new
    if txn.txn_type == 'deposit':
        acc.total_invested  = acc.total_invested - txn.amount + new_amount
    elif txn.txn_type == 'withdrawal':
        acc.total_withdrawn = acc.total_withdrawn - txn.amount + new_amount
    txn.amount   = new_amount
    txn.txn_date = date.fromisoformat(new_date)
    txn.notes    = new_notes
    db.session.commit()
    flash(f'{txn.txn_type.title()} updated to ${new_amount:,.2f}.', 'success')
    return redirect(url_for('trading_account_detail', acc_id=acc_id))


@app.route('/trading-accounts/<int:acc_id>/profit/<int:profit_id>/edit', methods=['POST'])
def trading_account_profit_edit(acc_id, profit_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    from datetime import date
    p = AccountProfit.query.get_or_404(profit_id)
    p.profit_amount = float(request.form.get('amount') or p.profit_amount)
    p.profit_date   = date.fromisoformat(request.form.get('profit_date') or p.profit_date.isoformat())
    p.notes         = request.form.get('notes', '')
    db.session.commit()
    flash(f'Profit entry updated to ${p.profit_amount:,.2f}.', 'success')
    return redirect(url_for('trading_account_detail', acc_id=acc_id))


@app.route('/trading-accounts/<int:acc_id>/transaction/<int:txn_id>/delete', methods=['POST'])
def trading_account_txn_delete(acc_id, txn_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    acc = TradingAccount.query.get_or_404(acc_id)
    txn = AccountTransaction.query.get_or_404(txn_id)
    # Reverse totals only — current_balance is manual
    if txn.txn_type == 'deposit':
        acc.total_invested  -= txn.amount
    elif txn.txn_type == 'withdrawal':
        acc.total_withdrawn -= txn.amount
    db.session.delete(txn)
    db.session.commit()
    flash(f'{txn.txn_type.title()} of ${txn.amount:,.2f} deleted and balance reversed.', 'success')
    return redirect(url_for('trading_account_detail', acc_id=acc_id))


@app.route('/trading-accounts/<int:acc_id>/detail')
def trading_account_detail(acc_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    from datetime import date
    acc      = TradingAccount.query.get_or_404(acc_id)
    profits  = AccountProfit.query.filter_by(account_id=acc_id).order_by(AccountProfit.profit_date.desc()).all()
    txns     = AccountTransaction.query.filter_by(account_id=acc_id).order_by(AccountTransaction.txn_date.desc()).all()
    return render_template('trading_account_detail.html',
        acc=acc, profits=profits, txns=txns,
        today=date.today().isoformat(),
        is_admin=session.get('is_admin', False),
        current_user=session.get('username', ''),
        current_user_pic=session.get('profile_pic'),
        sales_reps=[],
    )



# ── Forex Monthly Report ─────────────────────────────────────────────
@app.route('/trading-accounts/monthly-report')
def forex_monthly_report():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    from datetime import date, datetime
    import calendar as cal_mod

    # Determine selected month
    today = date.today()
    month_param = request.args.get('month', f"{today.year}-{today.month:02d}")
    try:
        sel_year, sel_month = map(int, month_param.split('-'))
    except Exception:
        sel_year, sel_month = today.year, today.month

    # Period
    first_day = date(sel_year, sel_month, 1)
    last_day  = date(sel_year, sel_month, cal_mod.monthrange(sel_year, sel_month)[1])
    period_end_actual = min(last_day, today)  # don't show future

    # Fetch all accounts
    try:
        from sqlalchemy import case, func
        accounts_raw = TradingAccount.query.order_by(
            TradingAccount.account_holder,
            TradingAccount.broker_name
        ).all()
    except Exception:
        accounts_raw = TradingAccount.query.order_by(TradingAccount.broker_name).all()

    # Build account rows
    accounts = []
    for a in accounts_raw:
        profit = a.current_balance - a.total_invested
        roi = (profit / a.total_invested * 100) if a.total_invested > 0 else 0
        accounts.append({
            'broker_name':    a.broker_name,
            'account_holder': a.account_holder or '',
            'account_number': a.account_number or '',
            'capital':        a.total_invested,
            'balance':        a.current_balance,
            'profit':         profit,
            'roi':            roi,
            'is_active':      a.is_active,
        })

    # Totals
    total_capital  = sum(a['capital'] for a in accounts)
    total_balance  = sum(a['balance'] for a in accounts)
    total_profit   = sum(a['profit']  for a in accounts)
    total_roi      = (total_profit / total_capital * 100) if total_capital > 0 else 0

    # Per-holder summary
    holder_map = {}
    for a in accounts:
        h = a['account_holder'] or ''
        if h not in holder_map:
            holder_map[h] = {'name': h, 'count': 0, 'capital': 0, 'balance': 0, 'profit': 0}
        holder_map[h]['count']   += 1
        holder_map[h]['capital'] += a['capital']
        holder_map[h]['balance'] += a['balance']
        holder_map[h]['profit']  += a['profit']
    holders = []
    for h in sorted(holder_map.keys()):
        hd = holder_map[h]
        hd['roi'] = (hd['profit'] / hd['capital'] * 100) if hd['capital'] > 0 else 0
        holders.append(hd)

    # Available months (from first transaction onwards, plus last 12 months)
    MONTH_NAMES = ['January','February','March','April','May','June',
                   'July','August','September','October','November','December']
    available_months = []
    for i in range(11, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0: m += 12; y -= 1
        available_months.append({
            'value': f"{y}-{m:02d}",
            'label': f"{MONTH_NAMES[m-1]} {y}"
        })

    # Trading days calculation (Mon-Fri = Gold market)
    from datetime import timedelta
    def count_trading_days(start, end):
        count = 0
        d = start
        while d <= end:
            if d.weekday() < 5:  # Mon=0..Fri=4
                count += 1
            d += timedelta(days=1)
        return count

    total_trading   = count_trading_days(first_day, last_day)
    gone_trading    = count_trading_days(first_day, min(today, last_day))
    pending_trading = max(0, total_trading - gone_trading)
    pct             = round(gone_trading / total_trading * 100, 1) if total_trading > 0 else 0

    trading_days = {
        'total':   total_trading,
        'gone':    gone_trading,
        'pending': pending_trading,
        'pct':     pct,
    }

    month_label    = f"{MONTH_NAMES[sel_month-1]} {sel_year}"
    generated_on   = datetime.now().strftime('%d %b %Y, %H:%M')
    period_start   = first_day.strftime('%d %b %Y')
    period_end_str = period_end_actual.strftime('%d %b %Y')

    return render_template('forex_monthly_report.html',
        accounts=accounts,
        holders=holders,
        totals={'capital': total_capital, 'balance': total_balance,
                'profit': total_profit, 'roi': total_roi},
        trading_days=trading_days,
        month_label=month_label,
        generated_on=generated_on,
        period_start=period_start,
        period_end=period_end_str,
        selected_month=month_param,
        available_months=available_months,
        is_admin=session.get('is_admin', False),
        current_user=session.get('username', ''),
    )


# ── Forex Calendar API ─────────────────────────────────────────────
@app.route('/trading-accounts/api/calendar')
def trading_accounts_calendar_api():
    """Return daily profit entries for calendar view.
    ?year=2026&month=7  → all accounts for that month
    ?acc_id=5           → filter to one account
    ?holder=Sadakat+Ali → filter by holder name
    """
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    from datetime import date, timedelta
    import calendar as cal_mod
    try:
        year  = int(request.args.get('year',  date.today().year))
        month = int(request.args.get('month', date.today().month))
        acc_id_filter = request.args.get('acc_id', type=int)
        holder_filter = request.args.get('holder', '')
    except Exception:
        return jsonify({'error': 'Bad params'}), 400

    # Month date range
    first_day = date(year, month, 1)
    last_day  = date(year, month, cal_mod.monthrange(year, month)[1])

    q = db.session.query(AccountProfit).join(TradingAccount)
    if acc_id_filter:
        q = q.filter(AccountProfit.account_id == acc_id_filter)
    elif holder_filter:
        q = q.filter(TradingAccount.account_holder == holder_filter)
    q = q.filter(
        AccountProfit.profit_date >= str(first_day),
        AccountProfit.profit_date <= str(last_day)
    )
    profits = q.all()

    # Aggregate by date
    day_map = {}
    for p in profits:
        d = str(p.profit_date)[:10]
        if d not in day_map:
            day_map[d] = {'total': 0, 'entries': []}
        day_map[d]['total'] += p.profit_amount
        day_map[d]['entries'].append({
            'broker': p.account.broker_name if p.account else '?',
            'holder': p.account.account_holder if p.account else '',
            'amount': p.profit_amount,
            'notes': p.notes or '',
        })

    # Month totals summary
    total = sum(v['total'] for v in day_map.values())
    trading_days = sum(1 for v in day_map.values() if v['total'] != 0)

    # Accounts list for filter dropdown
    accs = TradingAccount.query.order_by(TradingAccount.account_holder, TradingAccount.broker_name).all()
    accounts_list = [{'id': a.id, 'label': f"{a.broker_name} ({a.account_holder or 'Unassigned'})", 'holder': a.account_holder or ''} for a in accs]
    holders_list  = sorted(set(a.account_holder for a in accs if a.account_holder))

    return jsonify({
        'year': year, 'month': month,
        'days': day_map,
        'total': round(total, 2),
        'trading_days': trading_days,
        'accounts': accounts_list,
        'holders': holders_list,
    })


# ============================================================
# FOREX INVESTORS MODULE
# Completely separate from TopG It investors
# ============================================================

@app.route('/forex-investors')
@login_required
def forex_investors():
    investors = ForexInvestor.query.order_by(ForexInvestor.name).all()
    now = datetime.now()

    # Summary stats — use display_capital (linked account or manual)
    active = [i for i in investors if i.status=='Active']
    total_capital   = sum(i.display_capital for i in active)
    total_inv_due   = sum(i.monthly_investor_due for i in active)
    total_broker_tk = sum(i.monthly_broker_take for i in active)
    total_net       = sum(i.monthly_net_per_investor for i in active)

    # This month payouts
    this_month_payouts = ForexInvestorPayout.query.filter_by(
        year=now.year, month=now.month).all()
    total_paid_this_month = sum(p.amount_paid for p in this_month_payouts)

    # All trading accounts for add modal dropdown
    trading_accounts = TradingAccount.query.filter_by(is_active=True)\
        .order_by(TradingAccount.account_holder).all()

    return render_template('forex_investors.html',
        investors=investors,
        total_capital=total_capital,
        total_inv_due=total_inv_due,
        total_broker_tk=total_broker_tk,
        total_net=total_net,
        total_paid_this_month=total_paid_this_month,
        trading_accounts=trading_accounts,
        now=now,
    )


@app.route('/forex-investors/add', methods=['GET','POST'])
@login_required
def forex_investor_add():
    if request.method == 'POST':
        # Get linked trading account
        ta_id        = request.form.get('trading_account_id','')
        ta_id        = int(ta_id) if ta_id else None
        ta           = TradingAccount.query.get(ta_id) if ta_id else None

        # Name = account holder name from trading account
        name         = ta.account_holder if ta and ta.account_holder else request.form.get('name','').strip()
        # Capital = from trading account deposits (or manual)
        capital_usd  = ta.total_invested if ta else float(request.form.get('capital_usd',0) or 0)
        # Broker = from trading account
        broker_name  = ta.broker_name if ta else request.form.get('broker_name','').strip()

        broker_pct   = float(request.form.get('broker_pct',0) or 0)
        investor_pct = float(request.form.get('investor_pct',0) or 0)
        sales_rep    = request.form.get('sales_rep','').strip()
        status       = request.form.get('status','Active')
        notes        = request.form.get('notes','').strip()
        cs           = request.form.get('contract_start','')
        contract_start = datetime.strptime(cs,'%Y-%m-%d').date() if cs else None

        inv = ForexInvestor(
            name=name, capital_usd=capital_usd,
            broker_pct=broker_pct, investor_pct=investor_pct,
            broker_name=broker_name, sales_rep=sales_rep,
            status=status, notes=notes, contract_start=contract_start,
            trading_account_id=ta_id,
        )
        db.session.add(inv)
        db.session.commit()
        audit('ADD','ForexInvestor',name,inv.id)
        flash(f'Forex investor {name} added!','forex_success')
        return redirect(url_for('forex_investors'))
    trading_accounts = TradingAccount.query.filter_by(is_active=True)\
        .order_by(TradingAccount.account_holder).all()
    return render_template('forex_investor_form.html', investor=None, action='Add',
                           trading_accounts=trading_accounts)


@app.route('/forex-investors/<int:inv_id>/edit', methods=['GET','POST'])
@login_required
def forex_investor_edit(inv_id):
    inv = ForexInvestor.query.get_or_404(inv_id)
    if request.method == 'POST':
        ta_id = request.form.get('trading_account_id','')
        ta_id = int(ta_id) if ta_id else None
        ta    = TradingAccount.query.get(ta_id) if ta_id else None

        inv.trading_account_id = ta_id
        # If linked — pull name/capital/broker from trading account
        if ta:
            inv.name        = ta.account_holder or inv.name
            inv.capital_usd = ta.total_invested
            inv.broker_name = ta.broker_name
        else:
            inv.name        = request.form.get('name','').strip()
            inv.capital_usd = float(request.form.get('capital_usd',0) or 0)
            inv.broker_name = request.form.get('broker_name','').strip()

        inv.broker_pct   = float(request.form.get('broker_pct',0) or 0)
        inv.investor_pct = float(request.form.get('investor_pct',0) or 0)
        inv.sales_rep    = request.form.get('sales_rep','').strip()
        inv.status       = request.form.get('status','Active')
        inv.notes        = request.form.get('notes','').strip()
        cs = request.form.get('contract_start','')
        inv.contract_start = datetime.strptime(cs,'%Y-%m-%d').date() if cs else None
        db.session.commit()
        audit('EDIT','ForexInvestor',inv.name,inv.id)
        flash('Investor updated!','forex_success')
        return redirect(url_for('forex_investors'))
    trading_accounts = TradingAccount.query.filter_by(is_active=True)\
        .order_by(TradingAccount.account_holder).all()
    return render_template('forex_investor_form.html', investor=inv, action='Edit',
                           trading_accounts=trading_accounts)


@app.route('/forex-investors/<int:inv_id>/view')
@login_required
def forex_investor_view(inv_id):
    inv = ForexInvestor.query.get_or_404(inv_id)
    payouts = ForexInvestorPayout.query.filter_by(investor_id=inv_id)\
              .order_by(ForexInvestorPayout.year.desc(), ForexInvestorPayout.month.desc()).all()
    total_paid = sum(p.amount_paid for p in payouts)
    months_active = 0
    if inv.contract_start:
        delta = datetime.now().date() - inv.contract_start
        months_active = max(1, delta.days // 30)
    total_due = inv.monthly_investor_due * months_active
    return render_template('forex_investor_detail.html',
        inv=inv, payouts=payouts,
        total_paid=total_paid, total_due=total_due,
        months_active=months_active, now=datetime.now())


@app.route('/forex-investors/<int:inv_id>/payout', methods=['POST'])
@login_required
def forex_investor_payout(inv_id):
    inv = ForexInvestor.query.get_or_404(inv_id)
    year   = int(request.form.get('year', datetime.now().year))
    month  = int(request.form.get('month', datetime.now().month))
    amount = float(request.form.get('amount',0) or 0)
    notes  = request.form.get('notes','').strip()
    pd_str = request.form.get('paid_date','')
    paid_date = datetime.strptime(pd_str,'%Y-%m-%d').date() if pd_str else datetime.now().date()
    payout = ForexInvestorPayout(
        investor_id=inv_id, year=year, month=month,
        amount_paid=amount, paid_date=paid_date, notes=notes
    )
    db.session.add(payout)
    db.session.commit()
    audit('PAYOUT','ForexInvestor',inv.name,inv_id,f'${amount} for {year}-{month:02d}')
    flash(f'Payout of ${amount:,.2f} recorded!','success')
    return redirect(url_for('forex_investor_view', inv_id=inv_id))


@app.route('/forex-investors/<int:inv_id>/pct-update', methods=['POST'])
@login_required
def forex_investor_pct_update(inv_id):
    """Inline % update — pencil icon save"""
    inv   = ForexInvestor.query.get_or_404(inv_id)
    field = request.form.get('field')
    value = float(request.form.get('value', 0) or 0)
    if field == 'broker_pct':
        inv.broker_pct = value
        audit('EDIT','ForexInvestor',inv.name,inv_id,f'broker_pct → {value}%')
    elif field == 'investor_pct':
        inv.investor_pct = value
        audit('EDIT','ForexInvestor',inv.name,inv_id,f'investor_pct → {value}%')
    db.session.commit()
    flash(f'{inv.name} — % updated successfully!','success')
    return redirect(url_for('forex_investors'))


@app.route('/forex-investors/<int:inv_id>/delete', methods=['POST'])
@login_required
def forex_investor_delete(inv_id):
    inv = ForexInvestor.query.get_or_404(inv_id)
    ForexInvestorPayout.query.filter_by(investor_id=inv_id).delete()
    db.session.delete(inv)
    db.session.commit()
    audit('DELETE','ForexInvestor',inv.name,inv_id)
    flash('Investor deleted.','success')
    return redirect(url_for('forex_investors'))


@app.route('/forex-report', methods=['GET','POST'])
@login_required
def forex_report():
    now      = datetime.now()
    # Accept both GET and POST params
    year     = int(request.values.get('year', now.year))
    month    = int(request.values.get('month', now.month))
    broker   = request.values.get('broker_filter','All')
    paid_filter  = request.values.get('paid_filter', '')  # '' | 'paid' | 'unpaid'
    # Multi-select investor checkboxes (list of IDs as strings)
    selected_ids = request.values.getlist('inv_ids')  # empty = all

    # All active investors for the checkbox list (always full list)
    all_active_investors = ForexInvestor.query.filter_by(status='Active').order_by(ForexInvestor.name).all()

    # Filter by broker first
    investors = list(all_active_investors)
    if broker != 'All':
        investors = [i for i in investors if i.broker_name == broker]

    # Then filter by selected investor checkboxes (if any unchecked)
    if selected_ids:
        sel_set = set(int(x) for x in selected_ids if x.isdigit())
        investors = [i for i in investors if i.id in sel_set]

    # Monthly profit record
    profit_record = ForexMonthlyProfit.query.filter_by(
        year=year, month=month, broker_name=broker).first()

    total_generated   = profit_record.total_generated if profit_record else 0.0
    total_capital     = sum(i.capital_usd for i in investors)

    # Per investor calculations
    rows = []
    total_broker_share = 0
    total_inv_share    = 0
    for inv in investors:
        broker_earn = round(inv.capital_usd * (inv.broker_pct / 100), 2)
        inv_due     = round(inv.capital_usd * (inv.investor_pct / 100), 2)
        net         = round(broker_earn - inv_due, 2)
        # payout this month?
        paid = ForexInvestorPayout.query.filter_by(
            investor_id=inv.id, year=year, month=month).first()
        rows.append({
            'inv': inv,
            'broker_earn': broker_earn,
            'inv_due': inv_due,
            'net': net,
            'paid': paid.amount_paid if paid else 0,
            'paid_id': paid.id if paid else None,
        })
        total_broker_share += broker_earn
        total_inv_share    += inv_due

    # Apply paid/unpaid filter to rows
    if paid_filter == 'paid':
        rows = [r for r in rows if r['paid'] > 0]
    elif paid_filter == 'unpaid':
        rows = [r for r in rows if r['paid'] == 0]

    total_net           = round(total_broker_share - total_inv_share, 2)
    # Partner share = what's left after broker takes their cut from total generated
    generated_remaining = round(total_generated - total_broker_share, 2)
    partner_share       = round(generated_remaining / 3, 2) if total_generated > 0 else round(total_net / 3, 2)

    # All brokers for filter dropdown
    all_brokers = sorted(set(i.broker_name for i in ForexInvestor.query.all() if i.broker_name))

    # Revenue history
    history = ForexMonthlyProfit.query.order_by(
        ForexMonthlyProfit.year.desc(), ForexMonthlyProfit.month.desc()).all()
    # Most recent saved profit record (for top banner)
    latest_profit = history[0] if history else None

    MONTHS = ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

    return render_template('forex_report.html',
        year=year, month=month, broker=broker,
        investors=investors, rows=rows,
        all_active_investors=all_active_investors,
        selected_ids=[int(x) for x in selected_ids if x.isdigit()] if selected_ids else [],
        total_generated=total_generated,
        total_capital=total_capital,
        total_broker_share=total_broker_share,
        total_inv_share=total_inv_share,
        total_net=total_net,
        generated_remaining=generated_remaining,
        partner_share=partner_share,
        all_brokers=all_brokers,
        history=history,
        latest_profit=latest_profit,
        MONTHS=MONTHS,
        now=now,
        profit_record=profit_record,
        paid_filter=paid_filter,
    )


@app.route('/forex-report/save-profit', methods=['POST'])
@login_required
def forex_report_save_profit():
    year           = int(request.form.get('year', datetime.now().year))
    month          = int(request.form.get('month', datetime.now().month))
    broker         = request.form.get('broker_name','All')
    total_generated= float(request.form.get('total_generated',0) or 0)
    notes          = request.form.get('notes','').strip()

    rec = ForexMonthlyProfit.query.filter_by(
        year=year, month=month, broker_name=broker).first()
    if rec:
        rec.total_generated = total_generated
        rec.notes           = notes
    else:
        rec = ForexMonthlyProfit(
            year=year, month=month,
            broker_name=broker,
            total_generated=total_generated,
            notes=notes
        )
        db.session.add(rec)
    db.session.commit()
    flash('Monthly profit saved!','forex_success')
    return redirect(url_for('forex_report',
        year=year, month=month, broker_filter=broker))


@app.route('/forex-report/export-csv')
@login_required
def forex_report_export_csv():
    """Export filtered forex investor breakdown as CSV"""
    import csv, io
    now    = datetime.now()
    year   = int(request.args.get('year', now.year))
    month  = int(request.args.get('month', now.month))
    broker = request.args.get('broker_filter', 'All')
    paid_filter  = request.args.get('paid_filter', '')
    selected_ids = request.args.getlist('inv_ids')
    MONTHS = ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    AED    = 3.67

    investors = ForexInvestor.query.filter_by(status='Active').all()
    if broker != 'All':
        investors = [i for i in investors if i.broker_name == broker]
    if selected_ids:
        sel_set = set(int(x) for x in selected_ids if x.isdigit())
        investors = [i for i in investors if i.id in sel_set]

    profit_record = ForexMonthlyProfit.query.filter_by(year=year, month=month, broker_name=broker).first()
    total_generated = profit_record.total_generated if profit_record else 0.0

    rows = []
    for inv in investors:
        broker_earn = round(inv.capital_usd * (inv.broker_pct / 100), 2)
        inv_due     = round(inv.capital_usd * (inv.investor_pct / 100), 2)
        net         = round(broker_earn - inv_due, 2)
        paid_rec    = ForexInvestorPayout.query.filter_by(investor_id=inv.id, year=year, month=month).first()
        paid_amt    = paid_rec.amount_paid if paid_rec else 0
        rows.append({
            'name': inv.name, 'broker_name': inv.broker_name or '',
            'capital': inv.capital_usd,
            'broker_pct': inv.broker_pct, 'broker_earn': broker_earn,
            'inv_pct': inv.investor_pct, 'inv_due': inv_due,
            'net': net, 'paid': paid_amt,
        })

    if paid_filter == 'paid':
        rows = [r for r in rows if r['paid'] > 0]
    elif paid_filter == 'unpaid':
        rows = [r for r in rows if r['paid'] == 0]

    output = io.StringIO()
    writer = csv.writer(output)
    month_label  = f"{MONTHS[month]} {year}"
    broker_label = broker
    status_label = paid_filter.capitalize() if paid_filter else 'All'
    writer.writerow([f'TopGee Forex — Investor Report | {month_label} | Broker: {broker_label} | Status: {status_label}'])
    writer.writerow([])
    writer.writerow(['Investor', 'Broker', 'Capital (USD)', 'Capital (AED)',
                     'Broker %', 'Broker Earn (USD)', 'Broker Earn (AED)',
                     'Investor %', 'Investor Due (USD)', 'Investor Due (AED)',
                     'Net (USD)', 'Net (AED)', 'Paid This Month?', 'Amount Paid (USD)'])
    for r in rows:
        status = 'Paid' if r['paid'] > 0 else 'Unpaid'
        writer.writerow([
            r['name'], r['broker_name'],
            f"{r['capital']:,.2f}", f"{r['capital']*AED:,.2f}",
            f"{r['broker_pct']}%", f"{r['broker_earn']:,.2f}", f"{r['broker_earn']*AED:,.2f}",
            f"{r['inv_pct']}%", f"{r['inv_due']:,.2f}", f"{r['inv_due']*AED:,.2f}",
            f"{r['net']:,.2f}", f"{r['net']*AED:,.2f}",
            status, f"{r['paid']:,.2f}" if r['paid'] > 0 else '0.00',
        ])
    writer.writerow([])
    writer.writerow(['TOTAL', '',
        f"{sum(r['capital'] for r in rows):,.2f}",
        f"{sum(r['capital'] for r in rows)*AED:,.2f}",
        '', f"{sum(r['broker_earn'] for r in rows):,.2f}",
        f"{sum(r['broker_earn'] for r in rows)*AED:,.2f}",
        '', f"{sum(r['inv_due'] for r in rows):,.2f}",
        f"{sum(r['inv_due'] for r in rows)*AED:,.2f}",
        f"{sum(r['net'] for r in rows):,.2f}",
        f"{sum(r['net'] for r in rows)*AED:,.2f}",
        '', ''])
    if total_generated > 0:
        writer.writerow([])
        writer.writerow([f'Total Generated {month_label}', f"${total_generated:,.2f}", f"AED {total_generated*AED:,.2f}"])

    from flask import make_response
    today = datetime.now().strftime('%Y-%m-%d')
    status_slug = f"_{paid_filter}" if paid_filter else ''
    broker_slug = f"_{broker.replace(' ','_')}" if broker != 'All' else ''
    filename = f"TopGeeForex_{MONTHS[month]}_{year}{broker_slug}{status_slug}_{today}.csv"
    resp = make_response('\ufeff' + output.getvalue())
    resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
    resp.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


@app.route('/forex-dashboard-data')
@login_required
def forex_dashboard_data():
    """JSON endpoint for dashboard forex summary card"""
    investors = ForexInvestor.query.filter_by(status='Active').all()
    now = datetime.now()
    total_capital    = sum(i.capital_usd for i in investors)
    total_inv_due    = sum(i.monthly_investor_due for i in investors)
    total_broker_tk  = sum(i.monthly_broker_take for i in investors)
    total_net        = sum(i.monthly_net_per_investor for i in investors)
    count            = len(investors)
    this_month_paid  = sum(p.amount_paid for p in ForexInvestorPayout.query.filter_by(
                           year=now.year, month=now.month).all())
    return jsonify({
        'count': count,
        'total_capital_usd': total_capital,
        'total_inv_due': total_inv_due,
        'total_broker_take': total_broker_tk,
        'total_net': total_net,
        'this_month_paid': this_month_paid,
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    print("\n" + "="*60)
    print("🚀 TOPGEE IT")
    print("="*60)
    print(f"📊 Dashboard: http://localhost:{port}")
    print("="*60 + "\n")
    app.run(debug=False, host='0.0.0.0', port=port)
