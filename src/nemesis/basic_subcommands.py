"""
Impelements basic nemesis commands.

Date:   20261002
Author: Lyding Anrie Brumm.
"""

from nemesis.constants import DEFAULT_LOCAL_PATH
from nemesis.repository import Repository

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


def register_directory(
    path: Path, dir_type: str, force: bool, repository: Repository
):
    """
    Register a new directory in the nemesis db if it not already registered
    and only if is empty.
    """
    if repository.get_wid_from_path(path) is not None:
        raise RuntimeError("Can not register already registered directory")

    if any(path.iterdir()) and not force:
        raise RuntimeError("Can not register non-empty directory")
    _ = repository.add_working_directory(path, dir_type)
