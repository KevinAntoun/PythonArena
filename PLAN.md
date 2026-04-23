# Πthon Arena — Agent Implementation Plan
## EECE 350 Network Programming Project

> **READ THIS ENTIRE FILE BEFORE WRITING A SINGLE LINE OF CODE.**
> Follow each phase in order. Never skip ahead. Mark tasks `[x]` as you complete them.

---

## 0. Environment & Repository Setup

### 0.1 Dependencies
```
Python 3.11+
pygame==2.5.2
```
No other third-party packages. All networking uses the Python standard library (`socket`, `threading`, `json`, `queue`, `time`, `sys`, `argparse`).

### 0.2 Project Structure (create this tree first)
```
python_arena/
├── shared/
│   ├── __init__.py
│   ├── constants.py        # Grid size, tick rate, health values, colors, message types
│   └── protocol.py         # encode_msg() / decode_msg() — single source of truth for framing
├── server/
│   ├── __init__.py
│   ├── server.py           # Entry point: python -m server.server <port>
│   ├── client_handler.py   # One thread per connected client
│   ├── lobby.py            # Username registry, online-player list, matchmaking
│   ├── game_session.py     # Game loop, state machine, tick engine
│   ├── game_logic.py       # Snake movement, collision, pie spawning, scoring
│   └── game_state.py       # Pure dataclass: no I/O, fully serialisable to dict
├── client/
│   ├── __init__.py
│   ├── client.py           # Entry point: python -m client.client
│   ├── network.py          # Recv thread → inbound Queue; send helper
│   ├── screens/
│   │   ├── __init__.py
│   │   ├── connect_screen.py   # IP / port entry form
│   │   ├── username_screen.py  # Username prompt
│   │   ├── lobby_screen.py     # Player list, challenge / watch buttons
│   │   ├── customize_screen.py # Snake colour + key-binding chooser
│   │   ├── waiting_screen.py   # "Waiting for opponent…"
│   │   ├── game_screen.py      # Main gameplay renderer
│   │   └── result_screen.py    # Winner banner, final scores
│   └── assets/
│       └── fonts/              # (optional) place any .ttf here
└── README.md
```

### 0.3 Virtual Environment
```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install pygame==2.5.2
```

---

## 1. Shared Layer (`shared/`)

### 1.1 `shared/constants.py`
Define **every** magic number here. The rest of the code imports from this file.

```python
# Grid & display
GRID_COLS        = 30
GRID_ROWS        = 25
CELL_SIZE        = 24          # pixels per cell
HUD_HEIGHT       = 60          # pixels above the grid for scores / timer
WINDOW_W         = GRID_COLS * CELL_SIZE          # 720
WINDOW_H         = GRID_ROWS * CELL_SIZE + HUD_HEIGHT  # 660

# Gameplay
INITIAL_HEALTH   = 100
MAX_HEALTH       = 150
GAME_DURATION    = 180         # seconds
TICK_RATE        = 10          # server game-loop iterations per second
SNAKE_INIT_LEN   = 3

# Pie types  {type_id: (label, health_delta, color)}
PIE_TYPES = {
    "regular":  ("🥧 Pie",     +10, (255, 200,  80)),
    "golden":   ("🌟 Golden",  +25, (255, 215,   0)),
    "poison":   ("☠  Poison",  -15, ( 80, 200,  80)),
}
MAX_PIES         = 5           # max pies on board simultaneously

# Obstacle types {type_id: health_delta}
OBSTACLE_TYPES = {
    "rock":  -10,
    "spike": -20,
}
NUM_OBSTACLES    = 8

# Collision penalties
WALL_HIT_DMG       = 15
SNAKE_HIT_DMG      = 20
OBSTACLE_HIT_DMG   = None      # use OBSTACLE_TYPES value

# Network framing
HEADER_LEN   = 8               # bytes — zero-padded decimal length of JSON payload
ENCODING     = "utf-8"
BUFFER_SIZE  = 4096

# Message types (client → server)
C_CONNECT        = "C_CONNECT"
C_MOVE           = "C_MOVE"
C_CHALLENGE      = "C_CHALLENGE"
C_CHALLENGE_RESP = "C_CHALLENGE_RESP"
C_WATCH          = "C_WATCH"
C_CHAT           = "C_CHAT"
C_DISCONNECT     = "C_DISCONNECT"

# Message types (server → client)
S_CONNECT_ACK    = "S_CONNECT_ACK"
S_PLAYER_LIST    = "S_PLAYER_LIST"
S_CHALLENGE      = "S_CHALLENGE"
S_CHALLENGE_ACK  = "S_CHALLENGE_ACK"
S_GAME_START     = "S_GAME_START"
S_GAME_STATE     = "S_GAME_STATE"
S_GAME_END       = "S_GAME_END"
S_CHAT           = "S_CHAT"
S_ERROR          = "S_ERROR"
S_WATCH_ACK      = "S_WATCH_ACK"
S_PLAYER_JOINED  = "S_PLAYER_JOINED"
S_PLAYER_LEFT    = "S_PLAYER_LEFT"

# Directions
DIR_UP    = "UP"
DIR_DOWN  = "DOWN"
DIR_LEFT  = "LEFT"
DIR_RIGHT = "RIGHT"
OPPOSITE  = {DIR_UP: DIR_DOWN, DIR_DOWN: DIR_UP,
             DIR_LEFT: DIR_RIGHT, DIR_RIGHT: DIR_LEFT}

# Colors (RGB)
COLOR_BG         = ( 20,  20,  20)
COLOR_GRID       = ( 35,  35,  35)
COLOR_HUD        = ( 10,  10,  10)
COLOR_SNAKE_P1   = ( 50, 200,  50)
COLOR_SNAKE_P2   = ( 50, 100, 220)
COLOR_OBSTACLE   = (130,  80,  40)
COLOR_SPIKE      = (200,  50,  50)
COLOR_TEXT       = (230, 230, 230)
COLOR_HP_BAR_OK  = ( 50, 200,  50)
COLOR_HP_BAR_LOW = (220,  80,  50)
COLOR_CHAT_BG    = (  0,   0,   0, 160)  # alpha for surface
```

