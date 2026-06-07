"""
CLI bridge so vendor dashboard (port 5000) can call AI routes from backend/app.py
without importing mysql.connector into the vendor venv.

Usage:
  python ai_api_cli.py recommend-build  < payload.json
  python ai_api_cli.py create-build     < payload.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv

load_dotenv(BACKEND_DIR / '.env')

from app import app  # noqa: E402


def _run(path: str, payload: dict | None = None, *, method: str = 'POST') -> tuple[int, dict]:
    client = app.test_client()
    if method.upper() == 'GET':
        response = client.get(path)
    else:
        response = client.post(path, json=payload or {})
    try:
        body = response.get_json(silent=True) or {}
    except Exception:
        body = {'success': False, 'error': response.get_data(as_text=True)[:500]}
    if not isinstance(body, dict):
        body = {'success': False, 'error': str(body)}
    return response.status_code, body


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({'success': False, 'error': 'Usage: ai_api_cli.py <recommend-build|create-build>'}))
        return 1

    command = sys.argv[1].strip().lower()
    routes = {
        'recommend-build': '/api/recommend-build',
        'create-build': '/api/create-build',
        'ai-status': '/api/ai-status',
    }
    path = routes.get(command)
    if not path:
        print(json.dumps({'success': False, 'error': f'Unknown command: {command}'}))
        return 1

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(json.dumps({'success': False, 'error': f'Invalid JSON stdin: {exc}'}))
        return 1

    if not isinstance(payload, dict):
        print(json.dumps({'success': False, 'error': 'JSON body must be an object'}))
        return 1

    method = 'GET' if command == 'ai-status' else 'POST'
    status, body = _run(path, payload if method == 'POST' else None, method=method)
    print(json.dumps(body))
    if command == 'ai-status':
        return 0 if status < 400 else 1
    return 0 if status < 400 and body.get('success') else 1


if __name__ == '__main__':
    raise SystemExit(main())
