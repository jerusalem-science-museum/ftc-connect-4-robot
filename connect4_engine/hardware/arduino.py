from socket import timeout
from typing import Callable, Optional
from abc import ABC, abstractmethod
import serial
import time

from connect4_engine.utils.logger import logger


class IArduino(ABC):

    @abstractmethod
    def set_on_puck_dropped_callback(self, callback: Callable[[int], None]):
        pass
    
    @abstractmethod
    def set_game_start_callback(self, callback: Callable[[], None]):
        pass

    @abstractmethod
    def reset(self, column_state: Optional[str] = None):
        pass

class ArduinoCommunicator(IArduino):
    def __init__(self, ser: serial.Serial):
        self._ser = ser
        self._logger = logger
        self._accept_moves = False          # only accept drops when game is active

    def set_on_puck_dropped_callback(self, callback: Callable[[int], None]):
        self._on_puck_dropped = callback
    
    def set_game_start_callback(self, callback: Callable[[], None]):
        self.game_start = callback

    def read_loop(self):
        self._logger.info("Arduino read loop started")
        while True:
            line = self._ser.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            self._logger.debug(f"Serial line: {line}")
            self._handle_line(line)

    def _handle_line(self, line: str):
        parts = line.split()

        if parts[0] == "START":
            self.handle_start()
        elif parts[0] == "DROP" and self._accept_moves and len(parts) == 2:
            return self.handle_drop(line, parts)
        elif parts[0] == "LOG":
            self._logger.info(f"Arduino log: {' '.join(parts[1:])}")

    def handle_drop(self, line, parts):
        try:
            col = int(parts[1])
        except ValueError:
            self._logger.warning(f"Invalid column in line: {line}")
            return
        self._logger.info(f"Detected puck in column {col}")
        self._on_puck_dropped(col)

    def handle_start(self):
        self._logger.info("Start signal from Arduino")
        self._accept_moves = True
        self.game_start()

    def reset(self, column_state: Optional[str] = None):
        if column_state is not None:
            self.send_message(f"RESET {column_state}")
        else:
            self.send_message("RESET")
        self._accept_moves = False
    
    def turn_on_pump(self):
        self.send_message_sync_and_wait_ack("PUMP ON")
    
    def turn_off_pump(self):
        self.send_message_sync_and_wait_ack("PUMP OFF")
    
    def release_pump(self):
        self.send_message_sync_and_wait_ack("PUMP RELEASE")
        # todo: wait for response ack from arduino
    
    def send_message(self, message: str):
        msg = f"{message}\n"
        self._logger.info(f"Sending to Arduino: {msg.strip()}")
        self._ser.write(msg.encode("utf-8"))
    
    def send_message_sync(self,message: str):
        msg = f"{message}\n"
        self._logger.info(f"Sending to Arduino: {msg.strip()}")
        self._ser.write(msg.encode("utf-8"))

    def send_message_sync_and_wait_ack(self, message: str, timeout: float = 3.0):
        """
        Send a message to the Arduino, clear the serial input,
        and wait for an acknowledgement line formatted as 'ACK {message}'.

        Args:
            message: The message to send (without newline).
            timeout: Maximum time in seconds to wait for ACK.

        Returns:
            True if ACK received, False otherwise.
        """
        # Clear any existing input from serial buffer
        if hasattr(self._ser, "reset_input_buffer"):
            self._ser.reset_input_buffer()
        elif hasattr(self._ser, "flushInput"):
            self._ser.flushInput()
        else:
            # If the serial object doesn't support clear, read all lines in buffer
            start = time.time()
            while self._ser.in_waiting and (time.time() - start < 0.1):
                self._ser.readline()

        # Send the message
        msg = f"{message}\n"
        self._logger.info(f"Sending to Arduino: {msg.strip()}")
        self._ser.write(msg.encode("utf-8"))

        expected_ack = f"LOG: {message}".strip()
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._ser.in_waiting:
                try:
                    line = self._ser.readline().decode("utf-8").strip()
                except Exception as e:
                    self._logger.warning(f"Read exception: {e}")
                    continue
                if line == expected_ack:
                    self._logger.info(f"Received expected ACK: {line}")
                    return True
                else:
                    self._logger.debug(f"Received (but not ACK): {line}")
            time.sleep(0.05)
        self._logger.warning(f"Timeout waiting for ACK '{expected_ack}' after sending: {msg.strip()}")
        return False

if __name__ == "__main__":
    arduino = ArduinoCommunicator(ser=serial.Serial('COM3', 115200,tim))
    arduino.read_loop()