# GenSpark - Configuration
import os
from pathlib import Path
from urllib.parse import quote_plus
from dotenv import load_dotenv

# .env hamesha "vendor dashboard" folder se load karo (chaho jahan se run karo)
# override=True so .env values win over empty system env (fixes "using password: NO")
_env_path = Path(__file__).resolve().parent / '.env'
load_dotenv(_env_path, override=True)


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'genspark-erp-secret-key')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = 86400  # 24 hours

    # Email (vendor notifications) - optional; leave empty to skip sending
    MAIL_SERVER = os.getenv('MAIL_SERVER', '')
    MAIL_PORT = int(os.getenv('MAIL_PORT', '587'))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', '1').strip().lower() in ('1', 'true', 'yes')
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', MAIL_USERNAME or 'noreply@genspark.com')
    PREFERRED_URL = os.getenv('PREFERRED_URL', 'http://127.0.0.1:5000')
    # Portal URL for one-time password email (React app); if not set, PREFERRED_URL is used
    FRONTEND_URL = os.getenv('FRONTEND_URL', '')
    # OAuth – Google & GitHub (leave empty to hide social buttons or skip redirect)
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')
    GITHUB_CLIENT_ID = os.getenv('GITHUB_CLIENT_ID', '')
    GITHUB_CLIENT_SECRET = os.getenv('GITHUB_CLIENT_SECRET', '')

    # Database: set USE_SQLITE=1 to run without MySQL (development)
    USE_SQLITE = os.getenv('USE_SQLITE', '1').strip().lower() in ('1', 'true', 'yes')
    if USE_SQLITE:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///genspark_erp.db'
    else:
        DB_HOST = os.getenv('DB_HOST', 'localhost') or 'localhost'
        DB_PORT = os.getenv('DB_PORT', '3306') or '3306'
        DB_USER = os.getenv('DB_USER', 'root') or 'root'
        DB_PASSWORD = (os.getenv('DB_PASSWORD') or '').strip()
        DB_NAME = os.getenv('DB_NAME', 'genspark_erp') or 'genspark_erp'
        # URL-encode password so special chars like @ don't break the connection string
        safe_password = quote_plus(DB_PASSWORD)
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{DB_USER}:{safe_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
