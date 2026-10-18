"""
Implements dictionary which maps the name of subcommands to parsing
and deploying functions which parse the parameters for the subcommand
and invoke the subcommand with the right parameters.
The prefix "pai_" stands for "parse and invoke"

Date:   20261002
Author: Lyding Anrie Brumm.
"""

import tomllib
from typing import cast

from nemesis import query_command, show_command
from nemesis.config import Config
from nemesis.domain import WorkingDirectory, WorkingDirectoryEnv
from nemesis.repository import Repository
import nemesis.basic_subcommands as basic_subcommands
import nemesis.experiment_command as experiment_command

import argparse
from hashlib import sha256
from editor import editor
from time import time as now
from pathlib import Path


def handle_experiment_register(
    args: argparse.Namespace, config: Config, repository: Repository
):
    """
    Handle the experiment register command
    """
    _ = experiment_command.experiment_register(
        args.file, config.experiment_description_path, repository
    )


def handle_experiment_show(
    args: argparse.Namespace, _0: Config, repository: Repository
):
    """
    Hanlde the experiment show command
    """
    _ = experiment_command.experiment_show(args.name, repository)


def handle_experiment_list(
    _0: argparse.Namespace, _1: Config, repository: Repository
):
    """
    Hanlde the experiment list command
    """
    _ = experiment_command.experiment_list(repository)


def handle_experiment_run(
    args: argparse.Namespace,
    config: Config,
    repository: Repository,
):
    """
    Handle the experiment run command
    """
    # Fist interprete the specified path
    wid: int | None = (
        args.wid
        if args.wid is not None
        else repository.get_wid_from_path(args.path)
    )
    if wid is None:
        raise RuntimeError(
            f"Can not run experiment, {args.path} is not registered"
        )

    _ = experiment_command.experiment_run(
        wid,
        args.name,
        args.description,
        args.params,
        config.experiment_description_path,
        repository,
    )


def handle_experiment_check(
    args: argparse.Namespace,
    config: Config,
    repository: Repository,
):
    """
    Handle the experiment ceck command
    """
    wid: int | None = (
        args.wid
        if args.wid is not None
        else repository.get_wid_from_path(args.path)
    )
    if wid is None:
        raise RuntimeError(
            f"Can not run experiment, {args.path} is not registered"
        )
    experiment_command.experiment_check(
        args.type, wid, config.experiment_description_path, repository
    )


def handle_directory_register(
    args: argparse.Namespace, _: Config, repository: Repository
):
    working_directory: WorkingDirectory = basic_subcommands.register_directory(
        args.path, args.force, repository
    )

    content: str | None = None
    # Either read the config from a file
    if args.config_file:
        content = args.config_file.read_text()
    # or interactively
    elif args.interactive:
        content = editor()
    # or not at all
    else:
        print("Working directory registered without configuration.")
    # but only when content is present, automatically add a configuration
    if content is not None:
        _hash = sha256(content.encode()).hexdigest()
        working_directory_env = WorkingDirectoryEnv(
            id=None,
            wid=cast(int, working_directory.id),
            content=content,
            hash=_hash,
            created_at=now(),
            variables=tomllib.loads(content),
        )
        basic_subcommands.configure_working_directory(
            working_directory_env, repository
        )
        print("Working directory registered with configuration.")


def handle_directory_configure(
    args: argparse.Namespace, _: Config, repository: Repository
):
    # Either the user specified wid directly
    # or it has to be queried from the database
    wid = (
        args.wid
        if args.wid is not None
        else repository.get_wid_from_path(args.path)
    )
    if wid is None:
        raise RuntimeError(f"Can not find wid of path {args.path}")
    # Either read the config from a file
    if args.config_file:
        content = args.config_file.read_text()
    # or interactively
    elif args.interactive:
        # but if there are already configurations present use the latest
        # configuration as a template
        configs: list[WorkingDirectoryEnv] = repository.get_wdes(wid)
        content = editor(text="" if len(configs) == 0 else configs[-1].content)
    else:
        raise RuntimeError("Should never happend")
    _hash = sha256(content.encode()).hexdigest()
    working_directory_env: WorkingDirectoryEnv = WorkingDirectoryEnv(
        None, wid, content, _hash, now(), tomllib.loads(content)
    )
    working_directory_env.id = repository.add_working_directory_env(
        working_directory_env
    )


def handle_show_experiment(
    args: argparse.Namespace, _: Config, repository: Repository
):
    """
    Show experiments
    """
    ids: list[int] = args.ids
    for eid in ids:
        show_command.show_experiment(eid, repository)
        print("")


def handle_show_wd(args: argparse.Namespace, _: Config, repository: Repository):
    """
    Show working directories
    """
    show_full_history: bool = args.full_history
    # Fist interprete the specified path
    wid: int | None = (
        args.wid
        if args.wid is not None
        else repository.get_wid_from_path(args.path)
    )
    if wid is None:
        raise RuntimeError(
            f"Can not run experiment, {args.path} is not registered"
        )
    show_command.show_wd(wid, show_full_history, repository)


