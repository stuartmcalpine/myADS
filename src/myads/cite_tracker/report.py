import os

import myads.cite_tracker as cite_tracker
import toml
from myads.query import ADSQueryWrapper
from tabulate import tabulate


def report(db):
    """
    For each tracked author, print their current citation metrics.

    Parameters
    ----------
    db : myADS Database object
    """

    # Query object.
    query = ADSQueryWrapper(db.get_ads_token())

    # Loop over each user in the database.
    for author in db.get_authors():
        # Extract this users information.
        FIRST_NAME = author.forename
        LAST_NAME = author.surname
        ORCID = author.orcid
        print(f"\nReporting cites for {FIRST_NAME} {LAST_NAME}...")

        # Query.
        if not ORCID:
            q = f"first_author:{LAST_NAME},{FIRST_NAME}"
        else:
            q = (
                f"orcid_pub:{ORCID} OR orcid_user:{ORCID} OR orcid_other:{ORCID} "
                f"first_author:{LAST_NAME},{FIRST_NAME}"
            )

        ret_list = "title,citation_count,pubdate,bibcode"
        data = query.get(q=q, fl=ret_list)

        # Got a bad status code.
        if data is None:
            return

        # Found no papers in query.
        if len(data.papers) == 0:
            print(f"No paper hits for {FIRST_NAME} {LAST_NAME}")
            continue

        # Loop over each of my papers and print the number of cites.
        table = []
        for paper in data.papers:
            tmp = [
                paper.title,
                f"{paper.citation_count} ({paper.citations_per_year:.1f})",
                paper.pubdate,
                paper.link,
            ]

            table.append(tmp)

        headers = [
            "Title",
            "Citations\n(per year)",
            "Publication\nDate",
            "Bibcode",
        ]
        maxcolwidths = [50, None, None, None]

        print(
            tabulate(table, tablefmt="grid", maxcolwidths=maxcolwidths, headers=headers)
        )
