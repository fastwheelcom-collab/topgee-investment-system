# Add this to app.py after other models

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
