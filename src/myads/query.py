from urllib.parse import urlencode
import requests

from datetime import datetime
import pandas as pd
import numpy as np


class _ADSPaper:

    def __init__(self, data):
        """
        Simple class to hold information about ADS paper

        Parameters
        ----------
        data : dict
            Information from self.papers_dict
        """

        for att, v in data.items():
            setattr(self, att, v)

class _ADSQuery:
    def __init__(self, q, fl, rows, request_data):
        """
        Stores the result of an individual query to ADS.

        Not designed to be called standalone, should be called from within the
        ADSQueryWrapper object.

        Parameters
        ----------
        q : str
            The search query. This should be a UTF-8, URL-encoded string of
            <=1000 characters.
        fl : str
            The list of fields to return. The value should be a comma separated
            list of field names, e.g. `fl="bibcode,author,title"`.
        rows : int
            The number of results to return (maximum from ADS is 2000).
        request_data : `requests` "get" object
            The raw data returned from the query from the requests lib

        Attributes
        ----------
        q : str
        fl : str
        rows : int
        query_time : float
            Execution time of query
        query_status : int
            Query return status
        num_found : int
            Papers found as result from query
        papers_df : DataFrame
            DataFrame storing the query results
        papers_dict : dict
            Dict storing the query results
        """

        # Store the query info.
        self.q = q
        self.fl = fl
        self.rows = rows

        # Convert the query results into a DataFrame.
        self._parse(request_data)

    @property
    def papers(self):
        """ 
        Generator object to loop over each paper and return a _ADSPaper object
        for each.

        Example
        -------
        for paper in data.papers:
            print(paper.title)

        Yields
        ------
        - : _ADSPaper
        """

        if not hasattr(self, "papers_dict") or len(self.papers_dict) == 0:
            return
            yield

        atts = list(self.papers_dict.keys())

        for i in range(len(self.papers_dict[atts[0]])):
            tmp = {key: value[i] for (key, value) in self.papers_dict.items()}
            yield _ADSPaper(tmp)

    def _clean_df(self, row):
        """
        Clean rows before going into the data frame. Need to convert out lists,
        just take the 1st value. The full array will still be in the
        `self.papers_dict` dict.

        Parameters
        ----------
        row : dict
        """

        for att in self.fl.split(","):
            if att not in row.keys():
                row[att] = np.nan

            if type(row[att]) == list:
                row[att] = row[att][0]

        return row

    def _clean_dict(self, row):
        """
        Clean rows before appending them to the papers_dict. This is just to
        remove length 1 lists.
        """

        if type(row) == list:
            if len(row) == 1:
                return row[0]

        return row

    def _parse(self, request_data):
        """
        Ingest the query results into a dataframe.

        Here the `self.papers_df` DataFrame is created.

        Parameters
        ----------
        request_data : `requests` "get" object
            The data returned from the query from the requests lib
        """

        # Convert to JSON format.
        request_data = request_data.json()

        # Store some information about the query execution.
        rheader = request_data["responseHeader"]
        self.query_time = rheader["QTime"]
        self.query_status = rheader["status"]
        assert self.query_status == 0

        # Store the result.
        self.num_found = request_data["response"]["numFound"]

        # Case where max_rows wasn't big enough.
        if self.num_found > len(request_data["response"]["docs"]):
            print(
                f"Warning: Query {self.q} returns over max rows,"
                f"({self.num_found} > {self.rows})",
                "not all papers will be in the list",
            )

        # Loop over each query results and ingest them into a DataFrame
        self.papers_df = None
        self.papers_dict = {}
        for i in range(len(request_data["response"]["docs"])):
            # Add to the dict object.
            for att in self.fl.split(","):
                if att not in self.papers_dict.keys():
                    if att not in request_data["response"]["docs"][i].keys():
                        self.papers_dict[att] = [np.nan]
                    else:
                        self.papers_dict[att] = [
                            self._clean_dict(request_data["response"]["docs"][i][att])
                        ]
                else:
                    if att not in request_data["response"]["docs"][i].keys():
                        self.papers_dict[att].append(np.nan)
                    else:
                        self.papers_dict[att].append(
                            self._clean_dict(request_data["response"]["docs"][i][att])
                        )

            # Add to the dataframe object.
            if self.papers_df is None:
                self.papers_df = pd.DataFrame(
                    self._clean_df(request_data["response"]["docs"][i]), index=[0]
                )
            else:
                self.papers_df = pd.concat(
                    (
                        self.papers_df,
                        pd.DataFrame(
                            self._clean_df(request_data["response"]["docs"][i]),
                            index=[0],
                        ),
                    ),
                    ignore_index=True,
                )

        # Compute some additional properties

        # Compute the URL to the papers ADS page.
        if self.papers_df is not None:
            if "bibcode" in self.papers_df.columns:
                self.papers_df["ads_link"] = self.papers_df["bibcode"].apply(
                    self._generate_ads_link
                )
                self.papers_dict["ads_link"] = list(self.papers_df["ads_link"].values)

            # Compute the number of years since publication.
            if "pubdate" in self.papers_df.columns:
                self.papers_df["years_since_pub"] = self.papers_df["pubdate"].apply(
                    self._years_since_publication
                )
                self.papers_dict["years_since_pub"] = list(self.papers_df["years_since_pub"].values)

            # Compute the number of years since publication.
            if (
                "pubdate" in self.papers_df.columns
                and "citation_count" in self.papers_df.columns
            ):
                self.papers_df["citation_count_per_year"] = self.papers_df.apply(
                    lambda x: self._citations_per_year(
                        x["years_since_pub"], x["citation_count"]
                    ),
                    axis=1,
                )
                self.papers_dict["citation_count_per_year"] = list(
                    self.papers_df["citation_count_per_year"].values
                )

            # Checks
            count = None
            for att in self.papers_dict.keys():
                if count is None:
                    count = len(self.papers_dict[att])
                else:
                    if len(self.papers_dict[att]) != count:
                        raise ValueError(f"Array {att} has a bad length")

    def _generate_ads_link(self, bibcode) -> str:
        """
        Generate the ADS link from the bibcode

        Parameters
        ----------
        bibcode : str

        Returns
        -------
        uri : str
        """

        uri = f"https://ui.adsabs.harvard.edu/abs/{bibcode}/abstract"

        return uri

    def _years_since_publication(self, pubdate) -> float:
        """
        Return the number of years from a given pubdate.

        Parameters
        ----------
        pubdate : str

        Returns
        -------
        diff : float
            Total number of years since pubdate
        """

        # Convert pubdate string to datetime.
        pubyear = int(pubdate.split("-")[0])
        pubmonth = int(pubdate.split("-")[1])
        if pubmonth == 0:
            pubmonth += 1
        dt = f"{pubyear}-{pubmonth}"

        # Compute time difference from now.
        diff = datetime.now() - datetime.strptime(dt, "%Y-%m")
        diff = diff.total_seconds()

        # Convert to years.
        return diff / 31536000

    def _citations_per_year(self, pubyears, num_cites) -> float:
        """
        Compute the number of cites per year

        Parameters
        ----------
        pubyears : float
        num_cites : int

        Returns
        -------
        - : float
            The number of cites per year (pubyears/num_cites)
        """

        if (pubyears is None) or (num_cites is None):
            return None
        elif pubyears <= 1 / 12:
            return 0.0
        else:
            return num_cites / pubyears