def handle_query_experiments(
    args: argparse.Namespace, _: Config, repository: Repository
):
    """
    Handle the query experiment command
    """
    eids = []
    filters: list[tuple[str, str, str]] = []
    for filter_string in args.filter_strings:
        matches: int = 0
        operators: list[str] = ["=", "!=", ">", "<", ">=", "<=", "is", "is not"]
        operator: str = ""
        for op in operators:
            if op in filter_string:
                matches += 1
                operator = op
        if matches > 1:
            raise RuntimeError(f"More then one operator ({matches}) detected!")
        words: list[str] = filter_string.split(operator)
        filters.append((words[0], operator, words[1]))
        eids = query_command.query_experiments(filters, repository)
    for eid in eids:
        print(eid)


def invoke_subcommand(config: Config, repository: Repository) -> None:
    """
    Calls the parse and invoke layer for a given subcommand.
    This way the command line interface arguments are parsed according
    to the parameter list of the subcommand and the subcommand is invoked.
    """
    parser = argparse.ArgumentParser(prog="nemesis")
    commands = parser.add_subparsers(dest="command", required=True)

    # ============  EXPERIMENT COMMAND ========================================
    experiment = commands.add_parser("experiment")
    experiment_command = experiment.add_subparsers(dest="experiment_command")
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    experiment_register = experiment_command.add_parser("register")
    _ = experiment_register.add_argument("file", type=Path)
    _ = experiment_register.set_defaults(handler=handle_experiment_register)

    experiment_check = experiment_command.add_parser("check")
    _ = experiment_check.add_argument("type", type=str)
    g = experiment_check.add_mutually_exclusive_group(required=True)
    _ = g.add_argument("--path", type=Path)
    _ = g.add_argument("--wid", type=int)
    _ = experiment_check.set_defaults(handler=handle_experiment_check)

    experiment_run = experiment_command.add_parser("run")
    _ = experiment_run.add_argument("name", type=str)
    g = experiment_run.add_mutually_exclusive_group(required=True)
    _ = g.add_argument("--path", type=Path)
    _ = g.add_argument("--wid", type=int)
    _ = experiment_run.add_argument("--description", "-d", type=str)
    _ = experiment_run.add_argument("params", type=str, nargs="*")
    _ = experiment_run.set_defaults(handler=handle_experiment_run)

    # ============  DIRECTORY COMMAND =========================================
    directory = commands.add_parser("directory")
    directory_command = directory.add_subparsers(dest="directory_command")
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    directory_register = directory_command.add_parser("register")
    _ = directory_register.add_argument("path", type=Path)
    _ = directory_register.add_argument(
        "--force", "-f", action="store_true", default=False
    )
    g = directory_register.add_mutually_exclusive_group(required=False)
    _ = g.add_argument(
        "--config_file",
        "-cf",
        type=Path,
    )
    _ = g.add_argument("--interactive", "-ci", action="store_true")
    directory_register.set_defaults(handler=handle_directory_register)

    directory_configure = directory_command.add_parser("configure")
    g = directory_configure.add_mutually_exclusive_group(required=True)
    _ = g.add_argument("--path", type=Path, default=None)
    _ = g.add_argument("--wid", type=int)
    g = directory_configure.add_mutually_exclusive_group(required=True)
    _ = g.add_argument("--config_file", "-cf", type=Path, default=None)
    _ = g.add_argument("--interactive", "-ci", action="store_true")
    directory_configure.set_defaults(handler=handle_directory_configure)

    # ============  SHOW COMMAND ==============================================
    show = commands.add_parser("show")
    show_command = show.add_subparsers(dest="show_command")
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    show_experiment = show_command.add_parser("experiment")
    _ = show_experiment.add_argument("ids", type=int, nargs="*")
    show_experiment.set_defaults(handler=handle_show_experiment)

    show_wd = show_command.add_parser("wd")
    g = show_wd.add_mutually_exclusive_group(required=True)
    _ = g.add_argument("--path", type=Path, default=None)
    _ = g.add_argument("--wid", type=int)
    _ = show_wd.add_argument(
        "--full_history", default=False, action="store_true"
    )
    show_wd.set_defaults(handler=handle_show_wd)

    # ============ QUERY COMMAND ==============================================
    query = commands.add_parser("query")
    query_command = query.add_subparsers(dest="query_command")
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    query_experiment = query_command.add_parser("experiment")
    _ = query_experiment.add_argument("filter_strings", type=str, nargs="*")
    query_experiment.set_defaults(handler=handle_query_experiments)

    args = parser.parse_args()
    args.handler(args, config, repository)
