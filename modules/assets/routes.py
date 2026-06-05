import os
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import render_template, redirect, url_for, flash, request, jsonify, current_app,Blueprint, send_file
from flask_login import login_required, current_user
from core.models.system import User, AuditLog
from core.models.assets import Asset, AssetCategory
from core.models.organization import Location, Company, Department, Personnel
from core.models.lifecycle import AssetTransfer, AssetRepair, AssetDisposal
from core.workflow_service import WorkflowService
from core.qr_service import QRHelper
from extensions import db
from io import BytesIO
import qrcode
import zipfile
import pandas as pd

assets_bp = Blueprint('assets', __name__)

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@assets_bp.route('/')
@login_required
def index():
    # --- Search / Filter ---
    q = request.args.get('q', '').strip()
    category_id = request.args.get('category', type=int)
    location_id = request.args.get('location', type=int)
    status = request.args.get('status', '').strip()

    query = Asset.query

    if q:
        like_q = f'%{q}%'
        query = query.outerjoin(Personnel, Asset.custodian_id == Personnel.id).filter(
            db.or_(
                Asset.id.ilike(like_q),
                Asset.name.ilike(like_q),
                Personnel.name.ilike(like_q),
                Personnel.display_name.ilike(like_q),
            )
        )
    if category_id:
        query = query.filter(Asset.category_id == category_id)
    if location_id:
        query = query.filter(Asset.location_id == location_id)
    if status:
        query = query.filter(Asset.status == status)

    assets = query.order_by(Asset.id).all()

    # Pass filter options for dropdowns
    categories = AssetCategory.query.order_by(AssetCategory.name).all()
    locations = Location.query.order_by(Location.name).all()

    return render_template('assets/index.html',
        assets=assets, categories=categories, locations=locations,
        q=q, sel_category=category_id, sel_location=location_id, sel_status=status
    )

@assets_bp.route('/my')
@login_required
def my_assets():
    """行動版「我的資產」— 僅顯示當前使用者保管的資產"""
    if current_user.personnel_id:
        assets = Asset.query.filter_by(custodian_id=current_user.personnel_id).order_by(Asset.id).all()
    else:
        assets = []
    return render_template('assets/my_assets.html', assets=assets)

