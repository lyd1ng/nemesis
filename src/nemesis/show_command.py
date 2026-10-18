"""
Implements the 'experiment' command(s)

Date:   20261017
Author: Lyding Anrie Brumm.
"""

from typing import cast

from nemesis.domain import Experiment, ExperimentResult, WorkingDirectory, WorkingDirectoryEnv
from nemesis.repository import Repository
from nemesis.text_formatting import TextFormatter


def show_experiment(
    eid: int,
    fields: list[str],
    repository: Repository,
):
    tf: TextFormatter = TextFormatter()
    e: Experiment = repository.get_experiment(eid)
    wd: WorkingDirectory = repository.get_working_directory(e.wid)
    results: list[ExperimentResult] = repository.get_experiment_results(
        cast(int, e.id)
    )
    with tf.start_block(
        f"Experiment of type {e.type} with id {e.id}", 6, False
    ) as tf:
        _cond_print_var("Type", e.type, fields, tf)
        _cond_print_var("ID", e.id, fields, tf)
        _cond_print_var("Desc", e.description, fields, tf)
        _cond_print_var(
            "Params", e.params if e.params != "" else "NONE", fields, tf
        )
        _cond_print_var("Start", tf.date(e.start_time), fields, tf)
        _cond_print_var("End", tf.date(e.end_time), fields, tf)
        _cond_print_var("Status", e.status, fields, tf)
        _cond_print_var(
            "Mark", e.mark if e.mark is not None else "NONE", fields, tf
        )
        init = True
        if "results" in list(map(lambda s: s.lower(), fields)):
            with tf.start_block("Results"):
                for result in results:
                    with tf.start_block(f"Result ({result.id})", 11, not init):
                        tf.print_var("Description", result.description)
                        tf.print_var("Path", str(result.path))
                        tf.print_var("Hash", result.hash)
                    init = False
        if "wds" in list(map(lambda s: s.lower(), fields)):
            with tf.start_block(f"Working Directory ({wd.id})", padding=4):
                tf.print_var("Path", wd.path)
                tf.print_var("Type", wd.type)
                tf.print_var(
                    "SSH", wd.ssh_alias if wd.ssh_alias is not None else "NONE"
                )


def show_wd(wid: int, show_history: bool, repository: Repository):
    tf = TextFormatter()
    wd: WorkingDirectory = repository.get_working_directory(wid)
    with tf.start_block(f"Working Directory ({wd.id})", padding=4):
        tf.print_var("Path", wd.path)
        tf.print_var("Type", wd.type)
        tf.print_var(
            "SSH", wd.ssh_alias if wd.ssh_alias is not None else "NONE"
        )
        wdes: list[WorkingDirectoryEnv] = repository.get_wdes(wid)
        with tf.start_block(f"Environment(s)"):
            if show_history:
                for wde in wdes:
                    with tf.start_block(
                        f"Environment ({wde.id}) created at {tf.date(wde.created_at)}",
                        prepend_newline=False,
                    ):
                        tf.print_multiline(wde.content)
                        tf.print_var("Hash", wde.hash)
            else:
                with tf.start_block(
                    f"Environment ({wdes[-1].id}) created at {tf.date(wdes[-1].created_at)}",
                    prepend_newline=False,
                ):
                    tf.print_multiline(wdes[-1].content)
                    tf.print_var("Hash", wdes[-1].hash)


def _cond_print_var(
    name: str, value: object, fields: list[str], tf: TextFormatter
):
    """
    Only print a variable if the name is element of fields,
    but if the list of fields is empty print it nonetheless.
    """
    if len(fields) == 0 or name.lower() in list(
        map(lambda s: s.lower(), fields)
    ):
        tf.print_var(name, value)
