"""
Implements dictionary which maps the name of subcommands to parsing
and deploying functions which parse the parameters for the subcommand
and invoke the subcommand with the right parameters.
The prefix "pai_" stands for "parse and invoke"

Date:   20261002
Author: Lyding Anrie Brumm.
"""

from typing import cast

from nemesis.config import Config
from nemesis.domain import WorkingDirectory, WorkingDirectoryConfig
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
        working_directory_config = WorkingDirectoryConfig(
            None, cast(int, working_directory.id), content, _hash, now()
        )
        basic_subcommands.configure_working_directory(
            working_directory_config, repository
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
        configs: list[WorkingDirectoryConfig] = (
            repository.get_working_directory_configs(wid)
        )
        content = editor(text="" if len(configs) == 0 else configs[-1].content)
    else:
        raise RuntimeError("Should never happend")
    _hash = sha256(content.encode()).hexdigest()
    working_directory_config: WorkingDirectoryConfig = WorkingDirectoryConfig(
        None, wid, content, _hash, now()
    )
    working_directory_config.id = repository.add_working_directory_config(
        working_directory_config
    )


def invoke_subcommand(config: Config, repository: Repository) -> None:
    """
    Calls the parse and invoke layer for a given subcommand.
    This way the command line interface arguments are parsed according
    to the parameter list of the subcommand and the subcommand is invoked.
    """
    parser = argparse.ArgumentParser(prog="nemesis")

    commands = parser.add_subparsers(dest="command", required=True)
    experiment = commands.add_parser("experiment")
    experiment_command = experiment.add_subparsers(dest="experiment_command")
    experiment_register = experiment_command.add_parser("register")
    _ = experiment_register.add_argument("file", type=Path)
    experiment_register.set_defaults(handler=handle_experiment_register)
    experiment_show = experiment_command.add_parser("show")
    _ = experiment_show.add_argument("name", type=str)
    experiment_show.set_defaults(handler=handle_experiment_show)
    experiment_list = experiment_command.add_parser("list")
    experiment_list.set_defaults(handler=handle_experiment_list)
    experiment_run = experiment_command.add_parser("run")
    _ = experiment_run.add_argument("name", type=str)
    group = experiment_run.add_mutually_exclusive_group(required=True)
    _ = group.add_argument("--path", type=Path)
    _ = group.add_argument("--wid", type=int)
    _ = experiment_run.add_argument("--description", "-d", type=str)
    _ = experiment_run.add_argument("params", type=str, nargs="*")
    experiment_run.set_defaults(handler=handle_experiment_run)

    directory = commands.add_parser("directory")
    directory_command = directory.add_subparsers(dest="directory_command")
    directory_register = directory_command.add_parser("register")
    directory_configure = directory_command.add_parser("configure")

    _ = directory_register.add_argument("path", type=Path)
    _ = directory_register.add_argument(
        "--force", "-f", action="store_true", default=False
    )
    group = directory_register.add_mutually_exclusive_group(required=False)
    _ = group.add_argument(
        "--config_file",
        "-cf",
        type=Path,
    )
    _ = group.add_argument("--interactive", "-ci", action="store_true")
    directory_register.set_defaults(handler=handle_directory_register)

    group1 = directory_configure.add_mutually_exclusive_group(required=True)
    _ = group1.add_argument("--path", type=Path, default=None)
    _ = group1.add_argument("--wid", type=int)
    group2 = directory_configure.add_mutually_exclusive_group(required=True)
    _ = group2.add_argument("--config_file", "-cf", type=Path, default=None)
    _ = group2.add_argument("--interactive", "-ci", action="store_true")
    directory_configure.set_defaults(handler=handle_directory_configure)

    args = parser.parse_args()
    print(vars(args))
    args.handler(args, config, repository)
