"""
Define global variables
"""

from pathlib import Path

VERSION = "0.1.0"
BOOTSTRAP_DIR: Path = Path("/etc/nemesis")
BOOTSTRAP_PATH: Path = BOOTSTRAP_DIR / Path("bootstrap")
