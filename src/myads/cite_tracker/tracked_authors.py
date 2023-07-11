import os

import myads.cite_tracker as cite_tracker
import toml

__all__ = ["add_tracked_author", "list_tracked_authors", "remove_tracked_author"]


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


def _save_user_database(data):
    """ Save the user database. """

    with open(cite_tracker.AUTHOR_LIST_PATH, "w") as f:
        toml.dump(data, f)


def list_tracked_authors():
    """ Print all current tracked authors in the database. """

    authors = cite_tracker.load_author_list()

    if authors is None:
        raise Exception("No currently tracked authors to list, please add some")
    else:
        for att in authors.keys():
            if "author" in att:
                print(
                    f"{att}: {authors[att]['first_name']} {authors[att]['last_name']}",
                    f"(ORCID={authors[att]['orcid']})",
                )


def add_tracked_author():
    """ Track a new author. """

    # Create data directory if needed.
    cite_tracker.create_data_dir()

    # Get new profile information.
    new_user_data = _create_new_profile()

    # Get current list of tracked authors.
    authors = cite_tracker.load_author_list()

    if authors is not None:
        # Add new entry.
        authors["metadata"]["author_count"] += 1
        authors[f"author{authors['metadata']['author_count']}"] = new_user_data
    else:
        # First entry.
        authors = {"author1": new_user_data, "metadata": {"author_count": 1}}

    # Save database-
    _save_user_database(authors)


def remove_tracked_author(removeid):
    """
    Remove a user from the database.

    Parameters
    ----------
    removeid : int
        Author ID to remove from tracked author database
    """

    # Load current tracked author database.
    authors = cite_tracker.load_author_list()

    if authors is None:
        raise Exception("No tracked authors added yet to remove")

    # Remove user
    if f"author{removeid}" in authors.keys():
        print(f"Removing author{removeid}...")

        # Remove cite tracker database.
        # user_database = cite_tracker.get_user_database_path(f"user{removeid}")
        # if os.path.isfile(user_database):
        #    os.remove(user_database)
        #    print(f"Deleted {user_database}")

        # Remove from users list.
        del authors[f"author{removeid}"]
    else:
        raise Exception(f"No user {removeid} in database, check 'myads user list'")

    # Save database-
    _save_user_database(authors)
