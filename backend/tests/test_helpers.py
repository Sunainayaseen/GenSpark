"""White-box unit tests for the AI-build helper functions.

These target pure logic (no DB, no network):
  * _parse_budget_pkr      — budget string parsing       (WB-BUD-01..06)
  * _is_greeting_only_message — greeting vs build intent  (WB-GRT-01..03)

Run from the backend/ folder:  python -m pytest
"""
import pytest

from app.api.ai_build_routes import _parse_budget_pkr, _is_greeting_only_message


# --- WB-BUD: budget parsing -------------------------------------------------

@pytest.mark.parametrize('raw, expected', [
    ('1.2 lakh', 120_000),   # WB-BUD-01  lakh keyword path
    ('120k', 120_000),       # WB-BUD-02  "k" suffix path
    ('150000', 150_000),     # WB-BUD-03  plain integer path
    ('2', 200_000),          # WB-BUD-04  bare small number -> lakh assumption
    ('60000 PKR', 60_000),   # WB-BUD-05  currency suffix stripped
])
def test_parse_budget_pkr_values(raw, expected):
    assert _parse_budget_pkr(raw) == expected


@pytest.mark.parametrize('raw', ['', '   ', 'abc', None])
def test_parse_budget_pkr_invalid_returns_none(raw):
    """WB-BUD-06 — empty / non-numeric input is handled gracefully (None)."""
    assert _parse_budget_pkr(raw) is None


# --- WB-GRT: greeting detection ---------------------------------------------

@pytest.mark.parametrize('message', ['hi', 'hello there', 'salam'])
def test_greeting_only_is_true(message):
    """WB-GRT-01 — a bare greeting does NOT trigger a build."""
    assert _is_greeting_only_message(message) is True


def test_build_request_is_not_greeting():
    """WB-GRT-02 — an explicit build request proceeds to recommend."""
    assert _is_greeting_only_message('200k gaming build') is False


def test_mixed_message_detects_build_intent():
    """WB-GRT-03 — greeting + build request is treated as a build request."""
    assert _is_greeting_only_message('hi, suggest a 100k build') is False
