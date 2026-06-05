from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from core.models.system import User, AuditLog
from extensions import db, login_manager
from . import auth_bp

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        
        user = User.query.filter_by(username=username).first()
        
        if not user or not user.check_password(password):
            flash('請檢查您的帳號或密碼', 'danger')
            return redirect(url_for('auth.login'))
            
        if not user.is_active:
            flash('此帳號已被停用', 'warning')
            return redirect(url_for('auth.login'))
            
        login_user(user, remember=remember)
        
        # Log the login
        log = AuditLog(
            user_id=user.id,
            module='auth',
            action='LOGIN',
            description=f'User {username} logged in via Web'
        )
        db.session.add(log)
        db.session.commit()
        
        next_page = request.args.get('next')
        return redirect(next_page or url_for('dashboard.index'))
        
    return render_template('auth/login.html')

@auth_bp.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    user = User.query.filter_by(username=username).first()
    
    if not user or not user.check_password(password):
        return jsonify({"msg": "帳號或密碼錯誤"}), 401
        
    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)
    
    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role.name if user.role else None
        }
    }), 200

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

# ==================== JWT API for Mobile ====================
@auth_bp.route('/api/refresh', methods=['POST'])
@jwt_required(refresh=True)
def api_refresh():
    """Refresh access token using refresh token"""
    identity = get_jwt_identity()
    access_token = create_access_token(identity=identity)
    return jsonify({"access_token": access_token}), 200

@auth_bp.route('/api/me', methods=['GET'])
@jwt_required()
def api_me():
    """Get current user profile"""
    identity = get_jwt_identity()
    user = User.query.get(identity)
    
    if not user:
        return jsonify({"msg": "User not found"}), 404
    
    return jsonify({
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "email": user.email,
        "role": user.role.name if user.role else None,
        "is_active": user.is_active,
        "personnel_id": user.personnel_id
    }), 200

@auth_bp.route('/api/logout', methods=['POST'])
@jwt_required()
def api_logout():
    """Log out and invalidate token (client-side token disposal)"""
    identity = get_jwt_identity()
    user = User.query.get(identity)
    
    if user:
        log = AuditLog(
            user_id=user.id,
            module='auth',
            action='LOGOUT_API',
            description=f'User {user.username} logged out via API'
        )
        db.session.add(log)
        db.session.commit()
    
    return jsonify({"msg": "Successfully logged out"}), 200

# ==================== User Profile ====================
@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """個人設定頁面 — 高階主管可指定代理盤點人"""
    if request.method == 'POST':
        # 修改密碼
        new_password = request.form.get('new_password')
        if new_password and len(new_password) >= 6:
            current_user.set_password(new_password)
            flash('密碼修改成功', 'success')

        # 代理盤點人設定（僅高階主管）
        if current_user.is_senior_approver:
            proxy_id = request.form.get('proxy_user_id')
            if proxy_id:
                current_user.proxy_user_id = int(proxy_id) if proxy_id != '0' else None
            else:
                current_user.proxy_user_id = None

        try:
            db.session.commit()
            flash('設定已儲存', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'儲存失敗: {str(e)}', 'danger')

        return redirect(url_for('auth.profile'))

    # GET: 準備代理人候選清單
    proxy_candidates = []
    if current_user.is_senior_approver:
        proxy_candidates = User.query.filter(
            User.id != current_user.id,
            User.is_active == True
        ).order_by(User.display_name).all()

    return render_template('auth/profile.html',
        proxy_candidates=proxy_candidates
    )
