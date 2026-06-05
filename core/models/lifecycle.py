from datetime import datetime
from extensions import db

class AssetTransfer(db.Model):
    __tablename__ = 'asset_transfers'
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.String(50), db.ForeignKey('assets.id'), nullable=False)
    from_custodian_id = db.Column(db.Integer, db.ForeignKey('personnel.id'))
    to_custodian_id = db.Column(db.Integer, db.ForeignKey('personnel.id'))
    from_location_id = db.Column(db.Integer, db.ForeignKey('locations.id'))
    to_location_id = db.Column(db.Integer, db.ForeignKey('locations.id'))
    from_department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    to_department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    
    photo_path = db.Column(db.String(255))
    gps_lat = db.Column(db.Numeric(10, 7))
    gps_lng = db.Column(db.Numeric(10, 7))
    
    status = db.Column(db.String(20), default='pending') # pending/approved/rejected/completed
    reason = db.Column(db.Text)
    transfer_type = db.Column(db.String(20)) # custodian/warehouse
    attachment_path = db.Column(db.String(255))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    asset = db.relationship('Asset', backref='transfers')
    from_department = db.relationship('Department', foreign_keys=[from_department_id])
    to_department = db.relationship('Department', foreign_keys=[to_department_id])
    from_custodian = db.relationship('Personnel', foreign_keys=[from_custodian_id])
    to_custodian = db.relationship('Personnel', foreign_keys=[to_custodian_id])
    to_location = db.relationship('Location', foreign_keys=[to_location_id])

class AssetDisposal(db.Model):
    __tablename__ = 'asset_disposals'
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.String(50), db.ForeignKey('assets.id'), nullable=False)
    disposal_type = db.Column(db.String(20)) # scrap/donate/sell
    reason = db.Column(db.Text, nullable=False)
    disposal_date = db.Column(db.Date)
    disposal_value = db.Column(db.Numeric(15, 2))
    status = db.Column(db.String(20), default='pending') # pending/approved/rejected/completed
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AssetRepair(db.Model):
    __tablename__ = 'asset_repairs'
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.String(50), db.ForeignKey('assets.id'), nullable=False)
    issue_description = db.Column(db.Text, nullable=False)
    repair_type = db.Column(db.String(20)) # internal/external
    vendor = db.Column(db.String(200))
    repair_cost = db.Column(db.Numeric(15, 2))
    before_photo_path = db.Column(db.String(255))
    after_photo_path = db.Column(db.String(255))
    status = db.Column(db.String(20), default='repairing') # repairing/completed
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
