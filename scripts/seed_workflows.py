from app import create_app
from extensions import db
from core.models.workflow import WorkflowConfig, ApprovalStep
from core.models.system import Role

def seed_workflows():
    app = create_app()
    with app.app_context():
        # 1. Define Configs
        configs_data = [
            {'type': 'personal_inventory', 'name': '個人盤點標準流程'},
            {'type': 'location_inventory', 'name': '地點盤點標準流程'},
            {'type': 'full_inventory', 'name': '全資產盤點標準流程'},
            {'type': 'transfer', 'name': '資產移轉標準流程'},
            {'type': 'disposal', 'name': '資產報廢標準流程'},
            {'type': 'inventory_task', 'name': '單項盤點任務流程'},
        ]

        # Get Role IDs (Assuming standard roles exist)
        dept_manager_role = Role.query.filter_by(name='department_manager').first()
        if not dept_manager_role:
             # Fallback or create if missing (though they should exist in a mature system)
             # Let's assume ID 2 is Manager, 3 is GM per typical setup, or just use names.
             pass

        gm_role = Role.query.filter_by(name='general_manager').first()

        for data in configs_data:
            # Check if exists
            existing = WorkflowConfig.query.filter_by(workflow_type=data['type']).first()
            if existing:
                print(f"Skipping {data['name']}, already exists.")
                continue

            config = WorkflowConfig(
                workflow_type=data['type'],
                scope_type='company',
                scope_id=1,
                name=data['name'],
                require_dept_approval=True,
                require_senior_approval=True,
                allow_self_select=False, # Per user request: no manual select during execution
                is_active=True
            )
            db.session.add(config)
            db.session.flush()

            # Step 1: Dept Manager
            step1 = ApprovalStep(
                config_id=config.id,
                step_order=1,
                step_name='部門經理審核',
                approver_type='role',
                role_id=dept_manager_role.id if dept_manager_role else 2, # Fallback to common ID
                reminder_days=3,
                escalation_days=7
            )
            db.session.add(step1)

            # Step 2: GM
            step2 = ApprovalStep(
                config_id=config.id,
                step_order=2,
                step_name='總經理裁決',
                approver_type='role',
                role_id=gm_role.id if gm_role else 3, # Fallback to common ID
                reminder_days=3,
                escalation_days=7
            )
            db.session.add(step2)
            
            print(f"Created config for {data['name']}")

        db.session.commit()
        print("Workflow seeding completed.")

if __name__ == '__main__':
    seed_workflows()
