from extensions import db

class AssetCategory(db.Model):
    __tablename__ = 'asset_categories'
    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('asset_categories.id'))
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    depreciation_years = db.Column(db.Integer)
    level = db.Column(db.Integer, default=1)
    path = db.Column(db.String(500))
    
    parent = db.relationship('AssetCategory', remote_side=[id], backref='children')
    assets = db.relationship('Asset', backref='category', lazy='dynamic')

class Asset(db.Model):
    __tablename__ = 'assets'
    id = db.Column(db.String(50), primary_key=True) # 資產編號
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category_id = db.Column(db.Integer, db.ForeignKey('asset_categories.id'))
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'))
    custodian_id = db.Column(db.Integer, db.ForeignKey('personnel.id'))
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    
    brand = db.Column(db.String(100))
    model = db.Column(db.String(100))
    serial_number = db.Column(db.String(100))
    specifications = db.Column(db.Text)
    
    purchase_date = db.Column(db.Date)
    purchase_price = db.Column(db.Numeric(15, 2))
    currency = db.Column(db.String(3), default='TWD')
    supplier = db.Column(db.String(200))
    warranty_date = db.Column(db.Date)
    
    depreciation_method = db.Column(db.String(20))
    useful_life_years = db.Column(db.Integer)
    salvage_value = db.Column(db.Numeric(15, 2))
    current_value = db.Column(db.Numeric(15, 2))
    
    status = db.Column(db.String(20), default='active') # active/in_stock/repair/disposed/lost
    condition = db.Column(db.String(20), default='good') # new/good/fair/poor
    
    qr_code_path = db.Column(db.String(255))
    photo_path = db.Column(db.String(255))
    notes = db.Column(db.Text)
    
    # Relationships
    location = db.relationship('Location', backref='assets')
    custodian = db.relationship('Personnel', backref='custodian_assets', foreign_keys=[custodian_id])
    department = db.relationship('Department', backref='department_assets')
