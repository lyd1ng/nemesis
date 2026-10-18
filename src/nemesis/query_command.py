"""
Implements query command

Date:   20261018
Author: Lyding Anrie Brumm.
"""

from nemesis.repository import Repository


def query_experiments(
    filters: list[tuple[str, str, str]], repository: Repository
) -> list[int]:
    """
    Query the database for experiment ids subject to various filters
    """
    return repository.get_experiment_ids(filters)
