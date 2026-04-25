"""Basic regression checks for the client autopilot heuristic."""

from client.autoplay import choose_auto_move
from shared.constants import DIR_DOWN, DIR_RIGHT, DIR_UP


def make_state(body, direction="RIGHT", pies=None, obstacles=None):
    return {
        "tick": 1,
        "snakes": {
            "bot": {
                "body": body,
                "direction": direction,
                "health": 100,
                "alive": True,
                "color": "green",
                "score": 0,
                "shielded": False,
                "damage_flash_ticks": 0,
            },
            "human": {
                "body": [[20, 20], [19, 20], [18, 20]],
                "direction": "LEFT",
                "health": 100,
                "alive": True,
                "color": "red",
                "score": 0,
                "shielded": False,
                "damage_flash_ticks": 0,
            },
        },
        "pies": pies or [],
        "obstacles": obstacles or [],
    }


def test_moves_toward_good_pie():
    state = make_state(
        body=[[5, 5], [4, 5], [3, 5]],
        direction="RIGHT",
        pies=[{"col": 6, "row": 5, "type": "golden"}],
    )
    assert choose_auto_move(state, "bot") == DIR_RIGHT


def test_avoids_blocked_forward_cell():
    state = make_state(
        body=[[5, 5], [4, 5], [3, 5]],
        direction="RIGHT",
        pies=[{"col": 8, "row": 5, "type": "golden"}],
        obstacles=[{"col": 6, "row": 5, "type": "rock"}],
    )
    assert choose_auto_move(state, "bot") in {DIR_UP, DIR_DOWN}


def test_does_not_drive_out_of_bounds():
    state = make_state(
        body=[[0, 4], [1, 4], [2, 4]],
        direction="LEFT",
        pies=[{"col": 0, "row": 0, "type": "regular"}],
    )
    assert choose_auto_move(state, "bot") in {DIR_UP, DIR_DOWN}


if __name__ == "__main__":
    test_moves_toward_good_pie()
    test_avoids_blocked_forward_cell()
    test_does_not_drive_out_of_bounds()
    print("Autoplay heuristic tests passed.")
