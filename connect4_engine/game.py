from typing import Callable

from connect4_engine.core.board import Board
from connect4_engine.core.ai import AIPlayerDummy, AIPascalPons
from connect4_engine.hardware.robot import IRobot
from connect4_engine.hardware.arduino import IArduino
from connect4_engine.utils.logger import logger

class Connect4Game:

    PLAYER_COLOR = Board.P_RED
    AI_COLOR = Board.P_YELLOW
    def __init__(self,
                 arduino: IArduino,
                 robot: IRobot,
                 player_starts: bool = False):
        self.board = Board()
        self.ai = AIPascalPons(ai_executable_path="connect4_engine/core/c4solver.exe")
        self.robot = robot
        self.logger = logger
        self.arduino = arduino
        self.arduino.set_on_puck_dropped_callback(self.piece_dropped_in_board)
        self.arduino.set_game_start_callback(self.game_start)
        self.turns_taken = {'player': 0, 'ai': 0}
        self.player_starts = player_starts
        self.turn = 'ai'
        # possibly setup robot and arduino if not done elsewhere

    def game_start(self):
        # initial turn
        self.logger.info("Game started!")
        if self.player_starts:
            self.turn = 'player'
            self.robot.give_player_puck(self.turns_taken['player'])
        else:
            self.turn = 'ai'
            self.ai_turn()

    def game_over(self, message: str):
        """
        Handle game over scenario
        """
        self.logger.info(message)
        self.board.display()
        self.arduino.reset()
        self.robot.reset()
        self.board.reset()
    
    def piece_dropped_in_board(self, column: int):
        """
        arduino callback when a piece is dropped by the player.
        note we're only updating the board when the ledstrip detects a piece drop,
        not just when we tell the robot to insert it there.
        """
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
        self.logger.info(f"AI dropped piece in column {ai_column}")
        if self.check_winner():
            return
        self.turn = 'player'
        self.robot.give_player_puck(self.turns_taken['player'])