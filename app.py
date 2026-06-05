from flask import Flask
from config import config
from extensions import db, migrate, login_manager, jwt, socketio, scheduler
from core import models  # Ensure models are loaded for Migrations
from modules.assets.routes import assets_bp

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialize Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    jwt.init_app(app)
    socketio.init_app(app)
    
    # Scheduler initialization
    if not scheduler.running:
        scheduler.init_app(app)
        from core.tasks import init_scheduled_tasks
        init_scheduled_tasks(app)
        scheduler.start()

    # Register Blueprints
    from core.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    

    
    from modules.settings import settings_bp
    app.register_blueprint(settings_bp, url_prefix='/settings')
    
    from modules.workflows import workflows_bp
    app.register_blueprint(workflows_bp, url_prefix='/workflows')
    
    from modules.inventory import inventory_bp
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    
    from modules.documents import documents_bp
    app.register_blueprint(documents_bp, url_prefix='/documents')
    
    from modules.dashboard import dashboard_bp
    app.register_blueprint(dashboard_bp)
    
    from modules.finance import finance_bp
    app.register_blueprint(finance_bp, url_prefix='/finance')

    @app.route('/health')
    def health_check():
        return {'status': 'healthy', 'config': config_name}
    
    app.register_blueprint(assets_bp, url_prefix="/assets")

    return app
