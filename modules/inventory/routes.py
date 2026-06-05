from datetime import datetime, timedelta
import os
from werkzeug.utils import secure_filename
from flask import render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from core.models.inventory import InventoryPlan, InventoryTask, InventoryRecord, InventorySnapshot
from core.models.organization import Location , Personnel   
from core.models.assets import Asset
from core.models.system import User
from extensions import db
from . import inventory_bp

@inventory_bp.route('/plans')
@login_required
def plan_list():
    plans = InventoryPlan.query.all()
    return render_template('inventory/plan_list.html', plans=plans)

@inventory_bp.route('/plans/create', methods=['GET', 'POST'])
@login_required
def create_plan():
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d')
            end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d')
            plan_type = request.form.get('plan_type')
            location_ids = request.form.getlist('locations')
            assignee_ids = request.form.getlist('assignees')

            new_plan = InventoryPlan(
                name=name,
                plan_type=plan_type,
                start_date=start_date,
                end_date=end_date,
                target_location_ids=','.join(location_ids),
                submitted_by=current_user.id,
                status='draft'
            )
            db.session.add(new_plan)
            db.session.flush()

            # 找出資產
            query = Asset.query
            if location_ids and plan_type == 'location':
                query = query.filter(Asset.location_id.in_(location_ids))
            assets = query.all()

            # 建立任務
            if plan_type == 'personal':
                custodian_map = {}
                for asset in assets:
                    if not asset.custodian_id:
                        continue
                    custodian_map.setdefault(asset.custodian_id, []).append(asset)

                for cust_id, cust_assets in custodian_map.items():
                    person = Personnel.query.get(cust_id)
                    assignee_id = person.user.id if person and person.user else current_user.id
                    if person and person.user and person.user.proxy_user_id:
                        assignee_id = person.user.proxy_user_id

                    task = InventoryTask(
                        plan_id=new_plan.id,
                        location_id=cust_assets[0].location_id if cust_assets else None,
                        total_assets=len(cust_assets),
                        assignee_id=assignee_id,
                        status='pending'
                    )
                    db.session.add(task)
                    db.session.flush()

                    for asset in cust_assets:
                        _create_snapshot(task, asset)

            else:
                for loc_id in location_ids:
                    loc_assets = [a for a in assets if str(a.location_id) == str(loc_id)]
                    if not loc_assets:
                        continue

                    assignee_ids = request.form.getlist('assignees')
                    if assignee_ids:
                        for pid in assignee_ids:
                            task = InventoryTask(
                                plan_id=new_plan.id,
                                location_id=loc_id,
                                total_assets=len(loc_assets),
                                assignee_id=int(pid),  # 直接用 User.id
                                status='pending'
                            )
                            db.session.add(task)
                            db.session.flush()
                            for asset in loc_assets:
                                _create_snapshot(task, asset)
                    else:
                        location = Location.query.get(loc_id)
                        assignee_id = current_user.id
                        if location and location.manager and location.manager.user:
                            assignee_id = location.manager.user.id

                        task = InventoryTask(
                            plan_id=new_plan.id,
                            location_id=loc_id,
                            total_assets=len(loc_assets),
                            assignee_id=assignee_id,
                            status='pending'
                        )
                        db.session.add(task)
                        db.session.flush()

                        for asset in loc_assets:
                            _create_snapshot(task, asset)

            db.session.commit()
            flash('盤點計畫與快照已建立並分配盤點人員', 'success')
            return redirect(url_for('inventory.plan_list'))

        except Exception as e:
            db.session.rollback()
            flash(f'建立失敗: {str(e)}', 'danger')

    locations = Location.query.all()
    personnel = Personnel.query.all()
    return render_template('inventory/plan_form.html', locations=locations, personnel=personnel) 

def _create_snapshot(task, asset):
    snapshot = InventorySnapshot(
        task_id=task.id,
        asset_id=asset.id,
        asset_name=asset.name,
        asset_location=asset.location.name if asset.location else '未知',
        asset_custodian=asset.custodian.name if asset.custodian else '無',
        status='pending'
    )
    db.session.add(snapshot)

@inventory_bp.route('/tasks')
@login_required
def my_tasks():
    # 查詢自己的任務
    my_task_query = InventoryTask.query.filter(
        InventoryTask.assignee_id == current_user.id
    )

    # 查詢代理任務：找出「指定我為代理人」的主管，取得他們的任務
    proxy_principals = User.query.filter_by(proxy_user_id=current_user.id).all()
    proxy_tasks = []
    proxy_info = {}  # task_id -> principal_name
    for principal in proxy_principals:
        p_tasks = InventoryTask.query.join(InventoryPlan).filter(
            InventoryTask.assignee_id == principal.id,
            InventoryPlan.status.in_(['active', 'pending_dept', 'pending_review'])
        ).all()
        for t in p_tasks:
            proxy_info[t.id] = principal.display_name or principal.username
        proxy_tasks.extend(p_tasks)

    tasks = my_task_query.all() + proxy_tasks
    return render_template('inventory/task_list.html', tasks=tasks, proxy_info=proxy_info)

