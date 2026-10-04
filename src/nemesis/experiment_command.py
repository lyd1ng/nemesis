"""
Implements the 'experiment' command(s)

Date:   20261003
Author: Lyding Anrie Brumm.
"""

from nemesis.constants import VERSION
from nemesis.repository import Repository
from nemesis.domain import ExperimentDescription, ExperimentModule
import importlib.util
from typing import cast
from hashlib import sha256
from subprocess import run as invoke
from pathlib import Path


def _calculate_hash(path: Path) -> str:
    """
    Calculate the hash of a python file
    """
    return sha256(path.read_bytes()).hexdigest()


def _load_experiment_description(path: Path) -> ExperimentDescription:
    """
    Load an experiment description from a user specified module at path.
    Only the name is realy read from the python file.
    """
    spec = importlib.util.spec_from_file_location(
        "nemesis_experiment",
        path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load experiment from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    em = cast(ExperimentModule, module.experiment_module)
    name = em.name
    _hash = _calculate_hash(path)
    return ExperimentDescription(
        name=name, path=path, hash=_hash, api_version=VERSION
    )


def experiment_register(
    path: Path, experiment_description_path: Path, repository: Repository
) -> int:
    """
    Register an experiment description.
    """
    ed = _load_experiment_description(path)
    _ = invoke(
        [
            "cp",
            str(path),
            str(experiment_description_path / Path(ed.name + ".py")),
        ]
    )
    return repository.add_experiment_description(ed)


def experiment_show(name: str, repository: Repository) -> int:
    """
    Show an experiment description.
    """
    ed = repository.get_experiment_description(name)
    print(str(ed))
    return 0


def experiment_list(repository: Repository) -> int:
    """
    List all experiment descriptions
    """
    print(repository.get_list_of_experiments())
    return 0