### 1.2 `shared/protocol.py`
Use **length-prefixed framing** so messages never split or merge across TCP packets.

```python
import json
import socket
from shared.constants import HEADER_LEN, ENCODING

def encode_msg(msg: dict) -> bytes:
    """Serialize dict → length-prefixed bytes."""
    payload = json.dumps(msg).encode(ENCODING)
    header  = str(len(payload)).zfill(HEADER_LEN).encode(ENCODING)
    return header + payload

def send_msg(sock: socket.socket, msg: dict) -> None:
    """Send a complete framed message."""
    sock.sendall(encode_msg(msg))

def recv_msg(sock: socket.socket) -> dict | None:
    """
    Block until one complete message arrives.
    Returns None if the connection was closed cleanly.
    Raises ConnectionError on unexpected disconnect.
    """
    header = _recv_exactly(sock, HEADER_LEN)
    if header is None:
        return None
    length = int(header.decode(ENCODING))
    payload = _recv_exactly(sock, length)
    if payload is None:
        raise ConnectionError("Connection closed mid-message")
    return json.loads(payload.decode(ENCODING))

def _recv_exactly(sock: socket.socket, n: int) -> bytes | None:
    """Read exactly n bytes. Returns None if socket closed before first byte."""
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None if not buf else (_ for _ in ()).throw(
                ConnectionError("Partial read"))
        buf += chunk
    return buf
```

> **Why length-prefix?** TCP is a stream protocol. `recv()` does not guarantee you get exactly one JSON object per call. The header tells the receiver how many bytes to read before attempting `json.loads`. This is the single most important design decision for correctness.

---

## 2. Server Layer (`server/`)

### 2.1 `server/game_state.py` — Pure Data, Zero I/O

```python
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

@dataclass
class SnakeState:
    username: str
    body: List[Tuple[int, int]]   # [(col, row), ...] head first
    direction: str
    health: int
    alive: bool = True
    color: str = "green"          # chosen during customise screen
    score: int = 0                # pies collected

@dataclass
class PieItem:
    id: str                       # uuid4 short string
    col: int
    row: int
    pie_type: str                 # key in PIE_TYPES

@dataclass
class Obstacle:
    col: int
    row: int
    obs_type: str                 # key in OBSTACLE_TYPES

@dataclass
class GameState:
    snakes: Dict[str, SnakeState] = field(default_factory=dict)
    pies:   List[PieItem]         = field(default_factory=list)
    obstacles: List[Obstacle]     = field(default_factory=list)
    time_left: float              = 180.0
    tick: int                     = 0

    def to_dict(self) -> dict:
        """Serialise to plain dict for JSON transmission."""
        return {
            "snakes": {
                u: {
                    "body":      s.body,
                    "direction": s.direction,
                    "health":    s.health,
                    "alive":     s.alive,
                    "color":     s.color,
                    "score":     s.score,
                }
                for u, s in self.snakes.items()
            },
            "pies": [
                {"id": p.id, "col": p.col, "row": p.row, "type": p.pie_type}
                for p in self.pies
            ],
            "obstacles": [
                {"col": o.col, "row": o.row, "type": o.obs_type}
                for o in self.obstacles
            ],
            "time_left": round(self.time_left, 1),
            "tick":      self.tick,
        }
```

### 2.2 `server/game_logic.py` — Pure Functions, No Sockets

