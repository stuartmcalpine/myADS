import argparse
import myads.cite_tracker as cite_tracker


def main():

    # Command line options.
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(title="subcommand", dest="subcommand")

    # Primary options
    user_parser = subparsers.add_parser(
        "author", help="Add/remove/list tracked authors in the database"
    )
    token_parser = subparsers.add_parser("token", help="Add/update ADS API token")
    report_parser = subparsers.add_parser(
        "report", help="Report current citation statistics for tracked authors"
    )
    check_parser = subparsers.add_parser(
        "check", help="Check for any new cites for tracked authors"
    )

    # User options
    user_subparser = user_parser.add_subparsers(
        title="user_subparser", dest="user_subparser"
    )
    user_subparser.add_parser("add", help="Add a new author to be tracked")
    user_subparser.add_parser("list", help="List current tracked authors")
    tmp = user_subparser.add_parser("remove", help="Remove an existing tracked author")
    tmp.add_argument("user_id", help="User ID of tracked author to remove")

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

    args = parser.parse_args()

    if args.subcommand == "user":

        # Add a user to the database
        if args.user_subparser == "add":
            cite_tracker.add_user()

        # Remove a user from the database
        elif args.user_subparser == "remove":
            cite_tracker.remove_user(args.user_id)

        # Print user list.
        elif args.user_subparser == "list":
            cite_tracker.list_users()

    elif args.subcommand == "token":

        # Set the ADS API token.
        if args.token_subparser == "add":
            cite_tracker.set_ads_token(args.ads_token)

        # Display the current ADS API token.
        if args.token_subparser == "display":
            cite_tracker.display_ads_token()

    # Report users current citation statistics
    elif args.subcommand == "report":
        cite_tracker.report()

    # Check if any new cites have been made to the user since last call
    elif args.subcommand == "check":
        cite_tracker.check(args.verbose)
