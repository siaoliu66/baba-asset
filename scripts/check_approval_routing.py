from app import create_app
from core.models.inventory import InventoryTask
from core.models.workflow import WorkflowConfig, ApprovalStep
from core.models.system import User, Role
from core.models.organization import Department
from core.workflow_service import WorkflowService

app = create_app()

with app.app_context():
    # 1. Get the latest submitted task (status pending_review or just the latest one)
    task = InventoryTask.query.order_by(InventoryTask.id.desc()).first()
    
    if not task:
        print("No inventory tasks found.")
        exit()
        
    print(f"=== 診斷目標: 最新盤點任務 #{task.id} ===")
    print(f"任務狀態: {task.status}")
    
    assignee = task.assignee
    if not assignee:
        # Try to manual fetch if rel missing (should be fixed now)
        assignee = User.query.get(task.assignee_id)
        
    print(f"執行人員: {assignee.username if assignee else 'Unknown'} (ID: {task.assignee_id})")
    
    dept = None
    if assignee and assignee.personnel and assignee.personnel.department:
        dept = assignee.personnel.department
        
    print(f"所屬部門: {dept.name if dept else 'None'}")
    
    # 2. Determine Config
    print("\n[流程對應診斷]")
    config = WorkflowService.get_workflow_config('inventory_task', task)
    
    if not config:
        print("❌ 錯誤: 找不到對應的簽核流程設定 (No Config Found)")
    else:
        print(f"✅ 成功對應流程: 【{config.name}】")
        print(f"   - 流程類型: {config.workflow_type}")
        print(f"   - 適用範圍: {config.scope_type} (ID: {config.scope_id})")
        
        # 3. Resolve Steps
        print("\n[簽核路徑預覽]")
        steps = ApprovalStep.query.filter_by(config_id=config.id).order_by(ApprovalStep.step_order).all()
        
        for step in steps:
            print(f"👉 第 {step.step_order} 階: {step.step_name}")
            
            # Simulate logic
            approver_id = WorkflowService.resolve_approver(step, task, task.assignee_id)
            approver = User.query.get(approver_id)
            
            role_name = "Unknown Role"
            if step.role_id:
                r = Role.query.get(step.role_id)
                if r: role_name = r.name
                
            print(f"   - 設定規則: {step.approver_type} (Role: {role_name})")
            if approver:
                print(f"   - 實際簽核人: {approver.username} ({approver.email})")
                if approver.personnel and approver.personnel.department:
                    print(f"     (部門: {approver.personnel.department.name})")
            else:
                print("   - ❌ 無法找到對應人員 (將預設回退給 Admin)")
