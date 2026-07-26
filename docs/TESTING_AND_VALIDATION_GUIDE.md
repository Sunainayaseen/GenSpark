"""
GenSpark - Testing & Validation Guide

Complete guide for testing the refactored codebase and ensuring no functionality breaks.
"""

# =============================================================================
# TESTING STRATEGY
# =============================================================================

"""
## Three-Level Testing Approach

1. **Unit Tests** (Individual functions/methods)
   - Test services in isolation
   - Test helpers and utilities
   - Mock database calls
   - Quick to run, easy to debug

2. **Integration Tests** (API endpoints)
   - Test route → controller → service → database flow
   - Test with real database
   - Test error scenarios
   - Slower but catches real issues

3. **E2E Tests** (Full user workflows)
   - Test complete user journeys
   - Test UI interactions
   - Test across multiple pages
   - Slowest but most realistic

## Coverage Goals

- Backend: > 80% code coverage
- Frontend: > 70% component coverage
- Critical paths: 100% coverage

## Test Pyramid

        🔺 E2E (5%)
       🔺🔺 Integration (20%)
      🔺🔺🔺 Unit (75%)

Most tests should be unit tests (fast).
Some integration tests (moderate speed).
Few E2E tests (slow but comprehensive).
"""

# =============================================================================
# BACKEND TESTING SETUP
# =============================================================================

"""
## 1. Install Test Dependencies

pip install pytest pytest-cov pytest-mock faker factory-boy

## 2. Create test structure

backend/tests/
├── conftest.py           # Test configuration & fixtures
├── fixtures.py           # Test data factories
├── test_auth.py
├── test_builds.py
├── test_components.py
├── test_orders.py
├── test_payment.py
└── integration/
    ├── test_build_flow.py
    ├── test_order_flow.py
    └── test_payment_flow.py

## 3. Create conftest.py

```python
import pytest
from app.factory import create_app
from app.core.database import get_db_connection

@pytest.fixture
def app():
    '''Create app instance for testing'''
    app = create_app('testing')
    app.config['TESTING'] = True
    yield app

@pytest.fixture
def client(app):
    '''Test client'''
    return app.test_client()

@pytest.fixture
def db_connection():
    '''Database connection for tests'''
    conn = get_db_connection()
    yield conn
    conn.close()

@pytest.fixture(autouse=True)
def cleanup_db(db_connection):
    '''Clean up after each test'''
    cursor = db_connection.cursor()
    # Truncate test tables
    cursor.close()
```

## 4. Write Unit Tests

Example: test_components.py

```python
import pytest
from app.api.services import component_service

def test_search_components_returns_list():
    '''Search should return list of components'''
    result = component_service.search_catalog('cpu')
    assert isinstance(result, list)

def test_search_components_with_category_filter():
    '''Search with category should filter results'''
    result = component_service.search_catalog('intel', 'CPU')
    for item in result:
        assert item['category'] == 'CPU'

def test_find_component_by_name_exact_match():
    '''Should find component by exact name'''
    result = component_service.find_component_by_name('Intel Core i7')
    assert result is not None
    assert 'Intel Core i7' in result['name']

def test_find_component_by_name_fuzzy_match():
    '''Should do fuzzy match if exact match fails'''
    result = component_service.find_component_by_name('Core i7')
    assert result is not None

def test_search_components_limit(db_connection):
    '''Search should respect limit parameter'''
    result = component_service.search_catalog('cpu', limit=5)
    assert len(result) <= 5
```

## 5. Write Integration Tests

Example: test_build_flow.py

```python
def test_recommend_build_endpoint(client):
    '''Test POST /api/recommend-build'''
    response = client.post('/api/recommend-build', json={
        'message': 'gaming pc',
        'budget': 100000,
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] == True
    assert 'markdown' in data['data']

def test_create_build_endpoint(client):
    '''Test POST /api/create-build'''
    response = client.post('/api/create-build', json={
        'cpu': 'Intel Core i7',
        'ram': '32GB DDR4',
        'storage': 'Samsung 970 EVO 1TB',
    })
    assert response.status_code == 201
    data = response.get_json()
    assert 'build_id' in data['data']
```

## 6. Run Tests with Coverage

```bash
# Run all tests with coverage report
pytest --cov=app tests/ --cov-report=html

# Run specific test file
pytest tests/test_components.py -v

# Run with verbose output
pytest tests/ -v

# Run only tests matching pattern
pytest tests/ -k 'search' -v
```

## 7. Continuous Integration

Create .github/workflows/backend-tests.yml:

```yaml
name: Backend Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: 3.9
      - run: pip install -r Dashboard/requirements.txt
      - run: cd Dashboard && pytest --cov=app tests/
      - uses: codecov/codecov-action@v3
```
"""

