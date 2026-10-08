"""
Implements the API exposed to experiment descriptions files

Date:   20261002
Author: Lyding Anrie Brumm.
"""

from nemesis.domain import (Experiment, Run, RunArtifact)
from nemesis.repository import Repository
from nemesis.utility import (calculate_hash, get_git_commit)

import time
import subprocess
from typing import cast
from pathlib import Path
from functools import reduce
from argparse import ArgumentParser, Namespace
from concurrent.futures import (
    ThreadPoolExecutor,
    Future,
    wait,
    FIRST_COMPLETED,
)


class ExperimentContext(object):

    def __init__(
        self,
        repository: Repository,
        exp_type: str,
        params: list[str],
        parameter_types: dict[str, type],
        polling: float = 1.0,
    ):
        self._rep: Repository = repository
        self._exp_type: str = exp_type
        self._param_strs: list[str] = params
        self._param_types: dict[str, type] = parameter_types
        self.polling: float = polling
        self.params: Namespace = self._parse()
        # Just a dummy variable because None leads to static typo issues
        self.experiment: Experiment = Experiment("", 0, 0, "", "", "INIT")
        self.runs: list[Run] = []
        self.run_ids_modifier_dict: dict[int, dict[str, object]] = {}

    def init_experiment(self, description: str):
        """
        Start an experiment of the type $type.
        """
        experiment: Experiment = Experiment(
            self._exp_type,
            0,
            time.time(),
            description,
            reduce(lambda a, b: a + " " + b, self._param_strs),
        )
        self._rep.add_experiment(experiment)
        self.experiment = experiment

    def add_run(
        self,
        description: str,
        executable: Path,
        params: list[str],
        dependencies: list[int],
        outputs: list[str],
        **kwargs: object,
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
            -1,
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
        run.id = self._rep.add_run(run)
        for output in outputs:
            run.artifacts.append(RunArtifact(0, run.id, Path(output), ""))
        self.runs.append(run)
        internal_id = len(self.runs) - 1
        self._rep.update_run(run)
        # Store kwargs for later use
        self.run_ids_modifier_dict[internal_id] = kwargs
        return internal_id

    def update_status(self) -> list[int]:
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

    def conduct(self):
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
                    invocation = str(r.executable) + " "
                    invocation += r.params
                    r.start_time = time.time()
                    r.invocation = invocation
                    r.status = "RUNNING"
                    self._rep.update_run(r)
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
                    self._rep.update_run(r)
                dirty_run_ids = self.update_status()
                for i in dirty_run_ids:
                    self._rep.update_run(self.runs[i])
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
        self.experiment.status = (
            "SUCCESS"
            if all(run.status == "SUCCESS" for run in self.runs)
            else "FAILED"
        )
        self._rep.update_experiment(self.experiment)

    def fetch_run(self, run_id: int):
        """
        Fetch a run from the database
        """
        index = next(
            (i for i, item in enumerate(self.runs) if item.id == run_id), None
        )
        if index is None:
            raise RuntimeError(
                "Could not find a instance of Run with id={run_id}"
            )
        self.runs[index] = self._rep.get_run(run_id)

    def fetch_all_runs(self):
        """
        Fetch a all runs from the database
        """
        for i, run in enumerate(self.runs):
            self.runs[i] = self._rep.get_run(run.id)

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