STATUS_MAP = {
    "使用中": "active",
    "在庫": "in_stock",
    "維修中": "maintenance",
    "報廢": "disposed",
    "遺失": "lost"
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ['jpg', 'jpeg', 'png']

def get_fk_id(model, name_field, value, auto_create=False):
    """用文字名稱查詢外鍵表，回傳 id；只有 auto_create=True 時才自動新增"""
    if not value:
        return None
    obj = model.query.filter_by(**{name_field: value}).first()
    if not obj and auto_create:
        if model.__tablename__ == "asset_categories":
            # 自動產生 code，例如用名稱或 UUID
            import uuid
            code_value = f"C-{uuid.uuid4().hex[:6]}"  # 例如 C-abc123
            obj = model(code=code_value, **{name_field: value})
        else:
            obj = model(**{name_field: value})
        db.session.add(obj)
        db.session.flush()
    return obj.id if obj else None

@login_required
@assets_bp.route('/create', methods=['GET', 'POST'])
def create():
    if request.method == 'POST':
        try:
            asset_id = request.form.get('asset_id')
            name = request.form.get('name')

            # 處理照片上傳
            photo_path = None
            photo_file = request.files.get('photo')
            if photo_file and photo_file.filename and allowed_file(photo_file.filename):
                ext = photo_file.filename.rsplit('.', 1)[1].lower()
                filename = secure_filename(f"{asset_id}.{ext}")
                upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'assets')
                os.makedirs(upload_dir, exist_ok=True)
                photo_file.save(os.path.join(upload_dir, filename))
                photo_path = f"uploads/assets/{filename}"

            new_asset = Asset(
                id=asset_id,
                name=name,
                category_id=get_fk_id(AssetCategory, 'name', request.form.get('category_name'), auto_create=True),  # 分類找不到就新增
                location_id=get_fk_id(Location, 'name', request.form.get('location_name')),  # 只查詢
                custodian_id=get_fk_id(Personnel, 'name', request.form.get('custodian_name')),
                department_id=get_fk_id(Department, 'name', request.form.get('department_name')),
                company_id=get_fk_id(Company, 'name', request.form.get('company_name')),
                brand=request.form.get('brand'),
                model=request.form.get('model'),
                serial_number=request.form.get('serial_number'),
                notes=request.form.get('notes'),
                photo_path=photo_path,
                status='active',

                # 財務資訊
                purchase_date=datetime.strptime(request.form.get('purchase_date'), '%Y-%m-%d').date() if request.form.get('purchase_date') else None,
                purchase_price=request.form.get('purchase_price') or 0,
                useful_life_years=request.form.get('useful_life_years') or 0,
                salvage_value=request.form.get('salvage_value') or 0,
                depreciation_method=request.form.get('depreciation_method', 'straight_line'),
                current_value=request.form.get('purchase_price') or 0
            )
            db.session.add(new_asset)
            db.session.flush()

            # 產生 QR Code
            qr_path = QRHelper.generate_asset_qr(asset_id)
            if qr_path:
                new_asset.qr_code_path = qr_path

            db.session.commit()
            flash('資產建立成功', 'success')
            return redirect(url_for('assets.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'建立失敗: {str(e)}', 'danger')

    categories = AssetCategory.query.all()
    locations = Location.query.all()
    companies = Company.query.all()
    personnel = Personnel.query.all()
    departments = Department.query.all()
    return render_template('assets/form.html',
                           categories=categories,
                           locations=locations,
                           companies=companies,
                           personnel=personnel,
                           departments=departments)
                           

@assets_bp.route('/<string:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    asset = Asset.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            # Capture old state for audit
            old_state = {
                'name': asset.name,
                'category_id': asset.category_id,
                'location_id': asset.location_id,
                'custodian_id': asset.custodian_id,
                'department_id': asset.department_id,
                'company_id': asset.company_id,
                'brand': asset.brand,
                'model': asset.model,
                'serial_number': asset.serial_number,
                'status': asset.status,
                'photo_path': asset.photo_path,
                'purchase_price': asset.purchase_price,
                'notes': asset.notes
            }

            # Update basic fields
            asset.name = request.form.get('name')
            asset.category_id = request.form.get('category_id') or None
            asset.location_id = request.form.get('location_id') or None
            asset.custodian_id = request.form.get('custodian_id') or None
            asset.department_id = request.form.get('department_id') or None
            asset.company_id = request.form.get('company_id') or None
            asset.brand = request.form.get('brand')
            asset.model = request.form.get('model')
            asset.serial_number = request.form.get('serial_number')
            asset.notes = request.form.get('notes')
            asset.status = request.form.get('status', 'active')

            # Financial Info
            asset.purchase_date = datetime.strptime(request.form.get('purchase_date'), '%Y-%m-%d').date() if request.form.get('purchase_date') else None
            asset.purchase_price = request.form.get('purchase_price') or 0
            asset.useful_life_years = request.form.get('useful_life_years') or 0
            asset.salvage_value = request.form.get('salvage_value') or 0
            asset.depreciation_method = request.form.get('depreciation_method', 'straight_line')
            
            # Update current value to purchase price if new (simplified logic for now)
            # Todo: Recalculate if needed

            
            # Handle Photo Upload
            photo_file = request.files.get('photo')
            if photo_file and photo_file.filename and allowed_file(photo_file.filename):
                ext = photo_file.filename.rsplit('.', 1)[1].lower()
                filename = secure_filename(f"{asset.id}.{ext}")
                upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'assets')
                os.makedirs(upload_dir, exist_ok=True)
                photo_file.save(os.path.join(upload_dir, filename))
                asset.photo_path = f"uploads/assets/{filename}"
            
            # Regenerate QR Code if missing
            if not asset.qr_code_path:
                qr_path = QRHelper.generate_asset_qr(asset.id)
                if qr_path:
                    asset.qr_code_path = qr_path
            
            # Audit Log Logic
            changes = {}
            for key, old_val in old_state.items():
                new_val = getattr(asset, key)
                if old_val != new_val:
                    changes[key] = {'old': old_val, 'new': new_val}
            
            if changes:
                log = AuditLog(
                    user_id=current_user.id,
                    module='assets',
                    action='UPDATE',
                    reference_id=asset.id,
                    description=f'Updated asset {asset.id}',
                    old_value={k: str(v['old']) for k, v in changes.items()},
                    new_value={k: str(v['new']) for k, v in changes.items()}
                )
                db.session.add(log)

            db.session.commit()
            flash('資產更新成功', 'success')
            return redirect(url_for('assets.detail', id=asset.id))
        except Exception as e:
            db.session.rollback()
            flash(f'更新失敗: {str(e)}', 'danger')
    
    categories = AssetCategory.query.all()
    locations = Location.query.all()
    companies = Company.query.all()
    personnel = Personnel.query.all()
    departments = Department.query.all()
    return render_template('assets/edit.html', 
                           asset=asset,
                           categories=categories, 
                           locations=locations, 
                           companies=companies,
                           personnel=personnel,
                           departments=departments)

# 匯入資產
@assets_bp.route('/import', methods=['POST'])
def import_assets():
    file = request.files.get('file')
    if not file:
        flash("請選擇檔案", "danger")
        return redirect(url_for('assets.index'))

    if file.filename.endswith('.xlsx'):
        df = pd.read_excel(file)
    else:
        df = pd.read_csv(file)

    for _, row in df.iterrows():
        asset_id = str(row['資產編號']).strip()

        existing = Asset.query.get(asset_id)
        if existing:
            asset = existing
        else:
            asset = Asset(id=asset_id)
            db.session.add(asset)

        # 外鍵處理：只有分類會自動新增
        asset.name = row.get('名稱')
        asset.category_id = get_fk_id(AssetCategory, 'name', row.get('分類'), auto_create=True)
        asset.location_id = get_fk_id(Location, 'name', row.get('存放地點'))
        asset.custodian_id = get_fk_id(Personnel, 'name', row.get('保管人'))
        asset.department_id = get_fk_id(Department, 'name', row.get('歸屬部門'))
        asset.company_id = get_fk_id(Company, 'name', row.get('所屬公司'))
        asset.brand = row.get('品牌')
        asset.model = row.get('型號')
        asset.serial_number = row.get('序號')
        asset.notes = row.get('備註')
        asset.status = STATUS_MAP.get(row.get('狀態'), 'active')

        # 財務資訊
        if row.get('購買日期'):
            asset.purchase_date = datetime.strptime(str(row['購買日期']), '%Y-%m-%d').date()
        asset.purchase_price = row.get('購買金額') or 0
        asset.useful_life_years = row.get('耐用年限') or 0
        asset.salvage_value = row.get('殘值') or 0
        asset.depreciation_method = row.get('折舊方法') or 'straight_line'
        asset.current_value = row.get('購買金額') or 0

        # 產生 QR Code
        qr_path = QRHelper.generate_asset_qr(asset_id)
        if qr_path:
            asset.qr_code_path = qr_path

    try:
        db.session.commit()
        flash("匯入完成", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"匯入失敗: {e}", "danger")

    return redirect(url_for('assets.index'))

# 匯出資產 Excel
@assets_bp.route('/export', methods=['GET'], endpoint='export')
@login_required
def export_assets():

    status_map = {
        'active': '使用中',
        'in_stock': '在庫',
        'maintenance': '維修中',
        'disposed': '報廢',
        'lost': '遺失'
    }

    # 讀取清單頁的 query string
    q = request.args.get('q')
    category = request.args.get('category')
    location = request.args.get('location')
    status = request.args.get('status')

    query = Asset.query

    if q:
        query = query.filter(Asset.name.like(f"%{q}%"))
    if category:
        query = query.filter(Asset.category_id == category)
    if location:
        query = query.filter(Asset.location_id == location)
    if status:
        query = query.filter(Asset.status == status)

    assets = query.all()

    # 組成 DataFrame
    data = []
    for a in assets:
        data.append({
            '資產編號': a.id,
            '名稱': a.name,
            '分類': a.category.name if a.category else '',
            '品牌': a.brand,
            '型號': a.model,
            '序號': a.serial_number,
            '所屬公司': a.company.name if a.company else '',
            '歸屬部門': a.department.name if a.department else '',
            '保管人': a.custodian.name if a.custodian else '',
            '存放地點': a.location.name if a.location else '',
            '狀態': status_map.get(a.status, a.status),
            '購買日期': a.purchase_date.strftime('%Y-%m-%d') if a.purchase_date else '',
            '備註': a.notes
        })

    df = pd.DataFrame(data)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Assets')

    output.seek(0)
    return send_file(output,
                     as_attachment=True,
                     download_name="assets_export.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@assets_bp.route('/<string:id>')
@login_required
def detail(id):
    asset = Asset.query.get_or_404(id)
    # Fetch lifecycle history
    transfers = AssetTransfer.query.filter_by(asset_id=asset.id).order_by(AssetTransfer.created_at.desc()).all()
    repairs = AssetRepair.query.filter_by(asset_id=asset.id).order_by(AssetRepair.created_at.desc()).all()
    disposals = AssetDisposal.query.filter_by(asset_id=asset.id).order_by(AssetDisposal.created_at.desc()).all()
    audits = AuditLog.query.filter_by(module='assets', reference_id=asset.id).order_by(AuditLog.created_at.desc()).all()
    
    # Combined sorted timeline
    history = []
    for t in transfers: history.append({'type': 'transfer', 'date': t.created_at, 'data': t})
    for r in repairs: history.append({'type': 'repair', 'date': r.created_at, 'data': r})
    for d in disposals: history.append({'type': 'disposal', 'date': d.created_at, 'data': d})
    for a in audits: history.append({'type': 'audit', 'date': a.created_at, 'data': a})
    history.sort(key=lambda x: x['date'] if x['date'] else datetime.min, reverse=True)
    
    return render_template('assets/detail.html', asset=asset, history=history)

@assets_bp.route('/<string:id>/label')
@login_required
def print_label(id):
    asset = Asset.query.get_or_404(id)
    return render_template('assets/label.html', asset=asset)

@assets_bp.route('/<string:asset_id>/transfer', methods=['POST'])
@login_required
def request_transfer(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    target_dept_id = request.form.get('target_dept')
    reason = request.form.get('reason')
    
    # Create Transfer Record
    transfer = AssetTransfer(
        asset_id=asset.id,
        from_department_id=asset.department_id,
        to_department_id=target_dept_id,
        from_custodian_id=asset.custodian_id,
        reason=reason,
        status='pending'
    )
    db.session.add(transfer)
    db.session.commit()
    
    # Trigger Workflow
    success, msg = WorkflowService.start_workflow(
        reference_type='transfer', 
        reference_id=transfer.id,
        submitter_id=current_user.id
    )
    if success:
        flash('移轉申請已送出，已進入兩階簽核流程。', 'info')
    else:
        flash(f'申請已建立但流程啟動失敗: {msg}', 'warning')
        
    return redirect(url_for('assets.detail', id=asset.id))

@assets_bp.route('/<string:asset_id>/repair', methods=['POST'])
@login_required
def log_repair(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    repair = AssetRepair(
        asset_id=asset.id,
        issue_description=request.form.get('description'),
        vendor=request.form.get('vendor'),
        repair_cost=request.form.get('cost'),
        status='completed' # Or repairing
    )
    # Update asset status
    asset.status = 'maintenance'
    db.session.add(repair)
    db.session.commit()
    flash('維修紀錄已登記', 'success')
    return redirect(url_for('assets.detail', id=asset.id))

@assets_bp.route('/<string:asset_id>/disposal', methods=['POST'])
@login_required
def request_disposal(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    disposal = AssetDisposal(
        asset_id=asset.id,
        reason=request.form.get('reason'),
        disposal_type=request.form.get('type'),
        status='pending'
    )
    db.session.add(disposal)
    db.session.commit()
    
    # Trigger Workflow
    success, msg = WorkflowService.start_workflow(
        reference_type='disposal', 
        reference_id=disposal.id,
        submitter_id=current_user.id
    )
    if success:
        flash('報廢申請已送出，進入簽核流程。', 'warning')
    else:
        flash(f'申請已建立但流程啟動失敗: {msg}', 'danger')
        
    return redirect(url_for('assets.detail', id=asset.id))

@assets_bp.route('/transfers')
@login_required
def transfer_list():
    transfers = AssetTransfer.query.order_by(AssetTransfer.created_at.desc()).all()
    return render_template('assets/transfer_list.html', transfers=transfers)

@assets_bp.route('/disposals')
@login_required
def disposal_list():
    disposals = AssetDisposal.query.order_by(AssetDisposal.created_at.desc()).all()
    return render_template('assets/disposal_list.html', disposals=disposals)

# ==================== Transfer Edit/Delete ====================
@assets_bp.route('/transfers/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def transfer_edit(id):
    transfer = AssetTransfer.query.get_or_404(id)
    # Only allow editing if status is pending
    if transfer.status != 'pending':
        flash('只能編輯「待審核」狀態的移轉申請', 'warning')
        return redirect(url_for('assets.transfer_list'))
    
    if request.method == 'POST':
        try:
            transfer.reason = request.form.get('reason')
            transfer.to_custodian_id = request.form.get('to_custodian_id') or None
            transfer.to_location_id = request.form.get('to_location_id') or None
            transfer.to_department_id = request.form.get('to_department_id') or None
            db.session.commit()
            flash('移轉申請已更新', 'success')
            return redirect(url_for('assets.transfer_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新失敗: {str(e)}', 'danger')
    
    from core.models.organization import Personnel, Location, Department
    personnel = Personnel.query.filter_by(is_active=True).all()
    locations = Location.query.all()
    departments = Department.query.all()
    return render_template('assets/transfer_form.html', transfer=transfer, personnel=personnel, locations=locations, departments=departments)

@assets_bp.route('/transfers/<int:id>/delete', methods=['POST'])
@login_required
def transfer_delete(id):
    transfer = AssetTransfer.query.get_or_404(id)
    if transfer.status != 'pending':
        flash('只能刪除「待審核」狀態的移轉申請', 'warning')
        return redirect(url_for('assets.transfer_list'))
    
    try:
        db.session.delete(transfer)
        db.session.commit()
        flash('移轉申請已刪除', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'刪除失敗: {str(e)}', 'danger')
    return redirect(url_for('assets.transfer_list'))

# ==================== Disposal Edit/Delete ====================
@assets_bp.route('/disposals/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def disposal_edit(id):
    disposal = AssetDisposal.query.get_or_404(id)
    if disposal.status != 'pending':
        flash('只能編輯「待審核」狀態的報廢申請', 'warning')
        return redirect(url_for('assets.disposal_list'))
    
    if request.method == 'POST':
        try:
            disposal.reason = request.form.get('reason')
            disposal.disposal_type = request.form.get('disposal_type')
            disposal.disposal_value = request.form.get('disposal_value') or None
            db.session.commit()
            flash('報廢申請已更新', 'success')
            return redirect(url_for('assets.disposal_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新失敗: {str(e)}', 'danger')
    
    return render_template('assets/disposal_form.html', disposal=disposal)

@assets_bp.route('/disposals/<int:id>/delete', methods=['POST'])
@login_required
def disposal_delete(id):
    disposal = AssetDisposal.query.get_or_404(id)
    if disposal.status != 'pending':
        flash('只能刪除「待審核」狀態的報廢申請', 'warning')
        return redirect(url_for('assets.disposal_list'))
    
    try:
        db.session.delete(disposal)
        db.session.commit()
        flash('報廢申請已刪除', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'刪除失敗: {str(e)}', 'danger')
    return redirect(url_for('assets.disposal_list'))


@assets_bp.route('/download-template')
def download_template():
    file_path = os.path.join(os.getcwd(), 'static', 'assets', 'assets_template.xlsx')
    return send_file(file_path, as_attachment=True)


# 批次移轉
@assets_bp.route('/batch_transfer', methods=['POST'])
@login_required
def batch_transfer():
    asset_ids = request.form.getlist('asset_ids')
    transfer_type = request.form.get('transfer_type')
    target_dept_id = request.form.get('target_dept')
    target_custodian_id = request.form.get('target_custodian')
    target_loc_id = request.form.get('target_loc')
    reason = request.form.get('reason')

    if not asset_ids:
        flash('未選擇資產', 'warning')
        return redirect(url_for('assets.transfer_list'))
    if not reason:
        flash('請填寫移轉原因', 'warning')
        return redirect(url_for('assets.transfer_list'))

    try:
        created_ids = []
        for aid in asset_ids:
            asset = Asset.query.get(aid)
            if asset:
                transfer = AssetTransfer(
                    asset_id=asset.id,
                    from_department_id=asset.department_id,
                    to_department_id=target_dept_id if transfer_type == 'custodian' else None,
                    from_custodian_id=asset.custodian_id,
                    to_custodian_id=target_custodian_id if transfer_type == 'custodian' else None,
                    to_location_id=target_loc_id if transfer_type == 'warehouse' else None,
                    reason=reason,
                    status='pending'
                )
                db.session.add(transfer)
                created_ids.append(str(transfer.id))
        db.session.commit()

        WorkflowService.start_workflow(
            reference_type='batch_transfer',
            reference_id=",".join(created_ids),
            submitter_id=current_user.id
        )
        flash('批次移轉申請已送出，進入簽核流程。', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'批次移轉失敗: {str(e)}', 'danger')

    return redirect(url_for('assets.transfer_list'))


# 批次報廢
@assets_bp.route('/batch_disposal', methods=['POST'])
@login_required
def batch_disposal():
    asset_ids = request.form.getlist('asset_ids')
    disposal_type = request.form.get('disposal_type')
    reason = request.form.get('disposal_reason')

    if not asset_ids:
        flash('未選擇資產', 'warning')
        return redirect(url_for('assets.disposal_list'))
    if not reason:
        flash('請填寫報廢原因', 'warning')
        return redirect(url_for('assets.disposal_list'))

    try:
        created_ids = []
        for aid in asset_ids:
            asset = Asset.query.get(aid)
            if asset:
                disposal = AssetDisposal(
                    asset_id=asset.id,
                    reason=reason,
                    disposal_type=disposal_type,
                    status='pending'
                )
                db.session.add(disposal)
                created_ids.append(str(disposal.id))
        db.session.commit()

        WorkflowService.start_workflow(
            reference_type='batch_disposal',
            reference_id=",".join(created_ids),
            submitter_id=current_user.id
        )
        flash('批次報廢申請已送出，進入簽核流程。', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'批次報廢失敗: {str(e)}', 'danger')

    return redirect(url_for('assets.disposal_list'))


# 匯出 QR Code JPG (ZIP)
@assets_bp.route('/export_qrcodes', methods=['GET'], endpoint='export_qrcodes')
@login_required
def export_qrcodes():
    import qrcode
    import zipfile
    from io import BytesIO
    from flask import send_file, request

    # 讀取清單頁的 query string
    q = request.args.get('q')
    category = request.args.get('category')
    location = request.args.get('location')
    status = request.args.get('status')

    query = Asset.query

    if q:
        query = query.filter(Asset.name.like(f"%{q}%"))
    if category:
        query = query.filter(Asset.category_id == category)
    if location:
        query = query.filter(Asset.location_id == location)
    if status:
        query = query.filter(Asset.status == status)

    assets = query.all()

    # 建立 ZIP 檔
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for a in assets:
            qr_img = qrcode.make(a.id)
            img_bytes = BytesIO()
            qr_img.save(img_bytes, format='JPEG')
            img_bytes.seek(0)

            filename = f"{a.id}_{a.name}.jpg"
            zipf.writestr(filename, img_bytes.read())

    zip_buffer.seek(0)
    return send_file(zip_buffer,
                     as_attachment=True,
                     download_name="qrcodes.zip",
                     mimetype="application/zip")