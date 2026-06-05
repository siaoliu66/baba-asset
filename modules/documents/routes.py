import os
import uuid
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, jsonify, current_app, send_from_directory, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from core.models.documents import Document, DocumentCategory, DocumentAccessLog
from core.models.organization import Personnel
from extensions import db
from . import documents_bp

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'jpg', 'jpeg', 'png', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@documents_bp.before_request
@login_required
def check_module_enabled():
    if not current_app.config.get('DOCUMENT_MODULE_ENABLED', True): # Default True for now
        flash('文件管理模組目前尚未啟用', 'warning')
        return redirect(url_for('dashboard.index'))

@documents_bp.route('/')
@login_required
def index():
    docs = Document.query.order_by(Document.created_at.desc()).all()
    categories = DocumentCategory.query.all()
    return render_template('documents/index.html', docs=docs, categories=categories)

@documents_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        # 1. Validation
        if 'file' not in request.files:
            flash('未選擇檔案', 'danger')
            return redirect(request.url)
            
        file = request.files['file']
        if file.filename == '':
            flash('未選擇檔案', 'danger')
            return redirect(request.url)
            
        if not allowed_file(file.filename):
            flash('不支援的檔案格式', 'warning')
            return redirect(request.url)
            
        # 2. Check Personnel Link
        if not current_user.personnel_id:
            flash('您的帳號尚未連結人事資料，無法上傳文件', 'danger')
            return redirect(url_for('documents.index'))
            
        personnel = Personnel.query.get(current_user.personnel_id)
        if not personnel or not personnel.department_id:
             # Fallback or Block? Let's block for data integrity
            flash('您的人事資料缺少部門設定，無法上傳', 'danger')
            return redirect(url_for('documents.index'))

        try:
            # 3. File Processing
            original_filename = secure_filename(file.filename)
            ext = original_filename.rsplit('.', 1)[1].lower()
            unique_filename = f"{uuid.uuid4().hex}.{ext}"
            
            # Directory: static/uploads/documents/{YYYY}/{MM}
            now = datetime.now()
            relative_path = os.path.join('uploads', 'documents', now.strftime('%Y'), now.strftime('%m'))
            upload_dir = os.path.join(current_app.root_path, 'static', relative_path)
            os.makedirs(upload_dir, exist_ok=True)
            
            file_path = os.path.join(upload_dir, unique_filename)
            file.save(file_path)
            
            file_size = os.path.getsize(file_path)
            db_path = os.path.join(relative_path, unique_filename) # Store relative path
            
            # 4. Create Record
            doc_number = f"DOC-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
            
            new_doc = Document(
                doc_number=doc_number,
                title=request.form.get('title'),
                description=request.form.get('description'),
                category_id=request.form.get('category_id'),
                department_id=personnel.department_id,
                owner_id=personnel.id,
                file_path=db_path,
                file_size=file_size,
                file_type=ext,
                classification=request.form.get('classification', 'internal'),
                is_contract=request.form.get('is_contract') == 'on',
                status='active'
            )
            
            db.session.add(new_doc)
            db.session.commit()
            
            flash(f'文件上傳成功 (編號: {doc_number})', 'success')
            return redirect(url_for('documents.index'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Upload failed: {e}")
            flash(f'上傳失敗: {str(e)}', 'danger')

    categories = DocumentCategory.query.filter_by(is_active=True).all()
    companies = [] # Removed from form logic, using current user dept
    return render_template('documents/form.html', categories=categories)

@documents_bp.route('/download/<int:doc_id>')
@login_required
def download(doc_id):
    doc = Document.query.get_or_404(doc_id)
    
    # Security/Permission Check (Simplified)
    # TODO: Check classification vs User Role
    
    # Log Access
    log = DocumentAccessLog(
        document_id=doc.id,
        user_id=current_user.id,
        action='download',
        ip_address=request.remote_addr,
        user_agent=str(request.user_agent)
    )
    db.session.add(log)
    db.session.commit()
    
    # Serve File
    # db_path e.g. "uploads/documents/2026/01/uuid.pdf"
    # send_from_directory needs absolute directory and filename
    full_path = os.path.join(current_app.root_path, 'static', doc.file_path)
    directory = os.path.dirname(full_path)
    filename = os.path.basename(full_path)
    
    if not os.path.exists(full_path):
        flash('實體檔案遺失', 'danger')
        return redirect(url_for('documents.index'))
        
    return send_from_directory(directory, filename, as_attachment=True, download_name=f"{doc.title}.{doc.file_type}")

@documents_bp.route('/view/<int:doc_id>')
@login_required
def view_doc(doc_id):
    doc = Document.query.get_or_404(doc_id)
    
    # Log Access
    log = DocumentAccessLog(
        document_id=doc.id,
        user_id=current_user.id,
        action='view',
        ip_address=request.remote_addr,
        user_agent=str(request.user_agent)
    )
    db.session.add(log)
    db.session.commit()
    
    # If it's a viewable type (PDF, Image), show inline?
    # For now keep preview.html or redirect to download if not viewable
    return render_template('documents/preview.html', doc=doc)
