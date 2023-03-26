# myADS

## Installation

### From source

To install from source:

* Clone the repository using ``git clone https://github.com/stuartmcalpine/myADS.git``
* Navigate to the ``myADS`` folder
* Install using `pip install .`

## Keep track of your citations

``myADS`` can keep track of citations of multiple users.

### Adding a user to the database

Start by adding one or more users to the tracking database using:

``myads --add_user``

You will be prompted to enter a first and last name, and an optional ORCID
(however it is recommended you add this for each user when possible).

### Removing a user from the database

You can remove users from the tracking database using:

``myads --remove_user``

where you will be prompted to enter the users unique tracking ID.

You can get a list of tracking IDs by typing:

``myads --list_users``

## Simple ADS API query package