@inventory_bp.route('/asset/fetch/<asset_id>')
@login_required
def fetch_asset_info(asset_id):
    # Normalize ID (strip prefix)
    clean_id = asset_id.split(':')[-1] if ':' in asset_id else asset_id
    asset = Asset.query.get(clean_id)
    if not asset:
        return jsonify({'success': False, 'message': '找不到此資產編號'}), 404

    # 檢查是否為非盤點範圍資產 (Foreign Asset)
    task_id = request.args.get('task_id', type=int)
    is_foreign = False
    foreign_warning = None
    if task_id:
        task = InventoryTask.query.get(task_id)
        if task:
            # 檢查資產是否在任務清單中
            in_task = InventorySnapshot.query.filter_by(
                task_id=task_id, asset_id=clean_id
            ).first()
            if not in_task:
                # 不在清單中 —— 檢查保管人關係
                assignee = task.assignee
                owner_id = asset.custodian_id
                is_own = (assignee and assignee.personnel_id and owner_id == assignee.personnel_id)
                # 檢查代理關係
                is_proxy = False
                if not is_own and assignee:
                    proxy_principals = User.query.filter_by(proxy_user_id=assignee.id).all()
                    for p in proxy_principals:
                        if p.personnel_id == owner_id:
                            is_proxy = True
                            break
                if is_own or is_proxy:
                    is_foreign = False  # 可記為盤盈
                else:
                    is_foreign = True
                    custodian_name = (asset.custodian.display_name or asset.custodian.name) if asset.custodian else '未配發'
                    location_name = asset.location.name if asset.location else '未設定'
                    foreign_warning = f'非本任務範圍資產！保管人：{custodian_name}，位置：{location_name}'

    return jsonify({
        'success': True,
        'data': {
            'id': asset.id,
            'name': asset.name,
            'category': asset.category.name if asset.category else '-',
            'location': asset.location.name if asset.location else '-',
            'custodian': (asset.custodian.display_name or asset.custodian.name) if asset.custodian else '未配發',
            'status': asset.status
        },
        'is_foreign': is_foreign,
        'foreign_warning': foreign_warning
    })

@inventory_bp.route('/task/<int:task_id>/execute')
@login_required
def execute_task(task_id):
    task = InventoryTask.query.get_or_404(task_id)
    return render_template('inventory/execute.html', task=task)

@inventory_bp.route('/record/submit', methods=['POST'])
@login_required
def record_submit():
    task_id = request.form.get('task_id')
    raw_asset_id = request.form.get('asset_id')
    # Normalize ID (strip prefix)
    asset_id = raw_asset_id.split(':')[-1] if raw_asset_id and ':' in raw_asset_id else raw_asset_id
    
    result = request.form.get('result')
    lat = request.form.get('latitude')
    lng = request.form.get('longitude')
    
    task = InventoryTask.query.get_or_404(task_id)
    
    # Handle Photo Upload
    photo_file = request.files.get('photo')
    photo_path = None
    if photo_file:
        filename = secure_filename(f"task_{task_id}_{asset_id}_{datetime.now().strftime('%H%M%S')}.jpg")
        upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'inventory')
        os.makedirs(upload_dir, exist_ok=True)
        photo_file.save(os.path.join(upload_dir, filename))
        photo_path = f"uploads/inventory/{filename}"

    record = InventoryRecord(
        task_id=task.id,
        asset_id=asset_id,
        result=result,
        photo_path=photo_path,
        gps_lat=lat if lat else None,
        gps_lng=lng if lng else None,
        remarks=request.form.get('remarks')
    )
    db.session.add(record)
    
    # Update task progress
    task.scanned_count += 1
    if result != 'normal':
        task.abnormal_count += 1
        
    db.session.commit()
    return jsonify({
        "success": True, 
        "new_count": task.scanned_count,
        "new_abnormal": task.abnormal_count
    })

