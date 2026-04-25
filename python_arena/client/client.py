"""Pygame client entry point and screen manager."""

import sys

import pygame

from client.network import NetworkManager
from client.screens.connect_screen import ConnectScreen
from client.screens.customize_screen import CustomizeScreen
from client.screens.game_screen import GameScreen
from client.screens.lobby_screen import LobbyScreen
from client.screens.result_screen import ResultScreen
from client.screens.username_screen import UsernameScreen
from client.screens.waiting_screen import WaitingScreen
from shared.constants import WINDOW_H, WINDOW_W

FPS = 60


def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption("Python Arena")
    clock = pygame.time.Clock()
    net = NetworkManager()

    screens = {
        "connect": ConnectScreen(net),
        "username": UsernameScreen(net),
        "lobby": LobbyScreen(net),
        "customize": CustomizeScreen(net),
        "waiting": WaitingScreen(net),
        "game": GameScreen(net),
        "result": ResultScreen(net),
    }
    current = "connect"

    while True:
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                net.disconnect()
                pygame.quit()
                sys.exit()

        action = screens[current].update(events)
        screens[current].draw(screen)

        if action and action[0] == "transition":
            next_name = action[1]
            data = action[2] if len(action) > 2 else None
            screens[next_name].on_enter(data)
            current = next_name

        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()
