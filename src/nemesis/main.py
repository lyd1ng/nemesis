from nemesis.config import Config, read_config


def main():
    config: Config = read_config()
    print(config)
