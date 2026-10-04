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
from pathlib import Path
from hashlib import sha256
from subprocess import run as invoke


def _calculate_hash(path: Path) -> str:
    """
    Calculate the hash of a python file
    """
    return sha256(path.read_bytes()).hexdigest()


def _load_experiment_module(path: Path) -> tuple[ExperimentModule, str]:
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
    return em, _calculate_hash(path)


def _load_experiment_description(path: Path) -> ExperimentDescription:
    """
    Load an experiment description from a user specified module at path.
    Only the name is realy read from the python file.
    """
    em, _hash = _load_experiment_module(path)
    name = em.name
    return ExperimentDescription(
        name=name, path=path, hash=_hash, api_version=VERSION
    )


def experiment_register(
    path: Path, experiment_description_path: Path, rep: Repository
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
    return rep.add_experiment_description(ed)


def experiment_show(name: str, rep: Repository) -> int:
    """
    Show an experiment description.
    """
    ed = rep.get_experiment_description(name)
    print(str(ed))
    return 0


def experiment_list(rep: Repository) -> int:
    """
    List all experiment descriptions
    """
    print(rep.get_list_of_experiments())
    return 0


def experiment_run(
    name: str,
    params: list[str],
    experiment_description_path: Path,
    rep: Repository,
) -> int:
    """
    Run a registered experiment
    """
    # First the experiment module has to be retrieved and the hashes
    # have to be compared. This way it can be detected if the source file
    # was tempered with post-registration
    ed = rep.get_experiment_description(name)
    em, _hash = _load_experiment_module(
        experiment_description_path / Path(ed.path)
    )
    if ed.hash != _hash:
        raise RuntimeError("Detected post-registration tempering")
    # For all the logic happens in the module and here simply
    # all three hooks are invoked
    em.pre_conduct(em)
    experiment = em.conduct(params)
    experiment_result = em.post_conduct(experiment)
    return 0
