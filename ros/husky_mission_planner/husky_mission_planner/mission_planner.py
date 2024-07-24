import logging
import os
import sys

import click
import yaml
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from .network_interface import NetworkInterface
from .mp_decoder import MPDecoder

class MissionPlanner(Node):
    def __init__(
        self,
        logger: logging.Logger,
        name: str,
        schema_path: str,
        farm_layout: str,
        log_directory: str,
        host: str,
        port: int,
    ):
        super().__init__(name)
        # logger instance
        self.logger: logging.Logger = logger
        # set farm file paths
        self.farm_layout: str = farm_layout
        # logging GPT output folder
        self.log_directory: str = log_directory
        # decoder object
        self.decoder: MPDecoder = MPDecoder(schema_path, logger)

        self._configure_network(host, port)

        self.publisher_ = self.create_publisher(String, '/mission_plan', 10)

        self.run()

    def run(self) -> None:
        bytes_received, temp_xml_path = self.nic.receive_file()
        ret, e = self.decoder.validate_output(temp_xml_path)
        if ret:
            self.logger.debug(e)

            self.decoder.decode_xml_mp(temp_xml_path)
        else:
            self.logger.error(e)

        # if you got the MP
        if bytes_received > 0:
            # TODO: update this with a custom message that has a list of waypoints and robot actions
            self.logger.debug("Mission plan received successfully...")
            resp: String = String()
            resp.data = "Mission plan received..."
            self.publisher_.publish(resp)
        # if you actually didn't receive anything
        else:
            os.remove(temp_xml_path)
            self.logger.debug("Mission plan not received...")

        # TODO: find a break point to exit gracefully  
        # receive one message at a time
        self.nic.close_socket()

        raise SystemExit

    def _configure_network(self, host: str, port: int) -> None:
        self.nic: NetworkInterface = NetworkInterface(
            self.logger, self.log_directory, host, port
        )

@click.command()
@click.option(
    "--config",
    default="./ros/husky_mission_planner/husky_mission_planner/config/husky01.yaml",
    help="YAML config file",
)
def main(config: str):
    try:
        # Initialize ROS Client Libraries (RCL) for Python:
        rclpy.init()
        mp: MissionPlanner = None

        with open(config, "r") as file:
            config_yaml: yaml.Node = yaml.safe_load(file)

        try:
            # configure logger
            logging.basicConfig(level=logging._nameToLevel[config_yaml["logging"]])
            logger: logging.Logger = logging.getLogger()

            mp = MissionPlanner(
                logger,
                config_yaml["node_name"],
                config_yaml["schema"],
                config_yaml["farm_layout"],
                config_yaml["log_directory"],
                config_yaml["host"],
                config_yaml["port"],
            )
        except yaml.YAMLError as exc:
            logger.error(f"Improper YAML config: {exc}")

        try:
            rclpy.spin(mp)
        except SystemExit:
            logger.info("Graceful exit and receipt of MissionPlan...")

    except KeyboardInterrupt:
        logger.info('Ctrl+C received - exiting...')
        sys.exit(0)
    finally:
        logger.info('ROS MissionPlanner node shutdown...')
        if mp is not None:
            mp.destroy_node()

if __name__ == "__main__":
    main()
