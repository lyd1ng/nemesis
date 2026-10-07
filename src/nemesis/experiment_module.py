"""
Implements the API exposed to experiment descriptions files

Date:   20261007
Author: Lyding Anrie Brumm.
"""

from nemesis.experiment_context import ExperimentContext
from typing import Self
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
    # Invoked before conduct is started. Might be used to prepare for conduct
    # or to conduct some tests, etc.
    pre_conduct: Callable[[Self], None]
    # The function which actually conducts the numerical experiment, i.e
    # which orchestrate the different conducts etc.
    conduct: Callable[[ExperimentContext], None]
    # Invoked after a complete conduct. Might be used to generate result plot etc..
    post_conduct: Callable[[ExperimentContext], None]
