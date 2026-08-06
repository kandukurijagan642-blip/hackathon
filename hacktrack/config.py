import os
from dotenv import load_dotenv

# Load environment variables from .env file (only if it exists locally)
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

class Config:
    # Project Paths (defined first so other settings can use them)
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    EXPORT_FOLDER = os.path.join(BASE_DIR, 'exports')
    
    # Ensure directories exist
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(EXPORT_FOLDER, exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'static', 'qrcodes'), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'static', 'certificates'), exist_ok=True)
    
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'default_secret_key_if_none_set')
    DEBUG = os.environ.get('FLASK_DEBUG', 'False') == 'True'
    
    # Database settings
    # Priority: DATABASE_URL (Render PostgreSQL) > MYSQL_HOST (local MySQL) > SQLite fallback
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
    MYSQL_DB = os.environ.get('MYSQL_DB', 'hacktrack_db')
    
    DATABASE_URL = os.environ.get('DATABASE_URL')
    RENDER = os.environ.get('RENDER', False)  # Render sets this automatically
    
    if DATABASE_URL:
        # Render PostgreSQL or any external database
        if DATABASE_URL.startswith("postgres://"):
            SQLALCHEMY_DATABASE_URI = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        else:
            SQLALCHEMY_DATABASE_URI = DATABASE_URL
    elif RENDER:
        # On Render without DATABASE_URL — use SQLite
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, 'hacktrack.db')
    else:
        # Local development — use MySQL
        if MYSQL_PASSWORD:
            SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DB}"
        else:
            SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{MYSQL_USER}@{MYSQL_HOST}/{MYSQL_DB}"
        
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # MongoDB Atlas settings
    MONGO_URI = os.environ.get('MONGO_URI', 'mongodb+srv://kandukurijagan7_db_user:xTagPoLQCWfH0agP@cluster0.1yxvdq5.mongodb.net/hacktrack_db?retryWrites=true&w=majority&appName=Cluster0')
    MONGO_DB = os.environ.get('MONGO_DB', 'hacktrack_db')
    
    # Mock Email Settings
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'localhost')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 1025))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'False') == 'True'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@hacktrack.com')
