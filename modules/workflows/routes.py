from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from core.models.workflow import WorkflowConfig, ApprovalStep, ApprovalRecord
from core.models.organization import Company, Department
from core.models.system import User, Role
from extensions import db
from . import workflows_bp

# ==================== Workflow Config CRUD ====================
@workflows_bp.route('/configs')
@login_required
def config_list():
    configs = WorkflowConfig.query.order_by(WorkflowConfig.workflow_type).all()
    return render_template('workflows/config_list.html', configs=configs)

@workflows_bp.route('/configs/create', methods=['GET', 'POST'])
@login_required
def config_create():
    if request.method == 'POST':
        try:
            config = WorkflowConfig(
                workflow_type=request.form.get('workflow_type'),
                scope_type=request.form.get('scope_type'),
                scope_id=int(request.form.get('scope_id') or 0),
                name=request.form.get('name'),
                require_dept_approval=False,
                require_senior_approval=False,
                allow_self_select=False,
                is_active=request.form.get('is_active') == 'on'
            )
            db.session.add(config)
            db.session.commit()
            
            # No default steps created. User manually adds steps.
            flash('簽核流程設定已建立', 'success')
            return redirect(url_for('workflows.config_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'建立失敗: {str(e)}', 'danger')
    
    companies = Company.query.filter_by(is_active=True).all()
    departments = Department.query.all()
    roles = Role.query.all()
    users = User.query.filter_by(is_active=True).all()
    # Fetch Dept Managers for specific selection
    dept_managers = User.query.join(Role).filter(Role.name == 'dept_manager', User.is_active == True).all()
    return render_template('workflows/config_form.html', config=None, companies=companies, departments=departments, roles=roles, users=users, dept_managers=dept_managers)


@workflows_bp.route('/configs/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def config_edit(id):
    config = WorkflowConfig.query.get_or_404(id)
    if request.method == 'POST':
        try:
            config.workflow_type = request.form.get('workflow_type')
            config.scope_type = request.form.get('scope_type')
            config.scope_id = int(request.form.get('scope_id') or 0)
            config.name = request.form.get('name')
            config.require_dept_approval = request.form.get('require_dept_approval') == 'on'
            config.require_senior_approval = request.form.get('require_senior_approval') == 'on'
            config.allow_self_select = request.form.get('allow_self_select') == 'on'
            config.is_active = request.form.get('is_active') == 'on'
            db.session.commit()
            flash('簽核流程設定已更新', 'success')
            return redirect(url_for('workflows.config_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新失敗: {str(e)}', 'danger')
    
    companies = Company.query.filter_by(is_active=True).all()
    departments = Department.query.all()
    roles = Role.query.all()
    users = User.query.filter_by(is_active=True).all()
    dept_managers = User.query.join(Role).filter(Role.name == 'dept_manager', User.is_active == True).all()
    return render_template('workflows/config_form.html', config=config, companies=companies, departments=departments, roles=roles, users=users, dept_managers=dept_managers)

@workflows_bp.route('/configs/<int:id>/delete', methods=['POST'])
@login_required
def config_delete(id):
    config = WorkflowConfig.query.get_or_404(id)
    try:
        db.session.delete(config)
        db.session.commit()
        flash('簽核流程設定已刪除', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'刪除失敗: {str(e)}', 'danger')
    return redirect(url_for('workflows.config_list'))

# ==================== Approval Steps CRUD ====================
@workflows_bp.route('/configs/<int:config_id>/steps/add', methods=['POST'])
@login_required
def step_add(config_id):
    config = WorkflowConfig.query.get_or_404(config_id)
    try:
        max_order = db.session.query(db.func.max(ApprovalStep.step_order)).filter_by(config_id=config_id).scalar() or 0
        
        # Handle different approver types
        raw_approver_type = request.form.get('approver_type')
        approver_type = raw_approver_type
        default_approver_id = request.form.get('default_approver_id') or None
        
        # Special handling for specific Dept Manager selection
        if raw_approver_type == 'specific_user_dept':
            approver_type = 'specific_user'
            default_approver_id = request.form.get('specific_user_id_dept')
        
        step = ApprovalStep(
            config_id=config_id,
            step_order=max_order + 1,
            step_name=request.form.get('step_name'),
            approver_type=approver_type,
            default_approver_id=default_approver_id,
            role_id=request.form.get('role_id') or None,
            can_skip=request.form.get('can_skip') == 'on',
            reminder_days=int(request.form.get('reminder_days') or 3),
            escalation_days=int(request.form.get('escalation_days') or 7)
        )
        db.session.add(step)
        db.session.commit()
        flash('簽核步驟已新增', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'新增失敗: {str(e)}', 'danger')
    return redirect(url_for('workflows.config_edit', id=config_id))

@workflows_bp.route('/steps/<int:step_id>/delete', methods=['POST'])
@login_required
def step_delete(step_id):
    step = ApprovalStep.query.get_or_404(step_id)
    config_id = step.config_id
    try:
        db.session.delete(step)
        db.session.commit()
        flash('簽核步驟已刪除', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'刪除失敗: {str(e)}', 'danger')
    return redirect(url_for('workflows.config_edit', id=config_id))

# ==================== Pending Requests ====================
@workflows_bp.route('/requests')
@login_required
def pending_requests():
    # Fetch all pending records for the user, newest first
    all_pending = ApprovalRecord.query.filter_by(
        selected_approver_id=current_user.id,
        status='pending'
    ).order_by(ApprovalRecord.id.desc()).all()
    
    # Deduplicate by (reference_type, reference_id) to handle legacy duplicates
    seen = set()
    unique_pending = []
    for req in all_pending:
        key = (req.reference_type, req.reference_id)
        if key not in seen:
            seen.add(key)
            unique_pending.append(req)
        else:
            # Optional: We could mark these as 'skipped' or similar in DB later
            pass
            
    return render_template('workflows/requests.html', requests=unique_pending)

@workflows_bp.route('/approve/<int:record_id>', methods=['POST'])
@login_required
def approve_record(record_id):
    record = ApprovalRecord.query.get_or_404(record_id)
    if record.selected_approver_id != current_user.id:
        # Check Proxy?
        # If current user is proxy for selected approver, allow.
        # But ApprovalRecord stores 'selected_approver_id'.
        # If I am proxy, I am NOT selected_approver_id.
        # But WorkflowService.resolve_approver sets 'selected_approver_id' TO the proxy!
        # So 'selected_approver_id' should ALREADY be the proxy user ID.
        # So direct check is fine.
        return jsonify({"error": "Unauthorized"}), 403
        
    comment = request.form.get('comment')
    action = request.form.get('action')
    
    from core.workflow_service import WorkflowService
    
    # Map button action to status string
    status_map = {
        'approve': 'approved',
        'reject': 'rejected'
    }
    
    if action in status_map:
        success, message = WorkflowService.process_step(
            record_id=record.id,
            status=status_map[action],
            comment=comment,
            user_id=current_user.id
        )
        if success:
            flash(f'操作成功: {message}', 'success')
        else:
            flash(f'操作失敗: {message}', 'danger')
    else:
        flash(f'未知操作: {action}', 'warning')
        
    return redirect(url_for('workflows.pending_requests'))

# ==================== API Endpoints ====================
@workflows_bp.route('/api/users')
@login_required
def api_users():
    users = User.query.filter_by(is_active=True).all()
    return jsonify([{"id": u.id, "name": u.display_name or u.username} for u in users])