```python
"""
All game-logic functions are PURE (no side effects, no I/O).
They take a GameState, return a new/mutated GameState.
"""
import random, uuid
from shared.constants import *
from server.game_state import GameState, SnakeState, PieItem, Obstacle

DIRECTION_DELTA = {
    DIR_UP:    (0, -1),
    DIR_DOWN:  (0, +1),
    DIR_LEFT:  (-1, 0),
    DIR_RIGHT: (+1, 0),
}

def occupied_cells(state: GameState) -> set:
    cells = set()
    for s in state.snakes.values():
        cells.update(s.body)
    cells.update((o.col, o.row) for o in state.obstacles)
    cells.update((p.col, p.row) for p in state.pies)
    return cells

def random_free_cell(state: GameState) -> tuple:
    occupied = occupied_cells(state)
    all_cells = {(c, r) for c in range(GRID_COLS) for r in range(GRID_ROWS)}
    free = list(all_cells - occupied)
    return random.choice(free)

def spawn_pies(state: GameState) -> None:
    while len(state.pies) < MAX_PIES:
        col, row = random_free_cell(state)
        pie_type  = random.choice(list(PIE_TYPES.keys()))
        state.pies.append(PieItem(id=uuid.uuid4().hex[:8], col=col, row=row, pie_type=pie_type))

def place_obstacles(state: GameState) -> None:
    """Called once at game start."""
    for _ in range(NUM_OBSTACLES):
        col, row = random_free_cell(state)
        obs_type  = random.choice(list(OBSTACLE_TYPES.keys()))
        state.obstacles.append(Obstacle(col=col, row=row, obs_type=obs_type))

def advance_snake(snake: SnakeState, new_dir: str) -> None:
    """Move snake one step in new_dir (rejects 180° reversal)."""
    if new_dir and OPPOSITE.get(snake.direction) != new_dir:
        snake.direction = new_dir
    dc, dr = DIRECTION_DELTA[snake.direction]
    new_head = (snake.body[0][0] + dc, snake.body[0][1] + dr)
    snake.body.insert(0, new_head)
    snake.body.pop()          # remove tail (grows only on pie eat)

def check_collisions(state: GameState) -> None:
    """Mutate health / alive flags based on collisions."""
    all_bodies = {u: set(s.body[1:]) for u, s in state.snakes.items()}  # exclude own head

    for username, snake in state.snakes.items():
        if not snake.alive:
            continue
        hc, hr = snake.body[0]

        # Wall collision
        if not (0 <= hc < GRID_COLS and 0 <= hr < GRID_ROWS):
            snake.health -= WALL_HIT_DMG
            # Respawn head inside grid
            snake.body[0] = (max(0, min(hc, GRID_COLS - 1)),
                             max(0, min(hr, GRID_ROWS - 1)))

        # Obstacle collision
        for obs in state.obstacles:
            if (obs.col, obs.row) == (hc, hr):
                snake.health += OBSTACLE_TYPES[obs.obs_type]  # negative value

        # Snake-body collision (self or other)
        for other_u, body_set in all_bodies.items():
            if (hc, hr) in body_set:
                snake.health -= SNAKE_HIT_DMG

        # Pie collection
        for pie in list(state.pies):
            if (pie.col, pie.row) == (hc, hr):
                delta = PIE_TYPES[pie.pie_type][1]
                snake.health = min(MAX_HEALTH, snake.health + delta)
                snake.score += 1
                # Grow snake body
                snake.body.append(snake.body[-1])
                state.pies.remove(pie)

        # Clamp health
        snake.health = max(0, snake.health)
        if snake.health == 0:
            snake.alive = False

def tick(state: GameState, pending_moves: dict, dt: float) -> None:
    """
    One server tick.
    pending_moves: {username: direction_str}
    dt: seconds since last tick
    """
    state.time_left = max(0.0, state.time_left - dt)
    state.tick += 1
    for username, snake in state.snakes.items():
        if snake.alive:
            advance_snake(snake, pending_moves.get(username, ""))
    check_collisions(state)
    spawn_pies(state)

def is_game_over(state: GameState) -> bool:
    alive = [s for s in state.snakes.values() if s.alive]
    return len(alive) <= 1 or state.time_left <= 0

def determine_winner(state: GameState) -> str | None:
    """Returns username of winner, or None for a draw."""
    best = max(state.snakes.values(), key=lambda s: (s.alive, s.health))
    others = [s for u, s in state.snakes.items() if s is not best]
    if others and others[0].health == best.health and others[0].alive == best.alive:
        return None   # draw
    return best.username
```

### 2.3 `server/lobby.py` — Connection Registry

```python
import threading
from typing import Dict, Optional

class Lobby:
    """Thread-safe registry of connected clients."""

    def __init__(self):
        self._lock    = threading.Lock()
        self._clients: Dict[str, "ClientHandler"] = {}  # username → handler
        self._game    = None   # reference to active GameSession, or None

    # --- Username management ---

    def register(self, username: str, handler) -> bool:
        with self._lock:
            if username in self._clients:
                return False
            self._clients[username] = handler
            return True

    def unregister(self, username: str) -> None:
        with self._lock:
            self._clients.pop(username, None)

    def online_players(self) -> list[str]:
        with self._lock:
            return list(self._clients.keys())

    def get_handler(self, username: str):
        with self._lock:
            return self._clients.get(username)

    # --- Game session ---

    def set_game(self, game) -> None:
        with self._lock:
            self._game = game

    def get_game(self):
        with self._lock:
            return self._game

    def clear_game(self) -> None:
        with self._lock:
            self._game = None

    # --- Broadcast ---

    def broadcast(self, msg: dict, exclude: set = None) -> None:
        exclude = exclude or set()
        with self._lock:
            targets = dict(self._clients)
        for uname, handler in targets.items():
            if uname not in exclude:
                try:
                    handler.send(msg)
                except Exception:
                    pass
```

### 2.4 `server/game_session.py` — Game Loop

