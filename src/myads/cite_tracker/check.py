import os

import myads.cite_tracker as cite_tracker
import toml
from myads.query import ADSQueryWrapper
from tabulate import tabulate


def _refresh_database(data, query) -> dict:
    """
    Get the most up-to-date cites to the users' papers.

    Parameters
    ----------
    data : 
    query : ADSQueryWrapper object

    Returns
    -------
    database : dict
        Details the up-to-date cites of the users' papers
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
                f"{BOLD}{OKCYAN}{len(new)} new cite(s) for "
                f"{database[bibcode]['title']}{ENDC}",
            )
            table = []
            for paper in new:
                table.append(
                    [paper.title, paper.author, paper.date[:10], paper.link,]
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
    """
    Save the users cite database.

    Parameters
    ----------
    path : str
        Path to user database file
    data : dict
        Users' cite information
    """

    with open(path, "w") as f:
        toml.dump(data, f)


def check(verbose):
    """
    Check against each users' personal database to see if there are any new
    cites to their papers since the last call.

    Parameters
    ----------
    verbose : bool  
        True for more output
    """

    # Load the user database.
    users = toml.load(cite_tracker.USER_DATABASE)
    assert (
        "ads_token" in users["metadata"].keys()
    ), "No ADS API token has been added yet, run 'myads --set_ads_token <TOKEN>'"

    # Query object.
    query = ADSQueryWrapper(users["metadata"]["ads_token"])

    # Loop over each user in the database.
    for att in users.keys():
        if "user" not in att:
            continue

        # Extract user information.
        FIRST_NAME = users[att]["first_name"]
        LAST_NAME = users[att]["last_name"]
        ORCID = users[att]["orcid"]
        print(f"\nChecking new cites for {FIRST_NAME} {LAST_NAME}...")

        # Query.
        if ORCID == "":
            # Query just by first name last name.
            data = query.get(
                q=f"first_author:{LAST_NAME},{FIRST_NAME}",
                fl="title,citation_count,pubdate,bibcode",
            )
        else:
            # Query also using the ORCID.
            q = (
                f"orcid_pub:{ORCID} OR orcid_user:{ORCID} OR orcid_other:{ORCID} "
                f"first_author:{LAST_NAME},{FIRST_NAME}"
            )
            data = query.get(q=q, fl="title,citation_count,pubdate,bibcode")

        # Got a bad status code?
        if data is None:
            return

        if len(data.papers) == 0:
            print(f"No paper hits for {FIRST_NAME} {LAST_NAME}")
            continue

        # To store new cites.
        new_cite_list = {}
        brand_new_paper = False

        # Path to this users' database.
        user_database = cite_tracker.get_user_database_path(att)

        # Does this user already have a database?
        if os.path.isfile(user_database):
            # Load existing database.
            database = toml.load(user_database)

            # Is there a new paper for this user that's not in the database?
            for tmp_paper in data.papers:
                if tmp_paper.bibcode not in database.keys():
                    brand_new_paper = True
                    print(
                        f"New paper for {FIRST_NAME} {LAST_NAME} ({bibcode})",
                        f"adding to database...",
                    )

                    # Add new entry to database.
                    database[bibcode] = {"title": tmp_paper.title, "citations": []}

            new_entry = False

            # Loop over each paper in database.
            for bibcode in database.keys():
                if verbose:
                    print(f"Checking {bibcode}...")
                new_cite_list[bibcode] = []

                # Get up-to-date cites for this paper.
                tmp_query_data = query.citations(
                    bibcode, fl="title,bibcode,author,date,doi"
                )

                # Check the query was successful
                if tmp_query_data is None:
                    print(f"Skipping {bibcode} for now, try again..")
                    continue

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
            if new_entry or brand_new_paper:
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