@inventory_bp.route('/task/<int:task_id>/submit', methods=['POST'])
@login_required
def submit_task(task_id):
    task = InventoryTask.query.get_or_404(task_id)
    if task.assignee_id != current_user.id:
         flash('您無權提交此任務', 'danger')
         return redirect(url_for('inventory.my_tasks'))
         
    if task.scanned_count < task.total_assets:
         flash('盤點尚未完成，無法送出簽核', 'warning')
         return redirect(url_for('inventory.my_tasks'))
         
    if task.status in ['completed', 'pending_review']:
         flash('此任務已結案或審核中', 'warning')
         return redirect(url_for('inventory.my_tasks'))

    # Trigger Workflow for this specific task
    from core.workflow_service import WorkflowService
    
    try:
        success, message = WorkflowService.start_workflow(
            reference_type='inventory_task', 
            reference_id=task.id,
            scope_type='company', # Or resolve by submitter's dept
            scope_id=1,
            submitter_id=current_user.id
        )
        
        if success:
            task.status = 'pending_review'
            db.session.commit()
            flash('盤點任務已送出簽核！請靜候主管審核。', 'success')
        else:
            flash(f'送出失敗: {message}', 'danger')
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Submit Task Error: {str(e)}")
        flash(f'系統發生未預期錯誤，請聯繫管理員。錯誤代碼: {str(e)}', 'danger')

    return redirect(url_for('inventory.my_tasks'))

@inventory_bp.route('/task/<int:task_id>/report')
@login_required
def view_report(task_id):
    task = InventoryTask.query.get_or_404(task_id)
    
    # Organize data for report
    report_items = []
    
    # Map records by asset_id (normalized for resilience)
    records_map = {}
    for r in task.records:
        clean_key = r.asset_id.split(':')[-1] if ':' in r.asset_id else r.asset_id
        records_map[clean_key.strip()] = r
    
    for snap in task.snapshots:
        # Snapshots should already be clean, but normalization here ensures match
        clean_snap_id = snap.asset_id.split(':')[-1] if ':' in snap.asset_id else snap.asset_id
        clean_snap_id = clean_snap_id.strip()
        item = {
            'asset_id': snap.asset_id,
            'name': snap.asset_name,
            'location': snap.asset_location,
            'custodian': snap.asset_custodian,
            'status': snap.status, # pending/scanned/missing
            'result': '尚未盤點',
            'result_class': 'secondary',
            'photo_url': None,
            'gps_link': None,
            'remarks': snap.remarks or ''
        }
        
        if clean_snap_id in records_map:
            rec = records_map[clean_snap_id]
            
            # Result Mapping
            if rec.result == 'normal':
                item['result'] = '正常'
                item['result_class'] = 'success'
            elif rec.result == 'damaged':
                item['result'] = '損壞'
                item['result_class'] = 'danger'
            elif rec.result == 'missing':
                item['result'] = '缺失'
                item['result_class'] = 'danger'
            elif rec.result == 'found':
                item['result'] = '盤盈'
                item['result_class'] = 'warning'
                
            item['photo_url'] = url_for('static', filename=rec.photo_path.replace('\\', '/')) if rec.photo_path else None
            if rec.remarks:
                item['remarks'] = rec.remarks
            
            if rec.gps_lat and rec.gps_lng:
                item['gps_link'] = f"https://www.google.com/maps/search/?api=1&query={rec.gps_lat},{rec.gps_lng}"
                
            # Mark record as matched
            rec.matched = True
                
        report_items.append(item)
    
    # Identify Extra Scans (Records not matched to any snapshot)
    extra_items = []
    for clean_id, rec in records_map.items():
        if not getattr(rec, 'matched', False):
            # Fetch asset info for this extra record
            asset = Asset.query.get(clean_id)
            extra_items.append({
                'asset_id': rec.asset_id,
                'name': asset.name if asset else '未知資產',
                'custodian': (asset.custodian.display_name or asset.custodian.name) if asset and asset.custodian else '未知',
                'result': '盤盈 (非計畫內)' if rec.result != 'normal' else '非清單內資產',
                'result_class': 'warning',
                'photo_url': url_for('static', filename=rec.photo_path.replace('\\', '/')) if rec.photo_path else None,
                'gps_link': f"https://www.google.com/maps/search/?api=1&query={rec.gps_lat},{rec.gps_lng}" if rec.gps_lat else None,
                'remarks': rec.remarks or '-'
            })
            
    # Fetch Approval History
    from core.models.workflow import ApprovalRecord
    approval_history = ApprovalRecord.query.filter_by(
        reference_type='inventory_task',
        reference_id=task.id
    ).order_by(ApprovalRecord.step_order.asc(), ApprovalRecord.id.asc()).all()
    
    # Determine completion date (latest record sync time)
    completion_date = None
    if task.records:
        latest_rec = max(task.records, key=lambda r: r.synced_at or datetime.min)
        completion_date = latest_rec.synced_at or datetime.now() 
    elif task.status == 'completed':
        # Fallback if records don't have synced_at (e.g. legacy data)
        completion_date = datetime.now() # Rough estimate if not tracked

    return render_template('inventory/report.html', 
                         task=task, 
                         report_items=report_items, 
                         extra_items=extra_items,
                         approval_history=approval_history,
                         completion_date=completion_date)

