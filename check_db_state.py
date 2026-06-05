from app import create_app
from core.models.system import User, Role
from core.models.workflow import WorkflowConfig, ApprovalStep

app = create_app()

with app.app_context():
    print("--- USERS ---")
    users = User.query.all()
    for u in users:
        print(f"User: {u.username}, Role: {u.role.name if u.role else 'None'}, Proxy: {u.proxy_user_id}")

    print("\n--- WORKFLOW CONFIGS ---")
    configs = WorkflowConfig.query.all()
    for c in configs:
        print(f"Config: {c.name} (Type: {c.workflow_type})")
        steps = ApprovalStep.query.filter_by(config_id=c.id).order_by(ApprovalStep.step_order).all()
        for s in steps:
            print(f"  Step {s.step_order}: {s.step_name} (Type: {s.approver_type}, RoleID: {s.role_id})")
