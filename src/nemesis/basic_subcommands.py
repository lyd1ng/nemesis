"""
Impelements basic nemesis commands.

Date:   20261002
Author: Lyding Anrie Brumm.
"""

from nemesis.constants import DEFAULT_LOCAL_PATH
from nemesis.repository import Repository
from nemesis.domain import WorkingDirectory

from os import getcwd
from pathlib import Path
from subprocess import run as invoke


def initialise_nemesis_directory():
    """
    Initialises a new nemesis directory.
    This is rather trivial because a nemesis directory is only
    a directory which contains a hidden ./.nemesis sub-directory
    which potentially can store a local configuration file:
        ./.nemesis/nemesis.conf
    """
    result = invoke(["mkdir", "-p", "./.nemesis"])
    result.check_returncode()
    result = invoke(["touch", str(Path(getcwd()) / DEFAULT_LOCAL_PATH)])
    result.check_returncode()


def register_directory(path: Path, force: bool, repository: Repository):
    """
    Register a new directory in the nemesis db if it not already registered
    and only if is empty or force was specified.
    If the path contains a colon it is interpreted as a remote directory.
    """
    # TODO: IMPLEMENT REMOTE EMPTY CHECK
    if repository.get_wid_from_path(path) is not None:
        raise RuntimeError("Can not register already registered directory")

    # If no colon is found the diectory to register is local
    if str(path).find(":") == -1:
        print("DEBUG: LOCAL BRANCH")
        if any(path.iterdir()) and not force:
            raise RuntimeError("Can not register non-empty directory")
        working_directory = WorkingDirectory(None, path, "LOCAL", None)
        working_directory.id = repository.add_working_directory(
            working_directory
        )
    else:
        print("DEBUG: REMOTE BRANCH")
        colon_index = str(path).find(":")
        alias_part = str(path)[:colon_index]
        path_part = str(path)[colon_index + 1 :]
        working_directory = WorkingDirectory(
            None, Path(path_part), "REMOTE", alias_part
        )
        working_directory.id = repository.add_working_directory(
            working_directory
        )
