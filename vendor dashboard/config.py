# GenSpark - Configuration
import os
from pathlib import Path
from urllib.parse import quote_plus
from dotenv import load_dotenv

# .env is loaded from this folder only (not cwd-dependent).
_env_path = Path(__file__).resolve().parent / '.env'


def _is_cloud_runtime():
    """True on Railway / similar PaaS where localhost MySQL does not exist."""
    return bool(
        os.getenv('RAILWAY_ENVIRONMENT')
        or os.getenv('RAILWAY_PROJECT_ID')
        or os.getenv('RAILWAY_SERVICE_NAME')
        or os.getenv('RENDER')
        or os.getenv('PORT')  # Railway/Heroku always inject PORT
    )


def _load_environment():
    """
    Load .env for local dev. On cloud, platform variables must win over .env defaults
    (override=True would replace MYSQLHOST etc. with localhost from a committed .env).
    """
    if not _env_path.is_file():
        return
    load_dotenv(_env_path, override=not _is_cloud_runtime())


_load_environment()


def _use_sqlite_from_env():
    """Local dev: SQLite by default. Cloud/production: MySQL unless USE_SQLITE=1."""
    raw = os.getenv('USE_SQLITE')
    if raw is not None and str(raw).strip() != '':
        return str(raw).strip().lower() in ('1', 'true', 'yes')
    if _is_cloud_runtime():
        return False
    # Local: default SQLite unless FLASK_ENV=production explicitly
    return os.getenv('FLASK_ENV', '').strip().lower() != 'production'


def _normalize_mysql_url(url: str) -> str:
    """Ensure SQLAlchemy uses PyMySQL driver."""
    url = url.strip()
    if url.startswith('mysql://'):
        return 'mysql+pymysql://' + url[len('mysql://'):]
    if url.startswith('mysql+pymysql://'):
        return url
    return url


def build_sqlalchemy_database_uri():
    """
    Build DB URI from environment (Railway Variables, .env, or local defaults).

    Priority:
      1) DATABASE_URL / MYSQL_URL (full connection string)
      2) DB_HOST + DB_USER + ... or Railway MYSQLHOST / MYSQLUSER / ...
      3) localhost defaults (local MySQL only)
    """
    if _use_sqlite_from_env():
        return 'sqlite:///genspark_erp.db'

    for key in ('DATABASE_URL', 'MYSQL_URL', 'MYSQL_PUBLIC_URL'):
        url = (os.getenv(key) or '').strip()
        if url:
            return _normalize_mysql_url(url)

    host = (
        (os.getenv('DB_HOST') or '').strip()
        or (os.getenv('MYSQLHOST') or '').strip()
        or (os.getenv('MYSQL_HOST') or '').strip()
    )
    port = (
        (os.getenv('DB_PORT') or '').strip()
        or (os.getenv('MYSQLPORT') or '').strip()
        or (os.getenv('MYSQL_PORT') or '').strip()
        or '3306'
    )
    user = (
        (os.getenv('DB_USER') or '').strip()
        or (os.getenv('MYSQLUSER') or '').strip()
        or (os.getenv('MYSQL_USER') or '').strip()
        or 'root'
    )
    password = (
        os.getenv('DB_PASSWORD')
        or os.getenv('MYSQLPASSWORD')
        or os.getenv('MYSQL_PASSWORD')
        or ''
    )
    password = str(password).strip()
    name = (
        (os.getenv('DB_NAME') or '').strip()
        or (os.getenv('MYSQLDATABASE') or '').strip()
        or (os.getenv('MYSQL_DATABASE') or '').strip()
        or 'genspark_erp'
    )

    if _is_cloud_runtime() and host in ('', 'localhost', '127.0.0.1'):
        raise RuntimeError(
            'Database host is localhost on a cloud deploy. Link MySQL on Railway or set: '
            'DATABASE_URL / MYSQL_URL, or DB_HOST + DB_USER + DB_PASSWORD + DB_NAME '
            '(Railway plugin: MYSQLHOST, MYSQLUSER, MYSQLPASSWORD, MYSQLDATABASE).'
        )

    if not host:
        host = 'localhost'

    safe_password = quote_plus(password)
    return f'mysql+pymysql://{user}:{safe_password}@{host}:{port}/{name}'


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
    FRONTEND_URL = os.getenv('FRONTEND_URL', '')
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')
    GITHUB_CLIENT_ID = os.getenv('GITHUB_CLIENT_ID', '')
    GITHUB_CLIENT_SECRET = os.getenv('GITHUB_CLIENT_SECRET', '')

    # Do NOT call build_sqlalchemy_database_uri() here — that runs at import time and
    # crashes railpack/gunicorn before run.py loads. Set in create_app() instead.


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
