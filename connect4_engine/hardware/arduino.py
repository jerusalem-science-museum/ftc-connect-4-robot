from socket import timeout
from typing import Callable, Optional
from abc import ABC, abstractmethod
import serial
import threading
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
        self._accept_moves = False  # only accept drops when game is active
        self._active_thread = None
        self._ack_event = threading.Event()
        self._ack_expected = None  # the ACK string the worker thread is waiting for
        self._ack_lock = threading.Lock()  # protects _ack_expected

    def set_interrupt_callback(self, callback: Callable):
        self.interrupt_callback = callback

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

    # this runs always, so if we want to restart we can.
    def _handle_line(self, line: str):
        parts = line.split()
        if parts[0] == "START":
            # if start then game will killswitch the robot
            if(self._active_thread and self._active_thread.is_alive()):
                self.interrupt_callback()
                self._active_thread.join()
            self._active_thread = threading.Thread(target=self.handle_start)
            self._active_thread.start()

            # self.handle_start()
        # we want to handle the drop in a separate thread so we can kill it/reset if necessary.
        # otherwise we're stuck in concurrency.
        elif parts[0] == "DROP" and self._accept_moves and len(parts) == 2:
            # already existing start/drop routine running.
            if threading.active_count() > 1:
                logger.error("somehow user dropped an extra puck?!?!")
                return
            self._active_thread = threading.Thread(target=self.handle_drop, args=(line, parts))
            self._active_thread.start()
            # self.handle_drop(line, parts)
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
        self.send_message("PUMP ON")

    def turn_off_pump(self):
        self.send_message("PUMP OFF")

    def release_pump(self):
        self.send_message("PUMP RELEASE")
        # todo: wait for response ack from arduino

    def send_message(self, message: str):
        msg = f"{message}\n"
        self._logger.info(f"Sending to Arduino: {msg.strip()}")
        self._ser.write(msg.encode("utf-8"))