```python
import threading, time
from shared.constants import *
from shared.protocol import send_msg
from server.game_state import GameState, SnakeState
from server.game_logic import place_obstacles, spawn_pies, tick, is_game_over, determine_winner

class GameSession(threading.Thread):
    """
    Runs in its own thread.
    Ticks at TICK_RATE Hz, broadcasts S_GAME_STATE after each tick.
    """

    def __init__(self, player1_handler, player2_handler, lobby):
        super().__init__(daemon=True)
        self.p1      = player1_handler
        self.p2      = player2_handler
        self.lobby   = lobby
        self.state   = GameState()
        self._moves  = {}          # {username: latest_direction}
        self._lock   = threading.Lock()
        self._stop   = threading.Event()
        self.viewers = []          # list of ClientHandler watching

    def submit_move(self, username: str, direction: str) -> None:
        with self._lock:
            self._moves[username] = direction

    def add_viewer(self, handler) -> None:
        self.viewers.append(handler)

    def _init_state(self) -> None:
        # Place snakes at opposite corners
        p1_start = [(2, 2), (1, 2), (0, 2)]
        p2_start = [(GRID_COLS-3, GRID_ROWS-3),
                    (GRID_COLS-2, GRID_ROWS-3),
                    (GRID_COLS-1, GRID_ROWS-3)]

        self.state.snakes[self.p1.username] = SnakeState(
            username=self.p1.username,
            body=p1_start,
            direction=DIR_RIGHT,
            health=INITIAL_HEALTH,
            color=self.p1.snake_color,
        )
        self.state.snakes[self.p2.username] = SnakeState(
            username=self.p2.username,
            body=p2_start,
            direction=DIR_LEFT,
            health=INITIAL_HEALTH,
            color=self.p2.snake_color,
        )
        place_obstacles(self.state)
        spawn_pies(self.state)

    def _broadcast_state(self) -> None:
        msg = {
            "type":  S_GAME_STATE,
            "state": self.state.to_dict(),
        }
        for handler in [self.p1, self.p2] + self.viewers:
            try:
                handler.send(msg)
            except Exception:
                pass

    def run(self) -> None:
        self._init_state()

        # Notify players game has started
        for handler in [self.p1, self.p2]:
            handler.send({
                "type":       S_GAME_START,
                "your_snake": handler.username,
                "opponent":   (self.p2 if handler is self.p1 else self.p1).username,
                "state":      self.state.to_dict(),
            })

        interval = 1.0 / TICK_RATE
        last     = time.monotonic()

        while not self._stop.is_set():
            now = time.monotonic()
            dt  = now - last
            last = now

            with self._lock:
                moves = dict(self._moves)
                self._moves.clear()

            tick(self.state, moves, dt)
            self._broadcast_state()

            if is_game_over(self.state):
                break

            elapsed = time.monotonic() - now
            sleep_t = interval - elapsed
            if sleep_t > 0:
                time.sleep(sleep_t)

        # Game over
        winner = determine_winner(self.state)
        end_msg = {
            "type":   S_GAME_END,
            "winner": winner,
            "state":  self.state.to_dict(),
        }
        for handler in [self.p1, self.p2] + self.viewers:
            try:
                handler.send(end_msg)
            except Exception:
                pass

        self.lobby.clear_game()

    def stop(self) -> None:
        self._stop.set()
```

### 2.5 `server/client_handler.py` — One Thread Per Client

```python
import threading
from shared.constants import *
from shared.protocol import recv_msg, send_msg
from server.game_session import GameSession

class ClientHandler(threading.Thread):

    def __init__(self, sock, addr, lobby):
        super().__init__(daemon=True)
        self.sock        = sock
        self.addr        = addr
        self.lobby       = lobby
        self.username    = None
        self.snake_color = "green"
        self._send_lock  = threading.Lock()

    def send(self, msg: dict) -> None:
        with self._send_lock:
            send_msg(self.sock, msg)

    def run(self) -> None:
        try:
            self._handshake()
            self._main_loop()
        except (ConnectionError, OSError):
            pass
        finally:
            self._cleanup()

    def _handshake(self) -> None:
        msg = recv_msg(self.sock)
        if not msg or msg.get("type") != C_CONNECT:
            self.sock.close()
            return

        username     = msg.get("username", "").strip()
        snake_color  = msg.get("color", "green")

        if not username:
            self.send({"type": S_CONNECT_ACK, "status": "error",
                       "reason": "Username cannot be empty."})
            self.sock.close()
            return

        if not self.lobby.register(username, self):
            self.send({"type": S_CONNECT_ACK, "status": "error",
                       "reason": f'Username "{username}" is already taken.'})
            self.sock.close()
            return

        self.username    = username
        self.snake_color = snake_color
        self.send({"type": S_CONNECT_ACK, "status": "ok", "username": username})

        # Tell everyone else a new player joined
        self.lobby.broadcast(
            {"type": S_PLAYER_JOINED, "username": username},
            exclude={username}
        )
        # Send the newcomer the current player list
        self.send({"type": S_PLAYER_LIST, "players": self.lobby.online_players()})

    def _main_loop(self) -> None:
        while True:
            msg = recv_msg(self.sock)
            if msg is None:
                break
            self._dispatch(msg)

    def _dispatch(self, msg: dict) -> None:
        t = msg.get("type")

        if t == C_MOVE:
            game = self.lobby.get_game()
            if game:
                game.submit_move(self.username, msg.get("direction", ""))

        elif t == C_CHALLENGE:
            target_name = msg.get("target")
            target      = self.lobby.get_handler(target_name)
            if target is None:
                self.send({"type": S_ERROR, "reason": "Player not found."})
                return
            if self.lobby.get_game() is not None:
                self.send({"type": S_ERROR, "reason": "A game is already in progress."})
                return
            target.send({"type": S_CHALLENGE, "from": self.username})

        elif t == C_CHALLENGE_RESP:
            accepted     = msg.get("accepted", False)
            challenger   = self.lobby.get_handler(msg.get("from"))
            if not challenger:
                return
            if accepted:
                self._start_game(challenger, self)
            else:
                challenger.send({"type": S_CHALLENGE_ACK, "accepted": False,
                                 "from": self.username})

        elif t == C_WATCH:
            game = self.lobby.get_game()
            if game is None:
                self.send({"type": S_ERROR, "reason": "No game in progress."})
                return
            game.add_viewer(self)
            self.send({"type": S_WATCH_ACK, "state": game.state.to_dict()})

        elif t == C_CHAT:
            # Peer-to-peer relay: server forwards to target
            target_name = msg.get("to")
            content     = msg.get("message", "")
            if target_name:
                target = self.lobby.get_handler(target_name)
                if target:
                    target.send({"type": S_CHAT, "from": self.username,
                                 "message": content})
            else:
                # Broadcast chat to everyone in game (including viewers)
                self.lobby.broadcast(
                    {"type": S_CHAT, "from": self.username, "message": content},
                    exclude={self.username}
                )

        elif t == C_DISCONNECT:
            raise ConnectionError("Client disconnected gracefully")

    def _start_game(self, p1, p2) -> None:
        game = GameSession(p1, p2, self.lobby)
        self.lobby.set_game(game)
        p1.send({"type": S_CHALLENGE_ACK, "accepted": True, "from": p2.username})
        game.start()

    def _cleanup(self) -> None:
        if self.username:
            self.lobby.unregister(self.username)
            self.lobby.broadcast(
                {"type": S_PLAYER_LEFT, "username": self.username}
            )
        try:
            self.sock.close()
        except OSError:
            pass
```

