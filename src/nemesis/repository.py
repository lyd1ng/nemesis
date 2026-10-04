"""
Implements an abstraction to the sqlite database, s.t. the rest
of the aplication does not need to worry about sqlite etc...

Date:   20261002
Author: Lyding Anrie Brumm.
"""

from nemesis.domain import ExperimentDescription
from pathlib import Path
from typing import cast
import sqlite3


class Repository(object):
    """
    This class encapsulates the communication with the sqlite database.
    The only reason why this is turned into a class and not kept a module
    is the internal state i.e. the database connection.
    If kept as a module this would be an awkward global variable.
    """

    def __init__(self, db_path: Path):
        self.db_path: Path = db_path
        self._initialize()

    def add_experiment_description(self, ed: ExperimentDescription):
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO experiment_descriptions
                    (name, path, hash, api_version)
                VALUES
                    (?, ?, ?, ?)
                """,
                (ed.name, ed.name + ".py", ed.hash, ed.api_version),
            )
        if cursor.lastrowid is None:
            raise RuntimeError("Can not create expreiment description")
        return cursor.lastrowid

    def get_experiment_description(
        self, name: str
    ) -> ExperimentDescription | None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT name, path, hash, api_version FROM experiment_descriptions WHERE
                    name=?
                """,
                (name,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return ExperimentDescription(
                name=str(row[0]),
                path=Path(row[1]),
                hash=row[2],
                api_version=row[3],
            )

    def get_list_of_experiments(self) -> list[str]:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT name FROM experiment_descriptions ORDER BY name
                """,
            )
            return [row[0] for row in cursor.fetchall()]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        _ = connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            cursor = connection.execute("""
                CREATE TABLE IF NOT EXISTS experiment_descriptions (
                    id          INTEGER PRIMARY KEY,
                    name        TEXT NOT NULL UNIQUE,
                    path        TEXT NOT NULL,
                    hash        TEXT NOT NULL,
                    api_version TEXT NOT NULL
                )
                """)
        if cursor.lastrowid is None:
            raise RuntimeError("Can not create experiment description table")
