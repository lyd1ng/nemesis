"""
Implements dictionary which maps the name of subcommands to parsing
and deploying functions which parse the parameters for the subcommand
and invoke the subcommand with the right parameters.
The prefix "pai_" stands for "parse and invoke"

Date:   20261002
Author: Lyding Anrie Brumm.
"""

from collections.abc import Callable
from nemesis.basic_subcommands import initialise_nemesis_directory


def pai_initialise_nemesis_directory(args: list[str]) -> None:
    """
    Parse and invoke the initialise_nemesis_directory command.
    """
    initialise_nemesis_directory()


SUBCOMMAND_DEPLOYER: dict[str, Callable[[list[str]], None]] = {
    "init": pai_initialise_nemesis_directory
}


def invoke_subcommand(args: list[str]) -> None:
    """
    Calls the parse and invoke layer for a given subcommand.
    This way the command line interface arguments are parsed according
    to the parameter list of the subcommand and the subcommand is invoked.
    """
    SUBCOMMAND_DEPLOYER[args[1]](args)
