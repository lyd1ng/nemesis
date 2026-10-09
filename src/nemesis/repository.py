"""
Implements an abstraction to the sqlite database, s.t. the rest
of the aplication does not need to worry about sqlite etc...

Date:   20261002
Author: Lyding Anrie Brumm.
"""

from nemesis.domain import (
    ExperimentResult,
    ExperimentTemplate,
    Experiment,
    Run,
    RunArtifact,
)
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

    def add_experiment_template(self, ed: ExperimentTemplate):
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO experiment_templates
                    (name, path, hash, api_version)
                VALUES
                    (?, ?, ?, ?)
                """,
                (ed.type, ed.type + ".py", ed.hash, ed.api_version),
            )
        if cursor.lastrowid is None:
            raise RuntimeError("Can not create experiment template")
        return cursor.lastrowid

    def get_experiment_description(self, name: str) -> ExperimentTemplate:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT name, path, hash, api_version FROM experiment_templates WHERE
                    name=?
                """,
                (name,),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Experiment template could not be fetched")
            return ExperimentTemplate(
                type=str(row[0]),
                path=Path(row[1]),
                hash=row[2],
                api_version=row[3],
            )

    def upsert_experiment(self, ex: Experiment):
        """
        Add an experiment to the database
        """
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO experiments
                    (id, wid, type, start_time, end_time, description, params, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (id) DO UPDATE SET
                    type = excluded.type,
                    wid = excluded.wid,
                    start_time = excluded.start_time,
                    end_time = excluded.end_time,
                    description = excluded.description,
                    params = excluded.params,
                    status = excluded.status
                RETURNING id
            """,
                (
                    ex.id,
                    ex.wid,
                    ex.type,
                    ex.start_time,
                    ex.end_time,
                    ex.description,
                    ex.params,
                    ex.status,
                ),
            )
            id = cursor.fetchone()[0]
            if id is None:
                raise RuntimeError("Can not upsert experiment ")
            for result in ex.results:
                result.id = self.__upsert_experiment_result(connection, result)
            return id

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

    def upsert_run(self, run: Run) -> int:
        """
        Add a run object to an experiment
        """
        run_id = None
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO runs 
                    (id, eid, end_time, start_time, description, executable, executable_hash, executable_commit, params, exit_code, status, invocation)
                VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (id) DO UPDATE SET
                    eid = excluded.eid,
                    end_time = excluded.end_time,
                    start_time = excluded.start_time,
                    description = excluded.description,
                    executable = excluded.executable,
                    executable_hash = excluded.executable_hash,
                    executable_commit = excluded.executable_commit,
                    params = excluded.params,
                    exit_code = excluded.exit_code,
                    status = excluded.status,
                    invocation = excluded.invocation
                RETURNING id
                """,
                (
                    run.id,
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
            run_id = cursor.fetchone()[0]
            if run_id is None:
                raise RuntimeError("Can not upsert experiment ")
            for artifact in run.artifacts:
                artifact.id = self.__upsert_run_artifact(connection, artifact)
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

    def add_working_directory(self, path: Path, dir_type: str):
        """
        Add a new working directory to the db
        """
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO working_directories 
                    (path, type)
                VALUES
                    (?, ?)
                """,
                (str(path), dir_type),
            )
        if cursor.lastrowid is None:
            raise RuntimeError("Can add working directory")
        return cursor.lastrowid

    def get_wid_from_path(self, path: Path) -> int | None:
        """
        Get the wid of a path or None if it not yet registered
        """
        with self._connect() as connection:
            cursor = connection.execute(
                """
            SELECT id from working_directories WHERE path=?
            """,
                (str(path),),
            )
            row = cursor.fetchone()
            if row is None:
                return None
        return cast(int, row[0])

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        _ = connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            cursor = connection.execute("""
                CREATE TABLE IF NOT EXISTS experiment_templates (
                    id          INTEGER PRIMARY KEY,
                    name        TEXT NOT NULL UNIQUE,
                    path        TEXT NOT NULL,
                    hash        TEXT NOT NULL,
                    api_version TEXT NOT NULL
                )
                """)
            if cursor.lastrowid is None:
                raise RuntimeError("Can not create experiment templates table")
            cursor = connection.execute("""
                CREATE TABLE IF NOT EXISTS experiments (
                    id          INTEGER PRIMARY KEY,
                    wid         INTEGER,
                    type TEXT NOT NULL,
                    end_time    FLOAT,
                    start_time  FLOAT,
                    description TEXT,
                    params      TEXT,
                    mark        TEXT,
                    status      TEXT NOT NULL CHECK (status in ('INIT', 'RUNNING', 'FAILED', 'SUCCESS')),
                    FOREIGN KEY (wid) REFERENCES working_directories(id)
                )
                """)
            if cursor.lastrowid is None:
                raise RuntimeError("Can not create experiments table")
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
                raise RuntimeError("Can not create runs table")
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
                raise RuntimeError("Can not create run artifacts table")
            cursor = connection.execute("""
                CREATE TABLE IF NOT EXISTS experiment_results (
                    id              INTEGER PRIMARY KEY,
                    eid             INTEGER NOT NULL,
                    rid             INTEGER NOT NULL,
                    description     TEXT NOT NULL,
                    path            TEXT NOT NULL,
                    hash            TEXT NOT NULL,
                    FOREIGN KEY (eid) REFERENCES experiments(id)
                    FOREIGN KEY (rid) REFERENCES runs(id)
                )
                """)
            if cursor.lastrowid is None:
                raise RuntimeError("Can not create experiment result table")
            cursor = connection.execute("""
                CREATE TABLE IF NOT EXISTS working_directories(
                    id              INTEGER PRIMARY KEY,
                    path            TEXT NOT NULL,
                    type            TEXT NOT NULL CHECK (type in ('LOCAL', 'REMOTE'))
                )
                """)
            if cursor.lastrowid is None:
                raise RuntimeError("Can not create working directory table")

    def __upsert_run_artifact(
        self, connection: sqlite3.Connection, a: RunArtifact
    ) -> int:
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
            RETURNING id
            """,
            (a.id, a.rid, str(a.path), a.hash),
        )
        id = cursor.fetchone()[0]
        if id is None:
            raise RuntimeError("Can not upsert run artifact")
        return id

    def __upsert_experiment_result(
        self, connection: sqlite3.Connection, er: ExperimentResult
    ) -> int:
        """
        Upsert experiment result
        """
        cursor = connection.execute(
            """
            INSERT INTO experiment_results (id, eid, rid, description, path, hash)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                eid  = excluded.eid,
                rid  = excluded.rid,
                description = excluded.hash,
                path = excluded.path,
                hash = excluded.hash
            RETURNING id
            """,
            (er.id, er.eid, er.rid, er.description, str(er.path), er.hash),
        )
        id = cursor.fetchone()[0]
        if id is None:
            raise RuntimeError("Can not upsert run artifact")
        return id
