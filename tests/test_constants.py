"""Tests for constants module, particularly database path resolution."""

import os
import tempfile
from pathlib import Path
from myads.cite_tracker.constants import get_default_database_path


def test_database_path_env_variable(temp_env):
    """Test that MYADS_DATABASE_PATH environment variable takes precedence."""
    custom_path = "/custom/path/myads.db"
    temp_env.setenv("MYADS_DATABASE_PATH", custom_path)

    path = get_default_database_path()
    assert path == custom_path


def test_database_path_xdg_data_home(temp_env, tmp_path, monkeypatch):
    """Test XDG_DATA_HOME is used when set."""
    xdg_home = tmp_path / "xdg_data"
    xdg_home.mkdir()
    temp_env.setenv("XDG_DATA_HOME", str(xdg_home))

    # Mock Path.home() to prevent legacy path from existing
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "fake_home")

    path = get_default_database_path()
    expected = str(xdg_home / "myads" / "database.db")
    assert path == expected


def test_database_path_xdg_default(temp_env, tmp_path, monkeypatch):
    """Test default XDG path when XDG_DATA_HOME not set."""
    # Mock Path.home() to use tmp_path
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    path = get_default_database_path()
    expected = str(tmp_path / ".local" / "share" / "myads" / "database.db")
    assert path == expected


def test_database_path_legacy_exists(temp_env, tmp_path, monkeypatch):
    """Test that legacy database location is used if it exists."""
    # Mock Path.home() to use tmp_path
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    # Create legacy database file
    legacy_path = tmp_path / "myADS_database.db"
    legacy_path.touch()

    path = get_default_database_path()
    assert path == str(legacy_path)


def test_database_path_creates_directory(temp_env, tmp_path, monkeypatch):
    """Test that the data directory is created if it doesn't exist."""
    # Mock Path.home() to use tmp_path
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    path = get_default_database_path()

    # Check that directory was created
    data_dir = tmp_path / ".local" / "share" / "myads"
    assert data_dir.exists()
    assert data_dir.is_dir()
