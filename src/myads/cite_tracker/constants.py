"""Constants for the citation tracker."""

import os
from pathlib import Path


def get_default_database_path() -> str:
    """
    Get the default database path.

    Priority:
    1. MYADS_DATABASE_PATH environment variable
    2. XDG_DATA_HOME/myads/database.db (if XDG_DATA_HOME is set)
    3. ~/.local/share/myads/database.db (XDG default)
    4. ~/myADS_database.db (legacy fallback)

    Returns
    -------
    str
        Path to the database file
    """
    # Check environment variable first
    env_path = os.environ.get("MYADS_DATABASE_PATH")
    if env_path:
        return env_path

    # Use XDG Base Directory spec
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        data_dir = Path(xdg_data_home) / "myads"
    else:
        data_dir = Path.home() / ".local" / "share" / "myads"

    # Create directory if it doesn't exist
    data_dir.mkdir(parents=True, exist_ok=True)

    # Return the database path in the data directory
    xdg_path = data_dir / "database.db"

    # Check if legacy database exists
    legacy_path = Path.home() / "myADS_database.db"
    if legacy_path.exists() and not xdg_path.exists():
        # Use legacy path if it exists and XDG path doesn't
        return str(legacy_path)

    return str(xdg_path)


DEFAULT_DATABASE_PATH = get_default_database_path()
