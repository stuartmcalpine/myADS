from urllib.parse import urlencode
import requests

import myads
from datetime import datetime

class _ADSPaper:
    def __init__(self, paper_info):

        for att in paper_info.keys():
            setattr(self, att, paper_info[att])

    def get_years_since_publication(self):
        """
        Return the number of years since publication.

        Returns
        -------
        diff_years : float
            Total number of years since publication
        """

        # We need to have return publication date in our query.
        if hasattr(self, "pubdate"):

            # Convert to datetime
            pubyear = int(self.pubdate.split('-')[0])
            pubmonth = int(self.pubdate.split('-')[1])
            if pubmonth == 0:
                pubmonth += 1
            dt = f"{pubyear}-{pubmonth}"
            diff = datetime.now() - datetime.strptime(dt, "%Y-%m")

            # Convert to years.
            diff_years = diff.total_seconds() / 31536000
            return diff_years
        else:
            return None

    @property
    def citations_per_year(self) -> float:
        """ 
        How many citations has this paper has per year?

        Needs to have had "pubdate" and "citation_count" in the original query.
        """

        pubyears = self.get_years_since_publication()
        if pubyears is None or not hasattr(self, "citation_count"):
            return None
        else:
            return self.citation_count / pubyears

    @property
    def link(self) -> str:
        """ Return string hyperlink to ADS page """

        # Need bibcode in original query.
        if not hasattr(self, "bibcode"):
            return None
        
        label = self.bibcode
        uri = f"https://ui.adsabs.harvard.edu/abs/{self.bibcode}/abstract"
        parameters = ''

        # OSC 8 ; params ; URI ST <name> OSC 8 ;; ST 
        escape_mask = '\033]8;{};{}\033\\{}\033]8;;\033\\'

        return escape_mask.format(parameters, uri, label)

class _ADSQuery:
    def __init__(self, q, fl, rows, request_data):
        """
        Stores the result of an individual query.

        Not designed to be called standalone, should be called from within the
        ADSQueryWrapper object.

        Parameters
        ----------
        q : string
            The query sent to ADS
        fl : string
            Properties to return from query
        rows : int
            Max number of rows to return
        request_data : requests "get" object
            The data returned from the query from the requests lib

        Attributes
        ----------
        q : string
            See parameters
        fl : string
            See parameters
        rows : int
            See parameters
        query_time : float
            Execution time of query
        query_status: int
            Query return status
        num_found : int
            Papers found as result from query
        papers : list of dicts
            Each paper's info stored in a dict

        Example usage
        -------------
        import requests
        ...

        q = "first_author:McAlpine,Stuart" 
        fl = "title,citation_count,bibcode"
        rows = 20
        request_data = requests.get(...)

        X = _ADSQuery(q, fl, rows, request_data)
        """

        # Store the query info.
        self.q = q
        self.fl = fl
        self.rows = rows

        # Parse out the requests information for this query.
        self.parse(request_data)

    def parse(self, request_data):

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
            print(f"Warning: Query {self.q} returns over max rows,"
                  f"({self.num_found} > {self.rows})",
                  "not all papers will be in the list")

        self.papers = []
        for i in range(len(request_data["response"]["docs"])):
            self.papers.append(_ADSPaper(request_data["response"]["docs"][i]))

    def get_all(self, what):
        data = []

        for i in range(len(self.papers)):
            data.append(getattr(self.papers[i], what))

        return data


class ADSQueryWrapper:
    def __init__(self):
        """
        Class that wraps calls to the ADS API to make easy queries.

        Each method returns a _ADSQuery object, which contains information
        about the query, the reponse from the ADS API, and the result of the query. The
        result of the query is stored in a "paper" list in the _ASDQuery object, for
        which each entry is a list containing information about the papers in the query
        result. 

        Methods
        -------
        get(query_string, return_columns, max_return_rows)
            Perform a generic query to the ADS API
        citations(bibcode)
            Query the ADS API to return all cites to a given paper
        references(bibcode)
            Query the ADS API to return all references within a given paper

        """

        # ADS API token.
        self.token = myads.config["_ADS_TOKEN"]

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

    def get(self, q, fl, rows=20):
        """
        Perform generic query using the ADS API.

        Parameters
        ----------
        q : string
            The query sent to ADS
        fl : string
            Properties to return from query
        rows : int (optional)
            Max number of rows to return from the query

        Returns
        -------
        - : _ADSQuery object
            Object stores all information about query and the result
        """

        # Build query dict.
        query = {"q": q, "fl": fl, "rows": rows}

        # Convert query dict to string.
        q = self._encode_string(query)
        url = f"https://api.adsabs.harvard.edu/v1/search/query?{q}"

        # Need authorization token in header.
        headers = {"Authorization": f"Bearer:{self.token}"}

        # Make get request.
        resp = requests.get(url, headers=headers)
        self.ads_api_calls += 1

        # Look at the header to see how many queries we have left.
        self.ads_api_calls_remaining = resp.headers["X-RateLimit-Remaining"]

        return _ADSQuery(q, fl, rows, resp)

    #    def metrics(self, bibcode):
    #        # Make sure bibcode is list.
    #        if type(bibcode) == str:
    #            bibcode = [bibcode]
    #
    #        # Need authorization token in header.
    #        headers={"Authorization": f"Bearer:{self.token}"}
    #
    #        url = "https://api.adsabs.harvard.edu/v1/metrics"
    #        myobj = {'bibcodes': bibcode}
    #        x = requests.post(url, json=myobj, headers=headers)
    #        self.ads_api_calls += 1
    #
    #        return _ADSQuery(q, fl, rows, resp)

    def citations(self, bibcode, fl="title,bibcode,author,citation_count", rows=2000):
        """
        Query what papers cite a paper of a given bibcode.

        Parameters
        ----------
        bibcode : string
            The bibcode of the paper we want to know who cites
        fl : string (optional)
            Properties to return from query
        rows : int (optional)
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

    def references(self, bibcode, fl="title,bibcode,author,citation_count", rows=2000):
        """
        Query what references a paper contains.

        Parameters
        ----------
        bibcode : string
            The bibcode of the paper we want to know who cites
        fl : string (optional)
            Properties to return from query
        rows : int (optional)
            Max number of rows to return

        Returns
        -------
        - : _ADSQuery object
            Object stores all information about query and the result
        """

        # Make sure bibcode is a string.
        assert type(bibcode) == str

        q = f"references(bibcode:{bibcode})"

        return self.get(q, fl, rows=rows)
