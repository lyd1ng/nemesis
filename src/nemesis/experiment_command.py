"""
Implements the 'experiment' command(s)

Date:   20261003
Author: Lyding Anrie Brumm.
"""

from nemesis.constants import VERSION
from nemesis.repository import Repository
from nemesis.utility import calculate_hash
from nemesis.domain import ExperimentTemplate
from nemesis.experiment_module import ExperimentModule
from nemesis.api import Api

import importlib.util
from typing import cast
from pathlib import Path
from subprocess import run as invoke


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
    return em, calculate_hash(path)


def _load_experiment_description(path: Path) -> ExperimentTemplate:
    """
    Load an experiment description from a user specified module at path.
    Only the name is realy read from the python file.
    """
    em, _hash = _load_experiment_module(path)
    name = em.name
    return ExperimentTemplate(
        type=name, path=path, hash=_hash, api_version=VERSION
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
            str(experiment_description_path / Path(ed.type + ".py")),
        ]
    )
    return rep.add_experiment_description(ed)


def experiment_show(type: str, rep: Repository) -> int:
    """
    Show an experiment description.
    """
    ed = rep.get_experiment_description(type)
    print(str(ed))
    return 0


def experiment_list(rep: Repository) -> int:
    """
    List all experiment descriptions
    """
    print(rep.get_list_of_experiments())
    return 0


def experiment_run(
    type: str,
    description: str,
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
    ed = rep.get_experiment_description(type)
    em, _hash = _load_experiment_module(
        experiment_description_path / Path(ed.path)
    )
    if ed.hash != _hash:
        raise RuntimeError("Detected post-registration tempering")
    # The whole API is defined within the ExperimentContext,
    ec = Api(rep, type, params, em.parameters)
    ec._init_experiment(description)
    # For all the logic happens in the module and here simply
    # all three hooks are invoked
    em.setup(ec)
    ec._conduct()
    ec._postconduct()
    return 0
