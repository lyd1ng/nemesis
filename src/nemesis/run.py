"""
Contains the representation of a run within a numerical experiment

Date:   20261003
Author: Lyding Anrie Brumm.
"""

from typing import Literal
from dataclasses import dataclass


@dataclass
class Run:
    """
    The python representation of a run within a numerical experiment.
    """

    id: int
    experiment_id: int
    end_time: float
    start_time: float
    description: str
    status: (
        Literal["INIT"] | Literal["RUNNING"] | Literal["FAILED"] | Literal["SUCCESS"]
    ) = "INIT"
    dependencies: list[int] = []
