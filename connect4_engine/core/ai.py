import subprocess
from time import sleep

import numpy as np

from connect4_engine.core.board import Board
from connect4_engine.utils.logger import logger

class AIPlayerDummy:
    def __init__(self):
        pass

    def choose_move(self, board: Board):
        """
        Choose a move based on a simple strategy: pick the first available column.
        """
        logger.debug("AI is choosing a move...")
        sleep(3)  # simulate thinking time
        available_columns = board.available_actions()
        if available_columns:
            return available_columns[0]
        else:
            raise Exception("No available moves left.")
    
class AIPascalPons:
    def __init__(self, ai_executable_path: str, top_k: int = 5, temp: float = 5.0):
        # Higher temp = more randomness (softer softmax). Solver scores are in ~[-21, 21];
        # temp=1 made the best move dominate; temp=8 gives visible variety among good moves.
        self.ai_executable_path = ai_executable_path
        self.proc = subprocess.Popen(
            [self.ai_executable_path, "-a", "-b", "connect4_engine/core/7x6.book"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,      # work with str instead of bytes
        )
        self.top_k = top_k
        self.temp = temp

    def get_move_to_play(self, scores: np.ndarray):
        # Ignore invalid (full) columns: solver uses INVALID_MOVE for unplayable cols
        valid = np.isfinite(scores) & (scores > -999)
        if not np.any(valid):
            valid = np.ones_like(scores, dtype=bool)
        valid_scores = np.where(valid, scores, -np.inf)
        top_indices = np.argsort(valid_scores)[-self.top_k:][::-1]
        top_scores = valid_scores[top_indices]
        # Softmax: exp(score / temp) / sum — higher temp = more randomness
        exp_scores = np.exp(top_scores / self.temp)
        probs = exp_scores / np.sum(exp_scores)
        chosen_top_idx = np.random.choice(len(top_indices), p=probs)
        return top_indices[chosen_top_idx]

    def choose_move(self, board: Board):
        """
        Choose a move by invoking the external Pascal Pons AI executable.
        """


        logger.debug("AI (Pascal Pons) is choosing a move...")

        # send a string
        self.proc.stdin.write(board.pons_string + "\n")
        self.proc.stdin.flush() # ensure it's sent
        logger.debug(f"Sent board state to AI: {board.pons_string}")
        out = self.proc.stdout.readline().strip()
        logger.info(f"{out}")
        scores = out.split(' ')
        scores = np.array(scores,dtype=float)
        idx_to_play = self.get_move_to_play(scores)
        return idx_to_play
    
def main():
    # Example usage
    board = Board()
    ai_player = AIPascalPons(ai_executable_path="connect4_engine/core/c4solver")
    move = ai_player.choose_move(board)
    print(f"AI chose column: {move}")