from urllib.parse import urlencode
import requests
import logging
from datetime import datetime
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union, Generator, Any, Tuple

# Configure logging
logger = logging.getLogger(__name__)


class ADSPaper:
    """
    Represents a single paper from ADS search results.
    """

    def __init__(self, data: Dict[str, Any]):
        """
        Initialize a paper with attributes from ADS API response.

        Parameters
        ----------
        data : Dict[str, Any]
            Dictionary containing paper attributes
        """
        for att, v in data.items():
            setattr(self, att, v)

    def __repr__(self) -> str:
        """Return a string representation of the paper."""
        if hasattr(self, "title") and hasattr(self, "bibcode"):
            return f"Paper({self.bibcode}): {self.title}"
        elif hasattr(self, "bibcode"):
            return f"Paper({self.bibcode})"
        else:
            return "Paper(Unknown)"


class ADSQuery2:
    """
    Represents the results of a query to the ADS API.
    """

    # Class constants
    ADS_BASE_URL = "https://ui.adsabs.harvard.edu/abs"

    def __init__(
        self,
        q: str,
        fl: str,
        rows: int,
        response: requests.Response,
        suppress_warnings: bool = False,
    ):
        """
        Store and process the result of an ADS API query.

        Parameters
        ----------
        q : str
            The search query string (URL-encoded).
        fl : str
            Comma-separated list of fields to return.
        rows : int
            Number of results requested.
        response : requests.Response
            The response object from the API request.
        suppress_warnings : bool, optional
            Whether to suppress pagination warnings, by default False.
            Useful for citations/references queries where partial results are expected.
        """
        # Store query parameters
        self.q = q
        self.fl = fl
        self.rows = rows
        self.suppress_warnings = suppress_warnings

        # Process the response
        self._parse(response)

    def _parse(self, response: requests.Response) -> None:
        """
        Parse the API response and store the results.

        Parameters
        ----------
        response : requests.Response
            The response from the API request.

        Raises
        ------
        ValueError
            If the query status is not 0 (success).
        """
        # Parse JSON response
        data = response.json()

        # Store query metadata
        header = data["responseHeader"]
        self.query_time = header["QTime"]
        self.query_status = header["status"]

        if self.query_status != 0:
            raise ValueError(f"Query failed with status {self.query_status}")

        # Store result metadata
        self.num_found = data["response"]["numFound"]
        docs = data["response"]["docs"]

        # Check if we got all results (but suppress for citations/references)
        if self.num_found > len(docs) and not self.suppress_warnings:
            logger.warning(
                f"Query returns more results than retrieved: {self.num_found} > {self.rows}. "
                "Consider pagination for complete results."
            )

        # Process the documents
        self._process_documents(docs)


