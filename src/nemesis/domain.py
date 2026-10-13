"""
The domain level of nemesis

Date:   20261004
Author: Lyding Anrie Brumm.
"""

from pathlib import Path
from typing import Literal
from dataclasses import dataclass, field


@dataclass
class WorkingDirectory:
    """
    The python representation of a working directroy
    """

    id: int | None
    path: Path
    type: Literal["LOCAL"] | Literal["REMOTE"]
    ssh_alias: str | None


@dataclass
class ExperimentResult:
    """
    The python representation of a result of a numerical experiment.
    """

    id: int | None
    eid: int
    rid: int
    description: str
    path: Path
    hash: str


@dataclass
class Experiment:
    """
    The python representation of a numerical experiment.
    """

    id: int | None
    wid: int
    type: str
    end_time: float
    start_time: float
    description: str
    params: str
    status: (
        Literal["INIT"]
        | Literal["RUNNING"]
        | Literal["FAILED"]
        | Literal["SUCCESS"]
    ) = "INIT"
    results: list[ExperimentResult] = field(default_factory=list)
    mark: str = ""


@dataclass
class ExperimentTemplate(object):
    """
    Describes an experiment description within the database
    """

    type: str
    path: Path
    hash: str
    api_version: str


@dataclass
class RunArtifact:
    """
    The python representation of an artifact of a run
    """

    id: int | None
    rid: int
    path: Path
    hash: str


@dataclass
class Run:
    """
    The python representation of a run within a numerical experiment.
    """

    id: int | None
    eid: int
    params: str
    exit_code: int
    invocation: str
    end_time: float
    start_time: float
    description: str
    executable: Path
    executable_hash: str
    executable_commit: str
    # Additional internal field without a direct relation to the database
    # a confined
    # A run is confined if all generated assets are compatible with the
    # nemesis file structure (i.e. if all assets are written in a sub-directory
    # of the cwd at execution). If a run generates assets at arbitrary
    # paths the UNCONFINED mode has to be used.
    mode: Literal["CONFINED"] | Literal["UNCONFINED"]
    status: (
        Literal["INIT"]
        | Literal["WAITING"]
        | Literal["BLOCKED"]
        | Literal["RUNNING"]
        | Literal["FAILED"]
        | Literal["SUCCESS"]
    ) = "INIT"
    dependencies: list[int] = field(default_factory=list)
    artifacts: list[RunArtifact] = field(default_factory=list)
