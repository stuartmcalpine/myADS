import os

import myads.cite_tracker as cite_tracker
import toml


def _create_new_profile() -> dict:
    """ Get new user information. """

    first_name = input("Enter user first name: ")
    last_name = input("Enter user surname: ")
    orcid = input("Enter user orcid (optional): ")

    data = {
        "first_name": first_name,
        "last_name": last_name,
        "orcid": orcid,
    }

    return data


def _load_user_database() -> dict:
    """ Load the user database. """

    return toml.load(cite_tracker.USER_DATABASE)


def _save_user_database(data):
    """ Save the user database. """

    with open(cite_tracker.USER_DATABASE, "w") as f:
        toml.dump(data, f)


def list_users():
    """ Print all current users in the database. """

    data = _load_user_database()

    for att in data.keys():
        if "user" in att:
            print(
                f"{att}: {data[att]['first_name']} {data[att]['last_name']}",
                f"(ORCID={data[att]['orcid']})",
            )

    if "ads_token" in data["metadata"].keys():
        print(f"ADS token: {data['metadata']['ads_token']}")
    else:
        print("No ADS token added yet...")


def add_user():
    """ Adds new user to the database. """

    # Does the user database exist?
    database_exists = os.path.isfile(cite_tracker.USER_DATABASE)

    # Get new profile information.
    new_user_data = _create_new_profile()

    if database_exists:
        # Add new entry.
        data = _load_user_database()
        data["metadata"]["uid_count"] += 1
        data[f"user{data['metadata']['uid_count']}"] = new_user_data
    else:
        # First entry.
        data = {"user1": new_user_data, "metadata": {"uid_count": 1}}

    # Save database-
    _save_user_database(data)


def remove_user():
    """ Remove a user from the database. """

    # Does the user database exist?
    database_exists = os.path.isfile(cite_tracker.USER_DATABASE)
    assert database_exists, "No user database yet!"

    # Who to remove
    removeid = int(input("Enter user to remove (integer ID of user): "))

    # Load the user database.
    data = _load_user_database()

    # Remove user
    if f"user{removeid}" in data.keys():
        print(f"Removing user{removeid}...")

        # Remove cite tracker database.
        user_database = cite_tracker.get_user_database_path(f"user{removeid}")
        if os.path.isfile(user_database):
            os.remove(user_database)
            print(f"Deleted {user_database}")

        # Remove from users list.
        del data[f"user{removeid}"]
    else:
        print(
            f"No user{removeid} in database, try 'myads --list_users' to see current users"
        )

    # Save database-
    _save_user_database(data)


def set_ads_token(ads_token):
    """ Store the ADS API token """

    # Need the database first.
    database_exists = os.path.isfile(cite_tracker.USER_DATABASE)
    if not database_exists:
        print("No user database yet, first run --add_user")
        return

    # Load user database.
    data = _load_user_database()

    # Add the new API token.
    data["metadata"]["ads_token"] = ads_token
    print(f"Updated ADS API token to {ads_token}")

    # Save the database.
    _save_user_database(data)
