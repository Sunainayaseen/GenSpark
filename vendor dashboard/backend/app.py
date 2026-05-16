from flask import Flask, jsonify, request
from flask_cors import CORS  # Make sure CORS is imported

app = Flask(__name__)
CORS(app)  # Just call CORS on app; no need to assign

# ---------------------------------------------------------------------------
# Root – browser me 127.0.0.1:5000 open karne par valid page
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"><title>Flask Backend</title></head>
    <body style="font-family:sans-serif; padding:2rem; max-width:600px;">
        <h1>Flask API is running</h1>
        <p>Ye <strong>backend API</strong> hai – sirf JSON data deta hai.</p>
        <ul>
            <li><a href="/api/message">/api/message</a></li>
            <li><a href="/api/admin/dashboard">/api/admin/dashboard</a></li>
            <li><a href="/api/vendor/dashboard">/api/vendor/dashboard</a></li>
        </ul>
        <p style="color:#666; margin-top:2rem;">
            <strong>Admin / Vendor HTML UI</strong> ke liye parent folder se run karo:<br>
            <code>cd "vendor dashboard" &amp;&amp; python run.py</code><br>
            Phir <a href="http://127.0.0.1:5000/admin/dashboard">/admin/dashboard</a> aur <a href="http://127.0.0.1:5000/vendor/dashboard">/vendor/dashboard</a>.
        </p>
    </body>
    </html>
    '''

# ---------------------------------------------------------------------------
# Placeholder HTML pages – React iframe inhe load karta hai.
# Full admin/vendor UI ke liye run.py chalao (vendor dashboard folder se).
# ---------------------------------------------------------------------------
def _html_page(title, message, link_path):
    return f'''
    <!DOCTYPE html>
    <html><head><meta charset="utf-8"><title>{title}</title></head>
    <body style="font-family:sans-serif; padding:2rem; max-width:560px;">
        <h1>{title}</h1>
        <p>{message}</p>
        <p>Full Python (Flask) UI ke liye <strong>run.py</strong> chalao:</p>
        <p><code>cd "vendor dashboard"<br>python run.py</code></p>
        <p>Phir yehi URL open karo: <a href="http://127.0.0.1:5000{link_path}">http://127.0.0.1:5000{link_path}</a></p>
    </body></html>
    '''

@app.route('/admin')
@app.route('/admin/dashboard')
def admin_dashboard_page():
    return _html_page(
        'Admin Dashboard',
        'Ye sirf API backend hai. Admin ka full HTML dashboard yahan nahi hai.',
        '/admin/dashboard'
    ), 200

@app.route('/vendor')
@app.route('/vendor/dashboard')
def vendor_dashboard_page():
    return _html_page(
        'Vendor Dashboard',
        'Ye sirf API backend hai. Vendor ka full HTML dashboard yahan nahi hai.',
        '/vendor/dashboard'
    ), 200

# ---------------------------------------------------------------------------
# /api/login yahan NAHI hai – sirf run.py (main app) me hai
# ---------------------------------------------------------------------------
@app.route('/api/login', methods=['POST', 'OPTIONS'])
def api_login_placeholder():
    if request.method == 'OPTIONS':
        return '', 204
    return jsonify({
        'success': False,
        'error': 'Ye backend/app.py hai. Login ke liye run.py chalao: "vendor dashboard" folder me START-FLASK.bat (ya python run.py). backend folder me py app.py band karo.',
    }), 400

# ---------------------------------------------------------------------------
# Health / test
# ---------------------------------------------------------------------------
@app.route('/api/message', methods=['GET'])
def get_message():
    return jsonify({"message": "Hello Sunaina from Flask backend!"})

# ---------------------------------------------------------------------------
# Admin Dashboard API – React isliye data yahan se lega
# ---------------------------------------------------------------------------
@app.route('/api/admin/dashboard', methods=['GET'])
def admin_dashboard():
    return jsonify({
        "users": 120,
        "vendors": 35,
        "orders": 240,
        "revenue": 15000,
    })

# ---------------------------------------------------------------------------
# Vendor Dashboard API – React vendor stats yahan se lega
# ---------------------------------------------------------------------------
@app.route('/api/vendor/dashboard', methods=['GET'])
def vendor_dashboard():
    # Optional: ?vendor_id=1 se specific vendor ka data (future use)
    vendor_id = request.args.get('vendor_id', type=int)
    return jsonify({
        "total_orders": 120,
        "total_products": 45,
        "revenue": 5000,
        "vendor_id": vendor_id,
    })

if __name__ == "__main__":
    # Backend se chalane par MAIN app (run.py) start karo – isi me /api/login hai
    import sys
    import os
    import subprocess
    parent = os.path.join(os.path.dirname(__file__), "..")
    os.chdir(parent)
    sys.exit(subprocess.run([sys.executable, "run.py"]).returncode)