from datetime import datetime
from extensions import db

class DocumentCategory(db.Model):
    __tablename__ = 'document_categories'
    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('document_categories.id'))
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    retention_years = db.Column(db.Integer)
    is_active = db.Column(db.Boolean, default=True)
    
    parent = db.relationship('DocumentCategory', remote_side=[id], backref='children')

class Document(db.Model):
    __tablename__ = 'documents'
    id = db.Column(db.Integer, primary_key=True)
    doc_number = db.Column(db.String(50), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category_id = db.Column(db.Integer, db.ForeignKey('document_categories.id'))
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('personnel.id'), nullable=False)
    
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.BigInteger)
    file_type = db.Column(db.String(20))
    version = db.Column(db.Integer, default=1)
    
    classification = db.Column(db.String(20), default='public') # public/internal/confidential/top_secret
    status = db.Column(db.String(20), default='active') # draft/active/archived
    
    is_contract = db.Column(db.Boolean, default=False)
    contract_start_date = db.Column(db.Date)
    contract_end_date = db.Column(db.Date)
    reminder_days = db.Column(db.Integer)
    retention_years = db.Column(db.Integer)
    full_text_content = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

class DocumentVersion(db.Model):
    __tablename__ = 'document_versions'
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    version = db.Column(db.Integer, nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    change_summary = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DocumentAccessLog(db.Model):
    __tablename__ = 'document_access_logs'
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(20), nullable=False) # view/download/print/edit/delete/share
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    watermark_id = db.Column(db.String(50))
    accessed_at = db.Column(db.DateTime, default=datetime.utcnow)
