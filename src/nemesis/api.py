"""
Implements the API exposed to experiment descriptions files

Date:   20261002
Author: Lyding Anrie Brumm.
"""

from nemesis.domain import (Experiment, ExperimentResult, Run, RunArtifact)
from nemesis.repository import Repository
from nemesis.utility import (calculate_hash, get_git_commit)

import time
import subprocess
from copy import copy
from dataclasses import dataclass
from typing import TypedDict, Unpack, TextIO, cast
from pathlib import Path
from functools import reduce
from argparse import ArgumentParser, Namespace
from concurrent.futures import (
    ThreadPoolExecutor,
    Future,
    wait,
    FIRST_COMPLETED,
)


class RunOptions(TypedDict, total=False):
    """
    Additional options passed from add_run to subprocess.open
    """

    stdout: TextIO
    stderr: TextIO


@dataclass
class ResultData:
    run_index: int
    description: str
    path: Path


class Api(object):
    """
    The ExperimentContext defines the API used in nemesis experiment
    description files.
    """

    def __init__(
        self,
        repository: Repository,
        wid: int,
        exp_type: str,
        params: list[str],
        parameter_types: dict[str, type],
        polling: float = 1.0,
    ):
        self._rep: Repository = repository
        self._wid: int = wid
        self._exp_type: str = exp_type
        self._param_strs: list[str] = params
        self._param_types: dict[str, type] = parameter_types
        self.polling: float = polling
        self.params: Namespace = self._parse()
        # Just a dummy variable because None leads to static typo issues
        self.experiment: Experiment = Experiment(
            None, self._wid, "", 0, 0, "", "", "INIT"
        )
        self.runs: list[Run] = []
        self.result_run_data: list[ResultData] = []
        self.run_ids_modifier_dict: dict[int, RunOptions] = {}

    def add_run(
        self,
        description: str,
        executable: Path,
        params: list[str],
        dependencies: list[int],
        outputs: list[str],
        **kwargs: Unpack[RunOptions],
    ) -> int:
        """
        Add a run to the current experiment

        """
        if self.experiment.id is None:
            raise RuntimeError(
                "Can not add run to partially initialised experiment"
            )
        status = "INIT" if len(dependencies) == 0 else "WAITING"
        run: Run = Run(
            None,
            self.experiment.id,
            reduce(lambda a, b: a + " " + b, params),
            999,
            "",
            0,
            0,
            description,
            executable,
            calculate_hash(executable),
            get_git_commit(executable),
            status,
            dependencies,
        )
        run.id = self._rep.upsert_run(run)
        for output in outputs:
            run.artifacts.append(RunArtifact(None, run.id, Path(output), ""))
        self.runs.append(run)
        internal_id = len(self.runs) - 1
        _ = self._rep.upsert_run(run)
        # Store kwargs for later use
        self.run_ids_modifier_dict[internal_id] = kwargs
        return internal_id

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
        return list(range(len(self.runs)))

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
            lambda a, b: a + b, [run.dependencies for run in self.runs]
        )
        if result_data.run_index in joint_dependency_list:
            raise RuntimeError(
                f"Can not mark {result_data.run_index} as a result run. Other runs depend on it."
            )
        # Check if the names of the artifacts which should be lifted
        # to experiment results form a subsets of the registered artifacts
        # of the runs. Otherwise the user messed up.
        if result_data.path not in [
            a.path for a in self.runs[result_data.run_index].artifacts
        ]:
            raise RuntimeError(
                f"Can not mark {result_data.path} as experiment result. "
                + f"Expected result_data.source_paths of {result_data.run_index} are "
                + f"{[a.path for a in self.runs[result_data.run_index].artifacts]}"
                + f"got {result_data.path}"
            )
        data: ResultData = copy(result_data)
        self.result_run_data.append(data)

    def _update_status(self) -> list[int]:
        """
        Update which jobs are waiting
        """
        run_ids: list[int] = []
        waiting_runs = list(
            filter(
                lambda x: x.status == "WAITING" and len(x.dependencies) > 0,
                self.runs,
            )
        )
        for i, run in enumerate(waiting_runs):
            if all(self.runs[j].status == "SUCCESS" for j in run.dependencies):
                run.status = "INIT"
                run_ids.append(self.runs.index(run))
            elif (
                len(
                    list(
                        filter(
                            lambda x: self.runs[x].status
                            in ["FAILED", "BLOCKED"],
                            run.dependencies,
                        )
                    )
                )
                > 0
            ):
                run.status = "BLOCKED"
                run_ids.append(self.runs.index(run))
            else:
                pass
        return run_ids

    def _conduct(self):
        """
        Conduct the experiment
        """

        with ThreadPoolExecutor() as executor:
            active: dict[Future[int], Run] = {}
            while True:
                # Schedule all currently ready runs.
                init_runs = list(
                    filter(lambda x: x.status == "INIT", self.runs)
                )
                for r in init_runs:
                    invocation = self._get_invocation(r)
                    r.start_time = time.time()
                    r.invocation = invocation
                    r.status = "RUNNING"
                    _ = self._rep.upsert_run(r)
                    active[
                        executor.submit(self._invoke, self.runs.index(r))
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
                    _ = self._rep.upsert_run(self.runs[i])
                if (
                    len(
                        list(
                            filter(
                                lambda x: x.status
                                in ["INIT", "WAITING", "RUNNING"],
                                self.runs,
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

        self.experiment.status = (
            "SUCCESS"
            if all(run.status == "SUCCESS" for run in self.runs)
            else "FAILED"
        )
        if self.experiment.status == "SUCCESS":
            # If the experiment succeeded all runs succeeded as well, i.e.
            # all expected output files are present as well.
            for result_run in self.result_run_data:
                print(result_run.path, end=" ")
                self.experiment.results.append(
                    ExperimentResult(
                        None,
                        cast(int, self.experiment.id),
                        cast(int, self.runs[result_run.run_index].id),
                        result_run.description,
                        result_run.path,
                        calculate_hash(result_run.path),
                    )
                )
            print()
        else:
            # If the experiment did not succeed no results are added
            pass
        _ = self._rep.upsert_experiment(self.experiment)

    def _init_experiment(self, description: str):
        """
        Start an experiment of the type $type.
        """
        experiment: Experiment = Experiment(
            None,
            self._wid,
            self._exp_type,
            0,
            time.time(),
            description,
            reduce(lambda a, b: a + " " + b, self._param_strs),
        )
        experiment.id = self._rep.upsert_experiment(experiment)
        self.experiment = experiment

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
        Sets the start_time, add the invocation string and invoke the run
        """
        options = self.run_ids_modifier_dict[run_id]
        result = subprocess.run(
            [
                str(self.runs[run_id].executable),
                self.runs[run_id].params,
            ],
            **options,
        )
        return result.returncode

    def _catch_artifacts(self, run: Run):
        """
        Computes the hash of all artifacts.
        If an artifact is missing False is returned
        s.t. the status of the Run can be set to FAILED
        """
        success = True
        for artifact in run.artifacts:
            if artifact.path.exists():
                artifact.hash = calculate_hash(artifact.path)
            else:
                success = False
        return success

    def _get_invocation(self, run: Run):
        """
        Get the correct invocation including redirect symbols
        """
        suffix = ""
        options = self.run_ids_modifier_dict[self.runs.index(run)]
        if "stdout" in options:
            suffix += f" > {options['stdout'].name}"
        if "stderr" in options:
            suffix += f" 2> {options['stderr'].name}"
        invocation = str(run.executable) + " "
        invocation += run.params
        return invocation + suffix
