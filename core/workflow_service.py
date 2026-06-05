from datetime import datetime
from extensions import db
from core.models.workflow import WorkflowConfig, ApprovalStep, ApprovalRecord
from core.models.system import Notification, AuditLog
from core.utils import SystemHelper

class WorkflowService:
    @staticmethod
    def resolve_approver(step, reference_obj=None, submitter_id=None):
        """
        Determine the actual approver based on step configuration and proxy settings.
        """
        from core.models.system import User
        target_user_id = None
        
        # 1. Determine Target
        if step.approver_type == 'specific_user':
            target_user_id = step.default_approver_id
            
        elif step.approver_type in ['role', 'department_manager']:
            # 策略：尋找具備該角色，且與 reference_obj 或是 submitter 部門相關的人員
            dept_id = None
            if reference_obj:
                if hasattr(reference_obj, 'department_id') and reference_obj.department_id:
                    dept_id = reference_obj.department_id
                elif hasattr(reference_obj, 'asset') and reference_obj.asset:
                    dept_id = reference_obj.asset.department_id
            
            if not dept_id and submitter_id:
                submitter = User.query.get(submitter_id)
                if submitter: dept_id = submitter.department_id

            # 優先找同部門的指定角色人員
            query = User.query.filter_by(role_id=step.role_id, is_active=True)
            if dept_id:
                user = query.filter_by(department_id=dept_id).first()
                if user: target_user_id = user.id
            
            # 如果找不到同部門，則找全公司第一個具備該角色的人員
            if not target_user_id:
                user = query.first()
                if user: target_user_id = user.id
            
        if not target_user_id:
            # Fallback to Admin (ID 1) if resolution failed
            return 1 

        # 2. Check Proxy
        target_user = User.query.get(target_user_id)
        if target_user and target_user.proxy_user_id:
            return target_user.proxy_user_id
            
        return target_user_id

    @staticmethod
    def get_workflow_config(reference_type, ref_obj=None):
        """
        Resolve the correct WorkflowConfig with Scope Priority:
        1. Department Specific Config (if applicable context exists)
        2. Company Default Config
        """
        target_type = reference_type
        
        # 1. Map Inventory Task to standard workflow types
        if reference_type == 'inventory_task' and ref_obj:
            if hasattr(ref_obj, 'plan') and ref_obj.plan:
                plan_type_map = {
                    'personal': 'personal_inventory',
                    'location': 'location_inventory', 
                    'full': 'full_inventory'
                }
                target_type = plan_type_map.get(ref_obj.plan.plan_type, target_type)

        # 2. Determine Context (Department & Location)
        dept_id = None
        location_id = None
        
        # Case A: Inventory Task
        if reference_type == 'inventory_task' and ref_obj:
            # Department Context (for Personal Inventory)
            if ref_obj.assignee and ref_obj.assignee.personnel and ref_obj.assignee.personnel.department_id:
                dept_id = ref_obj.assignee.personnel.department_id
            # Location Context (for Location Inventory)
            if ref_obj.location_id:
                location_id = ref_obj.location_id
                
        # Case B: Transfer
        elif reference_type == 'transfer' and ref_obj:
            dept_id = ref_obj.from_department_id
            if ref_obj.to_location_id:
                location_id = ref_obj.to_location_id
            
        # Case C: Disposal
        elif reference_type == 'disposal' and ref_obj:
            if ref_obj.asset:
                if ref_obj.asset.department_id: dept_id = ref_obj.asset.department_id
                if ref_obj.asset.location_id: location_id = ref_obj.asset.location_id

        # 3. Lookup Strategy
        
        # Priority 1: Location Specific (if applicable context exists)
        if location_id:
            loc_config = WorkflowConfig.query.filter_by(
                workflow_type=target_type,
                scope_type='location',
                scope_id=location_id,
                is_active=True
            ).first()
            if loc_config:
                return loc_config

        # Priority 2: Department Specific
        if dept_id:
            dept_config = WorkflowConfig.query.filter_by(
                workflow_type=target_type,
                scope_type='department',
                scope_id=dept_id,
                is_active=True
            ).first()
            if dept_config:
                return dept_config

        # Priority 3: Company Default
        return WorkflowConfig.query.filter_by(
            workflow_type=target_type,
            scope_type='company',
            is_active=True
        ).first()

    @staticmethod
    def start_workflow(reference_type, reference_id, scope_type='company', scope_id=1, submitter_id=None):
        """
        Initiate a workflow.
        """
        # 1. Get Reference Object (Needed for Config Lookup now)
        ref_obj = WorkflowService.get_reference_object(reference_type, reference_id)
        
        # 2. Find Config (Using smart lookup)
        config = WorkflowService.get_workflow_config(reference_type, ref_obj)
        
        if not config or not config.steps:
            return False, f"No workflow configuration found for {reference_type}"

        # 2.5 Check for duplicate active workflow
        existing_pending = ApprovalRecord.query.filter_by(
            reference_type=reference_type,
            reference_id=reference_id,
            status='pending'
        ).first()
        if existing_pending:
            return True, "Workflow already in progress"
            
        # 3. Get First Step
        sorted_steps = sorted(config.steps, key=lambda x: x.step_order)
        first_step = sorted_steps[0]
        
        # 4. Resolve Approver
        approver_id = WorkflowService.resolve_approver(first_step, ref_obj, submitter_id)
        
        # 4. Create Record
        record = ApprovalRecord(
            reference_type=reference_type,
            reference_id=reference_id,
            step_order=first_step.step_order,
            selected_approver_id=approver_id,
            status='pending'
        )
        db.session.add(record)
        db.session.commit()
        
        # 5. Notify
        SystemHelper.send_notification(
            user_id=approver_id,
            n_type='APPROVAL',
            title=f"待簽核: {config.name}",
            content=f"您有一項 {reference_type} (#{reference_id}) 需要簽核",
            link=f"/workflows/pending"
        )
        
        return True, "Workflow initiated"

    @staticmethod
    def process_step(record_id, status, comment, user_id):
        """
        Handle Approve/Reject.
        """
        record = ApprovalRecord.query.get(record_id)
        if not record: return False, "Record not found"
        
        record.status = status
        record.comment = comment
        record.approved_by = user_id
        record.approved_at = datetime.utcnow()
        
        # Find Config via Helper
        ref_obj = WorkflowService.get_reference_object(record.reference_type, record.reference_id)
        config = WorkflowService.get_workflow_config(record.reference_type, ref_obj)
        
        if status == 'approved':
            # Check for Next Step
            if config:
                next_step = ApprovalStep.query.filter_by(
                    config_id=config.id, 
                    step_order=record.step_order + 1
                ).first()
                
                if next_step:
                    # Create Next Record
                    approver_id = WorkflowService.resolve_approver(next_step, ref_obj)
                    new_record = ApprovalRecord(
                        reference_type=record.reference_type,
                        reference_id=record.reference_id,
                        step_order=next_step.step_order,
                        selected_approver_id=approver_id,
                        status='pending'
                    )
                    db.session.add(new_record)
                    
                    # Notify
                    SystemHelper.send_notification(
                        user_id=approver_id,
                        n_type='APPROVAL',
                        title=f"待簽核 ({next_step.step_name})",
                        content=f"上一階已通過，輪到您進行 {next_step.step_name} ({record.reference_type} #{record.reference_id})",
                        link=f"/workflows/pending"
                    )
                else:
                    # Final Complete
                    WorkflowService.finalize_workflow(record)
            else:
                WorkflowService.finalize_workflow(record)

        elif status == 'rejected':
            # Reset Plan/Request Status
            WorkflowService.handle_rejection(record)
            
        db.session.commit()
        return True, "Step processed"

    @staticmethod
    def finalize_workflow(record):
        """
        當最後一階簽核通過時，執行對應模組的自動化結案連動。
        """
        if record.reference_type in ['inventory_plan', 'personal_inventory', 'location_inventory', 'full_inventory']:
            from core.models.inventory import InventoryPlan
            plan = InventoryPlan.query.get(record.reference_id)
            if plan:
                plan.status = 'completed'
                
                # SYNC ASSET STATUS: Auto-update asset status based on inventory results
                # This logic replaces the old "Recheck" auto-generation.
                # When GM approves (Finalize), the inventory results are considered FINAL.
                from core.models.assets import Asset
                
                updated_count = 0
                for task in plan.tasks:
                    # Map records for quick lookup
                    records_map = {r.asset_id: r for r in task.records}
                    
                    for snap in task.snapshots:
                        asset = Asset.query.get(snap.asset_id)
                        if not asset: continue
                        
                        # Determine final status for this asset from this plan
                        final_result = 'normal' # Default
                        
                        # Check if scanned
                        clean_id = snap.asset_id.split(':')[-1] if ':' in snap.asset_id else snap.asset_id
                        if clean_id in records_map:
                            rec = records_map[clean_id]
                            final_result = rec.result
                        else:
                            # Not scanned = Missing
                            final_result = 'missing'
                            
                        # Apply to Asset
                        if final_result == 'missing':
                            if asset.status != 'lost':
                                old_status = asset.status
                                asset.status = 'lost'
                                updated_count += 1
                                # Audit
                                db.session.add(AuditLog(
                                    user_id=record.approved_by,
                                    module='assets',
                                    action='UPDATE',
                                    reference_id=asset.id,
                                    description=f'Inventory Plan #{plan.id} result: Missing',
                                    old_value={'status': old_status},
                                    new_value={'status': 'lost'}
                                ))
                        elif final_result == 'damaged':
                            if asset.status != 'maintenance':
                                old_status = asset.status
                                asset.status = 'maintenance'
                                updated_count += 1
                                # Audit
                                db.session.add(AuditLog(
                                    user_id=record.approved_by,
                                    module='assets',
                                    action='UPDATE',
                                    reference_id=asset.id,
                                    description=f'Inventory Plan #{plan.id} result: Damaged',
                                    old_value={'status': old_status},
                                    new_value={'status': 'maintenance'}
                                ))
                        elif final_result in ['normal', 'found']:
                            # If asset was previously lost/maintenance, restore it
                            if asset.status in ['lost', 'maintenance']:
                                old_status = asset.status
                                asset.status = 'active'
                                updated_count += 1
                                # Audit
                                db.session.add(AuditLog(
                                    user_id=record.approved_by,
                                    module='assets',
                                    action='UPDATE',
                                    reference_id=asset.id,
                                    description=f'Inventory Plan #{plan.id} result: Found/Normal',
                                    old_value={'status': old_status},
                                    new_value={'status': 'active'}
                                ))
                                
                print(f"Plan {plan.id} finalized. synced {updated_count} assets.")
                # 此處未來可增加：寄送結果報表等
                
        elif record.reference_type == 'inventory_task':
            from core.models.inventory import InventoryTask
            task = InventoryTask.query.get(record.reference_id)
            if task:
                task.status = 'completed'
                # Check if all tasks in plan are completed
                plan = task.plan
                if plan and all(t.status == 'completed' for t in plan.tasks):
                    plan.status = 'completed'
                    # Future: Auto recheck generation hook here
                
        elif record.reference_type == 'transfer':
            from core.models.lifecycle import AssetTransfer
            from core.models.assets import Asset
            transfer = AssetTransfer.query.get(record.reference_id)
            if transfer:
                asset = Asset.query.get(transfer.asset_id)
                if asset:
                    # 自動變動資產位置與保管資訊 (對齊申請單)
                    if transfer.to_department_id: asset.department_id = transfer.to_department_id
                    if transfer.to_location_id: asset.location_id = transfer.to_location_id
                    if transfer.to_custodian_id: asset.custodian_id = transfer.to_custodian_id
                    asset.status = 'active'
                    
                    # Audit
                    db.session.add(AuditLog(
                        user_id=record.approved_by,
                        module='assets',
                        action='TRANSFER',
                        reference_id=asset.id,
                        description=f'Transfer completed via Workflow #{record.id}',
                        old_value={}, 
                        new_value={
                            'department_id': transfer.to_department_id,
                            'location_id': transfer.to_location_id,
                            'custodian_id': transfer.to_custodian_id
                        }
                    ))
                transfer.status = 'completed'
                
        elif record.reference_type == 'disposal':
            from core.models.lifecycle import AssetDisposal
            from core.models.assets import Asset
            disposal = AssetDisposal.query.get(record.reference_id)
            if disposal:
                asset = Asset.query.get(disposal.asset_id)
                if asset:
                    asset.status = 'disposed' # 標記為已報廢
                    
                    # Audit
                    db.session.add(AuditLog(
                        user_id=record.approved_by,
                        module='assets',
                        action='DISPOSAL',
                        reference_id=asset.id,
                        description=f'Disposal completed via Workflow #{record.id}',
                        old_value={'status': 'active'}, # Assumption
                        new_value={'status': 'disposed', 'reason': disposal.reason}
                    ))
                disposal.status = 'completed'

    @staticmethod
    def handle_rejection(record):
        """
        當簽核被駁回時的清理與通知邏輯。
        """
        if record.reference_type in ['inventory_plan', 'personal_inventory', 'location_inventory', 'full_inventory']:
             from core.models.inventory import InventoryPlan
             plan = InventoryPlan.query.get(record.reference_id)
             if plan:
                 plan.status = 'active' # 重開，讓人員可以重新提交
                 SystemHelper.send_notification(
                    user_id=plan.submitted_by or 1,
                    n_type='ALERT',
                    title="盤點簽核被駁回",
                    content=f"計畫 {plan.name} 已被駁回，請修正後重新提交。",
                    link=f"/inventory/plans"
                 )
        elif record.reference_type == 'inventory_task':
             from core.models.inventory import InventoryTask
             task = InventoryTask.query.get(record.reference_id)
             if task:
                 task.status = 'in_progress'
                 SystemHelper.send_notification(
                    user_id=task.assignee_id,
                    n_type='ALERT',
                    title="盤點任務被駁回",
                    content=f"您的盤點任務 #{task.id} 已被駁回，請修正後重新提交。",
                    link=f"/inventory/tasks"
                 )
        elif record.reference_type == 'transfer':
            from core.models.lifecycle import AssetTransfer
            transfer = AssetTransfer.query.get(record.reference_id)
            if transfer:
                transfer.status = 'rejected'
        elif record.reference_type == 'disposal':
            from core.models.lifecycle import AssetDisposal
            disposal = AssetDisposal.query.get(record.reference_id)
            if disposal:
                disposal.status = 'rejected'

    @staticmethod
    def get_reference_object(reference_type, reference_id):
        """
        Helper: 根據類型與 ID 取得對象模型實例。
        """
        if reference_type in ['inventory_plan', 'personal_inventory', 'location_inventory', 'full_inventory']:
            from core.models.inventory import InventoryPlan
            return InventoryPlan.query.get(reference_id)
        elif reference_type == 'inventory_task':
            from core.models.inventory import InventoryTask
            return InventoryTask.query.get(reference_id)
        elif reference_type == 'transfer':
            from core.models.lifecycle import AssetTransfer
            return AssetTransfer.query.get(reference_id)
        elif reference_type == 'disposal':
            from core.models.lifecycle import AssetDisposal
            return AssetDisposal.query.get(reference_id)
        return None
