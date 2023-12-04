from myads.query import ADSQueryWrapper
from tabulate import tabulate


def _print_new_cites(FIRST_NAME, LAST_NAME, reftitle, new_cites, updated=False):
    """
    Print any new citations to our papers since last call.

    Parameters
    ----------
    database : dict
        Current papers that cited our papers
    new_cites : dict
        New papers added to database (the ones we are printing here)
    updated : bool
        True if the cites are updated cites rather than new cites
    """

    # Colours for the terminal.
    BOLD = "\033[1m"
    if updated:
        OKCYAN = "\033[96m"
    else:
        OKCYAN = "\033[92m"
    ENDC = "\033[0m"

    # The paper we are printing new cites for.
    mystr = "update" if updated else "new"
    print(
        "\n",
        f"{BOLD}{OKCYAN}{len(new_cites)} {mystr} cite(s) for "
        f"{reftitle}{ENDC} by {FIRST_NAME} {LAST_NAME}",
    )

    # Loop over each of our papers.
    table = []
    for paper in new_cites:
        tmp = []

        # The attributes we want to print.
        for att in ["title", "author", "date", "bibcode"]:
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


def check(db, verbose, show_updates, rows=2000):
    """
    Check against each tracked authors' personal database to see if there are
    any new cites to their papers since the last call.

    Parameters
    ----------
    db : myADS Database object
    verbose : bool
        True for more output
    show_updates : bool
        True to also show updated cites, not just new ones
    rows : int, optional
        Max number of rows to return during query
    """

    # Query object.
    query = ADSQueryWrapper(db.get_ads_token())

    # Loop over each user in the database.
    for author in db.get_authors():
        # Extract tracked authors information.
        FIRST_NAME = author.forename
        LAST_NAME = author.surname
        ORCID = author.orcid
        # author_database = cite_tracker.get_author_database_path(att)
        print(f"\nChecking new cites for {FIRST_NAME} {LAST_NAME}...")

        # Query the tracked authors current papers.
        if not ORCID:
            # Query just by first name last name.
            data = query.get(
                q=f"first_author:{LAST_NAME},{FIRST_NAME}",
                fl="title,citation_count,pubdate,bibcode",
                rows=rows,
                verbose=verbose,
            )
        else:
            # Query also using the ORCID.
            q = (
                f"orcid_pub:{ORCID} OR orcid_user:{ORCID} OR orcid_other:{ORCID} "
                f"first_author:{LAST_NAME},{FIRST_NAME}"
            )
            data = query.get(
                q=q,
                fl="title,citation_count,pubdate,bibcode",
                rows=rows,
                verbose=verbose,
            )

        # Got a bad status code?
        if data is None:
            return

        if data.num_found == 0:
            print(f"No paper hits for {FIRST_NAME} {LAST_NAME}")
            continue

        # First refresh the authors publication list
        db.refresh_author_papers(author.id, data)

        for paper in data.papers:
            tmp_query_data = query.citations(
                paper.bibcode, fl="title,bibcode,author,date,doi"
            )

            new_cites, updated_cites = db.check_paper_new_cites(
                author.id, paper, tmp_query_data
            )

            if len(new_cites) > 0:
                _print_new_cites(FIRST_NAME, LAST_NAME, paper.title, new_cites)

            if show_updates and len(updated_cites) > 0:
                _print_new_cites(
                    FIRST_NAME, LAST_NAME, paper.title, updated_cites, updated=True
                )
