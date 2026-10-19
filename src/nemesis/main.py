from pathlib import Path
import subprocess

from nemesis.repository import Repository
from nemesis.subcommand_deployer import invoke_subcommand
from nemesis.constants import BOOTSTRAP_PATH, BOOTSTRAP_DIR


def main():
    # The bootstrap directory will contain the bootstrap file
    # which stores the path of the nemesis database.
    # This way every nemesis instance can find the database
    if not BOOTSTRAP_DIR.exists():
        BOOTSTRAP_DIR.mkdir()
        _ = subprocess.run(["chmod", "755", str(BOOTSTRAP_DIR)])
    # The database is the single source of truth, but if `nemesis init $path`
    # was not already called it does not exist yet and must be initialized
    # empty
    database_path = (
        Path(BOOTSTRAP_PATH.read_text()) / Path("nemesis.db")
        if BOOTSTRAP_PATH.exists()
        else Path("")
    )
    # Similar is the edf_path only set if the bootstrap file exists
    # and the nemesis path can be determined.
    edf_path = (
        Path(BOOTSTRAP_PATH.read_text()) / Path("edf")
        if BOOTSTRAP_PATH.exists()
        else Path("")
    )
    repository = Repository(database_path)
    invoke_subcommand(repository, edf_path)
