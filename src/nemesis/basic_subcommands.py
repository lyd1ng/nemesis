"""
Impelements basic nemesis commands.

Date:   20261002
Author: Lyding Anrie Brumm.
"""

from os import getcwd
from pathlib import Path
from subprocess import run as invoke
from nemesis.constants import DEFAULT_LOCAL_PATH


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
