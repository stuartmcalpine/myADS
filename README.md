# myADS

`myADS` is a simple package to keep track of citations to your (and other
authors) papers. Both reporting your current papers citation metrics, and
checking for any new cites to your papers since the last time of checking.

Once installed you can always run `myads --help` to see a list of available
commands.

## Installation

The easiest method is to install directly from
[PyPi](https://pypi.org/project/myads/) via:

`pip install myads`

### From source

To install from source:

* Clone the repository using ``git clone
  https://github.com/stuartmcalpine/myADS.git``
* Navigate to the ``myADS`` folder
* Install using `pip install .`

## Getting set up

``myADS`` can keep track of the citations for multiple users. Two steps before
you get started:

* Add your users to the database
* Add your ADS API token to the database

### Adding a user to the database

Once `myADS` is installed you can add users to the tracking database using:

``myads --add_user``

You will be prompted to enter a first and last name, and an optional ORCID
(however it is recommended you add this for each user when possible).

### Removing a user from the database

You can remove users from the tracking database using:

``myads --remove_user``

where you will be prompted to enter the users unique tracking ID.

You can get a list of tracking IDs by typing:

``myads --list_users``

### Adding your ADS API token

You must add your [ADS API token](https://ui.adsabs.harvard.edu/help/api/) so
the package can query on your behalf. 

To add it run:

`--set_ads_token <YOUR-API-TOKEN-HERE>`

## Usage

### Citation reporter

If you run `myads --report` you will get a report of all your registered users
current citations.

### Citation tracker

If you run `myads --check` it will tell you any papers that have cited your
users papers since the last call. 

The first time you run this it will create a local database of your citations.
From then on it will update the local database with your new cites and report
the changes.
