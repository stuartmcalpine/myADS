import os

import myads.cite_tracker as cite_tracker
import toml
from myads.query import ADSQueryWrapper
from tabulate import tabulate


def _refresh_database(data, query) -> dict:
    """
    Get the most up-to-date cites to our papers.

    Returns
    -------
    database : dict
        Details the up-to-date cites of our papers
    query : ADSQueryWrapper object
    """

    database = {}

    for paper in data.papers:
        tmp = query.citations(paper.bibcode)
        database[paper.bibcode] = {}
        database[paper.bibcode]["title"] = paper.title
        database[paper.bibcode]["citations"] = tmp.get_all("bibcode")

    return database


def _print_new_cites(database, new_cite_papers):
    """
    Print any new citations to our papers since last call.

    Parameters
    ----------
    database : dict
        Current papers that cited our papers
    new_cite_papers : dict
        New papers added to database (the ones we are printing here)
    """

    # Colours for the terminal.
    BOLD = "\033[1m"
    OKCYAN = "\033[96m"
    ENDC = "\033[0m"

    # Loop over each of our papers.
    for bibcode in new_cite_papers.keys():

        # Do we have any new cites?
        new = new_cite_papers[bibcode]

        if len(new) > 0:

            # Print new cites.
            print(
                "\n",
                f"{BOLD}{OKCYAN}{len(new)} new cite(s) for"
                f"{database[bibcode]['title'][0]}{ENDC}",
            )
            table = []
            for paper in new:
                table.append(
                    [paper.title[0], paper.author, paper.date[:10], paper.link,]
                )

            print(
                tabulate(
                    table,
                    tablefmt="grid",
                    maxcolwidths=[40, 40, None, 20],
                    headers=["Title", "Authors", "Date", "Bibcode"],
                )
            )


def _save_database(path, data):
    """ Save the user database. """

    with open(path, "w") as f:
        toml.dump(data, f)


def check():
    """
    Check against our personal database to see if there are any new cites to
    our papers since the last call.
    """

    # Load the user database.
    users = toml.load(cite_tracker.USER_DATABASE)
    assert (
        "ads_token" in users["metadata"].keys()
    ), "No ADS API token has been added yet, run 'myads --set_ads_token <TOKEN>'"

    # Query object.
    query = ADSQueryWrapper(users["metadata"]["ads_token"])

    # Loop over each user in the database.
    for i in range(users["metadata"]["uid_count"]):

        FIRST_NAME = users[f"user{i+1}"]["first_name"]
        LAST_NAME = users[f"user{i+1}"]["last_name"]
        ORCID = users[f"user{i+1}"]["orcid"]
        print(f"\nChecking new cites for {FIRST_NAME} {LAST_NAME}...")

        # Query.
        if ORCID == "":
            data = query.get(
                q=f"first_author:{LAST_NAME},{FIRST_NAME}",
                fl="title,citation_count,pubdate,bibcode",
            )
        else:
            data = query.get(
                q=f"orcid_pub:{ORCID} OR orcid_user:{ORCID} OR orcid_other:{ORCID} first_author:{LAST_NAME},{FIRST_NAME}",
                fl="title,citation_count,pubdate,bibcode",
            )

        # Got a bad status code.
        if data is None:
            return

        if len(data.papers) == 0:
            print(f"No paper hits for {FIRST_NAME} {LAST_NAME}")
            continue

        # To store new cites.
        new_cite_list = {}

        # Path to users database.
        user_database = cite_tracker.get_user_database_path(i + 1)

        # Does the user already have a database?
        if os.path.isfile(user_database):
            # Load existing database.
            database = toml.load(user_database)

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
                _save_database(user_database, database)
            else:
                print(f"No new cites for {FIRST_NAME} {LAST_NAME}")
        else:
            # Create new database (first time run).
            print(
                f"First time run for {FIRST_NAME} {LAST_NAME}, "
                f"creating new ADS cite tracker database file..."
            )
            _save_database(user_database, _refresh_database(data, query))
