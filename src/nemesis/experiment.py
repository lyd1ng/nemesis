"""
Contains the representation of a numerical experiment

Date:   20261003
Author: Lyding Anrie Brumm.
"""

from typing import Literal
from dataclasses import dataclass


@dataclass
class Experiment:
    """
    The python representation of a numerical experiment.
    """

    id: int
    end_time: float
    start_time: float
    description: str
    status: (
        Literal["INIT"] | Literal["RUNNING"] | Literal["FAILED"] | Literal["SUCCESS"]
    ) = "INIT"
