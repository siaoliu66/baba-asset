from app import create_app
from extensions import db
from core.models.workflow import WorkflowConfig, ApprovalStep
from core.models.system import User, Role

def seed_workflow():
    app = create_app()
    with app.app_context():
        # Clear existing configs for testing
        WorkflowConfig.query.filter_by(workflow_type='personal_inventory').delete()
        WorkflowConfig.query.filter_by(workflow_type='location_inventory').delete()
        db.session.commit()

        # roles
        manager_role = Role.query.filter_by(name='dept_manager').first()
        vp_role = Role.query.filter_by(name='vice_president').first()
        gm_role = Role.query.filter_by(name='general_manager').first()
        
        # users
        manager_user = User.query.filter_by(username='manager').first()
        vp_user = User.query.filter_by(username='vp').first()
        gm_user = User.query.filter_by(username='gm').first()

        # 1. Personal Inventory Workflow: Manager -> VP -> GM
        config = WorkflowConfig(
            workflow_type='personal_inventory',
            scope_type='company',
            scope_id=1,
            name='個人盤點標準流程',
            is_active=True
        )
        db.session.add(config)
        db.session.flush()

        step1 = ApprovalStep(
            config_id=config.id,
            step_order=1,
            step_name='部門經理審核',
            approver_type='role',
            role_id=manager_role.id
        )
        step2 = ApprovalStep(
            config_id=config.id,
            step_order=2,
            step_name='副總經理核准',
            approver_type='role',
            role_id=vp_role.id
        )
        step3 = ApprovalStep(
            config_id=config.id,
            step_order=3,
            step_name='總經理裁決',
            approver_type='role',
            role_id=gm_role.id
        )
        db.session.add_all([step1, step2, step3])

        # 2. Add Proxy for VP (Optional for testing proxy logic)
        # Let's say Admin is the proxy for VP
        admin_user = User.query.filter_by(username='admin').first()
        if vp_user and admin_user:
            vp_user.proxy_user_id = admin_user.id
            print(f"Set Admin as proxy for VP ({vp_user.username})")

        db.session.commit()
        print("Test Workflow seeded: Manager -> VP (Proxy: Admin) -> GM")

if __name__ == '__main__':
    seed_workflow()
