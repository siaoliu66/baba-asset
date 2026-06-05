from flask import render_template, redirect, url_for, flash, request, jsonify, send_file
from flask_login import login_required
from core.models.organization import Company, Department, Personnel, Location
from core.models.assets import AssetCategory
from core.models.system import User, Role
from extensions import db
from . import settings_bp
import pandas as pd

@settings_bp.route('/')
@login_required
def index():
    return render_template('settings/index.html')

@settings_bp.route('/org')
@login_required
def org_index():
    companies = Company.query.all()
    # Departments tree structure
    departments = Department.query.filter_by(parent_id=None).all()
    return render_template('settings/org_index.html', companies=companies, departments=departments)

@settings_bp.route('/departments/api/tree')
@login_required
def get_department_tree():
    def build_tree(parent_id=None):
        depts = Department.query.filter_by(parent_id=parent_id).order_by(Department.sort_order).all()
        tree = []
        for d in depts:
            tree.append({
                "id": d.id,
                "name": d.display_name or d.name,
                "code": d.code,
                "children": build_tree(d.id)
            })
        return tree
    
    return jsonify(build_tree())

@settings_bp.route('/personnel')
@login_required
def personnel_list():
    personnel = Personnel.query.all()
    return render_template('settings/personnel_list.html', personnel=personnel)

@settings_bp.route('/personnel/download-sample')
@login_required
def personnel_download_sample():

    # 指向 static/assets/personnel_sample.xlsx
    return send_file(
        'static/assets/personnel_sample.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='personnel_sample.xlsx'
    )

@settings_bp.route('/personnel/import', methods=['POST'])
@login_required
def personnel_import():
    file = request.files.get('file')
    if not file:
        flash('請選擇檔案')
        return redirect(url_for('settings.personnel_list'))

    df = pd.read_excel(file)
    print("Excel 欄位：", df.columns.tolist())  # 確認欄位名稱

    added_count = 0
    updated_count = 0
    skipped_count = 0

    try:
        for _, row in df.iterrows():
            emp_id = str(row['員工編號']).strip() if not pd.isna(row['員工編號']) else None
            name = str(row['姓名']).strip() if not pd.isna(row['姓名']) else None
            email = str(row['電子信箱']).strip() if not pd.isna(row['電子信箱']) else None
            phone = str(row['電話']).strip() if not pd.isna(row['電話']) else None
            dept_name = str(row['所屬部門']).strip() if not pd.isna(row['所屬部門']) else None
            is_active = str(row['是否在職']).strip().lower() in ['true', '1', 'yes', '是']

            # 檢查必填欄位
            if not emp_id or not name or not dept_name:
                flash(f"跳過：員工 {emp_id or '(未填編號)'} 缺少必填欄位")
                skipped_count += 1
                continue

            # 查找或建立部門
            dept = Department.query.filter_by(display_name=dept_name).first()
            if not dept:
                dept = Department(display_name=dept_name)
                db.session.add(dept)
                db.session.flush()

            # 查找或建立人員
            p = Personnel.query.filter_by(employee_id=emp_id).first()
            if not p:
                p = Personnel(employee_id=emp_id)
                db.session.add(p)
                added_count += 1
            else:
                updated_count += 1

            # 更新欄位
            p.name = name
            p.email = email
            p.phone = phone
            p.is_active = is_active
            p.department_id = dept.id

        db.session.commit()
        flash(f'匯入完成：新增 {added_count} 筆，更新 {updated_count} 筆，跳過 {skipped_count} 筆', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'匯入失敗: {str(e)}', 'danger')

    return redirect(url_for('settings.personnel_list'))


@settings_bp.route('/locations')
@login_required
def location_list():
    locations = Location.query.all()
    return render_template('settings/location_list.html', locations=locations)

# ==================== Company CRUD ====================
@settings_bp.route('/companies')
@login_required
def company_list():
    companies = Company.query.order_by(Company.sort_order, Company.name).all()
    return render_template('settings/company_list.html', companies=companies)

