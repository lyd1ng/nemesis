"""
Implements the ExperimentModule.
The ExperimentModule class is the main object of experiment definition files.
Through the ExperimentModule class the user specifies not only
necessary informations about the class of experiments to register,
like name, description as well as the parameters of the experiment,
but also the callback functions which are invoked by nemesis
if an experiment is conducted.

Date:   20261007
Author: Lyding Anrie Brumm.
"""

from nemesis.api import Api
from nemesis.sandbox_api import SandboxApi
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
    # A list of variables (and their expected types) which have
    # to be present within the working directory environment
    # for the experiment to be compatible with a given working directory.
    requires: list[tuple[type, str]]
    # A list of all required parameters
    parameters: dict[str, type]
    setup: Callable[[Api | SandboxApi], None]
