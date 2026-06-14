"""Dev launcher: one Dashboard instance, reloader OFF (avoids stacked servers)."""
import os
import sys

_d = os.path.dirname(os.path.abspath(__file__))
os.chdir(_d)
if _d not in sys.path:
    sys.path.insert(0, _d)
os.environ.setdefault('FLASK_ENV', 'development')

from run import app  # noqa: E402
from app import socketio  # noqa: E402

print('single instance, no reloader', flush=True)
socketio.run(
    app,
    host='0.0.0.0',
    port=5000,
    debug=False,
    use_reloader=False,
    allow_unsafe_werkzeug=True,
)
