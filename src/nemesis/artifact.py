"""
Contains the representation of an artifact of a run

Date:   20261003
Author: Lyding Anrie Brumm.
"""

from pathlib import Path
from dataclasses import dataclass


@dataclass
class RunArtifact:
    """
    The python representation of an artifact of a run
    """

    id: int
    run_id: int
    path: Path
    hash: int
