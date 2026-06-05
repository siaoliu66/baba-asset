from app import create_app
from extensions import db
from core.models.system import User
from core.models.organization import Personnel, Department, Company

app = create_app()

with app.app_context():
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        print("Admin user not found!")
        exit(1)
        
    print(f"Admin User: {admin.username}, Personnel ID: {admin.personnel_id}")
    
    if not admin.personnel_id:
        # Check if personnel exists
        person = Personnel.query.filter_by(employee_id='ADMIN001').first()
        if not person:
            # Create Personnel
            dept = Department.query.first()
            if not dept:
                # Create Company and Dept if clean db
                comp = Company(name="Default Corp", code="DEF", is_active=True)
                db.session.add(comp)
                db.session.commit()
                dept = Department(name="IT Dept", code="IT", company_id=comp.id, is_active=True)
                db.session.add(dept)
                db.session.commit()
                
            person = Personnel(
                name="Admin User",
                employee_id="ADMIN001",
                email="admin@example.com",
                department_id=dept.id,
                is_active=True
            )
            db.session.add(person)
            db.session.commit()
            print("Created new personnel for admin.")
            
        admin.personnel_id = person.id
        db.session.commit()
        print(f"Linked Admin to Personnel ID: {person.id}")
    else:
        print("Admin already linked.")
