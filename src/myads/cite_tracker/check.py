import os

import myads.cite_tracker as cite_tracker
import toml
from myads.query import ADSQueryWrapper
from tabulate import tabulate


def _init_database(database_path, data, query):
    """
    Initialize a database for a tracked author.

    Get the papers that cite papers from this author and store them.

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

    # Loop over each of the authors papers
    for i in range(data.num_found):
        database[f"paper{i}"] = {}
        database[f"paper{i}"]["title"] = data.papers_dict["title"][i]
        database[f"paper{i}"]["bibcode"] = data.papers_dict["bibcode"][i]

        # What papers cite this paper
        tmp = query.citations(data.papers_dict["bibcode"][i])
        if tmp.papers is not None:
            database[f"paper{i}"]["cited_by_bibcode"] = tmp.papers["bibcode"].values
            database[f"paper{i}"]["cited_by_title"] = tmp.papers["title"].values
        else:
            database[f"paper{i}"]["cited_by_bibcode"] = []
            database[f"paper{i}"]["cited_by_title"] = []

    assert len(database.keys()) == data.num_found

    database["metadata"] = {}
    database["metadata"]["num_papers"] = data.num_found

    # Store
    _save_database(database_path, database)


def _save_database(path, data):
    """
    Save the cite database for an author.

    Parameters
    ----------
    path : str
        Path to author cite database file
    data : dict
        Contains the authors cite information
    """

    with open(path, "w") as f:
        toml.dump(data, f)


def _print_new_cites(database, new_cites):
    """
    Print any new citations to our papers since last call.

    Parameters
    ----------
    database : dict
        Current papers that cited our papers
    new_cites : dict
        New papers added to database (the ones we are printing here)
    """

    # Colours for the terminal.
    BOLD = "\033[1m"
    OKCYAN = "\033[96m"
    ENDC = "\033[0m"

    # Loop over each paper from the author.
    for author_paper in new_cites.keys():

        # Do we have any new cites for this paper?
        new = len(new_cites[author_paper]["title"])

        if new == 0:
            continue

        # The paper we are printing new cites for.
        print(
            "\n",
            f"{BOLD}{OKCYAN}{new} new cite(s) for "
            f"{database[author_paper]['title']}{ENDC}",
        )

        # Print new cites
        print(
            tabulate(
                new_cites[author_paper],
                tablefmt="grid",
                maxcolwidths=[40, 40, 20],
                headers=["Title", "Authors", "Bibcode"],
            )
        )


def _check_for_new_papers(database, data, verbose):
    """
    Check if the tracked author has published any new papers since the last
    time of checking.

    Note that a papers title, or bibcode, can change, but it's still the same
    paper (through publication for example). The latest details are kept, but
    it's not classed as a "new" paper.

    The `database` is modified in place with any changes.

    Parameters
    ----------
    database : dict
        The tracked authors current citation database
    data : _ADSQuery object
        The tracked authors latest papers
    verbose : bool
        True for more output
    """

    # Loop over each paper from the author
    for paper_idx in range(data.num_found):

        found_bibcode, found_title = False, False

        this_bibcode = data.papers_dict["bibcode"][paper_idx]
        this_title = data.papers_dict["title"][paper_idx]

        # Loop over each paper in the current cite database
        for tmp_paper_current in list(database.keys()):

            if tmp_paper_current == "metadata":
                continue

            if this_bibcode == database[tmp_paper_current]["bibcode"]:
                found_bibcode = True

            if this_title == database[tmp_paper_current]["title"]:
                found_title = True

            # We already have this paper in the database.
            if found_bibcode or found_title:
                break

        # Case for a totally new paper.
        if found_title == False and found_bibcode == False:
            database["metadata"]["num_papers"] += 1
            idx = database["metadata"]["num_papers"]

            database[f"paper{idx}"] = {}
            database[f"paper{idx}"]["title"] = this_title
            database[f"paper{idx}"]["bibcode"] = this_bibcode
            database[f"paper{idx}"]["cited_by_bibcode"] = []
            database[f"paper{idx}"]["cited_by_title"] = []

            if verbose:
                print(
                    f"Tracked author has published a new paper,",
                    f"Title: {this_title}, adding to database",
                )

        # Case for updated bibcode.
        elif found_title == True and found_bibcode == False:
            database[tmp_paper_current]["bibcode"] = this_bibcode

            if verbose:
                print(
                    f"Paper {this_title} has a new bibcode, ",
                    f"{this_bibcode}, updating database",
                )

        # Case for updated title
        elif found_title == False and found_bibcode == True:
            database[tmp_paper_current]["title"] = this_title

            if verbose:
                print(
                    f"Paper {this_bibcode} has a new title, ",
                    f"{this_title}, updating database",
                )


def _check_for_new_cites(database, data, query, verbose):
    """
    Check if the tracked author's papers have got any new cites since the last
    time of checking.

    Parameters
    ----------
    database : dict
        The tracked author's current citation database
    data : _ADSQuery object
        The tracked author's latest papers
    query : ADSQueryWrapper object
    verbose : bool
        True for more output

    Returns
    -------
    new_cites : dict
        New cites for each paper for tracked author
    num_new_cites : int
        Total number of new cites for author
    """

    new_cites = {}
    num_new_cites = 0

    # Loop over each paper in author's database.
    for author_paper in database.keys():

        if author_paper == "metadata":
            continue

        if verbose:
            print(f"Checking {author_paper}...")

        # Get up-to-date cites for this paper.
        tmp_query_data = query.citations(
            database[author_paper]["bibcode"], fl="title,bibcode,author"
        )

        # Check the query was successful
        if tmp_query_data is None:
            print(f"Skipping {bibcode} for now, try again..")
            continue

        new_cites[author_paper] = {"title": [], "author": [], "bibcode": []}

        # Compare to database, and see if any new cites have happened since
        # last check.
        for paper_idx in range(tmp_query_data.num_found):

            this_bibcode = tmp_query_data.papers_dict["bibcode"][paper_idx]
            this_title = tmp_query_data.papers_dict["title"][paper_idx]

            found_bibcode, found_title = False, False

            if this_bibcode in database[author_paper]["cited_by_bibcode"]:
                found_bibcode = True

            if this_title in database[author_paper]["cited_by_title"]:
                found_title = True

            # Found a new cite
            if found_bibcode == False and found_title == False:
                for att in ["title", "author", "bibcode"]:
                    new_cites[author_paper][att].append(
                        tmp_query_data.papers_dict[att][paper_idx]
                    )
                num_new_cites += 1

            if found_bibcode == False and found_title == True:
                if verbose:
                    print(f"{this_title} has an updated bibcode, {this_bibcode}")

            if found_bibcode == True and found_title == False:
                if verbose:
                    print(f"{this_bibcode} has an updated title, {this_title}")

        # Update author's database with latest cites.
        if tmp_query_data.num_found > 0:
            database[author_paper]["cited_by_bibcode"] = tmp_query_data.papers_dict[
                "bibcode"
            ]
            database[author_paper]["cited_by_title"] = tmp_query_data.papers_dict[
                "title"
            ]

    return new_cites, num_new_cites


def check(verbose, rows=50):
    """
    Check against each tracked authors' personal database to see if there are
    any new cites to their papers since the last call.

    Parameters
    ----------
    verbose : bool  
        True for more output
    rows : int, optional
        Max number of rows to return during query
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
                rows=rows, verbose=verbose
            )
        else:
            # Query also using the ORCID.
            q = (
                f"orcid_pub:{ORCID} OR orcid_user:{ORCID} OR orcid_other:{ORCID} "
                f"first_author:{LAST_NAME},{FIRST_NAME}"
            )
            data = query.get(q=q, fl="title,citation_count,pubdate,bibcode", rows=rows,
                    verbose=verbose)

        # Got a bad status code?
        if data is None:
            return

        if data.num_found == 0:
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
            new_cites, num_new_cites = _check_for_new_cites(
                database, data, query, verbose
            )

            # Report new cites.
            if num_new_cites > 0:
                _print_new_cites(database, new_cites)
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
