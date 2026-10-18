"""
Impelements basic nemesis commands.

Date:   20261002
Author: Lyding Anrie Brumm.
"""

from nemesis.repository import Repository
from nemesis.domain import WorkingDirectory, WorkingDirectoryEnv

from hashlib import sha256
from pathlib import Path
from editor import editor
from typing import cast
from time import time as now


def register_directory(
    path: Path, force: bool, repository: Repository
) -> WorkingDirectory:
    """
    Register a new directory in the nemesis db if it not already registered
    and only if is empty or force was specified.
    If the path contains a colon it is interpreted as a remote directory.
    """
    # TODO: IMPLEMENT REMOTE EMPTY CHECK
    # If no colon is found the diectory to register is local
    if str(path).find(":") == -1:
        if any(path.iterdir()) and not force:
            raise RuntimeError("Can not register non-empty directory")
        if not path.iterdir() and not force:
            raise RuntimeError("Can not register non-empty directory")
        working_directory = WorkingDirectory(None, path, "LOCAL", None, [])
    else:
        colon_index = str(path).find(":")
        alias_part = str(path)[:colon_index]
        path_part = str(path)[colon_index + 1 :]
        working_directory = WorkingDirectory(
            None, Path(path_part), "REMOTE", alias_part, []
        )
    # Add the working_directory without configuration
    working_directory.id = repository.add_working_directory(working_directory)
    return working_directory


def configure_working_directory(
    working_directory_env: WorkingDirectoryEnv,
    rep: Repository,
) -> None:
    """
    Configures a working directory

    For now only the lastest configuration is used when an experiment is
    run, but all older versions are stored as well to ensure reproducability.
    """
    working_directory_env.id = rep.add_working_directory_env(
        working_directory_env
    )
