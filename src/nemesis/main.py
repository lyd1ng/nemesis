from pathlib import Path
import subprocess

from nemesis.repository import Repository
from nemesis.subcommand_deployer import invoke_subcommand
from nemesis.constants import BOOTSTRAP_PATH, BOOTSTRAP_DIR


def main():
    if not BOOTSTRAP_DIR.exists():
        BOOTSTRAP_DIR.mkdir()
        _ = subprocess.run(["chmod", "755", str(BOOTSTRAP_DIR)])
    database_path = (
        Path(BOOTSTRAP_PATH.read_text()) / Path("nemesis.db")
        if BOOTSTRAP_PATH.exists()
        else None
    )
    edf_path = (
        Path(BOOTSTRAP_PATH.read_text()) / Path("edf")
        if BOOTSTRAP_PATH.exists()
        else None
    )
    repository = Repository(database_path)
    invoke_subcommand(repository, edf_path)
