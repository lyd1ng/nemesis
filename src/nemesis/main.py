from nemesis.repository import Repository
from nemesis.config import Config, read_config
from nemesis.subcommand_deployer import invoke_subcommand


def main():
    config: Config = read_config()
    repository = Repository(config.database_path)
    print(config)
    try:
        invoke_subcommand(config, repository)
    except KeyError:
        print("FOO")
