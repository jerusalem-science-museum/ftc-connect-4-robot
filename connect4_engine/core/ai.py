import subprocess
from time import sleep

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
    def __init__(self, ai_executable_path: str):
        self.ai_executable_path = ai_executable_path
        self.proc = subprocess.Popen(
            [self.ai_executable_path, "-a", "-b", "connect4_engine/core/7x6.book"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,      # work with str instead of bytes
        )

    def choose_move(self, board: Board):
        """
        Choose a move by invoking the external Pascal Pons AI executable.
        """


        logger.debug("AI (Pascal Pons) is choosing a move...")

        # send a string
        self.proc.stdin.write(board.pons_string + "\n")
        self.proc.stdin.flush() # ensure it's sent
        logger.debug(f"Sent board state to AI: {board.pons_string}")
        out = self.proc.stdout.readline()
        return int(out.strip())
        # stdout, stderr = process.communicate(input=board.pons_string)

        # if process.returncode != 0:
        #     logger.error(f"AI executable error: {stderr}")
        #     raise Exception("AI executable failed to choose a move.")

        # # Parse the output to get the chosen column
        # chosen_column = int(stdout.strip())
        # return chosen_column
    
def main():
    # Example usage
    board = Board()
    ai_player = AIPascalPons(ai_executable_path="connect4_engine/core/c4solver")
    move = ai_player.choose_move(board)
    print(f"AI chose column: {move}")
# if __name__ == "__main__":  