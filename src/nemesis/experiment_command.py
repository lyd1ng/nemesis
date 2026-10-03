"""
Implements the 'experiment' command(s)

Date:   20261003
Author: Lyding Anrie Brumm.
"""

from nemesis.experiment_description import (
    ExperimentDescription,
    load_experiment_description,
    store_hash,
)
from subprocess import run as invoke
from pathlib import Path


def experiment_register(path: Path, experiment_description_path: Path) -> None:
    """
    Register an experiment description.

    usage: nemesis experiment register $description.py
    """
    ed: ExperimentDescription = load_experiment_description(path)
    store_hash(path, ed, experiment_description_path)
    _ = invoke(
        ["cp", str(path), str(experiment_description_path / Path(ed.name + ".py"))]
    )
