"""
GenSpark Backend - Refactoring Documentation

This file documents the architectural improvements made to the backend.

## Architecture Overview

The backend now follows a clean three-layer architecture pattern:

### Layer 1: Routes (API Blueprints)
- `app/api/routes/*.py` - Define HTTP endpoints and request/response handling
- Responsibilities: Parse requests, call controllers, return responses
- Pattern: Flask Blueprints for modular organization
- Key files:
  - `health_routes.py` - Health checks (/health, /ping)
  - `db_routes.py` - Database verification (/db-verify)
  - `build_routes.py` - PC build endpoints (/recommend-build, /create-build)
  - `detect_routes.py` - YOLO detection (/detect/component, /detect/model)
  - `component_routes.py` - Component catalog (/components/search, /components/<id>/vendors)

### Layer 2: Controllers
- `app/api/controllers/*.py` - Business logic orchestration
- Responsibilities: Validate input, coordinate services, handle errors
- Pattern: One controller per feature area
- Key files:
  - `build_controller.py` - Build recommendation and creation logic
  - `component_controller.py` - Component catalog operations
  - `detection_controller.py` - Image detection orchestration

### Layer 3: Services
- `app/api/services/*.py` - Database operations and external integrations
- Responsibilities: Database queries, API calls, data transformation
- Pattern: Thin data access layer
- Key files:
  - `build_service.py` - Build recommendation and persistence
  - `component_service.py` - Component catalog queries
  - `detection_service.py` - YOLO model access

### Core Infrastructure
- `app/core/responses.py` - Standardized JSON response formatting
  - `success()` - Return success responses
  - `error()` - Return error responses
  - Helpers: `created()`, `not_found()`, `bad_request()`, etc.

- `app/core/database.py` - Database connection and pool management
  - `get_db_connection()` - Get pooled MySQL connection
  - `resolve_db_config()` - Environment variable resolution
  - `probe_db_connection()` - Health check

- `app/common/constants.py` - Application-wide constants
  - YOLO class names
  - Build configuration
  - Component categories
  - CORS origins

- `app/factory.py` - Flask application factory
  - `create_app()` - Create and configure Flask app
  - Blueprint registration
  - Error handlers

## Response Format

All API endpoints now return standardized JSON:

### Success Response (200, 201, etc.)
```json
{
  "success": true,
  "message": "Human-readable message",
  "data": {...}
}
```

### Error Response (400, 404, 500, etc.)
```json
{
  "success": false,
  "message": "Error description",
  "error_code": "MACHINE_READABLE_CODE",
  "details": {...}
}
```

## Migration Guide

### From Old app.py to New Structure

**Before (Monolithic):**
```python
# app.py - 97.6 KB
@app.route('/api/recommend-build', methods=['POST'])
def recommend_build():
    data = _parse_json_body()
    # 200+ lines of logic here
    return _json_ok(...)
```

**After (Modular):**
```python
# app/api/routes/build_routes.py
@bp.route('/recommend-build', methods=['POST'])
def recommend_build():
    data = request.get_json() or {}
    result = build_controller.get_build_recommendation(data)
    return success(data=result)

# app/api/controllers/build_controller.py
def get_build_recommendation(payload: dict):
    recommendation = build_service.generate_recommendation(payload)
    return {'markdown': recommendation.get('markdown'), ...}

# app/api/services/build_service.py
def generate_recommendation(payload: dict):
    # Business logic here
    return {'markdown': '...', 'model_id': '...'}
```

## Benefits of New Architecture

✅ **Separation of Concerns**: Each layer has a single responsibility
✅ **Testability**: Services can be tested independently
✅ **Maintainability**: Logic is organized by feature, not by type
✅ **Scalability**: Easy to add new endpoints without touching existing code
✅ **Consistency**: Standardized response formats and error handling
✅ **Readability**: Clear data flow: Routes → Controllers → Services → Database
✅ **Reusability**: Services can be called from multiple controllers
✅ **Documentation**: Type hints and docstrings make intent clear

## Implementation Status

### Completed ✅
- [x] Core infrastructure (responses, database, constants)
- [x] Route blueprints structure
- [x] Controller interfaces
- [x] Service stubs
- [x] App factory

### In Progress 🔄
- [ ] Migrate existing app.py logic to services
- [ ] Implement build service with configurator integration
- [ ] Implement component service with database queries
- [ ] Implement detection service with YOLO integration
- [ ] Add error handling tests
- [ ] Add integration tests

### Future 📋
- [ ] Add OpenAPI/Swagger documentation
- [ ] Add request validation (marshmallow/pydantic)
- [ ] Add unit tests for each service
- [ ] Add authentication layer
- [ ] Add logging and monitoring
- [ ] Add database migrations (Alembic)

## Running the New Backend

```bash
# Option 1: Using new factory (recommended)
cd backend
python -c "from app.factory import create_app; app = create_app(); app.run()"

# Option 2: Using original app.py (still works)
python app.py
```

Both versions will work simultaneously during transition period.

## File Structure

```
backend/
├── app/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── responses.py      # Response formatting
│   │   └── database.py       # Connection management
│   ├── common/
│   │   ├── __init__.py
│   │   └── constants.py      # App constants
│   └── api/
│       ├── __init__.py
│       ├── routes/
│       │   ├── __init__.py
│       │   ├── health_routes.py
│       │   ├── db_routes.py
│       │   ├── build_routes.py
│       │   ├── detect_routes.py
│       │   └── component_routes.py
│       ├── controllers/
│       │   ├── __init__.py
│       │   ├── build_controller.py
│       │   ├── component_controller.py
│       │   └── detection_controller.py
│       └── services/
│           ├── __init__.py
│           ├── build_service.py
│           ├── component_service.py
│           └── detection_service.py
├── app.py                    # Original (still works)
├── factory.py               # NEW: App factory entry point
├── requirements.txt
├── .env
└── best.pt                  # YOLO weights
```

## Next Steps

1. Test new factory with simple requests
2. Gradually migrate endpoints from app.py
3. Add comprehensive logging
4. Add unit tests
5. Migrate frontend to use new response formats
6. Deploy and monitor
"""