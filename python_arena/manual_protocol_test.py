"""Manual loopback test for the shared protocol framing.

Run from this directory:
    python manual_protocol_test.py
"""

import socket
import threading

from shared.protocol import recv_msg, send_msg


def main() -> None:
    expected = {
        "type": "TEST",
        "username": "alice",
        "numbers": list(range(20)),
        "nested": {"message": "hello over loopback"},
    }
    received = {}

    server_ready = threading.Event()

    def server() -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            received["addr"] = listener.getsockname()
            server_ready.set()

            conn, _addr = listener.accept()
            with conn:
                received["message"] = recv_msg(conn)
                send_msg(conn, {"type": "ACK", "ok": True})

    thread = threading.Thread(target=server, daemon=True)
    thread.start()
    server_ready.wait(timeout=5)

    with socket.create_connection(received["addr"], timeout=5) as client:
        send_msg(client, expected)
        ack = recv_msg(client)

    thread.join(timeout=5)

    assert received["message"] == expected, received["message"]
    assert ack == {"type": "ACK", "ok": True}, ack
    print("Protocol loopback test passed.")


if __name__ == "__main__":
    main()
