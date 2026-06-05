from app import create_app
from extensions import db
from core.models.workflow import WorkflowConfig
from core.models.inventory import InventoryTask
from core.workflow_service import WorkflowService

app = create_app()

with app.app_context():
    # 1. Get the target task (User02 from Admin Dept)
    task = InventoryTask.query.filter_by(id=11).first() # Based on previous turn
    if not task:
        task = InventoryTask.query.order_by(InventoryTask.id.desc()).first()
        
    print(f"=== 測試目標任務 #{task.id} ===")
    dept_id = task.assignee.personnel.department_id
    print(f"部門 ID: {dept_id}")
    
    # 2. Check CURRENT config (Should be Company Default)
    print("\n[測試前: 尚未設定部門流程]")
    config_before = WorkflowService.get_workflow_config('inventory_task', task)
    print(f"當前對應: {config_before.name} (Scope: {config_before.scope_type})")
    
    # 3. INSERT Simulation Config
    print(f"\n[模擬: 新增部門 ID {dept_id} 的專屬流程...]")
    sim_config = WorkflowConfig(
        workflow_type='personal_inventory',
        scope_type='department',
        scope_id=dept_id,
        name='(模擬) 行政總務課專屬盤點流程',
        require_dept_approval=True,
        require_senior_approval=False, 
        is_active=True
    )
    db.session.add(sim_config)
    db.session.commit()
    
    try:
        # 4. Check NEW config (Should be Dept Specific)
        print("[測試後: 已設定部門流程]")
        config_after = WorkflowService.get_workflow_config('inventory_task', task)
        print(f"當前對應: {config_after.name} (Scope: {config_after.scope_type})")
        
        # 5. Validation
        if config_after.id == sim_config.id:
            print("\n✅ 驗證成功: 系統正確優先抓取了部門專屬設定！")
        else:
            print(f"\n❌ 驗證失敗: 系統仍然抓取 ID {config_after.id}")
            
    finally:
        # 6. Cleanup
        print("\n[清理環境: 移除模擬設定]")
        db.session.delete(sim_config)
        db.session.commit()