# =============================================================================
# FRONTEND TESTING SETUP
# =============================================================================

"""
## 1. Install Test Dependencies

npm install --save-dev vitest @testing-library/react @testing-library/jest-dom
npm install --save-dev jsdom @vitest/ui

## 2. Configure vitest.config.js

```js
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './tests/setup.js',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
    },
  },
});
```

## 3. Create Test Setup

my-react-app/tests/setup.js:
```js
import '@testing-library/jest-dom';

// Mock fetch
global.fetch = vi.fn();

// Mock localStorage
const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
};
global.localStorage = localStorageMock;
```

## 4. Write Component Tests

Example: tests/components/BuilderCanvas.test.jsx

```js
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BuilderCanvas } from '@/components/builder/BuilderCanvas';

describe('BuilderCanvas', () => {
  it('renders builder interface', () => {
    render(<BuilderCanvas />);
    expect(screen.getByText(/builder/i)).toBeTruthy();
  });

  it('calls onBuildUpdate when parts change', async () => {
    const onUpdate = vi.fn();
    render(<BuilderCanvas onBuildUpdate={onUpdate} />);
    
    const cpuSelect = screen.getByLabelText(/cpu/i);
    await userEvent.selectOption(cpuSelect, 'Intel Core i7');
    
    expect(onUpdate).toHaveBeenCalled();
  });

  it('displays selected components', async () => {
    render(<BuilderCanvas />);
    
    const cpuSelect = screen.getByLabelText(/cpu/i);
    await userEvent.selectOption(cpuSelect, 'Intel Core i7');
    
    expect(screen.getByText('Intel Core i7')).toBeTruthy();
  });
});
```

## 5. Write Service Tests

Example: tests/services/componentService.test.js

```js
import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as componentService from '@/services/componentService';
import * as apiClient from '@/services/apiClient';

vi.mock('@/services/apiClient');

describe('componentService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('searchComponents calls API correctly', async () => {
    apiClient.default.get.mockResolvedValue({
      data: { components: [{ id: 1, name: 'CPU' }] },
    });

    const result = await componentService.searchComponents('cpu');
    
    expect(apiClient.default.get).toHaveBeenCalledWith(
      '/api/components/search',
      { params: { query: 'cpu' } }
    );
    expect(result).toHaveLength(1);
  });
});
```

## 6. Run Tests

```bash
# Run all tests
npm test

# Run with coverage
npm test -- --coverage

# Run with UI
npm test -- --ui

# Run specific test file
npm test BuilderCanvas

# Watch mode
npm test -- --watch
```
"""

# =============================================================================
# VALIDATION CHECKLIST
# =============================================================================

