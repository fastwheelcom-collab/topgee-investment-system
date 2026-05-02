from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, session, flash
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

# Admin credentials (username: admin, password: admin123)
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD_HASH = hashlib.sha256('admin123'.encode()).hexdigest()

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

# Exchange rate
EXCHANGE_RATE = 3.68

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
    
    # ROI Split (total is always 5% of investment)
    investor_roi_percent = db.Column(db.Float, default=2.5)  # 2-3%
    sales_roi_percent = db.Column(db.Float, default=2.5)     # 2-3%
    
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
        """5% of TOTAL investment (including deposits/withdrawals)"""
        return self.total_capital * 0.05
    
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
    """Track deposits and withdrawals for each investor"""
    id = db.Column(db.Integer, primary_key=True)
    investor_id = db.Column(db.Integer, db.ForeignKey('investor.id'), nullable=False)
    
    transaction_type = db.Column(db.String(20), nullable=False)  # Deposit or Withdrawal
    amount = db.Column(db.Float, nullable=False)
    transaction_date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text)
    payment_evidence = db.Column(db.Text)  # Base64 encoded receipt/bank transfer proof
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
# ============= DATABASE INITIALIZATION =============

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
        username = request.form['username']
        password = request.form['password']
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        if username == ADMIN_USERNAME and password_hash == ADMIN_PASSWORD_HASH:
            session['logged_in'] = True
            session['is_admin'] = True
            session['username'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    """Main dashboard"""
    investors = Investor.query.all()
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
    
    # Current month totals
    monthly_revenue = sum(r.revenue_generated for r in current_records)
    monthly_roi_distributed = sum(r.investor_roi_paid + r.sales_roi_paid for r in current_records)
    
    # Sales team earnings (current month)
    sales_earnings = sum(r.sales_roi_paid for r in current_records)
    
    # Partner distribution for current month
    partner_dist = PartnerDistribution.query.filter_by(year=current_year, month=current_month).first()
    
    stats = {
        'total_investors': total_investors,
        'total_investment': total_investment,
        'monthly_revenue': monthly_revenue,
        'monthly_roi_distributed': monthly_roi_distributed,
        'sales_earnings': sales_earnings,
        'partner_distribution': partner_dist,
        'current_month': now.strftime('%B %Y')
    }
    
    # Search functionality
    search_query = request.args.get('search', '')
    if search_query:
        investors = Investor.query.filter(
            db.or_(
                Investor.name.ilike(f'%{search_query}%'),
                Investor.category.ilike(f'%{search_query}%'),
                Investor.notes.ilike(f'%{search_query}%')
            )
        ).all()
    
    return render_template('dashboard.html',
                         investors=investors,
                         sales_reps=sales_reps,
                         stats=stats,
                         current_year=current_year,
                         current_month=current_month,
                         search_query=search_query,
                         is_admin=session.get('is_admin', False))

@app.route('/investor/<int:investor_id>')
@login_required
def investor_detail(investor_id):
    investor = Investor.query.get_or_404(investor_id)
    now = datetime.now()
    current_year = now.year
    
    # Get manual ROI records for current year
    manual_records = ManualROI.query.filter_by(investor_id=investor.id, year=current_year).all()
    
    # Build 12-month ledger
    months = ['January', 'February', 'March', 'April', 'May', 'June',
              'July', 'August', 'September', 'October', 'November', 'December']
    ledger = []
    for month_num in range(1, 13):
        record = next((r for r in manual_records if r.month == month_num), None)
        ledger.append({'month': month_num, 'month_name': months[month_num-1], 'record': record})
    
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
                         transactions=transactions,
                         deposits=deposits,
                         withdrawals=withdrawals,
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
            sales_roi_percent=float(request.form.get('sales_roi_percent', 2.5)),
            contract_start=contract_start,
            contract_end=contract_end,
            status=request.form.get('status', 'Active'),
            notes=request.form.get('notes', '')
        )
        db.session.add(investor)
        db.session.commit()
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
        investor.sales_roi_percent = float(request.form.get('sales_roi_percent', 2.5))
        investor.contract_start = contract_start
        investor.contract_end = contract_end
        investor.status = request.form.get('status', 'Active')
        investor.notes = request.form.get('notes', '')
        
        db.session.commit()
        return redirect(url_for('investor_detail', investor_id=investor.id))
    
    sales_reps = SalesRep.query.filter_by(active=True).all()
    return render_template('edit_investor.html', investor=investor, sales_reps=sales_reps, countries=COUNTRIES)

