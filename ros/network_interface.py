import socket
import logging
import tempfile
import os


class NetworkInterface:
    def __init__(self, logger: logging.Logger, log_directory: str, host="0.0.0.0", port=12345):
        self.logger: logging.Logger = logger
        self.log_directory: str = log_directory
        # setting up server to listen
        self.host: str = host
        self.port: int = port
        self.max_rcv_bytes: int = 1024
        # Current mission file
        self.current_mission_file: str = None

        self.server_socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(1)
        self.logger.debug(f"Server listening on {self.host}:{self.port}")

        # creating logging directory
        os.makedirs(self.log_directory, exist_ok=True)

    def receive_file(self) -> str:
        self.logger.debug(f"Waiting for client to connect to port {self.port}...")
        self.server_socket, addr = self.server_socket.accept()
        self.logger.debug(f"Connection from {addr}")

        with tempfile.NamedTemporaryFile(dir=self.log_directory, delete=False, mode="wb") as temp_file:
            self.current_mission_file = temp_file.name
            while True:
                chunk = self.server_socket.recv(self.max_rcv_bytes)
                if not chunk:
                    break
                temp_file.write(chunk)

        self.logger.debug("File received successfully.")
        # receive one message at a time
        self.close_socket()

        return self.current_mission_file

    def send_acknowledgement(self):
        pass

    def close_socket(self):
        self.server_socket.close()
