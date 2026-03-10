import serial

from connect4_engine.game import Connect4Game
from connect4_engine.hardware.robot import RobotCommunicator
from connect4_engine.hardware.arduino import ArduinoCommunicator
from connect4_engine.hardware.mock import RobotDummy


class Main:
    def __init__(self):
        self.arduino = ArduinoCommunicator(ser=serial.Serial("/dev/ttyUSB0", 115200))
        # self.robot = RobotCommunicator(com_port="COM11", pump=self.arduino)
        self.robot = RobotDummy()
        self.game = Connect4Game(arduino=self.arduino, robot=self.robot, player_starts=False)
    
    def play(self):
        self.arduino.read_loop()  # in real hardware this would be the only thing running.

    
if __name__ == "__main__":
    m = Main()
    m.play()