### 2.6 `server/server.py` — Entry Point

```python
import socket, threading, argparse
from server.lobby import Lobby
from server.client_handler import ClientHandler

def main():
    parser = argparse.ArgumentParser(description="Πthon Arena Server")
    parser.add_argument("port", type=int, help="Port to listen on")
    args = parser.parse_args()

    lobby      = Lobby()
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("", args.port))
    server_sock.listen(10)
    print(f"[SERVER] Listening on port {args.port}")

    while True:
        conn, addr = server_sock.accept()
        print(f"[SERVER] New connection from {addr}")
        ClientHandler(conn, addr, lobby).start()

if __name__ == "__main__":
    main()
```

Run with:
```bash
python -m server.server 5555
```

---

## 3. Client Layer (`client/`)

### 3.1 `client/network.py` — Background Recv Thread

```python
import threading, socket, queue
from shared.protocol import recv_msg, send_msg

class NetworkManager:
    """
    Owns the socket.
    Recv runs in a daemon thread and pushes decoded dicts to inbound_q.
    Call send() from any thread safely.
    """

    def __init__(self):
        self.sock       = None
        self.inbound_q  = queue.Queue()
        self._send_lock = threading.Lock()
        self._connected = False

    def connect(self, host: str, port: int) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))
        self._connected = True
        t = threading.Thread(target=self._recv_loop, daemon=True)
        t.start()

    def send(self, msg: dict) -> None:
        with self._send_lock:
            send_msg(self.sock, msg)

    def _recv_loop(self) -> None:
        while self._connected:
            try:
                msg = recv_msg(self.sock)
                if msg is None:
                    break
                self.inbound_q.put(msg)
            except Exception:
                break
        self.inbound_q.put({"type": "_DISCONNECTED"})
        self._connected = False

    def disconnect(self) -> None:
        self._connected = False
        try:
            self.sock.close()
        except OSError:
            pass

    def poll(self) -> dict | None:
        """Non-blocking. Returns next message or None."""
        try:
            return self.inbound_q.get_nowait()
        except queue.Empty:
            return None
```

### 3.2 `client/screens/connect_screen.py`

Pygame screen with two text-input fields: **Server IP** and **Port**.

```
UI layout:
  ┌──────────────────────────────────┐
  │          Πthon Arena             │
  │                                  │
  │  Server IP:  [________________]  │
  │  Port:       [________________]  │
  │                                  │
  │           [ Connect ]            │
  │                                  │
  │  (error message in red if any)   │
  └──────────────────────────────────┘
```

**Implementation notes:**
- Maintain two string buffers, track `active_field` (0 or 1).
- Click on a box → set `active_field`.
- `KEYDOWN`: backspace deletes, printable chars append, Enter moves to next field or submits.
- On submit: call `net.connect(ip, int(port))`.
- Send `C_CONNECT` immediately after TCP connect (username not needed yet — wait for next screen).
- Return action `"connected"` to the screen manager.

### 3.3 `client/screens/username_screen.py`

Single text input + colour picker.

```
UI layout:
  ┌──────────────────────────────────┐
  │       Choose Your Identity       │
  │                                  │
  │  Username: [__________________]  │
  │                                  │
  │  Snake colour:                   │
  │  [●Green] [●Blue] [●Red] [●Cyan] │
  │                                  │
  │           [ Join! ]              │
  └──────────────────────────────────┘
```

**On submit:** send `C_CONNECT` `{type, username, color}`.
Wait for `S_CONNECT_ACK`. If `status == "error"` show reason in red. If `"ok"` proceed to lobby.

### 3.4 `client/screens/lobby_screen.py`

