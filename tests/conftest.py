"""Test isolation from a developer's own credentials.

`make test` loads `.env` now, which is what a reader filling it in expects. It
also means a machine with real keys in `.env` would run the suite against live
Terac and a live model -- slow, billable, and non-deterministic, with failures
that appear on one laptop and nowhere else.

Every live key is cleared for every test. A test that wants a tier stubs it
explicitly; nothing reaches the network by default.
"""

from __future__ import annotations

import pytest

LIVE_KEYS = (
    "TERAC_API_KEY",
    "TERAC_API_BASE",
    "STRIPE_RESTRICTED_KEY",
    "STRIPE_API_BASE",
    "MODEL_API_KEY",
    "MODEL_API_BASE",
    "MODEL_NAME",
)


@pytest.fixture(autouse=True)
def no_live_credentials(monkeypatch):
    for key in LIVE_KEYS:
        monkeypatch.delenv(key, raising=False)
