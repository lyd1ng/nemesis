"""
Implements a hierarchical configuration file parser.

Date:   20261002
Author: Lyding Anrie Brumm.
"""

import tomllib
from typing import Self
from pathlib import Path
from collections.abc import Callable
from platformdirs import user_data_path
from dataclasses import dataclass, fields, replace
from nemesis.constants import DEFAULT_GLOBAL_PATH, DEFAULT_LOCAL_PATH

# This string to callable map is used to convert the string annotations
# to constructors.
MAP: dict[str, Callable[[str], object]] = {
    "str": str,
    "float": float,
    "pathlib.Path": Path,
}


@dataclass(slots=True)
class Config:
    """
    The configuration full of nemesis.
    Also implements logic for merging two configurations.
    """

    # WARNING: Only use 'simple' type annotations
    # which are of the type "correct_type | invalid_type"
    author: str | None = None
    timeout: float | None = None
    database_path: Path | None = None
    artifact_path: Path | None = None
    experiment_description_path: Path | None = None

    def __mul__(self, other: Self) -> Self:
        """
        Use multiplication operation to merge configurations.
        Why multiplication? Because it is the most general mathematical
        symbol, both addition and 'or' imply (at least to me) that
        the operation is commutative, which is explicitly not the case!
        Instead the second configuration is the configuration of higher
        precedence.
        """
        parameters = {
            field.name: (
                getattr(other, field.name)
                if getattr(other, field.name) is not None
                else getattr(self, field.name)
            )
            for field in fields(self)
        }
        return replace(self, **parameters)


class ConfigDefault(object):
    """
    The default configurations for Nemesis
    """

    def __init__(self):
        self.config: Config = Config()

    def parse(self):
        """
        Generate an instance of 'Config' using default settings.
        """
        data_dir = user_data_path("nemesis")
        self.config = Config(
            author="Unknown",
            timeout=60.0,
            database_path=data_dir / Path("nemesis.db"),
            artifact_path=data_dir / Path("artifacts"),
            experiment_description_path=data_dir / Path("experiment_descriptions"),
        )
        return self.config


class ConfigFileReader(object):
    """
    Configuration file reader, creating an instance of 'Config' from a TOML
    file.
    """

    def __init__(self, path: Path):
        self.path: Path = path
        self.config: Config = Config()

    def parse(self):
        """
        Parse configuration file, if the path can not be loaded
        an empty configuration file (all fields set to None) is generated.
        This way it can be merged without affecting the resulting
        configuration.
        """
        config = Config()
        try:
            fd = open(self.path, "rb")
        except FileNotFoundError:
            self.config = Config()
            return self.config
        # Load the toml file and use the type annotations which are part
        # of pythons reflection system to convert the parsed strings
        # to the correct datatype.
        # WARNING: This only works for simple type annotations where
        # the first entry is the datatype on success and the second is
        # the default datatype if an error occurs.
        toml_dict: dict[str, str] = tomllib.load(fd)
        for field in fields(config):
            # This line of code might be difficult to digest...
            # It uses the first entry of a type annotation like "str | None"
            # and maps it to a constructor call which is then applied to
            # the entry in the toml_dictionary with the right name.
            # This way the toml file is parsed into a config file
            # using the annotated types!
            try:
                setattr(
                    config,
                    field.name,
                    MAP[str(field.type).split(" ")[0]](toml_dict[field.name]),
                )
            except KeyError:
                pass
        self.config = config
        fd.close()
        return self.config


class ConfigStringReader(object):
    """
    Configuration string reader, creating an instance of 'Config' from a TOML
    string.
    """

    def __init__(self, string: str):
        self.string: str = string
        self.config: Config = Config()

    def parse(self):
        """
        Parse configuration string.
        """
        config = Config()
        # Take the toml string file and use the type annotations which are part
        # of pythons reflection system to convert the parsed strings
        # to the correct datatype.
        # WARNING: This only works for simple type annotations where
        # the first entry is the datatype on success and the second is
        # the default datatype if an error occurs.
        toml_dict: dict[str, str] = tomllib.loads(self.string)
        for field in fields(config):
            # This line of code might be difficult to digest...
            # It uses the first entry of a type annotation like "str | None"
            # and maps it to a constructor call which is then applied to
            # the entry in the toml_dictionary with the right name.
            # This way the toml file is parsed into a config file
            # using the annotated types!
            try:
                setattr(
                    config,
                    field.name,
                    MAP[str(field.type).split(" ")[0]](toml_dict[field.name]),
                )
            except KeyError:
                pass
        self.config = config
        return self.config


def read_config(cli_arguments: str = "") -> Config:
    """
    Read the whole configuration. With increasing precedence the config
    is read as:
        global config -> local config -> cli parameter
    """
    return (
        ConfigDefault().parse()
        * ConfigFileReader(DEFAULT_GLOBAL_PATH).parse()
        * ConfigFileReader(DEFAULT_LOCAL_PATH).parse()
        * ConfigStringReader(cli_arguments).parse()
    )
