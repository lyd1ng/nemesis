"""
Implements the description of an experiment as provided by the user.

Date:   20261002
Author: Lyding Anrie Brumm.
"""

from nemesis.experiment import Experiment
from nemesis.experiment_result import ExperimentResult

import importlib.util
from typing import Self, cast
from pathlib import Path
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class ExperimentDescription(object):
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
    conduct: Callable[[list[object]], Experiment]
    # Invoked after a complete conduct. Might be used to generate result plot etc..
    post_conduct: Callable[[Experiment], ExperimentResult]
    # The python file describing this experiment will be copied
    # to the xdg_data_dir of the system using the specified name.
    # Because this does not protect the file to be tampered with AFTER
    # registration, the hash is stored and compared with an accompanying
    # metadata file
    hash: int = 0


def load_experiment_description(path: Path) -> ExperimentDescription:
    """
    Load an experiment description from a user specified module at path.
    """
    spec = importlib.util.spec_from_file_location(
        "nemesis_experiment",
        path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load experiment from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(ExperimentDescription, module.experiment_description)


def store_hash(
    path: Path, ed: ExperimentDescription, experiment_description_path: Path
) -> None:
    """
    Store the hash of an experiment description python file
    """
    _hash = hash(open(str(path), "r").read())
    with open(str(experiment_description_path / Path(ed.name + ".hash")), "w") as fd:
        _ = fd.write(str(_hash))
