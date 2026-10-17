"""
Implements the 'experiment' command(s)

Date:   20261003
Author: Lyding Anrie Brumm.
"""

from nemesis.constants import VERSION
from nemesis.repository import Repository
from nemesis.domain import ExperimentTemplate, WorkingDirectoryEnv
from nemesis.experiment_module import ExperimentModule
from nemesis.api import Api
from nemesis.sandbox_api import SandboxApi
from nemesis.utility import calculate_local_hash

import importlib.util
from typing import cast
from pathlib import Path
from subprocess import run as invoke


def experiment_register(
    path: Path, experiment_description_path: Path, rep: Repository
) -> int:
    """
    Register an experiment description if it passes some basic sanity checks.
    """
    em, ed = _load_experiment_description(path)
    _ = invoke(
        [
            "cp",
            str(path),
            str(experiment_description_path / Path(ed.type + ".py")),
        ]
    )
    _verify_experiment(em)
    # Also check if there is a at least one working directory this
    # experiment is compatible to
    wdes: list[WorkingDirectoryEnv] = rep.get_latest_wdes()
    if not any(
        [_check_working_directory_compatability(em, wde)[0] for wde in wdes]
    ):
        raise RuntimeError(
            "Experiment is not compatible to any working directory."
        )
    return rep.add_experiment_template(ed)


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
    print(rep.get_list_of_experiment_names())
    return 0


def experiment_run(
    wid: int,
    type: str,
    description: str,
    params: list[str],
    experiment_description_path: Path,
    rep: Repository,
):
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
    api = Api(rep, wid, type, description, params, em.parameters)
    # For all the logic happens in the module and here simply
    # all three hooks are invoked
    em.setup(api)
    api._conduct()  # pyright: ignore[reportPrivateUsage]
    api._postconduct()  # pyright: ignore[reportPrivateUsage]


def experiment_check(
    type: str, wid: int, experiment_description_path: Path, rep: Repository
):
    """
    Check if a given experiment is compatible with the latest environment
    of a working directroy
    """
    et: ExperimentTemplate = rep.get_experiment_description(type)
    em, _hash = _load_experiment_module(
        experiment_description_path / Path(et.path)
    )
    if et.hash != _hash:
        raise RuntimeError("Detected post-registration tempering")
    wde = rep.get_wdes(wid)[-1]
    compatible, msg = _check_working_directory_compatability(em, wde)
    if not compatible:
        print(f"Experiment {type} is not compatible with {wid}.")
        print(msg)
    else:
        print(f"Experiment {type} is compatible with {wid}.")


def _load_experiment_module(path: Path) -> tuple[ExperimentModule, str]:
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
    em = cast(ExperimentModule, module.experiment_module)
    return em, calculate_local_hash(path)


def _load_experiment_description(
    path: Path,
) -> tuple[ExperimentModule, ExperimentTemplate]:
    """
    Load an experiment description from a user specified module at path.
    Only the name is really read from the python file.
    """
    em, _hash = _load_experiment_module(path)
    name = em.name
    return em, ExperimentTemplate(
        type=name, path=path, hash=_hash, api_version=VERSION
    )


def _check_working_directory_compatability(
    em: ExperimentModule, wde: WorkingDirectoryEnv
) -> tuple[bool, str]:
    # Check if the requirements of the experiment module are satisfied
    # by the working directory environment and generate an error message
    # otherwise
    fulfilled = True
    missing_variables: list[str] = []
    wrongly_typed_variables: list[tuple[str, type, type]] = []
    for _type, name in em.requires:
        if name not in wde.variables.keys():
            fulfilled = False
            missing_variables.append(name)
        else:
            if not isinstance(wde.variables[name], _type):
                fulfilled = False
                wrongly_typed_variables.append(
                    (name, type(wde.variables[name]), _type)
                )
    error_msg = ""
    if len(missing_variables) > 0:
        error_msg += f"The variables {missing_variables} are not provided by the environment\n"
    for name, got, expected in wrongly_typed_variables:
        error_msg += (
            f"Variable {name} is of type {got} but {expected} was expected.\n"
        )
    assert (
        fulfilled == True
        and len(error_msg) == 0
        or fulfilled == False
        and len(error_msg) > 0
    ), "Assert missmatch between fulfilled and error message"
    return (fulfilled, error_msg)


def _verify_experiment(em: ExperimentModule):
    """
    Verifies an experiment using a sanbox api
    """
    sapi = SandboxApi(em.requires, em.parameters)
    em.setup(sapi)
    sapi._verify()  # pyright: ignore[reportPrivateUsage]
