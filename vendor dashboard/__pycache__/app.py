from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)   # React ko allow karega

@app.route('/dashboard-data', methods=['GET'])
def dashboard():
    data = {
        "users": 120,
        "orders": 45,
        "revenue": 5600
    }
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)