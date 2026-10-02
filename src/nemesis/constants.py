"""
Define global variables
"""

from pathlib import Path
from platformdirs import user_config_path

DEFAULT_GLOBAL_PATH: Path = user_config_path("nemesis") / Path("nemesis.conf")
DEFAULT_LOCAL_PATH: Path = Path("./.nemesis/nemesis.conf")
