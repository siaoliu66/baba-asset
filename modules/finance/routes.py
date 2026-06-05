from flask import render_template, request, flash, redirect, url_for
from flask_login import login_required
from . import finance_bp
from core.models.assets import Asset
from core.models.finance import DepreciationRecord
from .services import DepreciationService
from extensions import db
from datetime import datetime

@finance_bp.route('/')
@login_required
def dashboard():
    # Calculate Totals
    total_assets = Asset.query.filter_by(status='active').count()
    total_cost = db.session.query(db.func.sum(Asset.purchase_price)).filter(Asset.status=='active').scalar() or 0
    total_depreciated = db.session.query(db.func.sum(DepreciationRecord.depreciation_amount)).scalar() or 0
    net_book_value = total_cost - total_depreciated
    
    # Recent depreciation records
    recent_records = DepreciationRecord.query.order_by(DepreciationRecord.created_at.desc()).limit(10).all()
    
    return render_template('finance/dashboard.html', 
                           total_assets=total_assets,
                           total_cost=total_cost,
                           total_depreciated=total_depreciated,
                           net_book_value=net_book_value,
                           recent_records=recent_records,
                           now=datetime.now())

@finance_bp.route('/list')
@login_required
def asset_list():
    assets = Asset.query.filter_by(status='active').all()
    return render_template('finance/asset_list.html', assets=assets)

@finance_bp.route('/calculate', methods=['POST'])
@login_required
def calculate_depreciation():
    # Manual Trigger
    try:
        if request.form.get('year') and request.form.get('month'):
            year = int(request.form.get('year'))
            month = int(request.form.get('month'))
        else:
            now = datetime.now()
            year = now.year
            month = now.month
            
        count = DepreciationService.run_monthly_closing(year, month)
        flash(f'已完成 {year}年{month}月 折舊試算，共產生 {count} 筆分錄', 'success')
    except Exception as e:
        flash(f'試算失敗: {str(e)}', 'danger')
        
    return redirect(url_for('finance.dashboard'))

@finance_bp.route('/export')
@login_required
def export_ledger():
    import csv
    import io
    from flask import Response
    
    # Get all active assets
    assets = Asset.query.filter_by(status='active').all()
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['資產編號', '名稱', '取得日期', '取得成本', '殘值', '耐用年限', '目前淨值', '狀態'])
    
    # Data
    for asset in assets:
        purchase_date = asset.purchase_date.strftime('%Y-%m-%d') if asset.purchase_date else ''
        cost = asset.purchase_price or 0
        salvage = asset.salvage_value or 0
        life = asset.useful_life_years or 0
        current = asset.current_value or cost
        
        writer.writerow([
            asset.id,
            asset.name,
            purchase_date,
            cost,
            salvage,
            life,
            current,
            asset.status
        ])
        
    output.seek(0)
    
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=asset_ledger_{datetime.now().strftime('%Y%m%d')}.csv"}
    )
