import myads.cite_tracker as cite_tracker
from myads.query import ADSQueryWrapper
from tabulate import tabulate


def report():
    """ For each tracked author, print their current citation metrics. """

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
        data = query.get(q=q, fl=ret_list, rows=50, sort="pubdate desc")

        # Got a bad status code.
        if data is None:
            return

        # Found no papers in query.
        if data.num_found == 0:
            print(f"No paper hits for {FIRST_NAME} {LAST_NAME}")
            continue

        # Header names for the columns
        headers = [
            "Title",
            "Citations\n(per year)",
            "Publication\nDate",
            "Bibcode",
        ]
        maxcolwidths = [50, None, None, None]

        # Make a new column combining cite information
        df = data.papers
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
