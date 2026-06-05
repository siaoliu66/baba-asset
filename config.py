import os
from datetime import timedelta
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    # Basic
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-please-change-in-prod')
    APP_NAME = os.getenv('APP_NAME', '資產管理系統')
    BASE_URL = os.getenv('BASE_URL', 'http://localhost:7550')
    
    # Database
    # Default to SQLite if DATABASE_URL is not set
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 
        'sqlite:///' + os.path.join(basedir, 'data', 'asset.db'))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Auth - JWT
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt-dev-key')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=2)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # Auth - Session
    REMEMBER_COOKIE_DURATION = timedelta(days=1)
    
    # Modules
    DOCUMENT_MODULE_ENABLED = os.getenv('DOCUMENT_MODULE_ENABLED', 'true').lower() == 'true'
    WATERMARK_ENABLED = os.getenv('WATERMARK_ENABLED', 'true').lower() == 'true'
    FULLTEXT_SEARCH_ENABLED = os.getenv('FULLTEXT_SEARCH_ENABLED', 'true').lower() == 'true'
    
    # Inventory & Workflow
    INVENTORY_PHOTO_REQUIRED = os.getenv('INVENTORY_PHOTO_REQUIRED', 'true').lower() == 'true'
    INVENTORY_GPS_REQUIRED = os.getenv('INVENTORY_GPS_REQUIRED', 'true').lower() == 'true'
    TRANSFER_SENIOR_APPROVAL = os.getenv('TRANSFER_SENIOR_APPROVAL', 'true').lower() == 'true'
    DISPOSAL_SENIOR_APPROVAL = os.getenv('DISPOSAL_SENIOR_APPROVAL', 'true').lower() == 'true'
    
    # Scheduler & Notifications
    APPROVAL_REMINDER_DAYS = int(os.getenv('APPROVAL_REMINDER_DAYS', 3))
    APPROVAL_ESCALATION_DAYS = int(os.getenv('APPROVAL_ESCALATION_DAYS', 7))
    
    # Pagination
    ITEMS_PER_PAGE = int(os.getenv('ITEMS_PER_PAGE', 20))

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    # In production, these should be set via environment variables
    # SECRET_KEY, SQLALCHEMY_DATABASE_URI, JWT_SECRET_KEY, etc.

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