```
UI layout:
  ┌──────────────────────────────────┐
  │   Online Players          [You]  │
  │  ┌──────────────────────────┐   │
  │  │ alice              [Duel]│   │
  │  │ bob                [Duel]│   │
  │  │ charlie            [Duel]│   │
  │  └──────────────────────────┘   │
  │                                  │
  │  [ Watch ongoing game ]          │
  └──────────────────────────────────┘
```

**Implementation notes:**
- Poll `net.inbound_q` each frame for: `S_PLAYER_LIST`, `S_PLAYER_JOINED`, `S_PLAYER_LEFT`, `S_CHALLENGE`, `S_CHALLENGE_ACK`.
- Do not show own username in list.
- Clicking **Duel** sends `C_CHALLENGE {target: username}`.
- Incoming `S_CHALLENGE` → show popup "alice challenges you! [Accept] [Decline]".
- `S_CHALLENGE_ACK {accepted: true}` → transition to `customize_screen` (or straight to `waiting_screen` then `game_screen`).
- Clicking **Watch ongoing game** → send `C_WATCH`; wait for `S_WATCH_ACK` then transition to `game_screen` in viewer mode.

### 3.5 `client/screens/customize_screen.py`

Allows choosing keyboard keys for up/down/left/right. Show current binding and allow re-binding by clicking then pressing a key.

Store bindings as `{DIR_UP: pygame.K_w, ...}` in client state.

### 3.6 `client/screens/game_screen.py` — Main Renderer

This is the most complex screen. Render only — never modify state locally.

**Layout:**
```
 ┌─────────────────────────────────────────────────────┐
 │  [P1 name] ❤ ████░░░ 85hp    ⏱ 02:34    ❤ ████ 70hp [P2 name]  │  ← HUD
 ├─────────────────────────────────────────────────────┤
 │                                                     │
 │   (Grid of GRID_COLS × GRID_ROWS cells)             │
 │   Snakes, pies, obstacles rendered here             │
 │                                                     │
 ├─────────────────────────────────────────────────────┤
 │  Chat: [__________________________________] [Send]  │
 └─────────────────────────────────────────────────────┘
```

**Rendering pipeline (called every frame in event loop):**
```python
def draw(surface, state_dict, my_username, key_bindings):
    draw_background(surface)
    draw_grid(surface)
    draw_obstacles(surface, state_dict["obstacles"])
    draw_pies(surface, state_dict["pies"])
    draw_snakes(surface, state_dict["snakes"])
    draw_hud(surface, state_dict)
    draw_chat_panel(surface, chat_log)
```

**Key handling:**
- `KEYDOWN` event → check against `key_bindings` dict → call `net.send({type: C_MOVE, direction: ...})`.

**Chat:**
- Text input field at the bottom. Enter sends `C_CHAT {to: opponent_username, message: ...}`.
- Incoming `S_CHAT` → append to `chat_log` list (max 8 visible).

**Viewer mode:** identical renderer, no key input sent. Show "👀 Watching" badge in HUD.

### 3.7 `client/screens/result_screen.py`

Show winner banner, final health bars, pie scores. "Return to Lobby" button → transition back to `lobby_screen`.

### 3.8 `client/client.py` — Main Entry Point & Screen Manager

```python
import pygame, sys
from shared.constants import WINDOW_W, WINDOW_H
from client.network import NetworkManager
from client.screens.connect_screen    import ConnectScreen
from client.screens.username_screen   import UsernameScreen
from client.screens.lobby_screen      import LobbyScreen
from client.screens.customize_screen  import CustomizeScreen
from client.screens.game_screen       import GameScreen
from client.screens.result_screen     import ResultScreen

FPS = 60

def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption("Πthon Arena")
    clock  = pygame.time.Clock()
    net    = NetworkManager()

    screens = {
        "connect":   ConnectScreen(net),
        "username":  UsernameScreen(net),
        "lobby":     LobbyScreen(net),
        "customize": CustomizeScreen(net),
        "game":      GameScreen(net),
        "result":    ResultScreen(net),
    }

    current = "connect"

    while True:
        events = pygame.event.get()
        for e in events:
            if e.type == pygame.QUIT:
                net.disconnect()
                pygame.quit()
                sys.exit()

        action = screens[current].update(events)
        screens[current].draw(screen)

        if action:
            # action is a tuple: ("transition", "next_screen_name", optional_data)
            if action[0] == "transition":
                next_name = action[1]
                data      = action[2] if len(action) > 2 else None
                if data:
                    screens[next_name].on_enter(data)
                current = next_name

        pygame.display.flip()
        clock.tick(FPS)

if __name__ == "__main__":
    main()
```

**Screen interface contract** — every screen class must implement:
```python
class BaseScreen:
    def __init__(self, net: NetworkManager): ...
    def on_enter(self, data: dict = None): ...   # called when transitioning in
    def update(self, events: list) -> tuple|None: ...  # returns action or None
    def draw(self, surface: pygame.Surface): ...
```

---

## 4. Advanced Features

### 4.1 Text Chat (Peer-to-Peer)
- Already scaffolded in `C_CHAT` / `S_CHAT` above.
- The server acts as a relay — messages are not stored.
- In `game_screen.py`, add a `chat_input` buffer at the bottom.
- Limit chat history to 8 messages, each auto-expires after 10 seconds.

