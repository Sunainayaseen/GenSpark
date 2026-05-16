"""
Example Python dashboard API (Flask) that works with the Vite React frontend.

Run:
  pip install flask flask-cors
  python python-dashboard-api-example.py

Then start the React app (npm run dev). The frontend will call /api/* which Vite
proxies to http://127.0.0.1:5000 (this script).
"""

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins=["http://localhost:5173"])  # Vite dev server

# Or mount under /api so paths match the proxy:
# In React you call fetch('/api/stats') -> Vite proxies to http://127.0.0.1:5000/api/stats
# So your Flask routes should be under /api

@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "service": "python-dashboard"})

@app.route("/api/stats")
def stats():
    return jsonify({
        "orders_today": 42,
        "revenue": 12500.50,
        "pending_validation": 7,
    })

@app.route("/api/orders")
def orders():
    # Example: return list of orders from your DB
    return jsonify({
        "orders": [
            {"id": "1", "status": "photos-uploaded", "created": "2025-02-26T10:00:00Z"},
        ]
    })

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
