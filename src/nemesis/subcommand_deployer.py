"""
Implements dictionary which maps the name of subcommands to parsing
and deploying functions which parse the parameters for the subcommand
and invoke the subcommand with the right parameters.
The prefix "pai_" stands for "parse and invoke"

Date:   20261002
Author: Lyding Anrie Brumm.
"""

from nemesis.config import Config
from nemesis.basic_subcommands import initialise_nemesis_directory
from nemesis.experiment_command import experiment_register
from pathlib import Path
from typing import cast
from collections.abc import Callable


def pai_init(args: list[str], config: Config) -> None:
    """
    Parse and invoke the initialise_nemesis_directory command.
    """
    initialise_nemesis_directory()


def pai_experiment(args: list[str], config: Config) -> None:
    """
    Parse and invoke the experiment command.
    """
    # WARNING: STUPID AD HOC IMPLEMENTATION
    sub_commands = {"register": experiment_register}
    sub_commands[args[2]](Path(args[3]), cast(Path, config.experiment_description_path))


SUBCOMMAND_DEPLOYER: dict[str, Callable[[list[str], Config], None]] = {
    "init": pai_init,
    "experiment": pai_experiment,
}


def invoke_subcommand(args: list[str], config: Config) -> None:
    """
    Calls the parse and invoke layer for a given subcommand.
    This way the command line interface arguments are parsed according
    to the parameter list of the subcommand and the subcommand is invoked.
    """
    SUBCOMMAND_DEPLOYER[args[1]](args, config)
