import os

import myads.cite_tracker as cite_tracker
import toml
from myads.query import ADSQueryWrapper
from tabulate import tabulate


def _init_database(database_path, data, query):
    """
    Initialize a database for a tracked author.

    Get all papers that cite all the papers from this author.

    Parameters
    ----------
    database_path : str
        Full path to this tracked authors cite database
    data : _ADSQuery object
        Stores the tracked authors current papers
    query : ADSQueryWrapper object
        To make additional queries
    """

    database = {}

    for i, paper in enumerate(data.papers):
        database[f"paper{i}"] = {}
        database[f"paper{i}"]["title"] = paper.title
        database[f"paper{i}"]["bibcode"] = paper.bibcode

        # What papers cite this paper
        tmp = query.citations(paper.bibcode)
        database[f"paper{i}"]["cited_by_bibcode"] = tmp.get_all("bibcode")
        database[f"paper{i}"]["cited_by_title"] = tmp.get_all("title")

    assert len(database.keys()) == len(data.papers)

    database["metadata"] = {}
    database["metadata"]["num_papers"] = len(data.papers)

    _save_database(database_path, database)


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

            # The paper we are printing new cites for.
            print(
                "\n",
                f"{BOLD}{OKCYAN}{len(new)} new cite(s) for "
                f"{database[bibcode]['title']}{ENDC}",
            )
            table = []

            # For each new cite to this paper.
            for paper in new:
                tmp = []

                # The attributes we want to print.
                for att in ["title", "author", "date", "link"]:
                    if hasattr(paper, att):
                        if att == "date":
                            tmp.append(getattr(paper, att)[:10])
                        else:
                            tmp.append(getattr(paper, att))
                    else:
                        tmp.append("Unknown")
                table.append(tmp)

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


def _check_for_new_papers(database, data, verbose):
    """
    Check if the tracked author has published any new papers since the last
    time of checking.

    If so, update the tracked authors' database.

    `database` is modified in place.

    Parameters
    ----------
    database : dict
        The tracked authors current citation database
    data : _ADSQuery object
        The tracked authors latest papers
    verbose : bool
        True for more output
    """

    # Loop over each latest paper
    for tmp_paper_new in data.papers:

        found_bibcode, found_title = False, False

        # Loop over each paper in the current cite database
        for tmp_paper_current in list(database.keys()):

            if tmp_paper_current == "metadata":
                continue

            if tmp_paper_new.bibcode == database[tmp_paper_current]["bibcode"]:
                found_bibcode = True

            if tmp_paper_new.title == database[tmp_paper_current]["title"]:
                found_title = True

            if found_bibcode or found_title:
                break

        # Case for a totally new paper.
        if found_title == False and found_bibcode == False:
            database["metadata"]["num_papers"] += 1
            idx = database["metadata"]["num_papers"]

            database[f"paper{idx}"] = {}
            database[f"paper{idx}"]["title"] = tmp_paper_new.title
            database[f"paper{idx}"]["bibcode"] = tmp_paper_new.bibcode
            database[f"paper{idx}"]["cited_by_bibcode"] = []
            database[f"paper{idx}"]["cited_by_title"] = []

            if verbose:
                print(
                    f"Tracked author has published a new paper,",
                    f"Title: {tmp_paper_new.title},",
                    "adding to database",
                )

        # Case for updated bibcode.
        elif found_title == True and found_bibcode == False:
            database[tmp_paper_current]["bibcode"] = tmp_paper_new.bibcode

            if verbose:
                print(
                    f"Paper {tmp_paper_new.title} has a new bibcode, ",
                    f"{tmp_paper_new.bibcode}, updating database",
                )

        # Case for updated title
        elif found_title == False and found_bibcode == True:
            database[tmp_paper_current]["title"] = tmp_paper_new.title

            if verbose:
                print(
                    f"Paper {tmp_paper_new.bibcode} has a new title, ",
                    f"{tmp_paper_new.title}, updating database",
                )


def _check_for_new_cites(database, data, query, verbose):
    """
    Check if the tracked authors papers have got any new cites since the last
    time of checking.

    Parameters
    ----------
    database : dict
        The tracked authors current citation database
    data : _ADSQuery object
        The tracked authors latest papers
    query : ADSQueryWrapper object
    verbose : bool
        True for more output

    Returns
    -------
    new_cite_list : dict
        List of new cites for each paper for tracked author
    """

    new_cite_list = {}
    num_new_cites = 0

    # Loop over each paper in database.
    for author_paper in database.keys():

        if author_paper == "metadata":
            continue

        if verbose:
            print(f"Checking {author_paper}...")

        # To track new cites for printing later
        new_cite_list[author_paper] = []

        # Get up-to-date cites for this paper.
        tmp_query_data = query.citations(
            database[author_paper]["bibcode"], fl="title,bibcode,author,date,doi"
        )

        # Check the query was successful
        if tmp_query_data is None:
            print(f"Skipping {bibcode} for now, try again..")
            continue

        # Compare to database, and see if any new cites have happened since
        # last check.
        for paper in tmp_query_data.papers:

            found_bibcode, found_title = False, False

            if paper.bibcode in database[author_paper]["cited_by_bibcode"]:
                found_bibcode = True

            if paper.title in database[author_paper]["cited_by_title"]:
                found_title = True

            # Found a new cite
            if found_bibcode == False and found_title == False:
                new_cite_list[author_paper].append(paper)
                num_new_cites += 1

            if found_bibcode == False and found_title == True:
                if verbose:
                    print(f"{paper.title} has an updated bibcode, {paper.bibcode}")

            if found_bibcode == True and found_title == False:
                if verbose:
                    print(f"{paper.bibcode} has an updated title, {paper.title}")

        # Update database.
        database[author_paper]["cited_by_bibcode"] = tmp_query_data.get_all("bibcode")
        database[author_paper]["cited_by_title"] = tmp_query_data.get_all("title")

    return new_cite_list, num_new_cites


def check(verbose):
    """
    Check against each tracked authors' personal database to see if there are
    any new cites to their papers since the last call.

    Parameters
    ----------
    verbose : bool  
        True for more output
    """

    authors = cite_tracker.load_author_list()
    token = cite_tracker.load_ads_token()

    # Query object.
    query = ADSQueryWrapper(token)

    # Loop over each user in the database.
    for att in authors.keys():
        if att == "metadata":
            continue

        # Extract tracked authors information.
        FIRST_NAME = authors[att]["first_name"]
        LAST_NAME = authors[att]["last_name"]
        ORCID = authors[att]["orcid"]
        author_database = cite_tracker.get_author_database_path(att)
        print(f"\nChecking new cites for {FIRST_NAME} {LAST_NAME}...")

        # Query the tracked authors current papers.
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

        # Check for new cites.
        new_cite_list = {}
        brand_new_paper = False

        # Does this tracked author already have a database?
        if os.path.isfile(author_database):

            # Load existing database for tracked author.
            database = toml.load(author_database)

            # Is there a new paper for this user that's not in the database?
            _check_for_new_papers(database, data, verbose)

            # Any new cites to authors papers since last check?
            new_cite_list, num_new_cites = _check_for_new_cites(
                database, data, query, verbose
            )

            # Report new cites.
            if num_new_cites > 0:
                _print_new_cites(database, new_cite_list)
            else:
                print(f"No new cites for {FIRST_NAME} {LAST_NAME}")

            # Update the database.
            _save_database(author_database, database)
        else:
            # Create new database (first time run).
            print(
                f"First time run for {FIRST_NAME} {LAST_NAME}, "
                f"creating new ADS cite tracker database file..."
            )
            _init_database(author_database, data, query)