class ADSQueryWrapper:
    def __init__(self, ads_token):
        """
        Class that wraps calls to the ADS API to make easy queries.

        Each method returns a _ADSQuery object, which contains information
        about the query, the reponse from the ADS API, and the result of the query. The
        result of the query is stored in a "paper" list in the _ASDQuery object, for
        which each entry is a list containing information about the papers in the query
        result.

        Parameters
        ----------
        ads_token : str

        Methods
        -------
        get(...)
            Perform a generic query to the ADS API
        citations(...)
            Query the ADS API to return all cites to a given paper
        references(...)
            Query the ADS API to return all references within a given paper
        """

        # ADS API token.
        self.token = ads_token

        # Log how many ADS API calls this object has used in this session.
        self.ads_api_calls = 0

        # Log how many ADS API calls remaining on our token today.
        self.ads_api_calls_remaining = None

    def __del__(self):
        """
        On program end, report how many ADS API calls were used during this
        ADSQuery object instance. We are interested in this because the number
        of API calls to ADS has a daily limit of 5000.
        """
        if self.ads_api_calls > 0:
            print(
                f"Used {self.ads_api_calls} ADS API calls in this instance,",
                f"{self.ads_api_calls_remaining} more calls can be used today",
                f"on this token.",
            )

    def _encode_string(self, query):
        """
        Encode query dict into a string.

        Needs to include "q", the query, and "fl" the fields you want returned.

        Paramaters
        ----------
        query : dict

        Example
        -------
        query = {"q": "author:McAlpine,Stuart", "fl": "citation_count", "rows": 20}
        """

        return urlencode(query)

    def get(self, q, fl, sort=None, rows=10, max_attempts=3, verbose=False):
        """
        Perform generic query using the ADS API.

        Parameters
        ----------
        q : str
            The search query. This should be a UTF-8, URL-encoded string of
            <=1000 characters.
        fl : str
            The list of fields to return. The value should be a comma separated
            list of field names, e.g. `fl=bibcode,author,title`.
        sort : str, optional
            The sorting field and direction to be used when returning results.
            e.g., `citation_count+desc`
        rows : int, optional
            The number of results to return. The default is 10 and the maximum
            is 2000.
        max_attempts : int, optional
            How many times do we try before we give up?
        verbose : bool, optional
            True for more output

        Returns
        -------
        - : _ADSQuery object
            Object stores all information about query and the result
        """

        # Can't go above max rows
        if rows > 2000:
            raise ValueError("Maximum allowed number of rows for 1 query is 2000")

        # Build query dict.
        query = {"q": q, "fl": fl, "rows": rows}

        # Add sorting options
        if sort is not None:
            query["sort"] = sort

        # Convert query dict to string.
        if verbose:
            print(f"Query dict: {q}")
        q = self._encode_string(query)
        if verbose:
            print(f"Query str: {q}")
        url = f"https://api.adsabs.harvard.edu/v1/search/query?{q}"

        # Need authorization token in header.
        headers = {"Authorization": f"Bearer:{self.token}"}

        # Make get request.
        for i in range(max_attempts):
            resp = requests.get(url, headers=headers)
            self.ads_api_calls += 1

            # Check status code.
            if resp.status_code != 200:
                print(
                    f"Attempt {i+1} recieved status code ",
                    f"{resp.status_code} from ADS, trying again...",
                )
                continue
            else:
                break

        # Case where we never got a good reponse from ADS
        if resp.status_code != 200:
            print(f"Recieved too many bad status codes...")
            return None

        # Look at the header to see how many queries we have left.
        self.ads_api_calls_remaining = resp.headers["X-RateLimit-Remaining"]

        return _ADSQuery(q, fl, rows, resp)

    def citations(self, bibcode, fl="title,bibcode,author,citation_count", rows=2000):
        """
        Query what papers cite a paper of a given bibcode.

        Parameters
        ----------
        bibcode : str
            The bibcode of the paper we want to know who cites
        fl : str, optional
            Properties to return from query
        rows : int, optional
            Max number of rows to return

        Returns
        -------
        - : _ADSQuery object
            Object stores all information about query and the result
        """

        # Make sure bibcode is a string.
        assert type(bibcode) == str

        q = f"citations(bibcode:{bibcode})"

        return self.get(q, fl, rows=rows)


#    def references(self, bibcode, fl="title,bibcode,author,citation_count", rows=2000):
#        """
#        Query what references a paper contains.
#
#        Parameters
#        ----------
#        bibcode : str
#            The bibcode of the paper we want to know who cites
#        fl : str, optional
#            Properties to return from query
#        rows : int, optional
#            Max number of rows to return
#
#        Returns
#        -------
#        - : _ADSQuery object
#            Object stores all information about query and the result
#        """
#
#        # Make sure bibcode is a string.
#        assert type(bibcode) == str
#
#        q = f"references(bibcode:{bibcode})"
#
#        return self.get(q, fl, rows=rows)