"""
## Before Deploying Refactored Code

### Backend Validation

Manual Testing:
  ⬜ Health check: curl http://localhost:5000/api/health
  ⬜ Database: curl http://localhost:5000/api/db-verify
  ⬜ Component search: curl 'http://localhost:5000/api/components/search?q=cpu'
  ⬜ Build recommendation: POST to /api/recommend-build
  ⬜ Image detection: POST to /api/detect/component
  ⬜ User registration: POST to /api/auth/register
  ⬜ User login: POST to /api/auth/login
  ⬜ Cart operations: POST/GET/DELETE /api/cart/*
  ⬜ Order creation: POST /api/orders
  ⬜ Stripe payment: POST /api/payment/intent

Endpoint Testing:
  ⬜ All routes return consistent response format
  ⬜ All errors include error_code
  ⬜ All timestamps are ISO format
  ⬜ All prices are in correct currency
  ⬜ All pagination works (limit, offset)
  ⬜ All filters work (category, price range)

Code Quality:
  ⬜ No import errors
  ⬜ No circular imports
  ⬜ No unused imports
  ⬜ No debug print statements
  ⬜ All TODOs documented
  ⬜ All functions have docstrings
  ⬜ All type hints correct

Database:
  ⬜ All tables exist
  ⬜ All foreign keys work
  ⬜ All indexes in place
  ⬜ No n+1 query problems
  ⬜ Connection pooling works

### Frontend Validation

Manual Testing:
  ⬜ Page loads without errors
  ⬜ Navigation works
  ⬜ Login/logout works
  ⬜ Cart add/remove works
  ⬜ Checkout completes
  ⬜ PC builder loads
  ⬜ Component search works
  ⬜ Image detection uploads
  ⬜ All forms submit
  ⬜ All buttons respond

Browser Compatibility:
  ⬜ Chrome latest
  ⬜ Firefox latest
  ⬜ Safari latest
  ⬜ Edge latest
  ⬜ Mobile (iOS Safari)
  ⬜ Mobile (Chrome Android)

Performance:
  ⬜ Page load < 3s
  ⬜ API response < 1s
  ⬜ Image upload < 5s
  ⬜ No memory leaks
  ⬜ No console errors

Accessibility:
  ⬜ All buttons keyboard accessible
  ⬜ All inputs have labels
  ⬜ All images have alt text
  ⬜ Color contrast passes WCAG
  ⬜ Screen reader works

Code Quality:
  ⬜ No console.log statements
  ⬜ No unused variables
  ⬜ No unused imports
  ⬜ PropTypes/TypeScript correct
  ⬜ Components are focused (< 300 LOC)
  ⬜ Proper error boundaries

### Vendor Dashboard Validation

  ⬜ Admin login works
  ⬜ Dashboard loads
  ⬜ User manager works
  ⬜ Component manager works
  ⬜ Order manager works
  ⬜ All CRUD operations work
  ⬜ Reports generate correctly
  ⬜ Database queries optimized

### Integration Testing

User Journeys:
  ⬜ Guest can browse components
  ⬜ Guest can search catalog
  ⬜ New user can register
  ⬜ User can login
  ⬜ User can build PC
  ⬜ User can add to cart
  ⬜ User can checkout
  ⬜ Payment processes successfully
  ⬜ Order confirmation sent
  ⬜ Admin can view orders
  ⬜ Vendor can view inventory

Edge Cases:
  ⬜ Empty search results
  ⬜ Invalid image upload
  ⬜ Out of stock item
  ⬜ Expired payment token
  ⬜ Concurrent requests
  ⬜ Large file upload
  ⬜ Network timeout
  ⬜ Database error recovery
"""

# =============================================================================
# DEPLOYMENT VALIDATION
# =============================================================================

"""
## Pre-Deployment Checklist

Code:
  ✅ All tests passing
  ✅ No TODOs or FIXMEs left
  ✅ All imports resolved
  ✅ No debug code
  ✅ Code formatted consistently
  ✅ Security vulnerabilities fixed

Backend:
  ✅ Environment variables documented
  ✅ Database migrations created
  ✅ Error handling for all endpoints
  ✅ Logging for important operations
  ✅ Rate limiting enabled
  ✅ CORS configured

Frontend:
  ✅ Build succeeds
  ✅ No console errors
  ✅ Production build optimized
  ✅ Service worker cache strategy defined
  ✅ Error boundaries in place

Infrastructure:
  ✅ Database backups configured
  ✅ Monitoring alerts set up
  ✅ SSL certificates valid
  ✅ Reverse proxy configured
  ✅ Log aggregation enabled

Documentation:
  ✅ API docs updated
  ✅ Deployment guide updated
  ✅ README current
  ✅ Architecture diagrams accurate

## Post-Deployment Monitoring

  ⬜ Monitor error rates
  ⬜ Check database performance
  ⬜ Monitor API response times
  ⬜ Check frontend error tracking
  ⬜ Verify backups running
  ⬜ Monitor disk space
  ⬜ Monitor memory usage
  ⬜ Check log files for errors
  ⬜ Monitor user feedback
  ⬜ Run smoke tests periodically
"""