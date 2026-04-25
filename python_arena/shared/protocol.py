"""Length-prefixed JSON message framing for TCP sockets."""

import json
import socket

from shared.constants import ENCODING, HEADER_LEN


def encode_msg(msg: dict) -> bytes:
    """Serialize a dictionary into length-prefixed JSON bytes."""
    payload = json.dumps(msg).encode(ENCODING)
    header = str(len(payload)).zfill(HEADER_LEN).encode(ENCODING)
    return header + payload


def decode_msg(payload: bytes) -> dict:
    """Deserialize JSON payload bytes into a dictionary."""
    return json.loads(payload.decode(ENCODING))


def send_msg(sock: socket.socket, msg: dict) -> None:
    """Send a complete framed message."""
    sock.sendall(encode_msg(msg))


def recv_msg(sock: socket.socket) -> dict | None:
    """Receive one complete framed message.

    Returns None when the peer closes before sending a new message. Raises
    ConnectionError if the peer disconnects in the middle of a frame.
    """
    header = _recv_exactly(sock, HEADER_LEN)
    if header is None:
        return None

    try:
        length = int(header.decode(ENCODING))
    except ValueError as exc:
        raise ValueError(f"Invalid message header: {header!r}") from exc

    payload = _recv_exactly(sock, length)
    if payload is None:
        raise ConnectionError("Connection closed mid-message")
    return decode_msg(payload)


def _recv_exactly(sock: socket.socket, n: int) -> bytes | None:
    """Read exactly n bytes, or None if closed before the first byte."""
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            if not buf:
                return None
            raise ConnectionError("Partial read")
        buf += chunk
    return buf
