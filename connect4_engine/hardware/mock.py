from typing import Callable, Optional

from connect4_engine.hardware.arduino import IArduino
from connect4_engine.hardware.robot import IRobot
from connect4_engine.utils.logger import logger


class ArduinoPumpNoOp:
    """
    No-op Arduino used for robot location testing: pump and reset do nothing,
    so RobotCommunicator can run movement sequences without real hardware.
    """

    def turn_on_pump(self):
        pass

    def turn_off_pump(self):
        pass

    def release_pump(self):
        pass

    def reset(self, column_state: Optional[str] = None):
        pass


class ArduinoDummy(IArduino):
    def __init__(self):
        self.on_puck_dropped_callback: Optional[Callable[[int], None]] = None

    def set_on_puck_dropped_callback(self, callback: Callable[[int], None]):
        """
        Set the callback function to be called when a player move is detected.
        """
        self.on_puck_dropped_callback = callback

    def set_game_start_callback(self, callback: Callable[[], None]):
        self.game_start = callback

    def set_interrupt_callback(self, callback):
        pass

    def puck_dropped_in_col(self, column: int):
        """
        Simulate listening for player moves from the Arduino hardware.
        in this case we just tell it which column to simulate a move for.
        actual implementation would involve serial communication and waiting for input from the Arduino.
        """
        logger.debug("Arduino listening for player moves...")
        # Simulate a player move for demonstration purposes
        simulated_player_move = column
        logger.debug(f"Simulated player move detected in column {simulated_player_move}")
        if self.on_puck_dropped_callback is None:
            # Contract violated: someone forgot to register the callback
            raise RuntimeError("on_puck_dropped callback not set; call set_on_puck_dropped() first")
        self.on_puck_dropped_callback(simulated_player_move)

    def reset(self, column_state=None):
        """
        Simulate resetting the Arduino hardware.
        """
        logger.debug("Arduino resetting solenoids...")

class RobotDummy(IRobot):
    def __init__(self, arduino: ArduinoDummy = None):
        self.arduino = arduino

    def drop_piece(self, column: int, puck_no: int):
        """
        Simulate dropping a piece in the specified column using the robot hardware.
        (Does not call puck_dropped_in_col — the real robot's drop is not detected by the LED strip.)
        """
        logger.info(f"Robot dropped piece in column {column}")
        logger.debug("  go to robot puck pile, turn on pump, move to column, turn off pump, return home")

    def give_player_puck(self, puck_no: int):
        """
        Simulate giving a puck to the player.
        """
        logger.debug("""Robot giving puck to player
    go to player puck pile
    turn on pump
    move to player pickup location
    turn off pump
    return to home position""")
        
    def reset(self):
        """
        Simulate resetting the robot hardware.
        """
        logger.debug("Robot resetting to home position...")


class RobotDummySerial(IRobot):
    def __init__(self, ser):
        self.ser = ser
    def drop_piece(self, column: int):
        """
        Simulate dropping a piece in the specified column using the robot hardware.
        """
        logger.info(f"Robot dropping piece in column {column}")
        logger.debug(f"""    go to robot puck pile
    turn on pump
    move to column {column}
    turn off pump
    return to home position""")
        self.ser.push_line(f"DROP {column}\n")

    def give_player_puck(self):
        """
        Simulate giving a puck to the player.
        """
        logger.debug("""Robot giving puck to player
    go to player puck pile
    turn on pump
    move to player pickup location
    turn off pump
    return to home position""")
        
    def reset(self):
        """
        Simulate resetting the robot hardware.
        """
        logger.debug("Robot resetting to home position...")

