"""
Collection of utility functions

Date:   20261007
Author: Lyding Anrie Brumm.
"""

import shlex
import subprocess
from pathlib import Path
from hashlib import sha256
from collections.abc import Sequence
from typing import TextIO, TypedDict, Unpack, cast

from nemesis.domain import WorkingDirectory


class RunOptionsU(TypedDict, total=False):
    """
    Additional options passed from add_run to subprocess.open
    """

    stdout: str
    stderr: str
    capture: bool


class RunOptions(TypedDict, total=False):
    """
    Additional options passed from add_run to subprocess.open
    """

    stdout: TextIO
    stderr: TextIO


def invoke_within_wd(
    command: Sequence[str],
    subdir: Path,
    working_directory: WorkingDirectory,
    **kwargs: Unpack[RunOptionsU],
) -> subprocess.CompletedProcess[bytes]:
    """
    Invoke a command localy or remotely but always relative to the
    working_directory.
    """
    cwd = working_directory.path / subdir
    if working_directory.type == "LOCAL":
        options: RunOptions = RunOptions()
        if "stdout" in kwargs:
            options["stdout"] = Path(kwargs["stdout"]).open("w")
        if "stderr" in kwargs:
            options["stderr"] = Path(kwargs["stderr"]).open("w")
        capture_output = kwargs["capture"] if "capture" in kwargs else False
        result = subprocess.run(
            command, cwd=cwd, capture_output=capture_output, **options
        )
        return result
    elif working_directory.type == "REMOTE":
        ssh_alias = cast(str, working_directory.ssh_alias)
        # The remote invocation is a little bit more tricky.
        # First of all the cwd has to be changed manually cd,
        # then shlex. Then the stdout and stderr must be
        # handled manually and not by subprocess s.t. stdout and stderr
        # are redirected to *remote* files as well.
        remote_command = (
            f"cd {shlex.quote(str(cwd))} && " f"{shlex.join(command)}"
        )
        if "stdout" in kwargs:
            remote_command += f" > {kwargs['stdout']}"
        if "stderr" in kwargs:
            remote_command += f" 2> {kwargs['stderr']}"
        capture_output = kwargs["capture"] if "capture" in kwargs else False
        print("DEBUG: Invoking", "ssh", ssh_alias, remote_command)
        result = subprocess.run(
            ["ssh", ssh_alias, remote_command], capture_output=capture_output
        )
        return result
    else:
        raise RuntimeError("This should never happen!")


def calculate_local_hash(path: Path):
    """
    Calculate a hash of a local file
    """
    return sha256(path.read_bytes()).hexdigest()
