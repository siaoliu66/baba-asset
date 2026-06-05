from app import create_app
from extensions import db
from core.models.system import Role, User
from core.models.organization import Company, Department, Personnel

def seed_data():
    app = create_app()
    with app.app_context():
        # 1. Create Default Roles
        roles_data = [
            ('super_admin', '超級管理員', '擁有全系統最高權限'),
            ('admin', '管理員', '資產與系統管理權限'),
            ('dept_manager', '部門主管', '部門審核權限'),
            ('vice_president', '副總經理', '高階簽核權限'),
            ('general_manager', '總經理', '最高簽核權限'),
            ('chairman', '董事長', '董事會最高權限'),
            ('inventory_staff', '盤點人員', '執行盤點權限'),
            ('finance', '財務人員', '財務報表與折舊權限'),
            ('user', '一般使用者', '基本查詢與個人盤點')
        ]
        
        roles = {}
        for code, name, desc in roles_data:
            role = Role.query.filter_by(name=code).first()
            if not role:
                role = Role(name=code, display_name=name, description=desc, is_system=True)
                db.session.add(role)
            roles[code] = role
        db.session.commit()
        print("Roles seeded.")

        # 2. Create Default Company & Department
        comp = Company.query.filter_by(code='HQ').first()
        if not comp:
            comp = Company(code='HQ', name='Headquarters', display_name='總公司', short_name='總公司', is_active=True)
            db.session.add(comp)
            db.session.commit()
            print("Company seeded.")
            
        dept = Department.query.filter_by(code='IT').first()
        if not dept:
            dept = Department(company_id=comp.id, code='IT', name='Information Technology', display_name='管理部-資訊課', level=1)
            db.session.add(dept)
            db.session.commit()
            print("Department seeded.")

        # 3. Create Default Personnel & Admin User
        person = Personnel.query.filter_by(employee_id='ADMIN001').first()
        if not person:
            person = Personnel(
                employee_id='ADMIN001',
                department_id=dept.id,
                name='Admin',
                display_name='系統管理員',
                email='admin@example.com',
                is_active=True
            )
            db.session.add(person)
            db.session.commit()
            print("Personnel seeded.")
            
        user = User.query.filter_by(username='admin').first()
        if not user:
            user = User(
                personnel_id=person.id,
                username='admin',
                display_name='Admin',
                role_id=roles['super_admin'].id,
                email='admin@example.com',
                is_active=True,
                is_senior_approver=True
            )
            user.set_password('admin123')
            db.session.add(user)
            db.session.commit()
            print("Admin user created (admin / admin123).")

        # 4. Create Demo Users (Manager, VP, GM)
        # IT Manager
        it_mgr_person = Personnel.query.filter_by(employee_id='MGR001').first()
        if not it_mgr_person:
            it_mgr_person = Personnel(
                employee_id='MGR001', department_id=dept.id, name='IT Manager', display_name='陳經理 (IT)',
                email='manager@example.com', is_active=True, position='Manager'
            )
            db.session.add(it_mgr_person)
            db.session.commit()
            
            # Update Dept Manager
            dept.manager_id = it_mgr_person.id
            db.session.commit()
        
        it_mgr_user = User.query.filter_by(username='manager').first()
        if not it_mgr_user:
            it_mgr_user = User(
                personnel_id=it_mgr_person.id, username='manager', display_name='陳經理',
                role_id=roles['dept_manager'].id, email='manager@example.com', is_active=True
            )
            it_mgr_user.set_password('123456')
            db.session.add(it_mgr_user)
            db.session.commit()
            print("IT Manager created (manager / 123456).")

        # VP
        vp_person = Personnel.query.filter_by(employee_id='VP001').first()
        if not vp_person:
            vp_person = Personnel(
                employee_id='VP001', department_id=comp.departments.first().id, name='VP Wang', display_name='王副總',
                email='vp@example.com', is_active=True, position='Vice President'
            )
            db.session.add(vp_person)
            db.session.commit()
            
        vp_user = User.query.filter_by(username='vp').first()
        if not vp_user:
            vp_user = User(
                personnel_id=vp_person.id, username='vp', display_name='王副總',
                role_id=roles['vice_president'].id, email='vp@example.com', is_active=True, is_senior_approver=True
            )
            vp_user.set_password('123456')
            db.session.add(vp_user)
            db.session.commit()
            print("VP created (vp / 123456).")

        # GM
        gm_person = Personnel.query.filter_by(employee_id='GM001').first()
        if not gm_person:
            gm_person = Personnel(
                employee_id='GM001', department_id=comp.departments.first().id, name='GM Zhang', display_name='張總經理',
                email='gm@example.com', is_active=True, position='General Manager'
            )
            db.session.add(gm_person)
            db.session.commit()
            
        gm_user = User.query.filter_by(username='gm').first()
        if not gm_user:
            gm_user = User(
                personnel_id=gm_person.id, username='gm', display_name='張總經理',
                role_id=roles['general_manager'].id, email='gm@example.com', is_active=True, is_senior_approver=True
            )
            gm_user.set_password('123456')
            db.session.add(gm_user)
            db.session.commit()
            print("GM created (gm / 123456).")

if __name__ == '__main__':
    seed_data()
