# GenSpark - Application Entry Point (WSGI: gunicorn run:app)
import os
import sys

_script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(_script_dir)
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)


def resolve_config_name():
    """Pick config profile: production on Railway, development locally."""
    name = os.getenv('FLASK_ENV', '').strip().lower()
    if name in ('production', 'development'):
        return name
    if os.getenv('RAILWAY_ENVIRONMENT') or os.getenv('RAILWAY_PROJECT_ID'):
        return 'production'
    return 'development'


def create_application():
    from app import create_app
    return create_app(resolve_config_name())


# Gunicorn / railpack entry: gunicorn run:app
app = create_application()

# Some platforms look for `application`
application = app

from app.yolo_weights import MODEL_PATH

print(f'(GenSpark) YOLO MODEL_PATH: {MODEL_PATH} exists={MODEL_PATH.is_file()}')
if not MODEL_PATH.is_file():
    print(
        '(GenSpark) WARNING: models/best.pt missing — '
        'commit vendor dashboard/models/best.pt and redeploy.'
    )


@app.shell_context_processor
def make_shell_context():
    from app import db
    from app.models import (
        User, Role, Vendor, Component, ComponentCategory,
        PcBuild, BuildComponent, Order, OrderItem, Payment, Shipment
    )
    return {
        'db': db,
        'User': User, 'Role': Role, 'Vendor': Vendor,
        'Component': Component, 'ComponentCategory': ComponentCategory,
        'PcBuild': PcBuild, 'BuildComponent': BuildComponent,
        'Order': Order, 'OrderItem': OrderItem, 'Payment': Payment, 'Shipment': Shipment
    }


if __name__ == '__main__':
    config_name = resolve_config_name()
    port = int(os.getenv('PORT', '5000'))
    debug = config_name == 'development'
    print(f'(GenSpark) Running from: {_script_dir}')
    print(f'(GenSpark) config={config_name} port={port} debug={debug}')
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug,
        use_reloader=debug,
    )