class ADSQuery:
    """
    Represents the results of a query to the ADS API.
    """

    # Class constants
    ADS_BASE_URL = "https://ui.adsabs.harvard.edu/abs"

    def __init__(
        self,
        q: str,
        fl: str,
        rows: int,
        response: requests.Response,
        suppress_warnings: bool = False,
    ):
        """
        Store and process the result of an ADS API query.

        Parameters
        ----------
        q : str
            The search query string (URL-encoded).
        fl : str
            Comma-separated list of fields to return.
        rows : int
            Number of results requested.
        response : requests.Response
            The response object from the API request.
        suppress_warnings : bool, optional
            Whether to suppress pagination warnings, by default False.
            Useful for citations/references queries where partial results are expected.
        """
        # Store query parameters
        self.q = q
        self.fl = fl
        self.rows = rows
        self.suppress_warnings = suppress_warnings

        # Process the response
        self._parse(response)

    def _parse(self, response: requests.Response) -> None:
        """
        Parse the API response and store the results.

        Parameters
        ----------
        response : requests.Response
            The response from the API request.

        Raises
        ------
        ValueError
            If the query status is not 0 (success).
        """
        # Parse JSON response
        data = response.json()

        # Store query metadata
        header = data["responseHeader"]
        self.query_time = header["QTime"]
        self.query_status = header["status"]

        if self.query_status != 0:
            raise ValueError(f"Query failed with status {self.query_status}")

        # Store result metadata
        self.num_found = data["response"]["numFound"]
        docs = data["response"]["docs"]

        # Check if we got all results (but suppress for citations/references)
        if self.num_found > len(docs) and not self.suppress_warnings:
            logger.warning(
                f"Query returns more results than retrieved: {self.num_found} > {self.rows}. "
                "Consider pagination for complete results."
            )

        # Process the documents
        self._process_documents(docs)

    @property
    def papers(self) -> Generator[ADSPaper, None, None]:
        """
        Generate ADSPaper objects for each result.

        Yields
        ------
        ADSPaper
            Object representing a single paper.
        """
        if not hasattr(self, "papers_dict") or not self.papers_dict:
            return

        atts = list(self.papers_dict.keys())

        for i in range(len(self.papers_dict[atts[0]])):
            paper_data = {key: value[i] for key, value in self.papers_dict.items()}
            yield ADSPaper(paper_data)

    def _clean_value(self, value: Any) -> Any:
        """
        Clean values for storage in the papers dictionary.

        Parameters
        ----------
        value : Any
            The value to clean.

        Returns
        -------
        Any
            The cleaned value.
        """
        if isinstance(value, list) and len(value) == 1:
            return value[0]
        return value

    def _process_documents(self, docs: List[Dict[str, Any]]) -> None:
        """
        Process the documents returned by the API.

        Parameters
        ----------
        docs : List[Dict[str, Any]]
            The documents returned by the API.
        """
        # Initialize the dictionary to store results
        self.papers_dict = {field: [] for field in self.fl.split(",")}

        # Process each document
        rows_for_df = []
        for doc in docs:
            # Process for DataFrame
            row_dict = {}
            for field in self.fl.split(","):
                if field in doc:
                    value = self._clean_value(doc[field])
                    self.papers_dict[field].append(value)
                    # For DataFrame, handle lists
                    row_dict[field] = value if not isinstance(value, list) else value[0]
                else:
                    self.papers_dict[field].append(np.nan)
                    row_dict[field] = np.nan

            rows_for_df.append(row_dict)

        # Create DataFrame from all rows at once
        self.papers_df = pd.DataFrame(rows_for_df) if rows_for_df else None

        # Add computed columns
        self._add_computed_columns()

    def _add_computed_columns(self) -> None:
        """Add computed columns to the DataFrame and dictionary."""
        if self.papers_df is None or self.papers_df.empty:
            return

        # Add ADS link
        if "bibcode" in self.papers_df.columns:
            self.papers_df["ads_link"] = self.papers_df["bibcode"].apply(
                self._generate_ads_link
            )
            self.papers_dict["ads_link"] = self.papers_df["ads_link"].tolist()

        # Add years since publication
        if "pubdate" in self.papers_df.columns:
            self.papers_df["years_since_pub"] = self.papers_df["pubdate"].apply(
                self._years_since_publication
            )
            self.papers_dict["years_since_pub"] = self.papers_df[
                "years_since_pub"
            ].tolist()

        # Add citation count per year
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
            self.papers_dict["citation_count_per_year"] = self.papers_df[
                "citation_count_per_year"
            ].tolist()

        # Validate dictionary
        self._validate_dict_lengths()

    def _validate_dict_lengths(self) -> None:
        """
        Ensure all lists in the papers_dict have the same length.

        Raises
        ------
        ValueError
            If any list has a different length.
        """
        if not self.papers_dict:
            return

        lengths = {key: len(value) for key, value in self.papers_dict.items()}
        if len(set(lengths.values())) > 1:
            problematic = {
                k: v for k, v in lengths.items() if v != list(lengths.values())[0]
            }
            raise ValueError(f"Inconsistent array lengths: {problematic}")

    def _generate_ads_link(self, bibcode: str) -> str:
        """
        Generate the ADS webpage link for a paper.

        Parameters
        ----------
        bibcode : str
            The paper's bibcode.

        Returns
        -------
        str
            URL to the paper's ADS page.
        """
        return f"{self.ADS_BASE_URL}/{bibcode}/abstract"

    def _years_since_publication(self, pubdate: str) -> float:
        """
        Calculate years elapsed since publication.

        Parameters
        ----------
        pubdate : str
            The publication date in format 'YYYY-MM'.

        Returns
        -------
        float
            Number of years since publication.
        """
        try:
            # Parse the publication date
            year = int(pubdate.split("-")[0])
            month = int(pubdate.split("-")[1])
            if month == 0:
                month = 1

            pub_datetime = datetime.strptime(f"{year}-{month:02d}", "%Y-%m")

            # Calculate difference
            diff = (datetime.now() - pub_datetime).total_seconds()
            return diff / 31536000  # seconds in a year
        except (ValueError, IndexError, TypeError):
            logger.warning(f"Could not parse publication date: {pubdate}")
            return np.nan

    def _citations_per_year(self, years_since_pub: float, citation_count: int) -> float:
        """
        Calculate citations per year for a paper.

        Parameters
        ----------
        years_since_pub : float
            Years since publication.
        citation_count : int
            Total number of citations.

        Returns
        -------
        float
            Citations per year.
        """
        if pd.isna(years_since_pub) or pd.isna(citation_count):
            return np.nan
        elif years_since_pub <= 1 / 12:  # Less than a month old
            return 0.0
        else:
            return citation_count / years_since_pub