@settings_bp.route('/companies/create', methods=['GET', 'POST'])
@login_required
def company_create():
    if request.method == 'POST':
        try:
            company = Company(
                code=request.form.get('code'),
                name=request.form.get('name'),
                display_name=request.form.get('display_name'),
                tax_id=request.form.get('tax_id'),
                address=request.form.get('address'),
                phone=request.form.get('phone'),
                is_active=request.form.get('is_active') == 'on',
                sort_order=int(request.form.get('sort_order') or 0)
            )
            db.session.add(company)
            db.session.commit()
            flash('公司新增成功', 'success')
            return redirect(url_for('settings.company_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'新增失敗: {str(e)}', 'danger')
    return render_template('settings/company_form.html', company=None)

@settings_bp.route('/companies/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def company_edit(id):
    company = Company.query.get_or_404(id)
    if request.method == 'POST':
        try:
            company.code = request.form.get('code')
            company.name = request.form.get('name')
            company.display_name = request.form.get('display_name')
            company.tax_id = request.form.get('tax_id')
            company.address = request.form.get('address')
            company.phone = request.form.get('phone')
            company.is_active = request.form.get('is_active') == 'on'
            company.sort_order = int(request.form.get('sort_order') or 0)
            db.session.commit()
            flash('公司更新成功', 'success')
            return redirect(url_for('settings.company_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新失敗: {str(e)}', 'danger')
    return render_template('settings/company_form.html', company=company)

@settings_bp.route('/companies/<int:id>/delete', methods=['POST'])
@login_required
def company_delete(id):
    company = Company.query.get_or_404(id)
    try:
        db.session.delete(company)
        db.session.commit()
        flash('公司已刪除', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'刪除失敗: {str(e)}', 'danger')
    return redirect(url_for('settings.company_list'))

# ==================== Department CRUD ====================
@settings_bp.route('/departments')
@login_required
def department_list():
    departments = Department.query.order_by(Department.sort_order, Department.name).all()
    companies = Company.query.filter_by(is_active=True).all()
    return render_template('settings/department_list.html', departments=departments, companies=companies)

@settings_bp.route('/departments/create', methods=['GET', 'POST'])
@login_required
def department_create():
    if request.method == 'POST':
        try:
            dept = Department(
                name=request.form.get('name'),
                display_name=request.form.get('display_name'),
                code=request.form.get('code'),
                company_id=request.form.get('company_id') or None,
                parent_id=request.form.get('parent_id') or None,
                manager_id=request.form.get('manager_id') or None,
                sort_order=int(request.form.get('sort_order') or 0)
            )
            db.session.add(dept)
            db.session.commit()
            flash('部門新增成功', 'success')
            return redirect(url_for('settings.department_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'新增失敗: {str(e)}', 'danger')
    companies = Company.query.filter_by(is_active=True).all()
    departments = Department.query.all()
    personnel_list = Personnel.query.filter_by(is_active=True).all()
    return render_template('settings/department_form.html', dept=None, companies=companies, departments=departments, personnel=personnel_list)

@settings_bp.route('/departments/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def department_edit(id):
    dept = Department.query.get_or_404(id)
    if request.method == 'POST':
        try:
            dept.name = request.form.get('name')
            dept.display_name = request.form.get('display_name')
            dept.code = request.form.get('code')
            dept.company_id = request.form.get('company_id') or None
            dept.parent_id = request.form.get('parent_id') or None
            dept.manager_id = request.form.get('manager_id') or None
            dept.sort_order = int(request.form.get('sort_order') or 0)
            db.session.commit()
            flash('部門更新成功', 'success')
            return redirect(url_for('settings.department_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新失敗: {str(e)}', 'danger')
    companies = Company.query.filter_by(is_active=True).all()
    departments = Department.query.filter(Department.id != id).all()
    personnel_list = Personnel.query.filter_by(is_active=True).all()
    return render_template('settings/department_form.html', dept=dept, companies=companies, departments=departments, personnel=personnel_list)

@settings_bp.route('/departments/<int:id>/delete', methods=['POST'])
@login_required
def department_delete(id):
    dept = Department.query.get_or_404(id)
    try:
        db.session.delete(dept)
        db.session.commit()
        flash('部門已刪除', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'刪除失敗: {str(e)}', 'danger')
    return redirect(url_for('settings.department_list'))

# ==================== Location CRUD ====================
@settings_bp.route('/locations/create', methods=['GET', 'POST'])
@login_required
def location_create():
    if request.method == 'POST':
        try:
            loc = Location(
                code=request.form.get('code'),
                name=request.form.get('name'),
                company_id=request.form.get('company_id'),
                parent_id=request.form.get('parent_id') or None,
                address=request.form.get('address')
            )
            db.session.add(loc)
            db.session.commit()
            flash('地點新增成功', 'success')
            return redirect(url_for('settings.location_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'新增失敗: {str(e)}', 'danger')
    companies = Company.query.filter_by(is_active=True).all()
    locations = Location.query.all()
    return render_template('settings/location_form.html', location=None, companies=companies, locations=locations)

@settings_bp.route('/locations/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def location_edit(id):
    loc = Location.query.get_or_404(id)
    if request.method == 'POST':
        try:
            loc.code = request.form.get('code')
            loc.name = request.form.get('name')
            loc.company_id = request.form.get('company_id')
            loc.parent_id = request.form.get('parent_id') or None
            loc.address = request.form.get('address')
            db.session.commit()
            flash('地點更新成功', 'success')
            return redirect(url_for('settings.location_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新失敗: {str(e)}', 'danger')
    companies = Company.query.filter_by(is_active=True).all()
    locations = Location.query.filter(Location.id != id).all()
    return render_template('settings/location_form.html', location=loc, companies=companies, locations=locations)

@settings_bp.route('/locations/<int:id>/delete', methods=['POST'])
@login_required
def location_delete(id):
    loc = Location.query.get_or_404(id)
    try:
        db.session.delete(loc)
        db.session.commit()
        flash('地點已刪除', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'刪除失敗: {str(e)}', 'danger')
    return redirect(url_for('settings.location_list'))

# ==================== Personnel CRUD ====================
@settings_bp.route('/personnel/create', methods=['GET', 'POST'])
@login_required
def personnel_create():
    if request.method == 'POST':
        try:
            person = Personnel(
                name=request.form.get('name'),
                employee_id=request.form.get('employee_id'),
                email=request.form.get('email'),
                phone=request.form.get('phone'),
                department_id=request.form.get('department_id') or None,
                position=request.form.get('position'),
                is_active=request.form.get('is_active') == 'on'
            )
            db.session.add(person)
            db.session.flush()  # Get person.id for user creation
            
            # Handle quick account creation
            if request.form.get('create_account') == 'on':
                username = request.form.get('username')
                password = request.form.get('password')
                role_id = request.form.get('role_id')
                
                if username and password and role_id:
                    user = User(
                        username=username,
                        email=person.email,
                        display_name=person.name,
                        role_id=int(role_id),
                        personnel_id=person.id,
                        is_active=True
                    )
                    user.set_password(password)
                    db.session.add(user)
                    flash('人員與帳號新增成功', 'success')
                else:
                    flash('人員新增成功，但帳號資料不完整，未建立帳號', 'warning')
            else:
                flash('人員新增成功', 'success')
            
            db.session.commit()
            return redirect(url_for('settings.personnel_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'新增失敗: {str(e)}', 'danger')
    departments = Department.query.all()
    roles = Role.query.all()
    return render_template('settings/personnel_form.html', person=None, departments=departments, roles=roles)

@settings_bp.route('/personnel/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def personnel_edit(id):
    person = Personnel.query.get_or_404(id)
    if request.method == 'POST':
        try:
            person.name = request.form.get('name')
            person.employee_id = request.form.get('employee_id')
            person.email = request.form.get('email')
            person.phone = request.form.get('phone')
            person.department_id = request.form.get('department_id') or None
            person.position = request.form.get('position')
            person.is_active = request.form.get('is_active') == 'on'
            db.session.commit()
            flash('人員更新成功', 'success')
            return redirect(url_for('settings.personnel_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新失敗: {str(e)}', 'danger')
    departments = Department.query.all()
    return render_template('settings/personnel_form.html', person=person, departments=departments)

@settings_bp.route('/personnel/<int:id>/delete', methods=['POST'])
@login_required
def personnel_delete(id):
    person = Personnel.query.get_or_404(id)
    try:
        db.session.delete(person)
        db.session.commit()
        flash('人員已刪除', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'刪除失敗: {str(e)}', 'danger')
    return redirect(url_for('settings.personnel_list'))

# ==================== User CRUD ====================
@settings_bp.route('/users')
@login_required
def user_list():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('settings/user_list.html', users=users)

@settings_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
def user_create():
    if request.method == 'POST':
        try:
            user = User(
                username=request.form.get('username'),
                email=request.form.get('email'),
                display_name=request.form.get('display_name'),
                role_id=int(request.form.get('role_id')),
                personnel_id=request.form.get('personnel_id') or None,
                is_active=request.form.get('is_active') == 'on',
                is_senior_approver=request.form.get('is_senior_approver') == 'on'
            )
            user.set_password(request.form.get('password'))
            db.session.add(user)
            db.session.commit()
            flash('使用者新增成功', 'success')
            return redirect(url_for('settings.user_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'新增失敗: {str(e)}', 'danger')
    roles = Role.query.all()
    personnel = Personnel.query.filter_by(is_active=True).all()
    return render_template('settings/user_form.html', user=None, roles=roles, personnel=personnel)

@settings_bp.route('/users/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def user_edit(id):
    user = User.query.get_or_404(id)
    if request.method == 'POST':
        try:
            user.username = request.form.get('username')
            user.email = request.form.get('email')
            user.display_name = request.form.get('display_name')
            user.role_id = int(request.form.get('role_id'))
            user.personnel_id = request.form.get('personnel_id') or None
            user.is_active = request.form.get('is_active') == 'on'
            user.is_senior_approver = request.form.get('is_senior_approver') == 'on'
            # Only update password if provided
            new_password = request.form.get('password')
            if new_password:
                user.set_password(new_password)
            db.session.commit()
            flash('使用者更新成功', 'success')
            return redirect(url_for('settings.user_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新失敗: {str(e)}', 'danger')
    roles = Role.query.all()
    personnel = Personnel.query.filter_by(is_active=True).all()
    return render_template('settings/user_form.html', user=user, roles=roles, personnel=personnel)

@settings_bp.route('/users/<int:id>/delete', methods=['POST'])
@login_required
def user_delete(id):
    user = User.query.get_or_404(id)
    try:
        db.session.delete(user)
        db.session.commit()
        flash('使用者已刪除', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'刪除失敗: {str(e)}', 'danger')
    return redirect(url_for('settings.user_list'))

# ==================== Role List ====================
@settings_bp.route('/roles')
@login_required
def role_list():
    roles = Role.query.all()
    return render_template('settings/role_list.html', roles=roles)

# ==================== Asset Category CRUD ====================
@settings_bp.route('/categories')
@login_required
def category_list():
    categories = AssetCategory.query.order_by(AssetCategory.code).all()
    return render_template('settings/category_list.html', categories=categories)

@settings_bp.route('/categories/create', methods=['GET', 'POST'])
@login_required
def category_create():
    if request.method == 'POST':
        try:
            category = AssetCategory(
                code=request.form.get('code'),
                name=request.form.get('name'),
                depreciation_years=request.form.get('depreciation_years') or 0,
                parent_id=request.form.get('parent_id') or None
            )
            db.session.add(category)
            db.session.commit()
            flash('資產分類新增成功', 'success')
            return redirect(url_for('settings.category_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'新增失敗: {str(e)}', 'danger')
            
    categories = AssetCategory.query.all()
    return render_template('settings/category_form.html', category=None, categories=categories)

@settings_bp.route('/categories/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def category_edit(id):
    category = AssetCategory.query.get_or_404(id)
    if request.method == 'POST':
        try:
            category.code = request.form.get('code')
            category.name = request.form.get('name')
            category.depreciation_years = request.form.get('depreciation_years') or 0
            category.parent_id = request.form.get('parent_id') or None
            
            db.session.commit()
            flash('資產分類更新成功', 'success')
            return redirect(url_for('settings.category_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新失敗: {str(e)}', 'danger')
            
    categories = AssetCategory.query.filter(AssetCategory.id != id).all()
    return render_template('settings/category_form.html', category=category, categories=categories)

@settings_bp.route('/categories/<int:id>/delete', methods=['POST'])
@login_required
def category_delete(id):
    category = AssetCategory.query.get_or_404(id)
    try:
        db.session.delete(category)
        db.session.commit()
        flash('資產分類已刪除', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'刪除失敗: {str(e)}', 'danger')
    return redirect(url_for('settings.category_list'))
