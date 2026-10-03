"""
Tests the functionality of the config module

Date:   20261003
Author: Lyding Anrie Brumm
"""

from pathlib import Path
from nemesis import config
from dataclasses import asdict


def test_config_init_as_none():
    """
    Test if an empty constructor constructs alls fields as None
    """
    c: config.Config = config.Config()
    for key, value in asdict(c).items():
        assert value is None, f"{key} is not None"


def test_config_merge_override():
    """
    Test if the second config extends and overrides but does not delete entries.
    """
    a: config.Config = config.Config(author="A", database_path=Path("nemesis.db"))
    b: config.Config = config.Config(author="B", timeout=1234.0)
    c: config.Config = a * b
    assert str(c.database_path) == "nemesis.db", "database_path is overwritten"
    assert c.author == "B", "author is not updated"
    assert c.timeout == 1234.0, "timeout is not added"
