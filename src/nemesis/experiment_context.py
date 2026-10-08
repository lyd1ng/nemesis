"""
Implements the API exposed to experiment descriptions files

Date:   20261002
Author: Lyding Anrie Brumm.
"""

from nemesis.domain import (Experiment, Run)
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
        self.runs.append(run)
        return len(self.runs) - 1

    def update_status(self):
        """
        Update which jobs are waiting
        """
        waiting_runs = list(filter(lambda x: x.status == "WAITING", self.runs))
        for i, run in enumerate(waiting_runs):
            if all(self.runs[j].status == "SUCCESS" for j in run.dependencies):
                run.status = "INIT"
            elif (
                len(
                    list(
                        filter(
                            lambda x: self.runs[x].status == "FAILED",
                            run.dependencies,
                        )
                    )
                )
                > 0
            ):
                run.status = "BLOCKED"
                self._propagate_blocked_status(i)
            else:
                pass

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
                    r.status = "SUCCESS" if r.exit_code == 0 else "FAILED"
                    self._rep.update_run(r)
                self.update_status()
                if (
                    len(
                        list(
                            filter(
                                lambda x: x.status in ["INIT", "WAITING"],
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
        result = subprocess.run(
            [
                str(self.runs[run_id].executable),
                self.runs[run_id].params,
            ],
        )
        return result.returncode

    def _propagate_blocked_status(self, run_id: int):
        """
        If a run is set to BLOCKED all other jobs which depend on
        that run BLOCKED run must be set to BLOCKED as well.
        """
        nodes = [run_id]
        while len(nodes) > 0:
            for i in range(len(nodes)):
                self.runs[nodes[i]].status = "BLOCKED"
                nodes += self.runs[nodes[i]].dependencies
                _ = nodes.pop(i)
