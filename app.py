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
if os.environ.get('DATABASE_URL'):
    # Render provides DATABASE_URL for PostgreSQL
    database_url = os.environ.get('DATABASE_URL')
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    # Local SQLite
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data', 'investments.db')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'topgee-investment-system-2026')

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
    investment_amount = db.Column(db.Float, nullable=False)
    investment_date = db.Column(db.Date, nullable=False)
    sales_rep_id = db.Column(db.Integer, db.ForeignKey('sales_rep.id'))
    
    # ROI Split (total is always 5% of investment)
    investor_roi_percent = db.Column(db.Float, default=2.5)  # 2-3%
    sales_roi_percent = db.Column(db.Float, default=2.5)     # 2-3%
    
    status = db.Column(db.String(50), default='Active')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    monthly_records = db.relationship('MonthlyRecord', backref='investor', lazy=True, cascade='all, delete-orphan')
    
    @property
    def total_roi_pool(self):
        """5% of investment amount"""
        return self.investment_amount * 0.05
    
    @property
    def monthly_investor_roi(self):
        """Investor's share of ROI"""
        return self.investment_amount * (self.investor_roi_percent / 100)
    
    @property
    def monthly_sales_roi(self):
        """Sales rep's share of ROI"""
        return self.investment_amount * (self.sales_roi_percent / 100)

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

# ============= DATABASE INITIALIZATION =============

@app.before_request
def ensure_db_ready():
    """Ensure database tables exist before handling any request"""
    if not hasattr(app, '_db_initialized'):
        try:
            with app.app_context():
                db.create_all()
                app._db_initialized = True
                print("✅ Database tables created")
        except Exception as e:
            print(f"⚠️ DB init on request failed: {e}")

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
    total_investment = sum(i.investment_amount for i in investors)
    
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
    """Individual investor profile with 12-month ledger"""
    investor = Investor.query.get_or_404(investor_id)
    
    # Get all monthly records (last 12 months)
    now = datetime.now()
    records = MonthlyRecord.query.filter_by(investor_id=investor.id).order_by(
        MonthlyRecord.year.desc(), MonthlyRecord.month.desc()
    ).limit(12).all()
    
    # Calculate totals
    total_revenue = sum(r.revenue_generated for r in records)
    total_investor_roi = sum(r.investor_roi_paid for r in records)
    total_sales_roi = sum(r.sales_roi_paid for r in records)
    
    return render_template('investor_detail.html',
                         investor=investor,
                         records=records,
                         total_revenue=total_revenue,
                         total_investor_roi=total_investor_roi,
                         total_sales_roi=total_sales_roi,
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
        
        investor = Investor(
            name=request.form['name'],
            category=request.form['category'],
            investment_amount=investment_aed,
            investment_date=datetime.strptime(request.form['investment_date'], '%Y-%m-%d'),
            sales_rep_id=int(request.form['sales_rep_id']) if request.form.get('sales_rep_id') else None,
            investor_roi_percent=float(request.form.get('investor_roi_percent', 2.5)),
            sales_roi_percent=float(request.form.get('sales_roi_percent', 2.5)),
            status=request.form.get('status', 'Active'),
            notes=request.form.get('notes', '')
        )
        db.session.add(investor)
        db.session.commit()
        return redirect(url_for('dashboard'))
    
    sales_reps = SalesRep.query.filter_by(active=True).all()
    return render_template('add_investor.html', sales_reps=sales_reps)

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
        
        investor.name = request.form['name']
        investor.category = request.form['category']
        investor.investment_amount = investment_aed
        investor.investment_date = datetime.strptime(request.form['investment_date'], '%Y-%m-%d')
        investor.sales_rep_id = int(request.form['sales_rep_id']) if request.form.get('sales_rep_id') else None
        investor.investor_roi_percent = float(request.form.get('investor_roi_percent', 2.5))
        investor.sales_roi_percent = float(request.form.get('sales_roi_percent', 2.5))
        investor.status = request.form.get('status', 'Active')
        investor.notes = request.form.get('notes', '')
        
        db.session.commit()
        return redirect(url_for('investor_detail', investor_id=investor.id))
    
    sales_reps = SalesRep.query.filter_by(active=True).all()
    return render_template('edit_investor.html', investor=investor, sales_reps=sales_reps)

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
    return render_template('sales_reps.html', sales_reps=reps)

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
    return redirect(url_for('sales_reps'))

def init_db():
    """Initialize database with sample data"""
    try:
        with app.app_context():
            db.create_all()
            
            if SalesRep.query.count() == 0:
                print("Creating sample sales reps...")
                reps = [
                    SalesRep(name="John Smith", email="john@topgee.com"),
                    SalesRep(name="Sarah Johnson", email="sarah@topgee.com"),
                    SalesRep(name="Ahmed Ali", email="ahmed@topgee.com")
                ]
                for rep in reps:
                    db.session.add(rep)
                db.session.commit()
                print(f"✅ Added {len(reps)} sales reps")
            
            print("✅ Database ready")
    except Exception as e:
        print(f"⚠️ Database initialization error: {e}")
        print("Database will be initialized on first request")

# Initialize database on startup (safe with error handling)
try:
    init_db()
except Exception as e:
    print(f"Startup DB init failed (will retry): {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    print("\n" + "="*60)
    print("🚀 TOPGEE INVESTMENT MANAGEMENT SYSTEM")
    print("="*60)
    print(f"📊 Dashboard: http://localhost:{port}")
    print("="*60 + "\n")
    app.run(debug=False, host='0.0.0.0', port=port)
