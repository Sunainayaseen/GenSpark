# GenSpark - Application Entry Point (NOT CRUD - ye vendor dashboard hai)
import os
import sys

# Always run from this script's folder (vendor dashboard) so "app" and "config" are found
_script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(_script_dir)
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

from app import create_app, db

# So you know this is GenSpark, not CRUD
print("(GenSpark) Running from:", _script_dir)

app = create_app(os.getenv('FLASK_ENV', 'development'))


@app.shell_context_processor
def make_shell_context():
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
    app.run(host='0.0.0.0', port=5000, debug=True)
