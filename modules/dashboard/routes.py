from flask import render_template
from flask_login import login_required, current_user
from core.models.assets import Asset
from core.models.workflow import ApprovalRecord
from core.models.inventory import InventoryTask
from core.models.documents import Document
from core.models.system import AuditLog
from core.models.organization import Department
from extensions import db
from sqlalchemy import func
from . import dashboard_bp
from flask import current_app

@dashboard_bp.route('/')
@login_required
def index():
    # 1. Asset Stats
    total_assets = Asset.query.count()
    active_assets = Asset.query.filter_by(status='active').count()
    maintenance_assets = Asset.query.filter_by(status='maintenance').count()
    
    # 2. Approval Stats
    pending_approvals = ApprovalRecord.query.filter_by(
        selected_approver_id=current_user.id, 
        status='pending'
    ).count()
    
    # 3. Inventory Stats
    active_tasks = InventoryTask.query.filter(InventoryTask.status.in_(['pending', 'in_progress'])).count()
    
    # 4. Document Stats (Optional)
    doc_count = 0
    if current_app.config.get('DOCUMENT_MODULE_ENABLED'):
        doc_count = Document.query.count()

    stats = {
        'total_assets': total_assets,
        'active_assets': active_assets,
        'maintenance_assets': maintenance_assets,
        'pending_approvals': pending_approvals,
        'active_inventory_tasks': active_tasks,
        'doc_count': doc_count
    }
    
    # 5. Recent Activities
    # Join AuditLog with Asset to get details. 
    # Note: reference_id is string, Asset.id is string.
    recent_activities = db.session.query(AuditLog, Asset).join(
        Asset, AuditLog.reference_id == Asset.id
    ).filter(
        AuditLog.module == 'assets'
    ).order_by(
        AuditLog.created_at.desc()
    ).limit(5).all()
    
    # 6. Department Stats
    # Query: SELECT d.name, COUNT(a.id) FROM assets a LEFT JOIN departments d ON ... GROUP BY d.id
    dept_query = db.session.query(
        Department.name, func.count(Asset.id)
    ).outerjoin(
        Asset, Asset.department_id == Department.id
    ).group_by(
        Department.id
    ).all()
    
    # Handle assets with no department (optional, or included if outerjoin setup differently)
    # For simplicity, just list departments with assets
    dept_stats = [{'name': d[0] or '未分配', 'count': d[1]} for d in dept_query if d[1] > 0]
    
    return render_template('dashboard/index.html', stats=stats, recent_activities=recent_activities, dept_stats=dept_stats)
