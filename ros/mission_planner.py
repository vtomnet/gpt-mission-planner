import logging

import click
import yaml

from network_interface import NetworkInterface
from mp_decoder import MPDecoder

class MissionPlanner:
    def __init__(
        self,
        logger: logging.Logger,
        schema_path: str,
        farm_layout: str,
        log_directory: str,
        host: str,
        port: int,
    ):
        # logger instance
        self.logger: logging.Logger = logger
        # set farm file paths
        self.farm_layout: str = farm_layout
        # logging GPT output folder
        self.log_directory: str = log_directory
        # decoder object
        self.decoder: MPDecoder = MPDecoder(schema_path, logger)

        self._configure_network(host, port)

    def run(self) -> None:
        temp_xml_path: str = self.nic.receive_file()
        ret, e = self.decoder.validate_output(temp_xml_path)
        if ret:
            self.logger.debug(e)

            self.decoder.decode_xml_mp(temp_xml_path)
        else:
            self.logger.error(e)

    def _configure_network(self, host: str, port: int) -> None:
        self.nic: NetworkInterface = NetworkInterface(
            self.logger, self.log_directory, host, port
        )

@click.command()
@click.option(
    "--config",
    default="./ros/config/husky01.yaml",
    help="YAML config file",
)
def main(config: str):
    with open(config, "r") as file:
        config_yaml: yaml.Node = yaml.safe_load(file)

    try:
        # configure logger
        logging.basicConfig(level=logging._nameToLevel[config_yaml["logging"]])
        logger: logging.Logger = logging.getLogger()

        mp: MissionPlanner = MissionPlanner(
            logger,
            config_yaml["schema"],
            config_yaml["farm_layout"],
            config_yaml["log_directory"],
            config_yaml["host"],
            config_yaml["port"],
        )
    except yaml.YAMLError as exc:
        logger.error(f"Improper YAML config: {exc}")

    mp.run()


if __name__ == "__main__":
    main()
