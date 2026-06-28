# How to Create & Use Your Own APIs – GenSpark

All API routes live under **`/api`** and return **JSON**.

---

## Quick test (browser or terminal)

- **http://127.0.0.1:5000/api/orders** – list orders  
- **http://127.0.0.1:5000/api/vendors** – list approved vendors  
- **http://127.0.0.1:5000/api/ping** – health check  

---

## Existing API endpoints

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/orders` | List orders (optional: `?status=pending` or `?limit=10`) |
| GET | `/api/orders/<id>` | Get one order by ID |
| GET | `/api/vendors` | List approved vendors |
| GET/POST | `/api/ping` | Health check; POST echoes JSON body |
| POST | `/api/echo` | Echo back the JSON body (for testing) |

---

## How to add your own API

### 1. Open `app/api/routes.py`

### 2. Add a new route

**GET example (read data):**

```python
@api_bp.route('/products', methods=['GET'])
def list_products():
    from app.models import Component  # or your model
    items = Component.query.limit(20).all()
    return jsonify({
        'success': True,
        'products': [
            {'id': p.id, 'name': p.name, 'price': float(p.price or 0)}
            for p in items
        ]
    })
```

**POST example (create/update):**

```python
@api_bp.route('/notify', methods=['POST'])
def notify():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'JSON required'}), 400
    # use data.get('key') and save to DB if needed
    return jsonify({'success': True, 'message': 'Done'})
```

### 3. Return JSON

- Use **`jsonify({...})`** for success.
- For errors: **`return jsonify({...}), 404`** or **`400`**, etc.

### 4. Query parameters (GET)

```python
status = request.args.get('status')       # ?status=pending
limit  = request.args.get('limit', type=int, default=20)
```

### 5. JSON body (POST)

```python
data = request.get_json(silent=True)
name = data.get('name') if data else None
```

---

## Calling your APIs

**Browser:**  
Open `http://127.0.0.1:5000/api/orders` (GET).

**PowerShell (GET):**

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/orders"
```

**PowerShell (POST with JSON):**

```powershell
$body = '{"name":"test"}' 
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/echo" -Method Post -Body $body -ContentType "application/json"
```

**Postman / Insomnia:**  
Method = GET or POST, URL = `http://127.0.0.1:5000/api/...`, for POST set Body → raw → JSON.

---

## Security note

- API blueprint is **exempt from CSRF** so external clients can POST.
- For production, add **API key** or **JWT** in headers and check it in your API routes.