class ADSQueryWrapper:
    """
    Wrapper class for the ADS API.

    Provides methods to easily query the ADS API and retrieve results.
    """

    # Class constants
    API_URL = "https://api.adsabs.harvard.edu/v1/search/query"
    MAX_ROWS_PER_QUERY = 2000

    def __init__(self, ads_token: str, max_attempts: int = 3):
        """
        Initialize the ADS API wrapper.

        Parameters
        ----------
        ads_token : str
            Your ADS API token.
        max_attempts : int, optional
            Maximum number of attempts for failed requests, by default 3.
        """
        self.token = ads_token
        self.max_attempts = max_attempts
        self.ads_api_calls = 0
        self.ads_api_calls_remaining = None

    def __del__(self):
        """Log API usage information when the object is destroyed."""
        if self.ads_api_calls > 0:
            logger.info(
                f"Used {self.ads_api_calls} ADS API calls in this instance, "
                f"{self.ads_api_calls_remaining} calls remaining today."
            )

    def _safe_request(self, url: str, headers: Dict[str, str]) -> requests.Response:
        """
        Perform a safe API request, handling common errors like 401 Unauthorized.
        """
        for attempt in range(self.max_attempts):
            try:
                response = requests.get(url, headers=headers)
                self.ads_api_calls += 1
    
                if response.status_code == 200:
                    self.ads_api_calls_remaining = response.headers.get("X-RateLimit-Remaining")
                    return response
                elif response.status_code == 401:
                    raise ValueError("Unauthorized (401): Invalid or expired ADS token.")
                else:
                    logger.warning(
                        f"Attempt {attempt+1}/{self.max_attempts} failed with status {response.status_code}: {response.text}"
                    )
    
            except requests.RequestException as e:
                logger.warning(f"Attempt {attempt+1}/{self.max_attempts} failed: {str(e)}")
    
        raise RuntimeError(
            f"Failed to get a valid response from ADS API after {self.max_attempts} attempts."
        )

    def get_all_results(
        self,
        q: str,
        fl: str,
        sort: Optional[str] = None,
        max_results: Optional[int] = None,
    ) -> List[ADSQuery]:
        """
        Retrieve all results for a query using pagination.

        Parameters
        ----------
        q : str
            The search query string.
        fl : str
            Comma-separated list of fields to return.
        sort : str, optional
            Sort field and direction.
        max_results : int, optional
            Maximum number of results to retrieve.

        Returns
        -------
        List[ADSQuery]
            List of query result objects, one per page.
        """
        results = []
        page = 1
        rows = min(self.MAX_ROWS_PER_QUERY, max_results or self.MAX_ROWS_PER_QUERY)
        total_retrieved = 0

        # Get first page to determine total results
        first_query = self.get(q, fl, sort, rows, page)
        results.append(first_query)
        total_retrieved += len(first_query.papers_dict.get(fl.split(",")[0], []))

        # Get total count
        total_results = first_query.num_found
        if max_results is not None:
            total_results = min(total_results, max_results)

        # Continue pagination if needed
        while total_retrieved < total_results:
            page += 1
            rows_to_get = min(rows, total_results - total_retrieved)

            query = self.get(q, fl, sort, rows_to_get, page)
            results.append(query)

            retrieved = len(query.papers_dict.get(fl.split(",")[0], []))
            total_retrieved += retrieved

            # Break if we got fewer results than requested (end of results)
            if retrieved < rows_to_get:
                break

        return results

    def get(
        self,
        q: str,
        fl: str,
        sort: Optional[str] = None,
        rows: int = 10,
        page: int = 1,
        verbose: bool = False,
        suppress_warnings: bool = False,
    ) -> ADSQuery:
        """
        Perform a generic query to the ADS API.

        Parameters
        ----------
        q : str
            The search query string.
        fl : str
            Comma-separated list of fields to return.
        sort : str, optional
            Sort field and direction, e.g. "citation_count desc".
        rows : int, optional
            Number of results to return, by default 10.
        page : int, optional
            Page number for pagination, by default 1.
        verbose : bool, optional
            Whether to print verbose output, by default False.
        suppress_warnings : bool, optional
            Whether to suppress pagination warnings, by default False.

        Returns
        -------
        ADSQuery
            Object containing query results.

        Raises
        ------
        ValueError
            If rows exceeds the maximum allowed.
        RuntimeError
            If all API request attempts fail.
        """
        # Check rows limit
        if rows > self.MAX_ROWS_PER_QUERY:
            raise ValueError(f"Maximum allowed rows is {self.MAX_ROWS_PER_QUERY}")

        # Build query parameters
        params = {"q": q, "fl": fl, "rows": rows, "start": (page - 1) * rows}
        if sort:
            params["sort"] = sort

        # Log query if verbose
        if verbose:
            logger.info(f"Query: {params}")

        # Encode and build URL
        query_string = urlencode(params)
        url = f"{self.API_URL}?{query_string}"

        # Set up headers with auth token
        headers = {"Authorization": f"Bearer {self.token}"}

        # Make request with retries
        for attempt in range(self.max_attempts):
            try:
                response = self._safe_request(url, headers)
                self.ads_api_calls += 1

                # Check response status
                if response.status_code == 200:
                    # Update API calls remaining
                    self.ads_api_calls_remaining = response.headers.get(
                        "X-RateLimit-Remaining"
                    )
                    return ADSQuery(query_string, fl, rows, response, suppress_warnings)
                else:
                    logger.warning(
                        f"Attempt {attempt+1}/{self.max_attempts} failed with status "
                        f"{response.status_code}: {response.text}"
                    )
            except requests.RequestException as e:
                logger.warning(
                    f"Attempt {attempt+1}/{self.max_attempts} failed: {str(e)}"
                )

        # If we get here, all attempts failed
        raise RuntimeError(
            f"Failed to get response from ADS API after {self.max_attempts} attempts"
        )

    def citations(
        self,
        bibcode: str,
        fl: str = "title,bibcode,author,citation_count",
        rows: int = 2000,
    ) -> ADSQuery:
        """
        Find papers that cite a specific paper.

        Parameters
        ----------
        bibcode : str
            Bibcode of the paper to find citations for.
        fl : str, optional
            Fields to return.
        rows : int, optional
            Maximum number of results.

        Returns
        -------
        ADSQuery
            Query results containing citing papers.
        """
        if not isinstance(bibcode, str):
            raise TypeError("bibcode must be a string")

        query = f"citations(bibcode:{bibcode})"
        # Pass suppress_warnings=True to avoid pagination warnings for citations
        return self.get(query, fl, rows=rows, suppress_warnings=True)

    def references(
        self,
        bibcode: str,
        fl: str = "title,bibcode,author,citation_count",
        rows: int = 2000,
    ) -> ADSQuery:
        """
        Find references cited by a specific paper.

        Parameters
        ----------
        bibcode : str
            Bibcode of the paper to find references for.
        fl : str, optional
            Fields to return.
        rows : int, optional
            Maximum number of results.

        Returns
        -------
        ADSQuery
            Query results containing referenced papers.
        """
        if not isinstance(bibcode, str):
            raise TypeError("bibcode must be a string")

        query = f"references(bibcode:{bibcode})"
        # Pass suppress_warnings=True to avoid pagination warnings for references
        return self.get(query, fl, rows=rows, suppress_warnings=True)

    def search_author(
        self,
        author: str,
        fl: str = "title,bibcode,author,citation_count,pubdate",
        sort: str = "citation_count desc",
        rows: int = 100,
    ) -> ADSQuery:
        """
        Search for papers by a specific author.

        Parameters
        ----------
        author : str
            Author name in "LastName, FirstName" format.
        fl : str, optional
            Fields to return.
        sort : str, optional
            Sort order.
        rows : int, optional
            Maximum number of results.

        Returns
        -------
        ADSQuery
            Query results containing author's papers.
        """
        query = f'author:"{author}"'
        return self.get(query, fl, sort=sort, rows=rows)
