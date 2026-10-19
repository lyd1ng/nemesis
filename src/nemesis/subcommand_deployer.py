"""
Implements dictionary which maps the name of subcommands to parsing
and deploying functions which parse the parameters for the subcommand
and invoke the subcommand with the right parameters.
The prefix "pai_" stands for "parse and invoke"

Date:   20261002
Author: Lyding Anrie Brumm.
"""

from collections.abc import Callable
import subprocess
import tomllib
from typing import cast

from nemesis import query_command, show_command
from nemesis.constants import BOOTSTRAP_PATH
from nemesis.domain import User, WorkingDirectory, WorkingDirectoryEnv
from nemesis.repository import Repository
import nemesis.basic_subcommands as basic_subcommands
import nemesis.experiment_command as experiment_command

import argparse
from hashlib import sha256
from editor import editor
from time import time as now
from pathlib import Path
from getpass import getuser

# Global variable for the experiment description file.
# Set from invoke_subcommand at least if nemesis was registered.
edf_path: Path = Path("")


def with_initialization_check(
    func: Callable[[argparse.Namespace, Repository], None],
):
    """
    Checks if nemesis was already initialised.
    I.e. if edf_path was set
    """

    def inner(args: argparse.Namespace, repository: Repository) -> None:
        if edf_path == Path(""):
            raise RuntimeError("Nemesis initialization required")
        func(args, repository)

    return inner


def resolve_wd_path(path: Path, repository: Repository) -> int:
    """
    WD paths are either specified as a regular path, or
    through a leading ":" followed by the wid.
    E.g.
        ./foo/bar/baz
        :1
    are both valid specifications
    """
    if str(path)[0] == ":":
        return int(str(path)[1:])
    else:
        return repository.get_wid_from_path(path)


def handle_init(args: argparse.Namespace, repository: Repository):
    """
    Initialise nemesis
    """
    if not args.nemesis_path.is_absolute():
        raise RuntimeError("Can not initialise nemesis under relative path.")
    if BOOTSTRAP_PATH.exists():
        raise RuntimeError("Can not initialise nemesis; already initialized.")
    if repository.db_path != Path(""):
        raise RuntimeError("Somehow a repository is already initialized.")
    _ = BOOTSTRAP_PATH.write_text(str(args.nemesis_path))
    _ = subprocess.run(["chmod", "2770", str(args.nemesis_path)])
    _ = subprocess.run(["chgrp", "nemesis", str(args.nemesis_path)])
    edf_path = args.nemesis_path / Path("edf")
    edf_path.mkdir(exist_ok=False)
    _ = subprocess.run(["chmod", "2770", str(edf_path)])

    repository = Repository(args.nemesis_path / Path("nemesis.db"))
    _ = subprocess.run(["chmod", "770", str(repository.db_path)])


@with_initialization_check
def handle_experiment_register(
    args: argparse.Namespace, repository: Repository
):
    """
    Handle the experiment register command
    """
    _ = experiment_command.experiment_register(args.file, edf_path, repository)


@with_initialization_check
def handle_experiment_show(args: argparse.Namespace, repository: Repository):
    """
    Handle the experiment show command
    """
    _ = experiment_command.experiment_show(args.name, repository)


@with_initialization_check
def handle_experiment_list(_0: argparse.Namespace, repository: Repository):
    """
    Handle the experiment list command
    """
    _ = experiment_command.experiment_list(repository)


@with_initialization_check
def handle_experiment_run(
    args: argparse.Namespace,
    repository: Repository,
):
    """
    Handle the experiment run command
    """
    wid = resolve_wd_path(args.path, repository)

    _ = experiment_command.experiment_run(
        wid,
        args.name,
        getuser(),
        args.description,
        args.params,
        edf_path,
        repository,
    )


@with_initialization_check
def handle_experiment_check(
    args: argparse.Namespace,
    repository: Repository,
):
    """
    Handle the experiment ceck command
    """
    wid = resolve_wd_path(args.path, repository)
    experiment_command.experiment_check(args.type, wid, edf_path, repository)


@with_initialization_check
def handle_directory_register(args: argparse.Namespace, repository: Repository):
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


@with_initialization_check
def handle_directory_configure(
    args: argparse.Namespace, repository: Repository
):
    wid = resolve_wd_path(args.path, repository)
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


