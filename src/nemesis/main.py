from sys import argv
from nemesis.config import Config, read_config
from nemesis.subcommand_deployer import invoke_subcommand


def main():
    pass
    config: Config = read_config()
    try:
        invoke_subcommand(argv, config)
    except KeyError:
        print(argv[1], "not known subcommand")
