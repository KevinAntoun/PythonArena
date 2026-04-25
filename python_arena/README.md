# Python Arena

Networked two-player snake arena for EECE 350. The server owns all game
state, runs the 10 Hz tick loop, and broadcasts authoritative snapshots to
players and viewers.

## Setup

```powershell
cd "C:\Users\kevin\Desktop\AUB\Courses\EECE 350\Project"
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
```

The project currently uses Python 3.13 with `pygame==2.6.1`.

## Run Server

```powershell
cd "C:\Users\kevin\Desktop\AUB\Courses\EECE 350\Project"
cd python_arena
..\venv\Scripts\python.exe -m server.server 5555
```

## Run Clients

Open two or more additional terminals:

```powershell
cd "C:\Users\kevin\Desktop\AUB\Courses\EECE 350\Project"
cd python_arena
..\venv\Scripts\python.exe -m client.client
```

In each client, connect to `127.0.0.1` on port `5555`, choose a unique
username, then challenge another player from the lobby.

## Controls

Default movement keys are `W`, `A`, `S`, and `D`. Use the lobby Controls
screen to rebind movement before starting a match.

## Features

- Length-prefixed JSON protocol over TCP.
- Threaded server with one handler per client and one game-session thread.
- Two-player challenge/accept matchmaking.
- Live synchronized snake movement at 10 Hz.
- Static obstacles, random pies, poison pies, and shield power-ups.
- Damage flash and short post-hit immunity.
- Wall auto-redirect after border collisions.
- In-game player chat and fan chat.
- Viewer mode for watching an active match.
- In-game auto-pilot toggle for solo demos and local testing.
- Result screen with winner and final stats.

## Test Commands

Run from `python_arena`:

```powershell
..\venv\Scripts\python.exe -B manual_protocol_test.py
..\venv\Scripts\python.exe -B manual_game_logic_test.py
..\venv\Scripts\python.exe -B manual_autoplay_test.py
..\venv\Scripts\python.exe -B server_smoke_test.py
..\venv\Scripts\python.exe -B server_game_start_smoke_test.py
..\venv\Scripts\python.exe -B client_network_smoke_test.py
..\venv\Scripts\python.exe -B client_transition_smoke_test.py
..\venv\Scripts\python.exe -B phase_d_integration_test.py
..\venv\Scripts\python.exe -B phase_e_integration_test.py
```

## Protocol Summary

Every TCP message is framed as:

```text
8-byte zero-padded payload length + UTF-8 JSON payload
```

This avoids relying on `recv()` returning exactly one JSON object.