@with_initialization_check
def handle_show_experiment(args: argparse.Namespace, repository: Repository):
    """
    Show experiments
    """
    ids: list[int] = args.ids
    fields: list[str] = args.fields_string.split(",")
    if len(fields) == 1 and len(fields[0]) == 0:
        fields = []
    for eid in ids:
        show_command.show_experiment(eid, fields, repository)
        print("")


@with_initialization_check
def handle_show_wd(args: argparse.Namespace, repository: Repository):
    """
    Show working directories
    """
    wid = resolve_wd_path(args.path, repository)
    show_full_history: bool = args.full_history
    show_command.show_wd(wid, show_full_history, repository)


@with_initialization_check
def handle_show_user(args: argparse.Namespace, repository: Repository):
    """
    Show a specified user
    """
    show_command.show_user(args.name, repository)


@with_initialization_check
def handle_query_experiments(args: argparse.Namespace, repository: Repository):
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


@with_initialization_check
def handle_user_register(args: argparse.Namespace, repository: Repository):
    """
    Register a user
    """
    user: User = User(name=getuser(), alias=args.alias, email=args.email)
    _ = repository.upsert_user(user)


def invoke_subcommand(repository: Repository, _edf_path: Path) -> None:
    """
    Calls the parse and invoke layer for a given subcommand.
    This way the command line interface arguments are parsed according
    to the parameter list of the subcommand and the subcommand is invoked.
    """
    global edf_path
    parser = argparse.ArgumentParser(prog="nemesis")
    commands = parser.add_subparsers(dest="command", required=True)

    # ============  INIT COMMAND ==========================================
    init = commands.add_parser("init")
    _ = init.add_argument("nemesis_path", type=Path)
    init.set_defaults(handler=handle_init)
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    edf_path = _edf_path
    # Once nemesis was initialised all commands but nemesis init are possible
    # ============  EXPERIMENT COMMAND ========================================
    experiment = commands.add_parser("experiment")
    experiment_command = experiment.add_subparsers(dest="experiment_command")
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    experiment_register = experiment_command.add_parser("register")
    _ = experiment_register.add_argument("file", type=Path)
    _ = experiment_register.set_defaults(handler=handle_experiment_register)

    experiment_check = experiment_command.add_parser("check")
    _ = experiment_check.add_argument("type", type=str)
    _ = experiment_check.add_argument("path", type=Path)
    _ = experiment_check.set_defaults(handler=handle_experiment_check)

    experiment_run = experiment_command.add_parser("run")
    _ = experiment_run.add_argument("--description", "-d", type=str)
    _ = experiment_run.add_argument("name", type=str)
    _ = experiment_run.add_argument("path", type=Path)
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
    _ = directory_configure.add_argument("path", type=Path)
    g = directory_configure.add_mutually_exclusive_group(required=True)
    _ = g.add_argument("--config_file", "-cf", type=Path, default=None)
    _ = g.add_argument("--interactive", "-ci", action="store_true")
    directory_configure.set_defaults(handler=handle_directory_configure)

    # ============  USER COMMAND ==============================================
    user = commands.add_parser("user")
    user_command = user.add_subparsers(dest="user_command")
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    user_register = user_command.add_parser("register")
    _ = user_register.add_argument("alias", type=str)
    _ = user_register.add_argument("email", type=str)
    user_register.set_defaults(handler=handle_user_register)

    # ============  SHOW COMMAND ==============================================
    show = commands.add_parser("show")
    show_command = show.add_subparsers(dest="show_command")
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    show_experiment = show_command.add_parser("experiment")
    _ = show_experiment.add_argument("--fields_string", type=str, default="")
    _ = show_experiment.add_argument("ids", type=int, nargs="*")
    show_experiment.set_defaults(handler=handle_show_experiment)

    show_wd = show_command.add_parser("wd")
    _ = show_wd.add_argument("path", type=Path)
    _ = show_wd.add_argument(
        "--full_history", default=False, action="store_true"
    )
    show_wd.set_defaults(handler=handle_show_wd)

    show_user = show_command.add_parser("user")
    _ = show_user.add_argument("name", type=str)
    show_user.set_defaults(handler=handle_show_user)

    # ============ QUERY COMMAND ==============================================
    query = commands.add_parser("query")
    query_command = query.add_subparsers(dest="query_command")
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    query_experiment = query_command.add_parser("experiment")
    _ = query_experiment.add_argument("filter_strings", type=str, nargs="*")
    query_experiment.set_defaults(handler=handle_query_experiments)

    args = parser.parse_args()
    args.handler(args, repository)
