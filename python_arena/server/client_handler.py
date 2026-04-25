"""Thread-per-client server connection handler."""

import threading

from shared.constants import (
    C_CHALLENGE,
    C_CHALLENGE_RESP,
    C_CHAT,
    C_CONNECT,
    C_DISCONNECT,
    C_MOVE,
    C_WATCH,
    DIR_DOWN,
    DIR_LEFT,
    DIR_RIGHT,
    DIR_UP,
    S_CHALLENGE,
    S_CHALLENGE_ACK,
    S_CHAT,
    S_CONNECT_ACK,
    S_ERROR,
    S_PLAYER_JOINED,
    S_PLAYER_LEFT,
    S_PLAYER_LIST,
    S_WATCH_ACK,
)
from shared.protocol import recv_msg, send_msg
from server.game_session import GameSession

VALID_DIRECTIONS = {DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT}


class ClientHandler(threading.Thread):
    def __init__(self, sock, addr, lobby):
        super().__init__(daemon=True)
        self.sock = sock
        self.addr = addr
        self.lobby = lobby
        self.username = None
        self.snake_color = "green"
        self._send_lock = threading.Lock()
        self._registered = False

    def send(self, msg: dict) -> None:
        with self._send_lock:
            send_msg(self.sock, msg)

    def run(self) -> None:
        try:
            if self._handshake():
                self._main_loop()
        except (ConnectionError, OSError):
            pass
        finally:
            self._cleanup()

    def _handshake(self) -> bool:
        msg = recv_msg(self.sock)
        if not msg or msg.get("type") != C_CONNECT:
            return False

        username = str(msg.get("username", "")).strip()
        snake_color = str(msg.get("color", "green")).strip() or "green"

        if not username:
            self.send(
                {
                    "type": S_CONNECT_ACK,
                    "status": "error",
                    "reason": "Username cannot be empty.",
                }
            )
            return False

        if not self.lobby.register(username, self):
            self.send(
                {
                    "type": S_CONNECT_ACK,
                    "status": "error",
                    "reason": f'Username "{username}" is already taken.',
                }
            )
            return False

        self.username = username
        self.snake_color = snake_color
        self._registered = True
        self.send({"type": S_CONNECT_ACK, "status": "ok", "username": username})
        self.lobby.broadcast(
            {"type": S_PLAYER_JOINED, "username": username},
            exclude={username},
        )
        self.send({"type": S_PLAYER_LIST, **self.lobby.player_list_payload()})
        return True

    def _main_loop(self) -> None:
        while True:
            msg = recv_msg(self.sock)
            if msg is None:
                break
            self._dispatch(msg)

    def _dispatch(self, msg: dict) -> None:
        msg_type = msg.get("type")

        if msg_type == C_MOVE:
            self._handle_move(msg)
        elif msg_type == C_CHALLENGE:
            self._handle_challenge(msg)
        elif msg_type == C_CHALLENGE_RESP:
            self._handle_challenge_response(msg)
        elif msg_type == C_WATCH:
            self._handle_watch()
        elif msg_type == C_CHAT:
            self._handle_chat(msg)
        elif msg_type == C_DISCONNECT:
            raise ConnectionError("Client disconnected gracefully")
        else:
            self.send({"type": S_ERROR, "reason": "Unknown message type."})

    def _handle_move(self, msg: dict) -> None:
        direction = msg.get("direction", "")
        if direction not in VALID_DIRECTIONS:
            return
        game = self.lobby.get_game()
        if game:
            game.submit_move(self.username, direction)

    def _handle_challenge(self, msg: dict) -> None:
        target_name = msg.get("target")
        if target_name == self.username:
            self.send({"type": S_ERROR, "reason": "You cannot challenge yourself."})
            return

        target = self.lobby.get_handler(target_name)
        if target is None:
            self.send({"type": S_ERROR, "reason": "Player not found."})
            return
        if self.lobby.get_game() is not None:
            self.send({"type": S_ERROR, "reason": "A game is already in progress."})
            return
        target.send({"type": S_CHALLENGE, "from": self.username})

    def _handle_challenge_response(self, msg: dict) -> None:
        accepted = bool(msg.get("accepted", False))
        challenger = self.lobby.get_handler(msg.get("from"))
        if challenger is None:
            self.send({"type": S_ERROR, "reason": "Challenger is no longer online."})
            return

        if not accepted:
            challenger.send(
                {"type": S_CHALLENGE_ACK, "accepted": False, "from": self.username}
            )
            return

        if self.lobby.get_game() is not None:
            self.send({"type": S_ERROR, "reason": "A game is already in progress."})
            challenger.send({"type": S_ERROR, "reason": "A game is already in progress."})
            return

        self._start_game(challenger, self)

    def _handle_watch(self) -> None:
        game = self.lobby.get_game()
        if game is None:
            self.send({"type": S_ERROR, "reason": "No game in progress."})
            return
        game.add_viewer(self)
        self.send({"type": S_WATCH_ACK, "state": game.state.to_dict()})

    def _handle_chat(self, msg: dict) -> None:
        content = str(msg.get("message", ""))
        if not content:
            return

        target_name = msg.get("to")
        if target_name:
            target = self.lobby.get_handler(target_name)
            if target:
                target.send(
                    {"type": S_CHAT, "from": self.username, "message": content}
                )
            return

        game = self.lobby.get_game()
        if game:
            for handler in game._handlers():
                if handler is not self:
                    try:
                        handler.send(
                            {"type": S_CHAT, "from": self.username, "message": content}
                        )
                    except Exception:
                        pass
        else:
            self.lobby.broadcast(
                {"type": S_CHAT, "from": self.username, "message": content},
                exclude={self.username},
            )

    def _start_game(self, p1, p2) -> None:
        game = GameSession(p1, p2, self.lobby)
        self.lobby.set_game(game)
        self.lobby.broadcast({"type": S_PLAYER_LIST, **self.lobby.player_list_payload()})
        p1.send({"type": S_CHALLENGE_ACK, "accepted": True, "from": p2.username})
        p2.send({"type": S_CHALLENGE_ACK, "accepted": True, "from": p1.username})
        game.start()

    def _cleanup(self) -> None:
        game = self.lobby.get_game()
        if game and self._registered and self.username:
            game.remove_viewer(self)
            if self.username in (game.p1.username, game.p2.username):
                game.handle_player_disconnect(self.username)

        if self._registered and self.username:
            self.lobby.unregister(self.username)
            self.lobby.broadcast({"type": S_PLAYER_LEFT, "username": self.username})
            self.lobby.broadcast({"type": S_PLAYER_LIST, **self.lobby.player_list_payload()})

        try:
            self.sock.close()
        except OSError:
            pass
