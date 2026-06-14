"""
Minimal Flask server – no DB, no app package. Use to verify port 5000 works.
Run: python run_simple.py   then open http://127.0.0.1:5000/ or http://127.0.0.1:5000/health
If you see "OK" here but not with run.py, the issue is in the main app (create_app).
"""
from flask import Flask
app = Flask(__name__)

@app.route('/')
def index():
    return '<!DOCTYPE html><html><body><h1>Flask OK</h1><p><a href="/health">/health</a></p></body></html>'

@app.route('/health')
def health():
    return 'OK', 200, {'Content-Type': 'text/plain; charset=utf-8'}

if __name__ == '__main__':
    print('Minimal server. Open http://127.0.0.1:5000 or http://127.0.0.1:5000/health')
    app.run(host='0.0.0.0', port=5000, debug=False)
