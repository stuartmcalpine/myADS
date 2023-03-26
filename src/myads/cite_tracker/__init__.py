import os

from .check import check
from .report import report
from .users import add_user, list_users, remove_user, set_ads_token

# Make sure data directory exists.
# This is where the user database and cite tracker information goes.
data_dir = os.path.join(os.path.dirname(__file__), "data")
if not os.path.isdir(data_dir):
    os.makedirs(data_dir)

# User database.
USER_DATABASE = os.path.join(data_dir, "users.toml")

# Database that tracks cites.
def get_user_database_path(user_id) -> str:
    user_database = os.path.join(data_dir, f"{user_id}_database.toml")
    return user_database
