"""Pytest configuration and fixtures."""

import os
import tempfile
import pytest
from pathlib import Path


@pytest.fixture
def temp_db():
    """Create a temporary database file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    yield db_path

    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def temp_env(monkeypatch):
    """Provide a clean environment for testing."""
    # Clear any existing myADS environment variables
    monkeypatch.delenv("MYADS_DATABASE_PATH", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    return monkeypatch


@pytest.fixture
def mock_ads_token():
    """Provide a fake ADS token for testing."""
    return "fake-ads-token-for-testing-12345"
