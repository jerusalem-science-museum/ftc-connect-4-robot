
from asyncio import FIRST_COMPLETED
from connect4_engine.core.board import Board
from connect4_engine.core.ai import AIPascalPons
from connect4_engine.hardware.robot import RobotCommunicator
from connect4_engine.hardware.arduino import ArduinoCommunicator
from connect4_engine.utils.logger import logger
import threading
import sys
class Connect4Game:

    PLAYER_COLOR = Board.P_RED
    AI_COLOR = Board.P_YELLOW
    def __init__(self,
                 arduino: ArduinoCommunicator,
                 robot: RobotCommunicator,
                 player_starts: bool = False):
        self.board = Board()
        solver = "connect4_engine/core/c4solver" + ("" if sys.platform == "linux" else ".exe")
        self.ai = AIPascalPons(ai_executable_path=solver)
        self.robot = robot
        self.logger = logger
        self.arduino = arduino
        self.arduino.set_on_puck_dropped_callback(self.piece_dropped_in_board)
        self.arduino.set_game_start_callback(self.game_start)
        self.arduino.set_interrupt_callback(self.interrupt)
        self.turns_taken = {'player': 0, 'ai': 0}
        self.player_starts = player_starts
        self.turn = 'player'
        self.gave_player_puck = False
        self.first_game = True # first time we don't need to reset the board.
        # possibly setup robot and arduino if not done elsewhere

    def interrupt(self):
        self.robot.killswitch.set()

    def game_start(self):
        # initial turn, user always starts. Reset board and turns for a new game.
        self.logger.info("Game starting...")
        if self.turns_taken['player'] > 0:
            self.game_over("resetting dirty game")
        self.board.reset()
        self.turns_taken = {'player': 0, 'ai': 0}
        self.turn = 'player'
        if not self.gave_player_puck:
            self.robot.give_player_puck(self.turns_taken['player'])

    def game_over(self, message: str):
        """
        Handle game over scenario. Does not reset the board so callers can detect
        winner/draw and show "Play again?"; they should call board.reset() when starting a new game.
        """
        self.logger.info(message)
        self.board.display()
        self.arduino.reset(self.board.get_column_stack())
        self.robot.reset()
        # Board and turns are not reset here so callers can detect winner/draw and show "Play again?".
        # They are reset in game_start() when starting a new game.
    
    def piece_dropped_in_board(self, column: int):
        """
        arduino callback when a piece is dropped by the player.
        note we're only updating the board when the ledstrip detects a piece drop,
        not just when we tell the robot to insert it there.
        """
        self.gave_player_puck = False # no puck in cartridge anymore.
        self.turns_taken[self.turn] += 1
        if self.turn == 'ai':
            self.logger.error("board isn't supposed to see ai moves bc they fall under the ledstrip!")
        else: # player's turn, i.e. self.turn == 'player'
            self.board.drop_piece(column, Connect4Game.PLAYER_COLOR)
            self.logger.info(f"Player dropped piece in column {column}")
            if self.check_winner():
                return
            self.turn = 'ai'
            self.ai_turn()

    def check_winner(self):
        """
        unoptimized winner check after each move. checks for both players.
        """
        if self.board.is_player_winner(Connect4Game.PLAYER_COLOR):
            self.game_over("Player wins!")
            return True
        if self.board.is_player_winner(Connect4Game.AI_COLOR):
            self.game_over("AI wins!")
            return True
        elif self.board.is_draw():
            self.game_over("It's a draw!")
            return True
        return False
    
    def ai_turn(self):
        # AI's turn
        ai_column = self.ai.choose_move(self.board)
        self.robot.drop_piece(ai_column, self.turns_taken['ai'])
        self.turns_taken['ai'] += 1
        self.board.drop_piece(ai_column, Connect4Game.AI_COLOR) # ledstrip doesn't detect ai piece drop bc it falls under it.
        if self.check_winner():
            return
        self.turn = 'player'
        self.robot.give_player_puck(self.turns_taken['player'])
        self.gave_player_puck = True