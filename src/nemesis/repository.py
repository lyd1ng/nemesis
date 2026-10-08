"""
Implements an abstraction to the sqlite database, s.t. the rest
of the aplication does not need to worry about sqlite etc...

Date:   20261002
Author: Lyding Anrie Brumm.
"""

from nemesis.domain import (ExperimentDescription, Experiment, Run, RunArtifact)
from pathlib import Path
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
                (ed.type, ed.type + ".py", ed.hash, ed.api_version),
            )
        if cursor.lastrowid is None:
            raise RuntimeError("Can not create expreiment description")
        return cursor.lastrowid

    def get_experiment_description(self, name: str) -> ExperimentDescription:
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
                raise RuntimeError(
                    "Experiment description could not be fetched"
                )
            return ExperimentDescription(
                type=str(row[0]),
                path=Path(row[1]),
                hash=row[2],
                api_version=row[3],
            )

    def add_experiment(self, ex: Experiment):
        """
        Add an experiment to the database
        """
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO experiments
                    (type, start_time, end_time, description, params, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    ex.type,
                    ex.start_time,
                    ex.end_time,
                    ex.description,
                    ex.params,
                    ex.status,
                ),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("Can not insert experiment")
            ex.id = cursor.lastrowid

    def update_experiment(self, ex: Experiment):
        """
        Update an experiment
        """
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE experiments SET
                    type = ?, start_time = ?, end_time = ?,
                    description = ?, status = ?
                WHERE id = ?
            """,
                (
                    ex.type,
                    ex.start_time,
                    ex.end_time,
                    ex.description,
                    ex.status,
                    ex.id,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("Can not update experiment")

    def get_list_of_experiments(self) -> list[str]:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT name FROM experiment_descriptions ORDER BY name
                """,
            )
            return [row[0] for row in cursor.fetchall()]

    def experiment_list_runs(self, ex: Experiment):
        """
        Returns a list of all runs of an experiment
        """
        run_ids: list[tuple[int,]] = []
        runs: list[Run] = []
        if ex.id is None:
            raise RuntimeError(
                "Can not list runs of partially initialised experiment"
            )
        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT id from runs WHERE eid = ?
            """,
                (ex.id,),
            )
            run_ids = cursor.fetchall()
            for run_id in run_ids:
                runs.append(self.get_run(run_id[0]))
        return runs

    def add_run(self, run: Run) -> int:
        """
        Add a run object to an experiment
        """
        run_id = None
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO runs 
                    (eid, end_time, start_time, description, executable, executable_hash, executable_commit, params, exit_code, status, invocation)
                VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.eid,
                    run.end_time,
                    run.start_time,
                    run.description,
                    str(run.executable),
                    run.executable_hash,
                    run.executable_commit,
                    run.params,
                    run.exit_code,
                    run.status,
                    run.invocation,
                ),
            )
            run_id = cursor.lastrowid
            if run_id is None:
                raise RuntimeError("Can not add run")
            for artifact in run.artifacts:
                artifact.id = self.__add_run_artifact(connection, artifact)
        return run_id

    def get_run(self, run_id: int) -> Run:
        """
        Get an run object from an id
        """
        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT 
                    id, eid, end_time, start_time, description, executable, executable_hash, executable_commit, params, exit_code, status, invocation FROM runs
                WHERE id = ?
                """,
                (run_id,),
            )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Can not fetch run")
        run: Run = Run(
            id=row[0],
            eid=row[1],
            end_time=row[2],
            start_time=row[3],
            description=row[4],
            executable=row[5],
            executable_hash=row[6],
            executable_commit=row[7],
            params=row[8],
            exit_code=row[9],
            status=row[10],
            invocation=row[11],
        )
        return run

    def update_run(self, run: Run):
        """
        Update a run
        """
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE runs SET
                    eid = ?,  end_time = ?,  start_time = ?,  description = ?,  executable = ?, 
                    executable_hash = ?,  executable_commit = ?,  params = ?,  exit_code = ?, invocation = ?,
                    status = ?
                WHERE id = ?
                """,
                (
                    run.eid,
                    run.end_time,
                    run.start_time,
                    run.description,
                    str(run.executable),
                    run.executable_hash,
                    run.executable_commit,
                    run.params,
                    run.exit_code,
                    run.invocation,
                    run.status,
                    run.id,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("Can not update experiment")
            for artifact in run.artifacts:
                self.__update_run_artifact(connection, artifact)

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
                raise RuntimeError(
                    "Can not create experiment description table"
                )
            cursor = connection.execute("""
                CREATE TABLE IF NOT EXISTS experiments (
                    id          INTEGER PRIMARY KEY,
                    type TEXT NOT NULL,
                    end_time    FLOAT,
                    start_time  FLOAT,
                    description TEXT,
                    params      TEXT,
                    status      TEXT NOT NULL CHECK (status in ('INIT', 'RUNNING', 'FAILED', 'SUCCESS'))
                )
                """)
            if cursor.lastrowid is None:
                raise RuntimeError(
                    "Can not create experiment description table"
                )
            cursor = connection.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    id                  INTEGER PRIMARY KEY,
                    eid                 INTEGER NOT NULL,
                    end_time            FLOAT,
                    start_time          FLOAT,
                    description         TEXT NOT NULL,
                    executable          TEXT NOT NULL,
                    executable_hash     TEXT NOT NULL,
                    executable_commit   TEXT NOT NULL,
                    params              TEXT,
                    exit_code           INTEGER,
                    invocation          TEXT,
                    status      TEXT NOT NULL CHECK (status in ('INIT', 'WAITING', 'RUNNING', 'FAILED', 'SUCCESS', 'BLOCKED')),
                    FOREIGN KEY (eid) REFERENCES experiments(id)
                )
                """)
            if cursor.lastrowid is None:
                raise RuntimeError(
                    "Can not create experiment description table"
                )
            cursor = connection.execute("""
                CREATE TABLE IF NOT EXISTS run_artifacts (
                    id      INTEGER PRIMARY KEY,
                    rid     INTEGER NOT NULL,
                    path    TEXT NOT NULL,
                    hash    TEXT NOT NULL,
                    FOREIGN KEY (rid) REFERENCES runs(id)
                )
                """)
            if cursor.lastrowid is None:
                raise RuntimeError(
                    "Can not create experiment description table"
                )

    def __add_run_artifact(
        self, connection: sqlite3.Connection, a: RunArtifact
    ):
        """
        Add a run artifact
        """
        cursor = connection.execute(
            """
            INSERT INTO run_artifacts 
                (rid, path, hash)
            VALUES
                (?, ?, ?)
            """,
            (a.rid, a.path, a.hash),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("Can not add run artifact")
        return cursor.lastrowid

    def __update_run_artifact(
        self, connection: sqlite3.Connection, a: RunArtifact
    ):
        """
        Update run artifact
        """
        cursor = connection.execute(
            """
            INSERT INTO run_artifacts (id, rid, path, hash)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                rid  = excluded.rid,
                path = excluded.path,
                hash = excluded.hash
            """,
            (a.id, a.rid, str(a.path), a.hash),
        )
        if cursor.rowcount != 1:
            print(a)
            raise RuntimeError("Can not insert/update run artifact")
