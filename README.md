[![PyPI version](https://badge.fury.io/py/myads.svg)](https://badge.fury.io/py/myads)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/myads?logo=python)

# myADS

`myADS` is a simple package to keep track of citations to your (and other
authors) papers.

It both reports the authors current paper citation metrics, and checks for any
new cites to the authors papers since the last time of checking.

Once installed you can always run `myads --help` to see a list of available
commands.

## Installation

The easiest method is to install directly from
[PyPi](https://pypi.org/project/myads/) via:

```bash
pip install myads
```

### From source

To install from source:

* Clone the repository using ``git clone
  https://github.com/stuartmcalpine/myADS.git``
* Navigate to the ``myADS`` folder
* Install using `pip install .`

## Getting set up

``myADS`` can keep track of the citations for multiple authors. Two steps
before you get started:

* Add your authors you want to track to the database
* Add your ADS API token to the database

### Adding a author to the database

Once `myADS` is installed you can add the authors you wish to track using:

```bash
myads author add
```

You will be prompted to enter a first and last name, and an optional ORCID
(however it is recommended you add this for each author when possible).

### Removing a author from the database

You can remove authors from the tracking database using:

```bash
myads author remove <author id>
```

You can get a list of author IDs by typing:

```bash
myads author list
```

### Adding your ADS API token

You must add your [ADS API token](https://ui.adsabs.harvard.edu/help/api/) so
the package can query on your behalf. 

To add it run:

```bash
myads token update <YOUR-API-TOKEN-HERE>
```

## Usage

### Citation reporter

If you run `myads report` you will get a report of all your tracked authors
current citations, e.g.,

```bash
Reporting cites for Stuart McAlpine...
+----------------------------------------------------+--------------+---------------+---------------------+
| Title                                              | Citations    | Publication   | Bibcode             |
|                                                    | (per year)   | Date          |                     |
+====================================================+==============+===============+=====================+
| Galaxy mergers in EAGLE do not induce a            | 34 (12.0)    | 2020-06-00    | 2020MNRAS.494.5713M |
| significant amount of black hole growth yet do     |              |               |                     |
| increase the rate of luminous AGN                  |              |               |                     |
+----------------------------------------------------+--------------+---------------+---------------------+
```

### Citation tracker

If you run `myads check` it will tell you any papers that have cited your
tracked authors papers since the last call. 

The first time you run this it will create a local database of your citations.
From then on it will update the local database with your new cites and report
the changes, e.g.,

```bash
 1 new cite(s) for Galaxy mergers in EAGLE do not induce a significant amount of black hole growth yet do increase the rate of luminous AGN
+----------------------------------------+--------------------------------------+------------+---------------------+
| Title                                  | Authors                              | Date       | Bibcode             |
+========================================+======================================+============+=====================+
| The breakBRD Breakdown: Using          | ['Kopenhafer, Claire', 'Starkenburg, | 2020-11-01 | 2020ApJ...903..143K |
| IllustrisTNG to Track the Quenching of | Tjitske K.', 'Tonnesen, Stephanie',  |            |                     |
| an Observationally Motivated Sample of | 'Tuttle, Sarah']                     |            |                     |
| Centrally Star-forming Galaxies        |                                      |            |                     |
+----------------------------------------+--------------------------------------+------------+---------------------+
```