### 4.2 Fans (Viewers)
- Already scaffolded in `C_WATCH` / `S_WATCH_ACK` and `game_session.py`.
- Viewers receive all `S_GAME_STATE` broadcasts.
- In `lobby_screen.py`, show `[Watch]` button only when a game is in progress (track via `S_PLAYER_JOINED` / game-start notification).
- In `game_screen.py`, detect viewer mode (`is_viewer` flag) → disable keyboard input, show watching badge.
- Fans can also send fan chat: `C_CHAT {to: None, message: ...}` (broadcast mode).

### 4.3 Creative Feature — **Power-Up Shield**
Implement a temporary **Shield** power-up:
- A special pie type `"shield"` (golden colour with a ⚔ symbol) spawns randomly.
- Collecting it sets `snake.shielded = True` for 5 seconds (tracked as `shield_ticks` countdown).
- While shielded: wall/snake collisions deal 0 damage.
- Visual: animated blinking border around the snake head on client.
- Server changes: add `shielded: bool` and `shield_ticks: int` to `SnakeState`, decrement in `tick()`.
- Client changes: render shield aura (draw a slightly larger rect behind the head cell with alpha).

---

## 5. Step-by-Step Implementation Order

Follow this exact sequence. Each step should produce working, testable code.

### Phase A — Skeleton & Protocol (no Pygame yet)
- [ ] A1. Create full directory tree and all `__init__.py` files.
- [ ] A2. Implement `shared/constants.py` (all constants, no imports).
- [ ] A3. Implement `shared/protocol.py` (`encode_msg`, `send_msg`, `recv_msg`).
- [ ] A4. Write a manual test: open two Python REPLs, send a dict through a loopback socket, verify it arrives intact.

### Phase B — Server Core
- [ ] B1. Implement `server/game_state.py` (dataclasses + `to_dict`).
- [ ] B2. Implement `server/game_logic.py` (pure functions).
- [ ] B3. Unit-test `game_logic.py` in isolation (no sockets): create a `GameState`, run 10 ticks, print state. Verify snake moves, pie spawns, collision subtracts HP.
- [ ] B4. Implement `server/lobby.py`.
- [ ] B5. Implement `server/client_handler.py`.
- [ ] B6. Implement `server/game_session.py`.
- [ ] B7. Implement `server/server.py`.
- [ ] B8. Start the server (`python -m server.server 5555`). Use `telnet` or a throwaway `test_client.py` that sends a `C_CONNECT` JSON and reads back `S_CONNECT_ACK`.

### Phase C — Client Screens (one at a time)
- [ ] C1. Implement `client/network.py`.
- [ ] C2. Implement `client/client.py` (screen manager only, screens are stubs).
- [ ] C3. Implement `connect_screen.py` → can connect to server.
- [ ] C4. Implement `username_screen.py` → username accepted/rejected correctly.
- [ ] C5. Implement `lobby_screen.py` → player list updates live.
- [ ] C6. Implement `customize_screen.py` → key bindings stored in client state.
- [ ] C7. Implement `game_screen.py` renderer (static, fake state first → then live).
- [ ] C8. Implement `result_screen.py`.

### Phase D — Integration
- [ ] D1. Start server. Connect two clients. Challenge + accept → game starts.
- [ ] D2. Verify snake movement syncs at 10 Hz.
- [ ] D3. Verify collision, HP loss, pie collection.
- [ ] D4. Verify game-over condition (HP=0 or timer).
- [ ] D5. Test disconnection mid-game: remaining player wins.

### Phase E — Advanced Features
- [ ] E1. Text chat — test in-game chat between two players.
- [ ] E2. Fans — connect a third client, click Watch, verify they see game state.
- [ ] E3. Creative feature (Shield power-up) — implement and test.

### Phase F — Polish & Report
- [ ] F1. Add error popups for all edge cases (server full, already in game, etc.).
- [ ] F2. Pygame UI polish: smooth animations, health bar colour transitions, timer colour goes red under 30s.
- [ ] F3. Add README with run instructions.
- [ ] F4. Record 3-minute demo video.
- [ ] F5. Write project report per the rubric.

---

## 6. Pygame Rendering Reference

### Drawing a grid cell
```python
def cell_rect(col: int, row: int) -> pygame.Rect:
    return pygame.Rect(
        col * CELL_SIZE,
        row * CELL_SIZE + HUD_HEIGHT,
        CELL_SIZE,
        CELL_SIZE
    )
```

### Drawing a snake
```python
def draw_snake(surface, body, color, is_shielded=False):
    for i, (col, row) in enumerate(body):
        r = cell_rect(col, row)
        # Body segments slightly inset for gap effect
        inner = r.inflate(-2, -2)
        shade = tuple(max(0, c - 40) for c in color) if i > 0 else color
        pygame.draw.rect(surface, shade, inner, border_radius=4)
    # Shield aura on head
    if is_shielded:
        hr = cell_rect(body[0][0], body[0][1]).inflate(6, 6)
        aura_surf = pygame.Surface(hr.size, pygame.SRCALPHA)
        pygame.draw.rect(aura_surf, (100, 180, 255, 120), aura_surf.get_rect(), border_radius=6)
        surface.blit(aura_surf, hr.topleft)
```

