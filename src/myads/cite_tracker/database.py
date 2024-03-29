import os
import pandas as pd
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from tabulate import tabulate

home_directory = os.path.expanduser("~")
_DATABASE = os.path.join(home_directory, "myADS_database.db")


# Create a base class for declarative class definitions
class Base(DeclarativeBase):
    pass


# Authors we are keeping track of
class Author(Base):
    __tablename__ = "authors"
    id = Column(Integer, primary_key=True)
    forename = Column(String(50), nullable=False)
    surname = Column(String(50), nullable=False)
    orcid = Column(String(50))

    __table_args__ = (
        UniqueConstraint(
            "forename", "surname", "orcid", name="uq_forename_surname_orcid"
        ),
    )


# Stores information about authors publications
class Publication(Base):
    __tablename__ = "publications"
    id = Column(Integer, primary_key=True)
    bibcode = Column(String(50), nullable=False)
    title = Column(String, nullable=False)
    author_id = Column(Integer, ForeignKey("authors.id"), nullable=False)

    __table_args__ = (UniqueConstraint("title", "bibcode", name="uq_pub_title_bib"),)


# Stores information about publications that have cited our authors publications
class ReferencePublication(Base):
    __tablename__ = "reference_publications"
    id = Column(Integer, primary_key=True)
    bibcode = Column(String(50), nullable=False)
    title = Column(String, nullable=False)
    publication_id = Column(Integer, ForeignKey("publications.id"))

    __table_args__ = (
        UniqueConstraint(
            "title", "bibcode", "publication_id", name="uq_refpub_title_bib"
        ),
    )


# Stores metadata information, like the ADS token
class ADSToken(Base):
    __tablename__ = "ads_token"
    id = Column(Integer, primary_key=True)
    token = Column(String, nullable=False)


class Database:
    def __init__(self):
        self.engine = create_engine(f"sqlite:///{_DATABASE}")
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def __del__(self):
        # Close the session to the database
        self.session.close()

    def initialize(self):
        """First time initialization of the database"""

        # Create the tables in the database
        Base.metadata.create_all(self.engine)

    def add_author(self, forename: str, surname: str, orcid: str = None):
        """Add a new author to the database"""

        try:
            self.session.add(Author(forename=forename, surname=surname, orcid=orcid))
            self.session.commit()
        except:
            print("Author already exists in the database")

    def get_authors(self):
        """List all the authors in the database"""
        return self.session.query(Author).all()

    def delete_author(self, id: int):
        """Delete an tracked author from the database"""
        query_result = self.session.query(Author).filter_by(id=id).first()

        if query_result:
            self.session.delete(query_result)
            self.session.commit()
        else:
            print(f"Author {id} not found in database")

    def list_authors(self):
        """List all the authors in the database"""
        df = pd.read_sql_query(self.session.query(Author).statement, self.session.bind)

        print(
            tabulate(
                df,
                tablefmt="grid",
                showindex="never",
                headers=["Forename", "Surname", "ORCID"],
            )
        )

    def add_ads_token(self, token: str):
        """Add ADS token to database"""

        # Check if we already have an entry, if so we will replace it
        query_result = self.session.query(ADSToken).first()

        if query_result:
            query_result.token = token
        else:
            self.session.add(ADSToken(token=token))
        self.session.commit()
        print(f"Registered ADS token {token}")

    def get_ads_token(self) -> str:
        """Get ADS token from database"""

        query_result = self.session.query(ADSToken).first()
        if query_result:
            return query_result.token
        else:
            return None

    def _is_pub_in_database(self, author_id: int, bibcode: str, title: str, table):
        """
        Is this publication already in the database?

        Parameters
        ----------
        author_id : int
            The author id when table == "Publication", publication_id when
            table == "ReferencePublication"
        bibcode : str
        title : str
        table : str
            References the table we are searching, ["ReferencePublication" or
            "Publication"]

        Returns
        -------
        found_butnewtitle : bool
            True if paper is there, but the title needs updated
        found_butnewbibcode : bool
            True if paper is there, but the bibcode needs updated
        found : bool
            True if paper is there and up to date
        """

        found_butnewtitle = False
        found_butnewbibcode = False
        found = False

        if table == "Publication":
            X = Publication
        elif table == "ReferencePublication":
            X = ReferencePublication
        else:
            raise ValueError()

        # Is publication in database, but the title has changed?
        query_result = self.session.query(X).filter_by(bibcode=bibcode)

        if table == "Publication":
            query_result = query_result.filter_by(author_id=author_id).first()
        else:
            query_result = query_result.filter_by(publication_id=author_id).first()

        if query_result:
            if query_result.title != title:
                found_butnewtitle = True
                query_result.title = title

        # Is publication in database, but the bibcode has changed?
        query_result = self.session.query(X).filter_by(title=title)

        if table == "Publication":
            query_result = query_result.filter_by(author_id=author_id).first()
        else:
            query_result = query_result.filter_by(publication_id=author_id).first()

        if query_result:
            if query_result.bibcode != bibcode:
                found_butnewbibcode = True
                query_result.bibcode = bibcode

        # Is the publication in the database
        query_result = self.session.query(X).filter_by(bibcode=bibcode, title=title)

        if table == "Publication":
            query_result = query_result.filter_by(author_id=author_id).first()
        else:
            query_result = query_result.filter_by(publication_id=author_id).first()

        if query_result:
            found = True

        return found_butnewtitle, found_butnewbibcode, found

    def refresh_author_papers(self, id: int, data):
        """
        Update the publications for a given author.

        If the title or bibcode changes, make a new entry, but keep the old one to.

        Parameters
        ----------
        id : int
            Author ID
        data : list[myADS paper object]
            List of papers
        """

        for paper in data.papers:
            # Paper already in databae?
            found_butnewtitle, found_butnewbibcode, found = self._is_pub_in_database(
                id, paper.bibcode, paper.title, "Publication"
            )

            # If not, add it
            if not (found_butnewtitle or found_butnewbibcode) and (not found):
                self.session.add(
                    Publication(bibcode=paper.bibcode, title=paper.title, author_id=id)
                )

        self.session.commit()

    def check_paper_new_cites(self, id: int, refpaper, data):
        """
        Check if a publication has any new cites.

        If a paper that has cited an authors paper has been updated, e.g., a
        new bibcode, it is treated as a "updated_cite" rather than a
        "new_cite".

        Parameters
        ----------
        id : int
            Author ID
        refpaper : myADS paper object
            The publication we are currently checking new cites for
        data : list[myADS paper object]
            Up to date list of papers that site our publication

        Returns
        -------
        new_cites : dict
        updated_cites : dict
        """

        # Where is the ref paper in the database
        query_result = (
            self.session.query(Publication)
            .filter_by(bibcode=refpaper.bibcode, title=refpaper.title)
            .first()
        )

        if not query_result:
            raise Exception("Checking for new cites on a paper that doesn't exist")

        publication_id = query_result.id

        # Loop over each paper that cites this publication and see if any are new
        new_cites = []
        updated_cites = []
        for paper in data.papers:
            # Paper already in databae?
            found_butnewtitle, found_butnewbibcode, found = self._is_pub_in_database(
                publication_id, paper.bibcode, paper.title, "ReferencePublication"
            )

            if found_butnewtitle or found_butnewbibcode:
                updated_cites.append(paper)
                continue

            if not found:
                self.session.add(
                    ReferencePublication(
                        bibcode=paper.bibcode,
                        title=paper.title,
                        publication_id=publication_id,
                    )
                )

                new_cites.append(paper)

        self.session.commit()

        return new_cites, updated_cites
