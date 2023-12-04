import argparse
import myads.cite_tracker as cite_tracker


def main():
    # Command line options.
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(title="subcommand", dest="subcommand")

    # Primary options
    subparsers.add_parser("initialize")

    user_parser = subparsers.add_parser(
        "author", help="Add/remove/list tracked authors in the database"
    )
    token_parser = subparsers.add_parser("token", help="Add/update ADS API token")
    subparsers.add_parser(
        "report", help="Report current citation statistics for tracked authors"
    )
    check_parser = subparsers.add_parser(
        "check", help="Check for any new cites for tracked authors"
    )

    # Author options
    user_subparser = user_parser.add_subparsers(
        title="user_subparser", dest="user_subparser"
    )
    user_subparser.add_parser("add", help="Add a new author to be tracked")
    user_subparser.add_parser("list", help="List current tracked authors")
    tmp = user_subparser.add_parser("remove", help="Remove an existing tracked author")
    tmp.add_argument("author_id", help="ID of tracked author to remove", type=int)

    # ADS API token options
    token_subparser = token_parser.add_subparsers(
        title="token_subparser", dest="token_subparser"
    )
    tmp = token_subparser.add_parser("add", help="Add/update ADS API token")
    tmp.add_argument("ads_token", help="ADS token to add")
    token_subparser.add_parser("display", help="Display current ADS token")

    # Check options
    check_parser.add_argument(
        "--verbose", help="True for more output", action="store_true"
    )
    check_parser.add_argument(
        "--show_updates",
        help="True to show when a cite updates and not just new cites",
        action="store_true",
    )

    args = parser.parse_args()

    if args.subcommand == "token":
        db = cite_tracker.Database()

        # Set the ADS API token.
        if args.token_subparser == "add":
            db.add_ads_token(args.ads_token)

        # Display the current ADS API token.
        if args.token_subparser == "display":
            token = db.get_ads_token()
            print(f"Currently stored ADS token: {token}")

    # Report users current citation statistics
    elif args.subcommand == "report":
        db = cite_tracker.Database()
        cite_tracker.report(db)

    # Check if any new cites have been made to the user since last call
    elif args.subcommand == "check":
        db = cite_tracker.Database()
        cite_tracker.check(db, args.verbose, args.show_updates)

    # First time initialization of the database
    elif args.subcommand == "initialize":
        db = cite_tracker.Database()
        db.initialize()

    # Manage tracked authors
    elif args.subcommand == "author":
        db = cite_tracker.Database()

        # Add a user to the database
        if args.user_subparser == "add":
            forename = input("Enter author forename: ")
            surname = input("Enter author surname: ")
            orcid = input("Enter author orcid (optional): ")

            db.add_author(forename, surname, orcid)

        # Remove a user from the database
        elif args.user_subparser == "remove":
            db.delete_author(args.author_id)

        # Print user list.
        elif args.user_subparser == "list":
            db.list_authors()
