import argparse
import myads.cite_tracker as cite_tracker

def main():

    # Command line options.
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument(
        "--add_user",
        help="Add new person to track list",
        action="store_true",
    )
    group.add_argument(
        "--remove_user",
        help="Remove user from track list",
        action="store_true",
    )
    group.add_argument(
        "--list_users",
        help="Print user list",
        action="store_true",
    )
    group.add_argument(
        "--set_ads_token",
        help="Set the ADS API token",
        type=str,
    )
    group.add_argument(
        "--report", help="Report current citation statistics for users", action="store_true"
    )
    group.add_argument(
        "--check", help="Check for any new cites to users papers", action="store_true"
    )
    parser.add_argument(
        "--verbose", help="For more output", action="store_true"
    )
    args = parser.parse_args()

    # Add a user to the database
    if args.add_user:
        cite_tracker.add_user()

    # Remove a user from the database
    if args.remove_user:
        cite_tracker.remove_user()

    # Set the ADS API token.
    elif args.set_ads_token is not None:
        cite_tracker.set_ads_token(args.set_ads_token)

    # Report users current citation statistics
    elif args.report:
        cite_tracker.report()

    # Print user list.
    elif args.list_users:
        cite_tracker.list_users()

    # Check if any new cites have been made to the user since last call
    elif args.check:
        cite_tracker.check(args.verbose)