@app.route('/investor/<int:investor_id>/delete', methods=['POST'])
@admin_required
def delete_investor(investor_id):
    investor = Investor.query.get_or_404(investor_id)
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
    <b>ROI Split:</b> Investor {investor.investor_roi_percent}% | Sales {investor.sales_roi_percent}%
    """
    elements.append(Paragraph(details, styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Monthly records table
    data = [['Month', 'Revenue', 'Your ROI', 'Sales ROI', 'Payment Date']]
    for rec in records:
        data.append([
            rec.month_name,
            f"{rec.revenue_generated:,.2f}",
            f"{rec.investor_roi_paid:,.2f}",
            f"{rec.sales_roi_paid:,.2f}",
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
    """Monthly grid view for all investors"""
    # Get year (default to current)
    year = request.args.get('year', datetime.now().year, type=int)
    
    # Get all investors
    investors = Investor.query.all()
    
    # Get all monthly records for this year
    records = MonthlyRecord.query.filter_by(year=year).all()
    
    # Build grid data: investor -> month -> record
    grid_data = {}
    for investor in investors:
        grid_data[investor.id] = {
            'investor': investor,
            'months': {}
        }
        for month in range(1, 13):
            record = next((r for r in records if r.investor_id == investor.id and r.month == month), None)
            grid_data[investor.id]['months'][month] = record
    
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
    """Advanced reporting dashboard"""
    # Get date range from request
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    category = request.args.get('category', '')
    
    # Build query
    query = Investor.query
    if date_from:
        query = query.filter(Investor.investment_date >= datetime.strptime(date_from, '%Y-%m-%d'))
    if date_to:
        query = query.filter(Investor.investment_date <= datetime.strptime(date_to, '%Y-%m-%d'))
    if category:
        query = query.filter(Investor.category == category)
    
    investors = query.all()
    
    # Calculate stats
    total_investment = sum(i.investment_amount for i in investors)
    total_investors = len(investors)
    individual_count = len([i for i in investors if i.category == 'Individual'])
    company_count = len([i for i in investors if i.category == 'Company'])
    
    # Get monthly records for the filtered investors
    investor_ids = [i.id for i in investors]
    monthly_records = MonthlyRecord.query.filter(MonthlyRecord.investor_id.in_(investor_ids)).all() if investor_ids else []
    
    total_revenue = sum(r.revenue_generated for r in monthly_records)
    total_roi_paid = sum(r.investor_roi_paid + r.sales_roi_paid for r in monthly_records)
    
    stats = {
        'total_investment': total_investment,
        'total_investors': total_investors,
        'individual_count': individual_count,
        'company_count': company_count,
        'total_revenue': total_revenue,
        'total_roi_paid': total_roi_paid,
    }
    
    return render_template('reports_dashboard.html',
                         investors=investors,
                         stats=stats,
                         filters=request.args,
                         exchange_rate=EXCHANGE_RATE)

@app.route('/investor/<int:investor_id>/transaction/add', methods=['POST'])
@admin_required
def add_transaction(investor_id):
    """Add deposit or withdrawal"""
    investor = Investor.query.get_or_404(investor_id)
    
    # Handle payment evidence upload
    payment_evidence = None
    file = request.files.get('payment_evidence')
    if file and file.filename:
        import base64
        file_data = file.read()
        encoded = base64.b64encode(file_data).decode('utf-8')
        payment_evidence = f"data:{file.mimetype};base64,{encoded}"
    
    transaction = InvestmentTransaction(
        investor_id=investor_id,
        transaction_type=request.form['transaction_type'],  # Deposit or Withdrawal
        amount=float(request.form['amount']),
        transaction_date=datetime.strptime(request.form['transaction_date'], '%Y-%m-%d').date(),
        notes=request.form.get('notes', ''),
        payment_evidence=payment_evidence
    )
    db.session.add(transaction)
    db.session.commit()
    
    flash(f"{transaction.transaction_type} of {transaction.amount:,.2f} AED added successfully!", 'success')
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
    
    tx_type = transaction.transaction_type
    tx_amount = transaction.amount
    
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


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    print("\n" + "="*60)
    print("🚀 TOPGEE IT")
    print("="*60)
    print(f"📊 Dashboard: http://localhost:{port}")
    print("="*60 + "\n")
    app.run(debug=False, host='0.0.0.0', port=port)
