"""
Implements an abstraction to the sqlite database, s.t. the rest
of the aplication does not need to worry about sqlite etc...

Date:   20261002
Author: Lyding Anrie Brumm.
"""

from functools import reduce
import tomllib

from nemesis.domain import (
    ExperimentResult,
    ExperimentTemplate,
    Experiment,
    Run,
    RunArtifact,
    User,
    WorkingDirectory,
    WorkingDirectoryEnv,
)
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
        if db_path != Path(""):
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

    def add_working_directory(self, working_directory: WorkingDirectory):
        """
        Add a new working directory to the db
        """
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO working_directories 
                    (path, type, ssh_alias)
                VALUES
                    (?, ?, ?)
                """,
                (
                    str(working_directory.path),
                    working_directory.type,
                    working_directory.ssh_alias,
                ),
            )
        if cursor.lastrowid is None:
            raise RuntimeError("Can not add working directory")
        return cursor.lastrowid

    def add_working_directory_env(self, wdc: WorkingDirectoryEnv) -> int:
        """
        Add a working directory configuration
        """
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO working_directory_envs (wid, content, hash, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (wdc.wid, wdc.content, wdc.hash, wdc.created_at),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("Can not add working directory config")
            return cursor.lastrowid

    def upsert_experiment(self, ex: Experiment):
        """
        Add an experiment to the database
        """
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO experiments
                    (id, wid, weid, user, type, start_time, end_time, description, params, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (id) DO UPDATE SET
                    type = excluded.type,
                    wid = excluded.wid,
                    weid = excluded.weid,
                    user = excluded.user,
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
                    ex.weid,
                    ex.user,
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

    def upsert_run(self, run: Run) -> int:
        """
        Add a run object to an experiment
        """
        run_id = None
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO runs 
                    (id, eid, end_time, start_time, description, executable, executable_hash, executable_commit, mode, params, exit_code, status, invocation)
                VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (id) DO UPDATE SET
                    eid = excluded.eid,
                    end_time = excluded.end_time,
                    start_time = excluded.start_time,
                    description = excluded.description,
                    executable = excluded.executable,
                    executable_hash = excluded.executable_hash,
                    executable_commit = excluded.executable_commit,
                    mode = excluded.mode,
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
                    run.mode,
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

    def upsert_run_artifact(self, a: RunArtifact) -> int:
        """
        Update run artifact
        """
        with self._connect() as connection:
            return self.__upsert_run_artifact(connection, a)

    def upsert_user(self, u: User) -> int:
        """
        Update a user
        """
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO users (name, alias, email)
                VALUES (?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    alias = excluded.alias,
                    email = excluded.email
                RETURNING name
                """,
                (u.name, u.alias, u.email),
            )
            row = cursor.fetchone()[0]
        return row

    def get_wds(self) -> list[int]:
        """
        Get a list of all working directories
        """
        result: list[int] = []
        with self._connect() as connection:
            cursor = connection.execute("SELECT id from working_directories")
            wids: list[tuple[int]] = cursor.fetchall()
        for wid in wids:
            result.append(wid[0])
        return result

    def get_latest_wdes(self):
        """
        Get a list of all latest working directory environments
        """
        result: list[WorkingDirectoryEnv] = []
        wds = self.get_wds()
        for wd in wds:
            result.append(self.get_wdes(wd)[-1])
        return result

    def get_experiment(self, eid: int) -> Experiment:
        """
        Get an experiment from its eid
        """
        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT wid, weid, user, type, end_time, start_time, description, params, status, mark FROM experiments WHERE id = ?
                """,
                (eid,),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError(f"Can not get experiment with id={eid}")
            experiment: Experiment = Experiment(
                id=eid,
                wid=row[0],
                weid=row[1],
                user=row[2],
                type=row[3],
                end_time=row[4],
                start_time=row[5],
                description=row[6],
                params=row[7],
                status=row[8],
                results=[],
                mark=row[9],
            )
        return experiment

    def get_experiment_ids(
        self, filter: list[tuple[str, str, str]]
    ) -> list[int]:
        """
        Get experiment ids subject to various filters
        """
        prefix = "SELECT id from experiments tables WHERE "
        query = reduce(
            lambda a, b: a + " AND " + b,
            [f"{entry[0]}{entry[1]}?" for entry in filter],
        )
        with self._connect() as connection:
            cursor = connection.execute(
                prefix + query, list(map(lambda x: x[2], filter))
            )
            rows = cursor.fetchall()
        return list(map(lambda r: r[0], rows))

    def get_experiment_run_ids(self, ex: Experiment):
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

    def get_wid_from_path(self, path: Path) -> int:
        """
        Get the wid of a path
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
                raise RuntimeError(
                    f"Can not get wid from {path}. Not registered?"
                )
        return row[0]

    def get_working_directory(self, wid: int) -> WorkingDirectory:
        """
        Get working directory with id=wid
        """
        with self._connect() as connection:
            cursor = connection.execute(
                """
            SELECT id, path, type, ssh_alias from working_directories WHERE id=?
            """,
                (wid,),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError(
                    f"Could not get working_directory of id {wid}"
                )
        wid = row[0]
        config = self.get_wdes(wid)
        return WorkingDirectory(
            wid, path=row[1], type=row[2], ssh_alias=row[3], env=config
        )

    def get_list_of_experiment_names(self) -> list[str]:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT name FROM experiment_descriptions ORDER BY name
                """,
            )
            return [row[0] for row in cursor.fetchall()]

    def get_run(self, run_id: int) -> Run:
        """
        Get an run object from an id
        """
        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT 
                    id, eid, end_time, start_time, description, executable, executable_hash, executable_commit, mode, params, exit_code, status, invocation FROM runs
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
            mode=row[8],
            params=row[9],
            exit_code=row[10],
            status=row[11],
            invocation=row[12],
        )
        return run

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

    def get_wdes(self, wid: int) -> list[WorkingDirectoryEnv]:
        """
        Get the configs of a working directory in chronological order
        """
        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT id, wid, content, hash, created_at FROM working_directory_envs
                WHERE wid = ?
            """,
                (wid,),
            )
            rows = cursor.fetchall()
            result: list[WorkingDirectoryEnv] = []
            for row in rows:
                result.append(
                    WorkingDirectoryEnv(
                        id=row[0],
                        wid=row[1],
                        content=row[2],
                        hash=row[3],
                        created_at=row[4],
                        variables=tomllib.loads(row[2]),
                    )
                )
            # Sort the configurations by the date of creation
            # this way the latest configuration is a position -1,
            # as god intended
            result.sort(key=lambda x: x.created_at)
            return result

    def get_experiment_result(self, id: int) -> ExperimentResult:
        """
        Get an experiment result from a result id
        """
        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT eid, rid, description, path, hash from experiment_results where id=?
                """,
                (id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError(
                    f"Can not get experiment result with id {id}"
                )
            return ExperimentResult(
                id,
                eid=row[0],
                rid=row[1],
                description=row[2],
                path=Path(row[3]),
                hash=row[4],
            )

    def get_experiment_results(self, eid: int) -> list[ExperimentResult]:
        """
        Get a list of all results of a specifid experiment
        """
        rids: list[int] = []
        results: list[ExperimentResult] = []
        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT id from experiment_results where eid=?
                """,
                (eid,),
            )
            row = cursor.fetchall()
            for entry in row:
                rids.append(entry[0])
            for rid in rids:
                results.append(self.get_experiment_result(rid))
        return results

    def get_user(self, name: str) -> User:
        """
        Get a user from their name
        """
        with self._connect() as connection:
            cursor = connection.execute(
                "SELECT alias, email FROM users WHERE name=?", (name,)
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError(f"Can not get user with name {name}.")
            return User(name, row[0], row[1])

    def _connect(self) -> sqlite3.Connection:
        if self.db_path is None:
            raise RuntimeError("Trying to connect to NONE")
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
                    weid        INTEGER,
                    user        TEXT NOT NULL,
                    type TEXT NOT NULL,
                    end_time    FLOAT,
                    start_time  FLOAT,
                    description TEXT,
                    params      TEXT,
                    mark        TEXT,
                    status      TEXT NOT NULL CHECK (status in ('INIT', 'RUNNING', 'FAILED', 'SUCCESS')),
                    FOREIGN KEY (wid) REFERENCES working_directories(id)
                    FOREIGN KEY (weid) REFERENCES working_directory_envs(id)
                    FOREIGN KEY (user) REFERENCES users(name)
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
                    mode                TEXT NOT NULL,
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
                    FOREIGN KEY (eid) REFERENCES experiments(id),
                    FOREIGN KEY (rid) REFERENCES runs(id)
                )
                """)
            if cursor.lastrowid is None:
                raise RuntimeError("Can not create experiment result table")
            cursor = connection.execute("""
                CREATE TABLE IF NOT EXISTS working_directories(
                    id              INTEGER PRIMARY KEY,
                    path            TEXT NOT NULL,
                    type            TEXT NOT NULL CHECK (type in ('LOCAL', 'REMOTE')),
                    ssh_alias       TEXT
                )
                """)
            if cursor.lastrowid is None:
                raise RuntimeError("Can not create working directory table")
            cursor = connection.execute("""
                CREATE TABLE IF NOT EXISTS working_directory_envs(
                    id              INTEGER PRIMARY KEY,
                    wid             INTEGER NOT NULL,
                    content         TEXT NOT NULL,
                    hash            TEXT NOT NULL,
                    created_at  FLOAT NOT NULL,
                    FOREIGN KEY (wid) REFERENCES working_directories(id)
                )
                """)
            if cursor.lastrowid is None:
                raise RuntimeError(
                    "Can not create working directory configs table"
                )
            cursor = connection.execute("""
                CREATE TABLE IF NOT EXISTS users(
                    name            TEXT PRIMARY KEY,
                    alias           TEXT NOT NULL,
                    email           TEXT NOT NULL
                )
                """)
            if cursor.lastrowid is None:
                raise RuntimeError("Can not create user table")
            cursor = connection.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS unique_local_directory
                ON working_directories(path)
                WHERE ssh_alias IS NULL
                """)
            if cursor.lastrowid is None:
                raise RuntimeError("Can not create unique index for local")
            cursor = connection.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS unique_remote_directory
                ON working_directories(ssh_alias, path)
                WHERE ssh_alias IS NOT NULL
                """)
            if cursor.lastrowid is None:
                raise RuntimeError("Can not create unique index for remote")
            cursor = connection.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS unique_alias
                ON users(alias)
                """)
            if cursor.lastrowid is None:
                raise RuntimeError("Can not create unique index for user alias")
            for operation in ("UPDATE", "DELETE"):
                cursor = connection.execute(f"""
                    CREATE TRIGGER IF NOT EXISTS prevent_config_{operation.lower()}
                    BEFORE {operation} ON working_directory_envs 
                    BEGIN
                        SELECT RAISE(ABORT, 'Configuration revisions are immutable');
                    END;
                """)

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
