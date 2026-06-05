from datetime import datetime
from extensions import db

class InventoryPlan(db.Model):
    __tablename__ = 'inventory_plans'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    plan_type = db.Column(db.String(20)) # location/personal/full
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='draft') # draft/submitted/pending_dept/dept_approved/pending_senior/rejected/completed
    target_location_ids = db.Column(db.Text) # comma separated IDs
    
    submitted_at = db.Column(db.DateTime)
    submitted_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Quick approval access (replicated from records for performance)
    dept_approver_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    dept_approval_status = db.Column(db.String(20))
    dept_approval_comment = db.Column(db.Text)
    dept_approved_at = db.Column(db.DateTime)
    
    senior_approver_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    senior_approval_status = db.Column(db.String(20))
    senior_approval_comment = db.Column(db.Text)
    senior_approved_at = db.Column(db.DateTime)
    
    tasks = db.relationship('InventoryTask', backref='plan', cascade='all, delete-orphan')

class InventoryTask(db.Model):
    __tablename__ = 'inventory_tasks'
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('inventory_plans.id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'))
    personnel_id = db.Column(db.Integer, db.ForeignKey('personnel.id'))
    assignee_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    total_assets = db.Column(db.Integer, default=0)
    scanned_count = db.Column(db.Integer, default=0)
    normal_count = db.Column(db.Integer, default=0)
    abnormal_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='pending') # pending/in_progress/submitted/completed
    rejection_reason = db.Column(db.String(500))
    
    records = db.relationship('InventoryRecord', backref='task', cascade='all, delete-orphan')
    snapshots = db.relationship('InventorySnapshot', backref='task', cascade='all, delete-orphan')
    
    assignee = db.relationship('User', foreign_keys=[assignee_id])
    location = db.relationship('Location', foreign_keys=[location_id])
    personnel = db.relationship('Personnel', foreign_keys=[personnel_id])

class InventoryRecord(db.Model):
    __tablename__ = 'inventory_records'
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('inventory_tasks.id'), nullable=False)
    asset_id = db.Column(db.String(50), db.ForeignKey('assets.id'), nullable=False)
    result = db.Column(db.String(20), nullable=False) # normal/damaged/missing/found
    scan_type = db.Column(db.String(20)) # qr/manual
    photo_path = db.Column(db.String(255))
    gps_lat = db.Column(db.Numeric(10, 7))
    gps_lng = db.Column(db.Numeric(10, 7))
    gps_accuracy = db.Column(db.Integer)
    remarks = db.Column(db.Text)
    is_offline = db.Column(db.Boolean, default=False)
    synced_at = db.Column(db.DateTime)

class InventorySnapshot(db.Model):
    __tablename__ = 'inventory_snapshots'
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('inventory_tasks.id'), nullable=False)
    asset_id = db.Column(db.String(50), db.ForeignKey('assets.id'), nullable=False)
    status = db.Column(db.String(20), default='pending') # pending/scanned/missing
    asset_name = db.Column(db.String(200))
    asset_model = db.Column(db.String(100))
    asset_location = db.Column(db.String(200))
    asset_custodian = db.Column(db.String(100))
    remarks = db.Column(db.Text)
