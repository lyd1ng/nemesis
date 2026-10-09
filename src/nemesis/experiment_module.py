"""
Implements the API exposed to experiment descriptions files

Date:   20261007
Author: Lyding Anrie Brumm.
"""

from nemesis.api import Api
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class ExperimentModule(object):
    """
    Describes an experiment description as provided by the user
    """

    # The name used to interact with this type of experiment
    name: str
    # A small description of the type of experiment
    description: str
    # A list of all required parameters
    parameters: dict[str, type]
    setup: Callable[[Api], None]
