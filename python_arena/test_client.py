"""Throwaway framed-protocol client for manual server testing.

Run while the server is listening:
    python test_client.py 127.0.0.1 5555 alice green
"""

import argparse
import socket

from shared.constants import C_CONNECT
from shared.protocol import recv_msg, send_msg


def main() -> None:
    parser = argparse.ArgumentParser(description="Python Arena handshake test client")
    parser.add_argument("host")
    parser.add_argument("port", type=int)
    parser.add_argument("username")
    parser.add_argument("color", nargs="?", default="green")
    args = parser.parse_args()

    with socket.create_connection((args.host, args.port), timeout=5) as sock:
        send_msg(
            sock,
            {
                "type": C_CONNECT,
                "username": args.username,
                "color": args.color,
            },
        )
        print(recv_msg(sock))
        print(recv_msg(sock))


if __name__ == "__main__":
    main()
