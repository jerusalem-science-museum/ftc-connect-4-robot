import serial

from connect4_engine.game import Connect4Game
from connect4_engine.hardware import mock
from connect4_engine.hardware.mock import ArduinoDummy, RobotDummy
from connect4_engine.hardware.robot import RobotCommunicator
from connect4_engine.hardware.arduino import ArduinoCommunicator
from connect4_engine.core.ai import AIPascalPons, main
from connect4_engine.core.board import Board
from connect4_engine.hardware.ArmInterface import test_arm

class Main:
    def __init__(self):
        self.arduino = ArduinoCommunicator(ser=serial.Serial("COM5", 115200))
        # self.robot = RobotCommunicator("COM11", self.arduino)
        self.robot = RobotDummy()
        self.mock_arduino = ArduinoDummy()
        # self.arduino = ArduinoDummy()
        # self.robot = RobotDummy(arduino=self.arduino)
        self.game = Connect4Game(arduino=self.arduino, robot=self.robot, player_starts=False)
    
    def play(self):
        # self.game.game_start()
        # self.mock_arduino.puck_dropped_in_col(3)
        # self.mock_arduino.puck_dropped_in_col(2)
        # self.mock_arduino.puck_dropped_in_col(3)
        # self.mock_arduino.puck_dropped_in_col(0)

        self.arduino.read_loop()  # in real hardware this would be the only thing running.

    
if __name__ == "__main__":
    # print('testing arm')
    # test_arm()
    m = Main()
    m.play()
    # Example usage
    # main()
    # board = Board()
    # ai_player = AIPascalPons(ai_executable_path="./connect4_engine/core/connect4ai/connect4/c4solver")
    # move = ai_player.choose_move(board)
    # print(f"AI chose column: {move}")