### Drawing a health bar
```python
def draw_health_bar(surface, x, y, w, h, current, maximum):
    ratio  = current / maximum
    color  = COLOR_HP_BAR_OK if ratio > 0.3 else COLOR_HP_BAR_LOW
    pygame.draw.rect(surface, (60, 60, 60), (x, y, w, h))
    pygame.draw.rect(surface, color,        (x, y, int(w * ratio), h))
    pygame.draw.rect(surface, COLOR_TEXT,   (x, y, w, h), 1)
```

### Text rendering helper
```python
_font_cache = {}
def get_font(size: int) -> pygame.font.Font:
    if size not in _font_cache:
        _font_cache[size] = pygame.font.SysFont("monospace", size)
    return _font_cache[size]

def draw_text(surface, text, x, y, size=18, color=COLOR_TEXT, anchor="topleft"):
    font   = get_font(size)
    render = font.render(text, True, color)
    rect   = render.get_rect(**{anchor: (x, y)})
    surface.blit(render, rect)
```

---

## 7. Protocol Message Reference

Full list of every message that flows over the wire. Use as a lookup during development.

| Direction | Type | Key Fields |
|-----------|------|------------|
| C→S | `C_CONNECT` | `username`, `color` |
| S→C | `S_CONNECT_ACK` | `status` ("ok"/"error"), `reason?`, `username?` |
| S→C | `S_PLAYER_LIST` | `players: [str]` |
| S→C | `S_PLAYER_JOINED` | `username` |
| S→C | `S_PLAYER_LEFT` | `username` |
| C→S | `C_CHALLENGE` | `target` |
| S→C | `S_CHALLENGE` | `from` |
| C→S | `C_CHALLENGE_RESP` | `from`, `accepted: bool` |
| S→C | `S_CHALLENGE_ACK` | `accepted: bool`, `from` |
| C→S | `C_WATCH` | — |
| S→C | `S_WATCH_ACK` | `state` |
| S→C | `S_GAME_START` | `your_snake`, `opponent`, `state` |
| C→S | `C_MOVE` | `direction` ("UP"/"DOWN"/"LEFT"/"RIGHT") |
| S→C | `S_GAME_STATE` | `state` (full GameState dict) |
| S→C | `S_GAME_END` | `winner` (username or null), `state` |
| C→S | `C_CHAT` | `to` (username or null), `message` |
| S→C | `S_CHAT` | `from`, `message` |
| C→S | `C_DISCONNECT` | — |
| S→C | `S_ERROR` | `reason` |

---

## 8. Common Pitfalls — Read Before You Code

1. **Never `json.loads(sock.recv(4096))` directly.** TCP may split your message. Always use the length-prefix framing in `protocol.py`.

2. **Never call `pygame.*` from a background thread.** All Pygame calls must happen in the main thread. The `NetworkManager` recv thread only pushes to the queue; the main loop drains it.

3. **`sock.sendall()` not `sock.send()`.** `send()` is not guaranteed to send all bytes in one call.

4. **`threading.Lock` around sends.** Multiple threads may try to send simultaneously (e.g., game state broadcast). Use `_send_lock`.

5. **Snake body representation.** `body[0]` is always the head. When the snake grows, append the current tail position before advancing; don't just append after moving.

6. **180° reversal guard.** A snake cannot immediately reverse direction. Check `OPPOSITE[current] != new_dir` before updating direction.

7. **Thread-safe game state.** `GameSession` mutates state in its own thread and broadcasts. `ClientHandler` threads call `submit_move()` which writes to `_moves`. Use the `_lock` in `GameSession`. Do NOT let ClientHandlers touch `state` directly.

8. **Pygame event loop.** Call `pygame.event.get()` every frame. If you don't drain the event queue, the OS will consider the window unresponsive.

9. **Framing test.** Before doing anything else, test `protocol.py` end-to-end with two threads and a socketpair. Many bugs come from the framing layer.

10. **Port already in use.** Use `SO_REUSEADDR = 1` on the server socket (already done in the template above).

---

## 9. Testing Checklist

Before submitting, run through every item:

- [ ] Two clients connect with **same username** → second client rejected with clear error.
- [ ] Client A challenges Client B → B accepts → game starts for both.
- [ ] Client A challenges Client B → B declines → both stay in lobby.
- [ ] Snake hits wall → loses `WALL_HIT_DMG` HP.
- [ ] Snake eats regular pie → gains 10 HP, grows 1 segment.
- [ ] Snake eats poison pie → loses 15 HP.
- [ ] Snake eats golden pie → gains 25 HP.
- [ ] HP never exceeds `MAX_HEALTH` (150).
- [ ] HP reaches 0 → game over, other player wins.
- [ ] Timer hits 0 → player with higher HP wins.
- [ ] Equal HP at timer-end → draw announced.
- [ ] Third client connects, clicks Watch → sees live game, cannot move snakes.
- [ ] Chat message from P1 appears in P2's chat panel (and vice versa).
- [ ] Disconnection mid-game → remaining player declared winner.
- [ ] After game ends, both players return to lobby and can start a new game.
- [ ] Shield power-up collected → snake takes no collision damage for 5 seconds.

---

## 10. Run Instructions (for README)

```bash
# Terminal 1 — start server
cd python_arena
python -m server.server 5555

# Terminal 2 — first client
python -m client.client

# Terminal 3 — second client
python -m client.client
```

Requirements: `pip install pygame==2.5.2` (Python 3.11+ standard library used for everything else).
