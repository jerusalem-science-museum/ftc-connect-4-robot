"""
Play Connect 4 against the AI using text only (no Arduino, no robot).
Run from project root: python -m system_tests.play_ai_text
"""
import sys

from connect4_engine.game import Connect4Game
from connect4_engine.hardware.mock import ArduinoDummy, RobotDummy
from connect4_engine.core.board import Board
from connect4_engine.utils.logger import logger


def main():
    arduino = ArduinoDummy()
    robot = RobotDummy(arduino)
    game = Connect4Game(arduino=arduino, robot=robot, player_starts=True)

    while True:
        game.arduino.game_start()
        logger.info("Game started. You are Red (R), AI is Yellow (Y). Enter column 0-6 or 'quit'.")

        while True:
            game.board.display()
            try:
                raw = input("Column (0-6) or 'quit': ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nBye.")
                sys.exit(0)
            if raw == "quit" or raw == "q":
                print("Bye.")
                sys.exit(0)
            try:
                col = int(raw)
            except ValueError:
                logger.warning("Enter a number 0-6 or 'quit'.")
                continue
            if col not in range(7):
                logger.warning("Column must be 0-6.")
                continue
            if not game.board.is_col_valid(col):
                logger.warning("Column %d is full." % col)
                continue
            game.arduino.puck_dropped_in_col(col)
            if game.board.is_player_winner(Board.P_RED) or game.board.is_player_winner(Board.P_YELLOW) or game.board.is_draw():
                break

        game.board.display()
        again = input("Play again? (y/n): ").strip().lower()
        if again != "y" and again != "yes":
            print("Bye.")
            break
        # Board and turns reset happens in game_start() on next loop iteration


if __name__ == "__main__":
    main()
