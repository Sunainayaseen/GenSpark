"""Quick check: app loads and /health, /api/health return 200. Run from vendor dashboard folder."""
import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

try:
    from app import create_app
    app = create_app()
    with app.test_client() as c:
        r = c.get('/health')
        r2 = c.get('/api/health')
    if r.status_code == 200 and r2.status_code == 200 and r.data == b'OK' and r2.data == b'OK':
        print('OK - App loads. /health and /api/health return OK.')
    else:
        print('FAIL - /health:', r.status_code, r.data[:50], '| /api/health:', r2.status_code, r2.data[:50])
except Exception as e:
    print('FAIL -', type(e).__name__, e)