@inventory_bp.route('/plan/<int:plan_id>/close', methods=['POST'])
@login_required
def close_plan(plan_id):
    plan = InventoryPlan.query.get_or_404(plan_id)
    if plan.status in ['completed', 'pending_review']:
        flash('此計畫已結案或已在簽核中', 'warning')
        return redirect(url_for('inventory.plan_list'))

    # 直接走舊邏輯，不跑 Workflow
    return close_plan_logic_legacy(plan)

@inventory_bp.route('/plan/<int:plan_id>/start', methods=['POST'])
@login_required
def start_plan(plan_id):
    plan = InventoryPlan.query.get_or_404(plan_id)
    if plan.status != 'draft':
        flash('只有草稿狀態的計畫可以啟動', 'warning')
        return redirect(url_for('inventory.plan_list'))
    
    plan.status = 'active'
    db.session.commit()
    flash(f'盤點計畫 「{plan.name}」 已成功啟動！現在執行人員可以開始盤點。', 'success')
    return redirect(url_for('inventory.plan_list'))

@inventory_bp.route('/plan/<int:plan_id>/delete', methods=['POST'])
@login_required
def delete_plan(plan_id):
    plan = InventoryPlan.query.get_or_404(plan_id)
    
    # Check for Admin privileges (super_admin or admin)
    is_admin = current_user.role and current_user.role.name in ['super_admin', 'admin']
    
    if not is_admin and plan.status != 'draft':
        flash('只有草稿狀態的計畫可以刪除', 'warning')
        return redirect(url_for('inventory.plan_list'))
    
    try:
        # Cascade delete is configured in models (cascade='all, delete-orphan'),
        # so deleting the plan should remove tasks and snapshots.
        db.session.delete(plan)
        db.session.commit()
        flash(f'已刪除計畫：{plan.name}', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Delete Plan Error: {str(e)}")
        flash(f'刪除失敗: {str(e)}', 'danger')
        
    return redirect(url_for('inventory.plan_list'))

@inventory_bp.route('/plan/<int:plan_id>')
@login_required
def view_plan(plan_id):
    plan = InventoryPlan.query.get_or_404(plan_id)
    
    # Calculate Statistics
    stats = {
        'total_assets': 0,
        'scanned_assets': 0,
        'abnormal_assets': 0,
        'progress': 0
    }
    
    tasks_data = []
    
    for task in plan.tasks:
        stats['total_assets'] += task.total_assets
        stats['scanned_assets'] += task.scanned_count
        stats['abnormal_assets'] += task.abnormal_count
        
        # Prepare task info
        assignee_name = task.assignee.display_name if task.assignee else '未指派'
        location_name = task.location.name if task.location else '全區/個人'
        
        tasks_data.append({
            'id': task.id,
            'assignee': assignee_name,
            'location': location_name,
            'status': task.status,
            'scanned': task.scanned_count,
            'total': task.total_assets,
            'abnormal': task.abnormal_count,
            'progress': int((task.scanned_count / task.total_assets * 100) if task.total_assets > 0 else 0)
        })
        
    if stats['total_assets'] > 0:
        stats['progress'] = int((stats['scanned_assets'] / stats['total_assets']) * 100)
        
    return render_template('inventory/plan_detail.html', plan=plan, stats=stats, tasks=tasks_data)

def close_plan_logic_legacy(plan):
    # Modified: No longer auto-creates recheck plans.
    plan.status = 'completed'
    
    abnormal_count = 0
    recheck_needed = False
    
    for task in plan.tasks:
        records = {r.asset_id: r for r in task.records}
        for snapshot in task.snapshots:
            asset_id = snapshot.asset_id
            if asset_id not in records:
                snapshot.status = 'missing'
                abnormal_count += 1
                recheck_needed = True
            else:
                record = records[asset_id]
                if record.result != 'normal':
                    snapshot.status = record.result
                    abnormal_count += 1
                    recheck_needed = True
                else:
                    snapshot.status = 'scanned'
                    
    if plan.plan_type != 'recheck' and recheck_needed:
        flash(f'已結案。發現 {abnormal_count} 筆異常項目。請依據盤點結果手動建立複盤計畫。', 'warning')

    elif plan.plan_type == 'recheck':
        adjusted_count = 0
        for task in plan.tasks:
            for snap in task.snapshots:
                asset = Asset.query.get(snap.asset_id)
                if not asset: continue
                if snap.status == 'missing':
                    asset.status = 'lost'
                    adjusted_count += 1
                elif snap.status == 'damaged':
                    asset.status = 'maintenance'
                    adjusted_count += 1
                elif snap.status in ['scanned', 'normal'] and asset.status == 'lost':
                    asset.status = 'active'
                    adjusted_count += 1
        flash(f'複盤已結案。系統已自動更新 {adjusted_count} 筆資產狀態。', 'success')
    else:
        flash('已結案，盤點結果皆正常。', 'success')
        
    db.session.commit()
    return redirect(url_for('inventory.plan_list'))
