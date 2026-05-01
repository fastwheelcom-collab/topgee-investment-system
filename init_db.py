"""Initialize database for Render deployment"""
from app import app, db, SalesRep

print("Initializing database...")
with app.app_context():
    db.create_all()
    print("✅ Tables created")
    
    if SalesRep.query.count() == 0:
        print("Adding sample sales reps...")
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
