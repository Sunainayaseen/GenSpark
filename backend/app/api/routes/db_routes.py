"""
Database verification and diagnostics endpoints.
Used to verify active database connection and environment origin.
"""

from flask import Blueprint, current_app
from sqlalchemy import text

from app.core.responses import success, server_error
from app.core.database import resolve_db_config, get_db_connection

bp = Blueprint('db', __name__, url_prefix='/api')


def _mask_db_uri(uri: str) -> str:
    """Mask credentials from database URI for safe logging."""
    if not uri or '://' not in uri:
        return uri or ''
    try:
        scheme, rest = uri.split('://', 1)
        if '@' in rest:
            _, host = rest.split('@', 1)
            return f'{scheme}://{host}'
        return uri
    except Exception:
        return 'Hidden / Encrypted Configurations'


@bp.route('/db-verify', methods=['GET'])
def verify_db_connection():
    """
    GET /api/db-verify - Verify database connectivity and environment.
    
    Returns diagnostic information about the active database connection.
    Safely masks credentials while showing host origin.
    """
    connection = None
    cursor = None
    
    try:
        cfg = resolve_db_config()
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute('SELECT 1')
        row = cursor.fetchone()
        
        if not row or int(row[0]) != 1:
            raise RuntimeError('SELECT 1 returned unexpected result')
        
        db_uri = f"mysql://{cfg['user']}@{cfg['host']}:{cfg['port']}/{cfg['database']}"
        host = str(cfg['host']).lower()
        is_cloud = host not in ('localhost', '127.0.0.1') and not host.startswith('localhost')
        
        return success(
            data={
                'status': 'connected',
                'active_environment': 'CLOUD PRODUCTION ENGINE (Railway/Hugging Face)' if is_cloud else 'LOCAL ENGINE (Localhost Machine Server)',
                'database_host_origin': db_uri.split('@')[-1] if '@' in db_uri else 'Hidden / Encrypted Configurations',
                'db_config': {
                    'host': cfg['host'],
                    'port': cfg['port'],
                    'database': cfg['database'],
                },
            },
            message='Database connection verified',
            http_status=200,
        )
    except Exception as exc:
        current_app.logger.exception('db_verify failed')
        return server_error(
            message='Database connection failed',
            error_code='DB_CONNECTION_FAILED',
            details={'error': str(exc)},
        )
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if connection and connection.is_connected():
            try:
                connection.close()
            except Exception:
                pass
