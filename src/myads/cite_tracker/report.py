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
        data = query.get(q=q, fl=ret_list, rows=50, sort="pubdate desc")

        # Got a bad status code.
        if data is None:
            return

        # Found no papers in query.
        if data.num_found == 0:
            print(f"No paper hits for {FIRST_NAME} {LAST_NAME}")
            continue

        # Loop over each of my papers and print the number of cites.
        table = []
        for paper in data.papers:
            tmp = [
                paper.title,
                f"{paper.citation_count} ({paper.citation_count_per_year:.1f})",
                paper.pubdate,
                paper.ads_link,
            ]

            table.append(tmp)

        headers = [
            "Title",
            "Citations\n(per year)",
            "Publication\nDate",
            "Bibcode",
        ]
        maxcolwidths = [50, None, None, None]

        # Make a new column combining cite information
        df = data.papers_df
        df["citation_count_extra"] = df.apply(
            lambda x: f"{x['citation_count']} ({x['citation_count_per_year']:.1f})",
            axis=1,
        )

        # Print the table
        print(
            tabulate(
                df[["title", "citation_count_extra", "pubdate", "bibcode"]],
                tablefmt="grid",
                maxcolwidths=maxcolwidths,
                showindex="never",
                headers=headers,
            )
        )
