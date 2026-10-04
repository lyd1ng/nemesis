"""
Implements dictionary which maps the name of subcommands to parsing
and deploying functions which parse the parameters for the subcommand
and invoke the subcommand with the right parameters.
The prefix "pai_" stands for "parse and invoke"

Date:   20261002
Author: Lyding Anrie Brumm.
"""

from nemesis.config import Config
from nemesis.repository import Repository
from nemesis.basic_subcommands import initialise_nemesis_directory
import nemesis.experiment_command as ec

import argparse
from pathlib import Path

'''
def pai_init(args: list[str], config: Config, repository: Repository) -> None:
    """
    Parse and invoke the initialise_nemesis_directory command.
    """
    initialise_nemesis_directory()
'''


def handle_experiment_register(
    args: argparse.Namespace, config: Config, repository: Repository
):
    """
    Handle the experiment register command
    """
    _ = ec.experiment_register(
        args.file, config.experiment_description_path, repository
    )


def handle_experiment_show(
    args: argparse.Namespace, config: Config, repository: Repository
):
    """
    Hanlde the experiment show command
    """
    _ = ec.experiment_show(args.name, repository)


def handle_experiment_list(
    args: argparse.Namespace, config: Config, repository: Repository
):
    """
    Hanlde the experiment list command
    """
    _ = ec.experiment_list(repository)


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
    args = parser.parse_args()
    args.handler(args, config, repository)
