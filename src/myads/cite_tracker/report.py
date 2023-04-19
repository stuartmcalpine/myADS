import os

import myads.cite_tracker as cite_tracker
import toml
from myads.query import ADSQueryWrapper
from tabulate import tabulate


def report():

    # Load the user database.
    assert os.path.isfile(
        cite_tracker.USER_DATABASE
    ), "No user database created yet, run 'myads --add_user'"
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

        # Extract this users information.
        FIRST_NAME = users[att]["first_name"]
        LAST_NAME = users[att]["last_name"]
        ORCID = users[att]["orcid"]
        print(f"\nReporting cites for {FIRST_NAME} {LAST_NAME}...")

        # Query.
        if ORCID == "":
            q = f"first_author:{LAST_NAME},{FIRST_NAME}"
        else:
            q = (
                f"orcid_pub:{ORCID} OR orcid_user:{ORCID} OR orcid_other:{ORCID} "
                f"first_author:{LAST_NAME},{FIRST_NAME}"
            )

        data = query.get(q=q, fl="title,citation_count,pubdate,bibcode")

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
            table.append(
                [
                    paper.title,
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
                headers=[
                    "Title",
                    "Citations\n(per year)",
                    "Publication\nDate",
                    "Bibcode",
                ],
            )
        )
