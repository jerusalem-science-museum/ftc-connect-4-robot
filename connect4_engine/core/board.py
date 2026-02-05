import numpy as np
from typing import Tuple

from connect4_engine.utils.logger import logger


class Board:
    # Constants for grid representation
    P_EMPTY = 0
    P_RED = 1
    P_YELLOW = 2

    # Constants for display
    value_to_symbol = {P_EMPTY: "O", P_RED: "R", P_YELLOW: "Y"}

    def __init__(self):
        # Initialize board dimensions
        self.width = 7
        self.height = 6
        self.pons_string = ''
        self.grid = np.full((self.height, self.width), Board.P_EMPTY, dtype=np.int8)

        # Initialize game status
        self.done = False
        self.winner = None
        # self.logger = get_logger(__name__)

    def reset(self):
        # Reset the board to its initial state
        self.__init__()

    def display(self):
        """
        Display the board in text format
        """
        lines = []
        for row in self.grid[::-1]:
            line = " ".join(Board.value_to_symbol[cell] for cell in row)
            lines.append(line)

        board_str = "\n" + "\n".join(lines) + "\n"  # final extra newline if you want
        logger.info(board_str)

    def is_draw(self):
        """
        Check if the game is a draw
        """
        return len(self.available_actions()) == 0 and self.winner is None

    def _check_symbol(self, player):
        """
        Return the symbol to check for a win condition based on the player
        """
        if player == self.P_RED:
            check = "1 1 1 1"
        else:
            check = "2 2 2 2"
        return check

    def _check_vertical_win(self, board_state, player):
        """
        Check for a vertical win condition
        """
        check = self._check_symbol(player)
        for col in range(self.width):
            if check in np.array_str(board_state[:, col]):
                return True
        return False

    def _check_horizontal_win(self, board_state, player):
        """
        Check for a horizontal win condition
        """
        check = self._check_symbol(player)
        for row in range(self.height):
            if check in np.array_str(board_state[row, :]):
                return True
        return False

    def _check_leading_diag(self, board_state: np.ndarray, player):
        """
        Check for a win condition in the leading diagonals
        """
        check = self._check_symbol(player)
        for k in range(- self.height + 4, self.width - 3):
            if check in np.array_str(board_state.diagonal(k)):
                return True
        return False

    def _check_counter_diag(self, board_state: np.ndarray, player):
        """
        Check for a win condition in the counter diagonals
        """
        board_state_flipped = np.fliplr(board_state)
        return self._check_leading_diag(board_state_flipped, player)

    def is_player_winner(self, player):
        """
        Check if the given player has won
        """
        board_state = np.array(self.grid)
        return any([
            self._check_vertical_win(board_state, player),
            self._check_horizontal_win(board_state, player),
            self._check_leading_diag(board_state, player),
            self._check_counter_diag(board_state, player)
        ])

    def available_actions(self):
        """
        Return a list of available actions (columns where a piece can be dropped)
        """
        return [col for col in range(self.width) if self.is_col_valid(col)]

    def is_col_valid(self, col: int):
        """
        Check if a piece can be dropped in the given column
        """
        if self.grid[-1][col] == Board.P_EMPTY:
            return True
        else:
            return False

    def available_cell(self, col: int) -> int:
        """
        Return the row# of the available cell in the given column
        """
        for row_num, cell in enumerate(self.grid[:, col]):
            if cell == Board.P_EMPTY:
                return row_num
        return -1

    def drop_piece(self, col, player):
        """
        Drop a piece of the given player in the given column
        """
        if self.is_col_valid(col):
            row = self.available_cell(col)
            self.grid[row][col] = player
            self.pons_string += str(col + 1) # assuming turns are always valid
        else:
            raise Exception(f"Not valid move. Column {col} is full.")
        self.display()

    def check_board_state_valid(self):
        count_red = 0
        count_yellow = 0
        for row in self.grid:
            for entry in row:
                if entry == Board.P_RED:
                    count_red += 1
                elif entry == Board.P_YELLOW:
                    count_yellow += 1

        # red_should_have, yellow_should_have = Board.should_have_pieces(round)
        # if red_should_have != count_red or yellow_should_have != count_yellow:
        #     self.logger.error(
        #         f"In round {round}, the board should have {red_should_have} red pieces,{yellow_should_have} yellow pieces,but only got {count_red} red pieces, {count_yellow} yellow pieces"
        #     )
        #     return False
        # else:
        #     return True

        if abs(count_red - count_yellow) >= 2:
            return False
        else:
            return True

    def should_have_pieces(self, round: int) -> Tuple[int, int]:
        """Return how many red & yellow pieces should the board have when in round x

        Args:
            round (int): round number
        """
        if round % 2 == 0:
            return round // 2, round // 2 - 1
        else:
            return round // 2, round // 2

    def get_column_stack(self):
        str_repr = np.array_str((self.grid != Board.P_EMPTY).sum(axis=0)) # e.g. '[1 2 0 3 1 0 2]'
        return str_repr[1::2] # take odd parts, i.e. '1203102'