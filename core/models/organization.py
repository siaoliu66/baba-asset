from extensions import db

class Company(db.Model):
    __tablename__ = 'companies'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    display_name = db.Column(db.String(100))
    short_name = db.Column(db.String(20))
    tax_id = db.Column(db.String(20))
    address = db.Column(db.Text)
    phone = db.Column(db.String(30))
    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
    
    departments = db.relationship('Department', backref='company', lazy='dynamic')
    locations = db.relationship('Location', backref='company', lazy='dynamic')
    assets = db.relationship('Asset', backref='company', lazy='dynamic')

class Department(db.Model):
    __tablename__ = 'departments'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    code = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    display_name = db.Column(db.String(100))
    manager_id = db.Column(db.Integer, db.ForeignKey('personnel.id'))
    level = db.Column(db.Integer, default=1)
    path = db.Column(db.String(500))
    sort_order = db.Column(db.Integer, default=0)
    
    parent = db.relationship('Department', remote_side=[id], backref='children')
    personnel_list = db.relationship('Personnel', backref='department', lazy='dynamic', foreign_keys='Personnel.department_id')

class Personnel(db.Model):
    __tablename__ = 'personnel'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(20), unique=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    display_name = db.Column(db.String(50))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(30))
    position = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)
    is_system_custodian = db.Column(db.Boolean, default=False)
    is_inventory_staff = db.Column(db.Boolean, default=False)
    
    # One-to-one with user
    user = db.relationship('User', backref='personnel', uselist=False, foreign_keys='User.personnel_id')
    managed_departments = db.relationship('Department', backref='manager', foreign_keys='Department.manager_id')
    managed_locations = db.relationship('Location', backref='manager', foreign_keys='Location.manager_id')

class Location(db.Model):
    __tablename__ = 'locations'
    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('locations.id'))
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    code = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.Text)
    manager_id = db.Column(db.Integer, db.ForeignKey('personnel.id'))
    
    parent = db.relationship('Location', remote_side=[id], backref='children')
