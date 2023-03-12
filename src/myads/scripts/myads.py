import argparse
import os
from datetime import datetime

import toml
from tabulate import tabulate

import myads
from myads.query import ADSQueryWrapper

# Set up ADS Query object.
query = ADSQueryWrapper()


def _load_database(_DATABASE_FILE):
    """ Load the database file. """

    with open(_DATABASE_FILE, "r") as file:
        data = toml.load(file)

    return data


def _save_database(data, _DATABASE_FILE):
    """ Save/update database file. """

    with open(_DATABASE_FILE, "w") as outfile:
        toml.dump(data, outfile)
    print(f"Saved {_DATABASE_FILE}.")


def _refresh_database(data):
    """ Get the most up to date cites to our papers. """

    database = {}

    for paper in data.papers:
        tmp = query.citations(paper.bibcode)
        database[paper.bibcode] = {}
        database[paper.bibcode]["title"] = paper.title
        database[paper.bibcode]["citations"] = tmp.get_all("bibcode")

    return database


def _print_new_cites(database, new_cite_papers):
    BOLD = "\033[1m"
    OKCYAN = "\033[96m"
    ENDC = "\033[0m"

    for bibcode in new_cite_papers.keys():
        new = new_cite_papers[bibcode]

        if len(new) > 0:
            print(
                "\n"
                + f"{BOLD}{OKCYAN}{len(new)} new cite(s) for {database[bibcode]['title'][0]}{ENDC}"
            )
            table = []
            for paper in new:
                table.append(
                    [
                        paper.title[0],
                        paper.author,
                        paper.date[:10],
                        f"https://ui.adsabs.harvard.edu/abs/{paper.bibcode}/abstract",
                    ]
                )

            print(
                tabulate(
                    table,
                    tablefmt="grid",
                    maxcolwidths=[40, 40, None, 20],
                    headers=["Title", "Authors", "Date", "Bibcode"],
                )
            )


def _check():
    """
    Check against our personal database to see if there are any new cites to
    our papers.
    """

    # My information.
    _FIRST_NAME = myads.config["_FIRST_NAME"]
    _LAST_NAME = myads.config["_LAST_NAME"]
    _DATABASE_FILE = myads.config["_DATABASE_FILE"]

    # Query my papers.
    data = query.get(
        q=f"first_author:{_LAST_NAME},{_FIRST_NAME}", fl="title,citation_count,bibcode"
    )

    # To store new cites.
    new_cite_list = {}

    if os.path.isfile(_DATABASE_FILE):
        # Load existing database.
        database = _load_database(_DATABASE_FILE)

        # Is there a new paper since last time thats not in the database?
        for bibcode in data.get_all("bibcode"):
            if bibcode not in database.keys():
                raise NotImplementedError(f"New paper {bibcode}, implement this")

        new_entry = False

        # Loop over each paper in database.
        for bibcode in database.keys():
            new_cite_list[bibcode] = []

            # Get up-to-date cites for this paper.
            tmp_query_data = query.citations(
                bibcode, fl="title,bibcode,author,date,doi"
            )

            # Compare to database, and see if any new cites have happened since
            # last check.
            for paper in tmp_query_data.papers:

                if paper.bibcode not in database[bibcode]["citations"]:
                    new_cite_list[bibcode].append(paper)

                    # Record we found a new paper (to refresh the database later)
                    new_entry = True

            # Update database.
            database[bibcode]["citations"] = tmp_query_data.get_all("bibcode")

        # Report new cites.
        _print_new_cites(database, new_cite_list)

        # Update database with new entries.
        if new_entry:
            _save_database(database, _DATABASE_FILE)
    else:
        # Create new database (first time run).
        print("First time run, creating new ADS database file...")
        _save_database(_refresh_database(data), _DATABASE_FILE)


def _report():
    """
    Query the user as first author, and print the current citation count. This
    uses the details in the profile set by "myads --init".
    """

    # My information.
    _FIRST_NAME = myads.config["_FIRST_NAME"]
    _LAST_NAME = myads.config["_LAST_NAME"]

    # Query my papers.
    data = query.get(
        q=f"first_author:{_LAST_NAME},{_FIRST_NAME}",
        fl="title,citation_count,pubdate,bibcode",
    )

    # Loop over each of my papers and print the number of cites.
    table = []
    for paper in data.papers:
        table.append(
            [
                paper.title[0],
                f"{paper.citation_count} ({paper.citations_per_year:.1f})",
                paper.pubdate,
                paper.link,
            ]
        )

    print(
        tabulate(
            table,
            tablefmt="grid",
            maxcolwidths=[50, None, None, None],
            headers=["Title", "Citations\n(per year)", "Publication\nDate", "Bibcode"],
        )
    )


def _create_new_profile():
    """ Create ADS details about the user and store in config file. """

    first_name = input("Enter you first name: ")
    last_name = input("Enter your surname: ")
    ads_token = input("Enter your ADS API token: ")

    user_profile = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "myinfo.toml")
    )

    data = {
        "info": {
            "first_name": first_name,
            "last_name": last_name,
            "ads_token": ads_token,
        }
    }

    with open(user_profile, "w") as f:
        toml.dump(data, f)


def _init():
    """
    Sets (or updates) the users ADS details and stores them in a config file.
    """

    # Check and see if we have inited before.
    user_profile = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "myinfo.toml")
    )

    # Case where a user has created a profile before.
    if os.path.isfile(user_profile):
        print("User profile already exists:")
        myinfo = toml.load(user_profile)
        for att in myinfo["info"].keys():
            print(f" - {att}: {myinfo['info'][att]}")

        # Want to update the details?
        ans = input("Overwrite current ADS details? [y/n]: ")
        if ans.lower() == "y":
            _create_new_profile()

    # Case where we don't have a profile.
    else:
        _create_new_profile()


def main():

    # Command line options.
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--init",
        help="Initialise your ADS details (must be run once)",
        action="store_true",
    )
    group.add_argument(
        "--report", help="Report your current citation statistics", action="store_true"
    )
    group.add_argument(
        "--check", help="Check for any new cites to your papers", action="store_true"
    )
    args = parser.parse_args()

    # Create or update user ADS details
    if args.init:
        _init()

    # Report users current citation statistics
    elif args.report:
        _report()

    # Check if any new cites have been made to the user since last call
    elif args.check:
        _check()
