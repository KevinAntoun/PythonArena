"""Python Arena server entry point."""

import argparse
import socket

from server.client_handler import ClientHandler
from server.lobby import Lobby


def serve(port: int) -> None:
    lobby = Lobby()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind(("", port))
        server_sock.listen(10)
        actual_port = server_sock.getsockname()[1]
        print(f"[SERVER] Listening on port {actual_port}", flush=True)

        while True:
            conn, addr = server_sock.accept()
            print(f"[SERVER] New connection from {addr}", flush=True)
            ClientHandler(conn, addr, lobby).start()


def main() -> None:
    parser = argparse.ArgumentParser(description="Python Arena Server")
    parser.add_argument("port", type=int, help="Port to listen on")
    args = parser.parse_args()
    serve(args.port)


if __name__ == "__main__":
    main()
