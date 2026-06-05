from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO
from flask_apscheduler import APScheduler

# SQLAlchemy ORM
db = SQLAlchemy()

# Database Migrations
migrate = Migrate()

# Authentication - Session
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

# Authentication - JWT
jwt = JWTManager()

# Real-time Communication
socketio = SocketIO(cors_allowed_origins="*", async_mode='threading')

# Task Scheduler
scheduler = APScheduler()
