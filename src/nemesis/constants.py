"""
Define global variables
"""

from pathlib import Path

# The nemesis database should remain a valid source of truth
# even if the user switches to a newer version of nemesis.
# This is why the API version is stored within the experiment
# template table
VERSION = "0.1.0"

# Nemesis should be able to be located at arbitrary paths to remain flexible.
# This makes it neccesary for da;; instances of nemesis to be able
# to find the nemesis database. This is acomplished by locating a bootstrap
# file which contains the nemesis path, i.e. the path the database
# and experiment description files are located
BOOTSTRAP_DIR: Path = Path("/etc/nemesis")
BOOTSTRAP_PATH: Path = BOOTSTRAP_DIR / Path("bootstrap")
