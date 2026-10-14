"""
Implements the API exposed to experiment descriptions files

Date:   20261002
Author: Lyding Anrie Brumm.
"""

from nemesis.domain import (
    Experiment,
    ExperimentResult,
    Run,
    RunArtifact,
    WorkingDirectory,
    WorkingDirectoryEnv,
)
from nemesis.repository import Repository
from nemesis.utility import (
    invoke_within_wd,
    RunOptionsU,
)
import nemesis.filesystem as fs

import time
import tomllib
from copy import copy
from dataclasses import dataclass
from typing import Unpack, cast, Literal
from pathlib import Path
from functools import reduce
from collections.abc import Sequence, Mapping
from argparse import ArgumentParser, Namespace
from concurrent.futures import (
    ThreadPoolExecutor,
    Future,
    wait,
    FIRST_COMPLETED,
)


@dataclass
class ResultData:
    run_index: int
    description: str
    path: Path


class Api(object):
    """
    Defines the API used in nemesis experiment
    description files.
    """

    def __init__(
        self,
        repository: Repository,
        wid: int,
        exp_type: str,
        description: str,
        params: list[str],
        parameter_types: dict[str, type],
        polling: float = 1.0,
    ):
        self._rep: Repository = repository
        self._wid: int = wid
        self._exp_type: str = exp_type
        self._param_strs: list[str] = params
        self._param_types: dict[str, type] = parameter_types
        self._polling: float = polling
        self._experiment: Experiment = self._init_experiment(description)
        self._runs: list[Run] = []
        self._result_run_data: list[ResultData] = []
        self._run_ids_modifier_dict: dict[int, RunOptionsU] = {}
        self._working_directory: WorkingDirectory = (
            self._rep.get_working_directory(self._wid)
        )

        error_code = fs.confined_path_mkdir(
            Path(str(self._experiment.id)), self._working_directory
        )
        if error_code != 0:
            raise RuntimeError(
                f"Can not create experiment directory $working_dir/{self._experiment.id}"
            )

        # Public interface available to the user
        # =====================================================================

        # Namespace of parameters
        self.params: Namespace = self._parse()

        # A read only interface for the parameters of the latest configuration
        self.env: Mapping[str, object] = (
            self._generate_parameter_dict_from_lastest_working_directory_env(
                self._working_directory.env[-1]
            )
        )
        # =====================================================================

    def _add_run(
        self,
        description: str,
        executable: Path,
        params: list[str],
        dependencies: list[int],
        outputs: list[str],
        mode: Literal["CONFINED"] | Literal["UNCONFINED"],
        **kwargs: Unpack[RunOptionsU],
    ) -> int:
        """
        Add a run to the current experiment
        """
        if self._experiment.id is None:
            raise RuntimeError(
                "Can not add run to partially initialised experiment"
            )
        run: Run = Run(
            None,
            self._experiment.id,
            reduce(lambda a, b: a + " " + b, params),
            999,
            "",
            0,
            0,
            description,
            executable,
            fs.unconfined_hash(executable, self._working_directory),
            fs.get_git_commit(executable, self._working_directory),
            mode,
            "INIT",
            dependencies,
        )
        run.status = "INIT" if len(dependencies) == 0 else "WAITING"
        run.id = self._rep.upsert_run(run)
        for output in outputs:
            run.artifacts.append(
                RunArtifact(None, run.id, Path(output), hash="")
            )
        self._runs.append(run)
        internal_id = len(self._runs) - 1
        _ = self._rep.upsert_run(run)
        # Store kwargs for later use
        self._run_ids_modifier_dict[internal_id] = kwargs
        # Create the directory for the run
        error_code = fs.confined_path_mkdir(
            Path(str(self._experiment.id)) / Path(str(run.id)),
            self._working_directory,
        )
        if error_code != 0:
            raise RuntimeError(
                f"Can not create run directory $working_dir/{self._experiment.id}/{run.id}"
            )
        return internal_id

    def add_confined_run(
        self,
        description: str,
        executable: Path,
        params: list[str],
        dependencies: list[int],
        outputs: list[str],
        **kwargs: Unpack[RunOptionsU],
    ) -> int:
        """
        Add a confined run to the experiment.
        A run is confined if all assets are generated in the CWD
        or subdirectories, i.e. if all assets obey the nemesis
        file structure.
        """
        for output in outputs:
            output_path = Path(output)
            if output_path.is_absolute():
                raise RuntimeError(
                    "Confined runs must not contain absolute asset paths"
                )
            if ".." in output_path.parts:
                raise RuntimeError(
                    "Confined runs must not escpaing asset paths (../ detected)"
                )
        return self._add_run(
            description,
            executable,
            params,
            dependencies,
            outputs,
            "CONFINED",
            **kwargs,
        )

    def add_unconfined_run(
        self,
        description: str,
        executable: Path,
        params: list[str],
        dependencies: list[int],
        outputs: list[str],
        **kwargs: Unpack[RunOptionsU],
    ) -> int:
        """
        Add an unconfined run to the experiment.
        An unconfined run can create assets at arbitrary places
        not necessarily obeying the nemesis file structure.
        """
        for output in outputs:
            output_path = Path(output)
            if not output_path.is_absolute():
                raise RuntimeError(
                    "Unconfined runs must not contain reltive asset paths"
                )
        return self._add_run(
            description,
            executable,
            params,
            dependencies,
            outputs,
            "UNCONFINED",
            **kwargs,
        )

    def depends_on_nothing(self) -> list[int]:
        """
        Returns an empty list. This way creating an experiment with
        no dependencies is more visual
        """
        return []

    def depends_on_all(self) -> list[int]:
        """
        Returns a list indices of all previously added runs.
        This way creating a run which depends on all previously added runs
        is more visual
        """
        return list(range(len(self._runs)))

    def mark_artifact_as_result(
        self,
        run_index: int,
        description: str,
        path: Path,
    ) -> None:
        """
        Check if the artifact belongs to a run which qualifies to produce
        a result. A run qualifies to produce a result if there is no
        other run depending on it.
        """
        result_data = ResultData(run_index, description, path)
        joint_dependency_list: list[int] = reduce(
            lambda a, b: a + b, [run.dependencies for run in self._runs]
        )
        if result_data.run_index in joint_dependency_list:
            raise RuntimeError(
                f"Can not mark {result_data.run_index} as a result run. Other runs depend on it."
            )
        # Check if the names of the artifacts which should be lifted
        # to experiment results form a subsets of the registered artifacts
        # of the runs. Otherwise the user messed up.
        if result_data.path not in [
            a.path for a in self._runs[result_data.run_index].artifacts
        ]:
            raise RuntimeError(
                f"Can not mark {result_data.path} as experiment result. "
                + f"Expected result_data.source_paths of {result_data.run_index} are "
                + f"{[a.path for a in self._runs[result_data.run_index].artifacts]}"
                + f"got {result_data.path}"
            )
        data: ResultData = copy(result_data)
        self._result_run_data.append(data)

    def _update_status(self) -> list[int]:
        """
        Update which jobs are waiting
        """
        run_ids: list[int] = []
        waiting_runs = list(
            filter(
                lambda x: x.status == "WAITING" and len(x.dependencies) > 0,
                self._runs,
            )
        )
        for i, run in enumerate(waiting_runs):
            if all(self._runs[j].status == "SUCCESS" for j in run.dependencies):
                run.status = "INIT"
                run_ids.append(self._runs.index(run))
            elif (
                len(
                    list(
                        filter(
                            lambda x: self._runs[x].status
                            in ["FAILED", "BLOCKED"],
                            run.dependencies,
                        )
                    )
                )
                > 0
            ):
                run.status = "BLOCKED"
                run_ids.append(self._runs.index(run))
            else:
                pass
        return run_ids

    def _conduct(self):
        """
        Conduct the experiment
        """
        self._experiment.start_time = time.time()

        with ThreadPoolExecutor() as executor:
            active: dict[Future[int], Run] = {}
            while True:
                # Schedule all currently ready runs.
                init_runs = list(
                    filter(lambda x: x.status == "INIT", self._runs)
                )
                for r in init_runs:
                    invocation = self._get_invocation(r)
                    r.start_time = time.time()
                    r.invocation = invocation
                    r.status = "RUNNING"
                    _ = self._rep.upsert_run(r)
                    active[
                        executor.submit(self._invoke, self._runs.index(r))
                    ] = r

                # Wait for one or more runs to finish.
                done, _ = wait(
                    active,
                    return_when=FIRST_COMPLETED,
                )

                for future in done:
                    result = future.result()
                    r = active.pop(future)
                    r.exit_code = result
                    r.end_time = time.time()
                    r.status = (
                        "SUCCESS"
                        if r.exit_code == 0 and self._catch_artifacts(r)
                        else "FAILED"
                    )
                    _ = self._rep.upsert_run(r)
                dirty_run_ids = self._update_status()
                for i in dirty_run_ids:
                    _ = self._rep.upsert_run(self._runs[i])
                if (
                    len(
                        list(
                            filter(
                                lambda x: x.status
                                in ["INIT", "WAITING", "RUNNING"],
                                self._runs,
                            )
                        )
                    )
                    == 0
                ):
                    break

    def _postconduct(self):
        """
        Set the experiment status.
        Add experiment results.
        """

        self._experiment.status = (
            "SUCCESS"
            if all(run.status == "SUCCESS" for run in self._runs)
            else "FAILED"
        )
        if self._experiment.status == "SUCCESS":
            # If the experiment succeeded all runs succeeded as well, i.e.
            # all expected output files are present as well.
            for result_run in self._result_run_data:
                print(result_run.path, end=" ")
                self._experiment.results.append(
                    ExperimentResult(
                        None,
                        cast(int, self._experiment.id),
                        cast(int, self._runs[result_run.run_index].id),
                        result_run.description,
                        result_run.path,
                        fs.confined_hash(
                            result_run.path, self._working_directory
                        ),
                    )
                )
            print()
        else:
            # If the experiment did not succeed no results are added
            pass
        _ = self._rep.upsert_experiment(self._experiment)

    def _init_experiment(self, description: str):
        """
        Start an experiment of the type $type.
        """
        experiment: Experiment = Experiment(
            None,
            self._wid,
            self._exp_type,
            0,
            0,
            description,
            reduce(lambda a, b: a + " " + b, self._param_strs, ""),
        )
        experiment.id = self._rep.upsert_experiment(experiment)
        return experiment

    def _parse(self) -> Namespace:
        """
        Parse the parameter strings accordingly to the parameter_types
        dictionary.
        """
        parser = ArgumentParser(
            prog=self._exp_type,
            description=f"Parser autogenerated from {self._exp_type} module.",
        )
        for key, value in self._param_types.items():
            _ = parser.add_argument(key, type=value)
        return parser.parse_args(self._param_strs)

    def _invoke(self, run_id: int) -> int:
        """
        Invoke a run
        """
        run = self._runs[run_id]
        command: Sequence[str] = [str(run.executable), run.params]
        subdir = Path("")
        options = self._run_ids_modifier_dict[run_id]
        return invoke_within_wd(
            command, subdir, self._working_directory, **options
        ).returncode

    def _catch_artifacts(self, run: Run) -> bool:
        """
        Computes the hash of all artifacts.
        If an artifact is missing False is returned
        s.t. the status of the Run can be set to FAILED.

        For unconfined runs the assets are also copied to
        the corresponding nemesis->experiment->run path
        """
        success = True
        exists = (
            fs.confined_path_exists
            if run.mode == "CONFINED"
            else fs.unconfined_path_exists
        )
        calculate_hash = (
            fs.confined_hash if run.mode == "CONFINED" else fs.unconfined_hash
        )
        for artifact in run.artifacts:
            if 0 == exists(artifact.path, self._working_directory):
                artifact.hash = calculate_hash(
                    artifact.path, self._working_directory
                )

                if run.mode == "UNCONFINED":
                    confined_path: Path = (
                        Path(str(self._experiment.id))
                        / Path(str(run.id))
                        / Path(artifact.path.parts[-1])
                    )
                    error_code = fs.unconfined_cp(
                        artifact.path,
                        self._working_directory.path / confined_path,
                        self._working_directory,
                    )
                    print("DEBUG > cp error: ", error_code)
                    if error_code != 0:
                        raise RuntimeError("Can not confine unconfined asset")
                    artifact.path = confined_path
                    _ = self._rep.upsert_run_artifact(artifact)
                else:
                    # Artifact is already confined
                    pass
            else:
                success = False
        return success

    def _get_invocation(self, run: Run):
        """
        Get the correct invocation including redirect symbols
        """
        suffix = ""
        options = self._run_ids_modifier_dict[self._runs.index(run)]
        if "stdout" in options:
            suffix += f" > {options['stdout']}"
        if "stderr" in options:
            suffix += f" 2> {options['stderr']}"
        invocation = str(run.executable) + " "
        invocation += run.params
        return invocation + suffix

    def _generate_parameter_dict_from_lastest_working_directory_env(
        self, working_directory_env: WorkingDirectoryEnv
    ) -> dict[str, object]:
        """
        Use the latest working directory configuration to get a dictionary
        of parameters for the user.
        """
        result = tomllib.loads(str(working_directory_env.content))
        return result
