"""
Implements the API exposed to experiment descriptions files

Date:   20261015
Author: Lyding Anrie Brumm.
"""

from argparse import Namespace
from functools import reduce

import networkx as nx
from pathlib import Path
from typing import Literal, Unpack
from collections.abc import Mapping
from datetime import date, datetime, time, timezone

from nemesis.utility import RunOptionsU

DUMMY_VALUES: dict[type, object] = {
    str: "dummy",
    int: 1,
    float: 1.0,
    bool: True,
    datetime: datetime(2000, 1, 1, tzinfo=timezone.utc),
    date: date(2000, 1, 1),
    time: time(12, 0),
}


class SandboxApi(object):
    """
    Defines a sandboxed version of the API, which does not make any
    changes to the database but is used to perform sanity checks on
    the experiment description.
    """

    def __init__(
        self, requirements: list[tuple[type, str]], parameters: dict[str, type]
    ):
        self._dependency_graph: nx.DiGraph[int] = nx.DiGraph()
        self._runs: list[tuple[int, list[int]]] = []
        self._produces_results: bool = False
        # Use the DUMMY_VALUES dictionary to create an environment
        # which yields a dummy variable of the correct type for each
        # required variable.
        self.env: Mapping[str, object] = {
            requirement[1]: DUMMY_VALUES[requirement[0]]
            for requirement in requirements
        }
        self.params: Namespace = Namespace(
            **{
                parameter[0]: DUMMY_VALUES[parameter[1]]
                for parameter in parameters.items()
            }
        )

    def add_confined_run(
        self,
        description: str,
        executable: Path,
        params: list[str],
        dependencies: list[int],
        outputs: list[str],
        **kwargs: Unpack[RunOptionsU],
    ) -> int:
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
        return self._add_run(
            description,
            executable,
            params,
            dependencies,
            outputs,
            "UNCONFINED",
            **kwargs,
        )

    def mark_artifact_as_result(
        self,
        run_index: int,
        description: str,  # pyright: ignore[reportUnusedParameter]
        path: Path,  # pyright: ignore[reportUnusedParameter]
    ) -> None:
        joint_dependency_list: list[int] = reduce(
            lambda a, b: a + b, [run[1] for run in self._runs]
        )
        if run_index in joint_dependency_list:
            raise RuntimeError(
                f"Can not mark {run_index} as a result run. Other runs depend on it."
            )
        self._produces_results = True

    def _verify(self):
        if not self._produces_results:
            raise RuntimeError("Experiment does not produce a result")
        self._build_and_check_dependency_tree()

    def _add_run(
        self,
        description: str,  # pyright: ignore[reportUnusedParameter]
        executable: Path,  # pyright: ignore[reportUnusedParameter]
        params: list[str],  # pyright: ignore[reportUnusedParameter]
        dependencies: list[int],
        outputs: list[str],  # pyright: ignore[reportUnusedParameter]
        mode: (  # pyright: ignore[reportUnusedParameter]
            Literal["CONFINED"] | Literal["UNCONFINED"]
        ),
        **kwargs: Unpack[RunOptionsU],  # pyright: ignore[reportUnusedParameter]
    ) -> int:
        """
        Generate a node for each run
        """
        rid = len(self._runs)
        self._runs.append((rid, dependencies))
        self._dependency_graph.add_node(rid)
        return rid

    def _build_and_check_dependency_tree(self):
        """
        Build and check the dependency tree for cyclicity
        """
        for rid, dependencies in self._runs:
            for dependency in dependencies:
                _ = self._dependency_graph.add_edge(rid, dependency)
        if not nx.is_directed_acyclic_graph(self._dependency_graph):
            raise RuntimeError("Cyclic dependencies detected!")
