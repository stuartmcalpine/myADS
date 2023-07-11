import os

import myads.cite_tracker as cite_tracker
import toml
from myads.query import ADSQueryWrapper
from tabulate import tabulate


def report(long_report):
    """
    For each tracked author, print their current citation metrics.

    Parameters
    ----------
    long_report : bool
        True for more columns
    """

    authors = cite_tracker.load_author_list()
    token = cite_tracker.load_ads_token()

    # Query object.
    query = ADSQueryWrapper(token)

    # Loop over each user in the database.
    for att in authors.keys():
        if att == "metadata":
            continue

        # Extract this users information.
        FIRST_NAME = authors[att]["first_name"]
        LAST_NAME = authors[att]["last_name"]
        ORCID = authors[att]["orcid"]
        print(f"\nReporting cites for {FIRST_NAME} {LAST_NAME}...")

        # Query.
        if ORCID == "":
            q = f"first_author:{LAST_NAME},{FIRST_NAME}"
        else:
            q = (
                f"orcid_pub:{ORCID} OR orcid_user:{ORCID} OR orcid_other:{ORCID} "
                f"first_author:{LAST_NAME},{FIRST_NAME}"
            )
    
        ret_list = "title,citation_count,pubdate,bibcode"
        if long_report:
            ret_list += ",read_count"
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
            
            if long_report:
                tmp.append(paper.read_count)

            table.append(tmp)

        headers = [
                    "Title",
                    "Citations\n(per year)",
                    "Publication\nDate",
                    "Bibcode",
                ]
        maxcolwidths=[50, None, None, None]
        if long_report:
            headers.append("Read count\n(90 days)")
            maxcolwidths.append(None)

        print(
            tabulate(
                table,
                tablefmt="grid",
                maxcolwidths=maxcolwidths,
                headers=headers
            )
        )
