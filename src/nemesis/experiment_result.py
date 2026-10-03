"""
Contains the representation of a result of numerical experiment

Date:   20261004
Author: Lyding Anrie Brumm.
"""

from pathlib import Path
from dataclasses import dataclass


@dataclass
class ExperimentResult:
    """
    The python representation of a result of a numerical experiment.
    """

    id: int
    experiment_id: int
    kind: str
    description: str
    path: Path
    hash: int
