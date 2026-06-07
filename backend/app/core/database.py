"""
Database connection and pool management.
Centralizes all MySQL connectivity logic to prevent duplication.
"""

import os
import threading
import mysql.connector
from mysql.connector import Error as MySQLError, pooling
from flask import current_app


# Global connection pool
_db_pool = None
_db_pool_lock = threading.Lock()


def resolve_db_config() -> dict[str, str | int]:
    """
    Resolve database configuration from environment variables.
    
    Supports three naming conventions:
    1. Local style: DB_HOST, DB_USER, DB_PASSWORD, DB_NAME
    2. Hugging Face style: MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
    3. Railway style: MYSQLHOST, MYSQLUSER, MYSQLPASSWORD, MYSQLDATABASE
    
    Returns:
        Dictionary with keys: host, port, user, password, database
    """
    def env_first(*keys: str, default: str = '') -> str:
        for key in keys:
            raw = os.getenv(key)
            if raw is not None and str(raw).strip() != '':
                return str(raw).strip()
        return default

    return {
        'host': env_first('DB_HOST', 'MYSQL_HOST', 'MYSQLHOST', default='localhost'),
        'port': int(env_first('DB_PORT', 'MYSQL_PORT', 'MYSQLPORT', default='3306')),
        'user': env_first('DB_USER', 'MYSQL_USER', 'MYSQLUSER', default='root'),
        'password': env_first('DB_PASSWORD', 'MYSQL_PASSWORD', 'MYSQLPASSWORD', default=''),
        'database': env_first('DB_NAME', 'MYSQL_DATABASE', 'MYSQLDATABASE', default='genspark_erp'),
    }


def get_db_connection():
    """
    Get a database connection from the pool or create a new one.
    
    Raises:
        ConnectionError: If connection fails
    
    Returns:
        MySQL connection object
    """
    try:
        return _init_db_pool().get_connection()
    except Exception as pool_exc:
        current_app.logger.warning('DB pool failed, attempting direct connection: %s', pool_exc)
        try:
            return mysql.connector.connect(**_get_mysql_connect_kwargs())
        except MySQLError as exc:
            raise ConnectionError(f'Database connection failed: {exc}') from exc


def _init_db_pool():
    """Initialize connection pool (thread-safe)."""
    global _db_pool
    if _db_pool is not None:
        return _db_pool
    
    with _db_pool_lock:
        if _db_pool is not None:
            return _db_pool
        
        pool_size = max(1, min(int(os.getenv('DB_POOL_SIZE', '5')), 32))
        _db_pool = pooling.MySQLConnectionPool(
            pool_name='genspark_pool',
            pool_size=pool_size,
            pool_reset_session=True,
            **_get_mysql_connect_kwargs(),
        )
        current_app.logger.info('MySQL connection pool initialized (size=%s)', pool_size)
        return _db_pool


def _get_mysql_connect_kwargs() -> dict:
    """Get connection keyword arguments."""
    cfg = resolve_db_config()
    host_s = str(cfg['host']).lower()
    default_timeout = '3' if host_s in ('localhost', '127.0.0.1') else '15'
    
    return {
        'host': cfg['host'],
        'port': cfg['port'],
        'user': cfg['user'],
        'password': cfg['password'],
        'database': cfg['database'],
        'autocommit': False,
        'connection_timeout': int(os.getenv('DB_CONNECT_TIMEOUT', default_timeout)),
        'auth_plugin': 'mysql_native_password',
    }


def probe_db_connection() -> tuple[bool, str, dict]:
    """
    Non-fatal database connection test (for startup health checks).
    
    Returns:
        Tuple of (is_connected, message, details)
    """
    cfg = resolve_db_config()
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute('SELECT 1')
        row = cursor.fetchone()
        
        if not row or int(row[0]) != 1:
            return False, 'SELECT 1 failed', {'host': cfg['host']}
        
        return True, 'Database connected', {
            'host': cfg['host'],
            'port': cfg['port'],
            'database': cfg['database'],
        }
    except Exception as exc:
        return False, str(exc), {'host': cfg['host']}
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
