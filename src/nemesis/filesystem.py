"""
Implements filesystem operations

Date:   20261011
Author: Lyding Anrie Brumm.
"""

from nemesis.utility import invoke_within_wd
from nemesis.domain import WorkingDirectory
from hashlib import sha256
from pathlib import Path
from shlex import quote
from shutil import copyfile
import subprocess
from typing import cast


def check_lexical_confinement(path: Path):
    """
    Checks if a path is
        1. not absolute
        2. does not contain ../ escapes
    This assures that the given path can be safely interpreted
    to be relative to a given working_dir.
    """
    return (not path.is_absolute()) and (not ".." in path.parts)


def confined_path_exists(path: Path, working_dir: WorkingDirectory) -> int:
    """
    Checks if a confined path exits
    """
    if not check_lexical_confinement(path):
        raise RuntimeError(f"Path {str(path)} is not confined.")
    return _exists(path, working_dir)


def confined_cp(src: Path, dst: Path, working_dir: WorkingDirectory) -> int:
    """
    Copy two confined paths
    """
    if not check_lexical_confinement(src):
        raise RuntimeError(f"Path {str(src)} is not confined.")
    if not check_lexical_confinement(dst):
        raise RuntimeError(f"Path {str(dst)} is not confined.")
    return _copy(src, dst, working_dir)


def confined_path_mkdir(path: Path, working_dir: WorkingDirectory) -> int:
    """
    Make a directory at a confined path
    """
    if not check_lexical_confinement(path):
        raise RuntimeError(f"Path {str(path)} is not confined.")
    return _mkdir(path, working_dir)


def confined_hash(path: Path, working_dir: WorkingDirectory) -> str:
    """
    Compute the hash of at cofined path
    """
    if not check_lexical_confinement(path):
        raise RuntimeError(f"Path {str(path)} is not confined.")
    return _hash(path, working_dir)


def unconfined_path_mkdir(path: Path, working_dir: WorkingDirectory) -> int:
    """
    Make a directory at an unconfined path
    """
    if check_lexical_confinement(path):
        raise RuntimeError(f"Path {str(path)} is confined.")
    return _mkdir(path, working_dir)


def unconfined_cp(src: Path, dst: Path, working_dir: WorkingDirectory) -> int:
    """
    Copy two unconfined paths
    """
    if check_lexical_confinement(src):
        raise RuntimeError(f"Path {str(src)} is confined.")
    if check_lexical_confinement(dst):
        raise RuntimeError(f"Path {str(dst)} is confined.")
    return _copy(src, dst, working_dir)


def unconfined_path_exists(path: Path, working_dir: WorkingDirectory) -> int:
    """
    Checks if an unconfined path exits, locally or remotely
    """
    if check_lexical_confinement(path):
        raise RuntimeError(f"Path {str(path)} is confined.")
    return _exists(path, working_dir)


def unconfined_hash(path: Path, working_dir: WorkingDirectory) -> str:
    """
    Compute the hash of at cofined path
    """
    if check_lexical_confinement(path):
        raise RuntimeError(f"Path {str(path)} is confined.")
    return _hash(path, working_dir)


def _exists(path: Path, working_dir: WorkingDirectory) -> int:
    if working_dir.type == "LOCAL":
        return 0 if path.exists() else 1
    elif working_dir.type == "REMOTE":
        code = (
            "import sys\n"
            "from pathlib import Path\n"
            "sys.exit(0 if Path(sys.argv[1]).exists() else 1)\n"
        )
        error_code: int = invoke_within_wd(
            ["python3", "-c", code, quote(str(path))],
            Path(""),
            working_dir,
        ).returncode
        return error_code
    else:
        raise RuntimeError("Should never happen!")


def _mkdir(path: Path, working_dir: WorkingDirectory) -> int:
    """
    Make a directory
    """
    if working_dir.type == "LOCAL":
        path.mkdir()
        return 0
    elif working_dir.type == "REMOTE":
        code = (
            "import sys\n"
            "from pathlib import Path\n"
            "path = Path(sys.argv[1])\n"
            "path.mkdir()\n"
        )
        result = invoke_within_wd(
            ["python3", "-c", code, quote(str(path))],
            Path(""),
            working_dir,
        )
        print(result.stdout)
        print(result.stderr)
        return result.returncode
    else:
        raise RuntimeError("Should never happen!")


def _copy(src: Path, dst: Path, wd: WorkingDirectory) -> int:
    """
    Copy a file
    """
    if wd.type == "LOCAL":
        try:
            _ = copyfile(src, dst)
            return 0
        except OSError:
            return 1
    elif wd.type == "REMOTE":
        code = (
            "import sys\n"
            "from shutil import copyfile\n"
            "src = sys.argv[1]\n"
            "dst = sys.argv[2]\n"
            "try:\n"
            "\tcopyfile(src, dst)\n"
            "\tsys.exit(0)\n"
            "except OSError:\n"
            "\tsys.exit(-1)\n"
        )
        return invoke_within_wd(
            [
                "python3",
                "-c",
                code,
                quote(str(src)),
                quote(str(dst)),
            ],
            Path(""),
            wd,
        ).returncode
    else:
        raise RuntimeError("Should never happen")


def _hash(path: Path, wd: WorkingDirectory) -> str:
    """
    Compute the hash of a file
    """
    if wd.type == "LOCAL":
        return sha256(path.read_bytes()).hexdigest()
    elif wd.type == "REMOTE":
        # TODO: Better error handling
        code = (
            "import sys\n"
            "from hashlib import sha256\n"
            "from pathlib import Path\n"
            "path = Path(sys.argv[1])\n"
            "print(sha256(path.read_bytes()).hexdigest())\n"
            "sys.exit(0)"
        )
        result = invoke_within_wd(
            [
                "python3",
                "-c",
                code,
                quote(str(path)),
            ],
            Path(""),
            wd,
            capture=True,
        )
        result.check_returncode()
        return str(result.stdout)
    else:
        raise RuntimeError("Should never happen")


def get_git_commit(
    executable: Path, working_directory: WorkingDirectory
) -> str:
    """
    Gets the current git commit of the executable or None
    if the executable is not part of a git repo
    """
    if working_directory.type == "LOCAL":
        # Why not use invoke_within_wd here as well?
        # Because external codes should not be part of the working_directory!
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=executable.resolve().parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    elif working_directory.type == "REMOTE":
        result = subprocess.run(
            [
                "ssh",
                cast(str, working_directory.ssh_alias),
                "git",
                "rev-parse",
                "HEAD",
            ],
            cwd=executable.resolve().parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    else:
        raise RuntimeError("Should never happen")
    return result.stdout.strip() if result.returncode == 0 else ""
