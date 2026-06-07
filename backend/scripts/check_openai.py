"""
Check OpenAI API key + live call (backend/.env).

Usage:
  backend\\.venv\\Scripts\\python.exe backend\\scripts\\check_openai.py
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv

load_dotenv(BACKEND / '.env', override=True)

from app import (  # noqa: E402
    OPENAI_API_KEY,
    _live_model_id,
    _openai_is_configured,
    _resolve_ai_provider,
)


def main() -> int:
    print('backend/.env loaded:', (BACKEND / '.env').is_file())
    print('AI_PROVIDER resolved:', _resolve_ai_provider())
    print('OPENAI_API_KEY set:', bool((OPENAI_API_KEY or '').strip()))
    print('openai_configured:', _openai_is_configured())

    if not _openai_is_configured():
        print('\nFix: OPENAI_API_KEY=sk-proj-... in backend/.env (no quotes).')
        print('Billing: https://platform.openai.com/settings/billing')
        return 1

    import os

    from openai import OpenAI

    model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
    print(f'\nLive test model={model} …')
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=model,
            messages=[{'role': 'user', 'content': 'Reply with exactly: OPENAI_OK'}],
            max_tokens=20,
        )
        text = (response.choices[0].message.content or '').strip()
        print('Response:', text[:120])
        if 'OPENAI_OK' in text.upper() or text:
            print('\nSUCCESS: OpenAI API is live.')
            print('Model for builds:', _live_model_id('openai'))
            return 0
        print('\nWARN: empty response')
        return 1
    except Exception as exc:
        msg = str(exc)
        print('ERROR:', msg[:400])
        if 'insufficient_quota' in msg.lower() or 'billing' in msg.lower():
            print('\nAdd at least $5 at https://platform.openai.com/settings/billing')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
