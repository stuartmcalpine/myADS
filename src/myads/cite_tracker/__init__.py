import os

import toml

from .check import check
from .report import report
from .tracked_authors import *

# This is where the user database and cite tracker information goes.
data_dir = os.path.join(os.path.dirname(__file__), "data")
AUTHOR_LIST_PATH = os.path.join(data_dir, "tracked_authors.toml")
ADS_TOKEN_PATH = os.path.join(data_dir, ".my_ads_token")


def create_data_dir():
    """ Create the data directory to store author list and cites. """
    if not os.path.isdir(data_dir):
        os.makedirs(data_dir)


def load_author_list() -> dict:
    """
    Load list of tracked authors.

    Returns
    -------
    authors : dict
    """

    if os.path.isfile(AUTHOR_LIST_PATH):
        return toml.load(AUTHOR_LIST_PATH)
    else:
        return None


def load_ads_token() -> str:
    """
    Load stored ADS token.

    If it hasn't been set yet, raise an exception.

    Returns
    -------
    token : str
    """

    if not os.path.isfile(ADS_TOKEN_PATH):
        raise Exception(
            "ADS token has not been set yet, do 'myads token update <token>'"
        )

    with open(ADS_TOKEN_PATH, "r") as f:
        token = f.readline()

    return token


def update_ads_token(token):
    """
    Update the logged ADS API token.

    Parameters
    ----------
    token : str
    """

    create_data_dir()

    with open(ADS_TOKEN_PATH, "w") as f:
        f.write(token)

    print(f"Updated ADS token to {token}")


def get_author_database_path(author_id) -> str:
    """ Get full path to tracked authors cite tracking database. """

    return os.path.join(data_dir, f"{author_id}_database.toml")
