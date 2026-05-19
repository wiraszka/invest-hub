import os

import pytest


@pytest.fixture(autouse=True)
def _stub_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide dummy values for env vars so service functions don't raise before mocks fire."""
    for key, value in {
        "FMP_API_KEY": "test_fmp_key",
        "FINNHUB_API_KEY": "test_finnhub_key",
        "TD_API_KEY": "test_td_key",
        "DATABASE_URL": "postgresql://test:test@localhost/test",
    }.items():
        if not os.environ.get(key):
            monkeypatch.setenv(key, value)
