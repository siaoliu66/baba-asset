from datetime import datetime
from extensions import db

class DepreciationRecord(db.Model):
    __tablename__ = 'depreciation_records'
    
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.String(50), db.ForeignKey('assets.id'), nullable=False)
    
    fiscal_year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    
    depreciation_amount = db.Column(db.Numeric(15, 2), nullable=False)
    accumulated_depreciation = db.Column(db.Numeric(15, 2), nullable=False)
    book_value = db.Column(db.Numeric(15, 2), nullable=False)
    
    method = db.Column(db.String(20), default='straight_line')
    note = db.Column(db.String(200))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    asset = db.relationship('Asset', backref=db.backref('depreciation_records', lazy=True))

    __table_args__ = (
        db.UniqueConstraint('asset_id', 'fiscal_year', 'month', name='uix_asset_period'),
    )
