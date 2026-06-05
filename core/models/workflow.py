from datetime import datetime
from extensions import db

class WorkflowConfig(db.Model):
    __tablename__ = 'workflow_configs'
    id = db.Column(db.Integer, primary_key=True)
    workflow_type = db.Column(db.String(30), nullable=False) # personal_inventory / location_inventory / transfer / disposal
    scope_type = db.Column(db.String(20), nullable=False) # company / department / location
    scope_id = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(100))
    require_dept_approval = db.Column(db.Boolean, default=True)
    require_senior_approval = db.Column(db.Boolean, default=True)
    allow_self_select = db.Column(db.Boolean, default=True)
    is_active = db.Column(db.Boolean, default=True)
    
    steps = db.relationship('ApprovalStep', backref='config', cascade='all, delete-orphan')

class ApprovalStep(db.Model):
    __tablename__ = 'approval_steps'
    id = db.Column(db.Integer, primary_key=True)
    config_id = db.Column(db.Integer, db.ForeignKey('workflow_configs.id'), nullable=False)
    step_order = db.Column(db.Integer, nullable=False) # 1=部門, 2=高階
    step_name = db.Column(db.String(50), nullable=False)
    approver_type = db.Column(db.String(20), nullable=False) # role / specific_user / self_select / department_manager
    default_approver_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    can_skip = db.Column(db.Boolean, default=False)
    skip_condition = db.Column(db.JSON)
    reminder_days = db.Column(db.Integer, default=3)
    escalation_days = db.Column(db.Integer, default=7)

    approver_user = db.relationship('User', foreign_keys=[default_approver_id])
    approver_role = db.relationship('Role', foreign_keys=[role_id])

class ApprovalRecord(db.Model):
    __tablename__ = 'approval_records'
    id = db.Column(db.Integer, primary_key=True)
    reference_type = db.Column(db.String(30), nullable=False) # inventory_plan / transfer / disposal
    reference_id = db.Column(db.Integer, nullable=False)
    step_order = db.Column(db.Integer, nullable=False)
    selected_approver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='pending') # pending / approved / rejected / skipped
    comment = db.Column(db.Text)
    reminded_count = db.Column(db.Integer, default=0)
    reminded_at = db.Column(db.DateTime)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_at = db.Column(db.DateTime)
    
    approver = db.relationship('User', foreign_keys=[selected_approver_id])
    actual_approver = db.relationship('User', foreign_keys=[approved_by])

    @property
    def submitter_name(self):
        """
        Dynamically resolve the name of the person who submitted this request.
        """
        from core.workflow_service import WorkflowService
        obj = WorkflowService.get_reference_object(self.reference_type, self.reference_id)
        if not obj: return "未知"

        if self.reference_type == 'inventory_task' and hasattr(obj, 'assignee'):
             return obj.assignee.display_name or obj.assignee.username if obj.assignee else "未知"
        elif self.reference_type == 'inventory_plan' and hasattr(obj, 'submitter'):
             return obj.submitter.display_name or obj.submitter.username if obj.submitter else "未知"
        elif self.reference_type == 'transfer' and hasattr(obj, 'applicant'):
             return obj.applicant.display_name or obj.applicant.username if obj.applicant else "未知"
        elif self.reference_type == 'personal_inventory':
            # personal inventory uses InventoryPlan model
             return obj.submitter.display_name or obj.submitter.username if obj.submitter else "未知"
             
        return "系統"
