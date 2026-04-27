from abc import ABC, abstractmethod
import threading
import time
import json

import numpy as np
from pymycobot import MyCobot280

from connect4_engine.utils.config import get_config
from connect4_engine.utils.logger import logger, timed
from connect4_engine.hardware.arduino import ArduinoCommunicator as Arduino


class IRobot(ABC):

    @abstractmethod
    def drop_piece(self, column: int, puck_no: int):
        """
        Drop a puck in the specified column, given that it's the nth puck.
        Args:
            column: int - the column to drop the puck in
            puck_no: int - the number of the puck to drop (from red stack.)
        Returns:
            None
        """
        pass

    @abstractmethod
    def give_player_puck(self, puck_no: int):
        """
        Give player a yellow puck from that stack, given that it's the nth pucki.
        Args:
            puck_no: int - the number of the puck to drop (from yellow stack.)
        Returns:
            None
        """
        pass

    @abstractmethod
    def reset(self):
        pass


class RobotCommunicator(IRobot):
    def __init__(
        self,
        com_port: str | None,
        pump: Arduino = None,
        coord_json: dict = None,
        json_path: str = None,
    ):
        if pump is None:
            raise ValueError("pump must be provided")
        self.pump = pump
        self.mc = MyCobot280(com_port)
        if coord_json is not None:
            self.coord_json = coord_json
        elif json_path is not None:
            with open(json_path, "r") as f:
                self.coord_json = json.load(f)
        self.angles_json = json.load(open("connect4_engine/hardware/angles.json"))
        self.ARM_SPEED = 100
        self.ARM_SPEED_PRECISE = 50
        self.MOVE_TIMEOUT = 1
        self.killswitch = threading.Event()
        robo_config = get_config()["hardware"]["robot"]
        self.pause_between_moves = robo_config["pause_between_moves"]
        # Define angle tables for different positions
        self.angle_table = self.angles_json["angle_table"]

        # Define chess table for different positions
        self.chess_table = self.angles_json["chess_table"]

        # Define drop table for different positions
        self.drop_table = self.angles_json["drop_table"]

    def send_angles(self, angles, speed, direction="forwards"):
        if any(isinstance(item, list) for item in angles):
            self.send_angle_sequence(angles, speed, direction)
        else:
            self.send_angle(angles, speed)

    def send_angle(self, angle, speed):
        self.check_exit()
        self.mc.sync_send_angles(angle, speed, self.MOVE_TIMEOUT)
        for tries in range(3):
            self.check_exit()
            if not self.mc.is_in_position(angle, 0):
                self.mc.sync_send_angles(angle, speed, self.MOVE_TIMEOUT)
        if self.pause_between_moves:
            input("press <Enter> to proceed.")

    """
    go through a sequence of angles (some saved linear motion sequence).
    """

    def send_angle_sequence(self, angles, speed, direction):
        if direction == "backwards":
            angles = angles[::-1]
        for step in angles:
            self.mc.sync_send_angles(step, speed, self.MOVE_TIMEOUT)
            for tries in range(3):
                self.check_exit()
                if not self.mc.is_in_position(step, 0):
                    self.mc.sync_send_angles(step, speed, self.MOVE_TIMEOUT)
            if self.pause_between_moves:
                input("press <Enter> to proceed.")

    # check if you should ky
    def check_exit(self):
        if self.killswitch.is_set():
            logger.error("thread requested exit, going back to observe and exit.")
            # TODO: return puck to place if i'm still holding something.
            self.mc.sync_send_coords(self.angle_table["observe"], self.ARM_SPEED)
            self.killswitch.clear()
            logger.error("exit robot thread")
            raise SystemExit

    # Method to send coords with retry logic

    def send_coords(self, target_coords, speed, direction="forward"):
        if any(isinstance(item, list) for item in target_coords):
            self.send_coords_sequence(target_coords, speed, direction)
        else:
            self.send_coord(target_coords, speed)

    def send_coord(self, target_coords, speed):
        """
        send coords in a synced fashion. use custom linear func for linear motion as mycobot's linear mode is bad.
        """
        logger.debug(f"GOING TO {target_coords}")
        self.check_exit()
        self.mc.sync_send_coords(target_coords, speed, 0, self.MOVE_TIMEOUT)

    """
    go through a sequence of coords (some saved linear motion sequence).
    """

    def send_coords_sequence(self, target_coords, speed, direction="forwards"):
        if direction == "backwards":
            target_coords = target_coords[::-1]
        for step in target_coords:
            self.mc.sync_send_coords(step, speed, 0, self.MOVE_TIMEOUT)
            if self.pause_between_moves:
                input("press <Enter> to proceed.")

    def get_coords_interpolated(self, target_coords, step_mm):
        """get list of interpolated waypoints from current position to target (incl. start and end)
        Only interpolates x, y, z; rx, ry, rz are taken from target_coords.
        Computes number of waypoints so each step is ~step_mm apart.
        replaces the bad linear motion supplied by mycobot."""
        import math

        self.check_exit()
        start = self.get_current_coords()
        print(f"start: {start[:3]}\nend:   {list(target_coords[:3])}")
        dist = math.sqrt(sum((target_coords[j] - start[j]) ** 2 for j in range(3)))
        num_points = max(
            1, round(dist / step_mm) + 1
        )  # bc we're including the fst & lst so need + 1
        print(f"dist: {dist}. numpoints: {num_points}")
        self.check_exit()
        waypoints = []
        for i in range(num_points + 1):
            t = i / num_points
            waypoint = [
                start[j] + (target_coords[j] - start[j]) * t for j in range(3)
            ] + list(target_coords[3:])
            waypoints.append(waypoint)
        return waypoints

    # test

    def get_current_angles(self):
        """Return current joint angles (for location edit flow)."""
        return self.mc.get_angles()

    def get_current_coords(self):
        """Return current Cartesian coords [x, y, z, rx, ry, rz] (for location edit flow)."""
        return self.mc.get_coords()

    def release_servos(self):
        """Release all servos so the arm can be moved by hand."""
        self.mc.release_all_servos()

    def lock_servos(self):
        """Re-engage servos at current position (call after release_servos)."""
        angles = self.get_current_angles()
        if angles is not None and len(angles) == 6:
            self.send_angles(angles, self.ARM_SPEED)

    # Method to pass to the prepare position
    def prepare(self):
        self.send_angles(self.angle_table["prepare"], self.ARM_SPEED)

    # Method to return to the initial position
    def recovery(self):
        self.send_angles(self.angle_table["recovery"], self.ARM_SPEED)

    # Method to move to the top of the left discs stack
    def hover_over_stack_red(self):
        self.send_coords(self.angle_table["stack-hover-red"], self.ARM_SPEED_PRECISE)

    # Method to move to in front of left discs stack
    def apro_stack_red(self):
        self.send_coords(self.angle_table["stack-apro-red"], self.ARM_SPEED)

    # Method to move to the top of the right disks stack
    def hover_over_stack_yellow(self):
        self.send_coords(self.angle_table["stack-hover-ylw"], self.ARM_SPEED_PRECISE)

    # Method to move to in front of right discs stack
    def apro_stack_yellow(self):
        self.send_coords(self.angle_table["stack-apro-ylw"], self.ARM_SPEED)

    def _pump_on(self):
        print("pump on")
        self.pump.turn_on_pump()
    
    def pump_on_short_then_off(self):
        print("pump on")
        self.pump.turn_on_pump()
        time.sleep(1)
        print("pump off")
        self.pump.turn_off_pump()
    
    def _pump_off(self):
        print("pump off")
        self.pump.turn_off_pump()

    @timed
    def pump_release_and_off(self):
        self._pump_open_release_solenoid()
        time.sleep(0.2)
        self._pump_off()

    def _pump_open_release_solenoid(self):
        """
        keeps solenoid on to open air suction, remember to turn it off!!!
        """
        print("pump release")
        self.pump.release_pump()

    # TODO: possibly keep the full list in one place, and in the others just the last posistion to be in and #steps from the 20th puck to use
    # def get_puck_loc(self, clr, counter):
    
    # we precompute all locations in system_tests/calibrate_robot_locations.py
    def get_disc(self, counter: int, clr: str):
        self.target_angles = self.angle_table[f"stack-{clr}-{counter}"]
        self.send_angles(self.target_angles, self.ARM_SPEED)
        self._pump_on()
        time.sleep(1)
        self._pump_off()
        self.send_angles(self.target_angles, self.ARM_SPEED, direction="backwards")

    # Method to move to the handover window and drop the disk
    def drop_in_window(self):
        # logger.debug("droping disc in window")
        self.send_coords(self.angle_table["handover-window"], self.ARM_SPEED)
        self.send_coords(self.angle_table["in-window"], self.ARM_SPEED)
        self.pump_release_and_off()
        self.send_coords(self.angle_table["handover-window"], self.ARM_SPEED)

    # Method to move to the top of the chessboard
    def hover_over_chessboard_n(self, n: int):
        if n is not None and 0 <= n <= 6:
            # logger.debug(f"Move to chess position {n}, Coords: {self.chess_table[n]}")
            self.send_coords(self.chess_table[n], self.ARM_SPEED)
            self.send_coords(self.drop_table[n], self.ARM_SPEED)
            self.pump_release_and_off()
            self.send_coords(self.chess_table[n], self.ARM_SPEED)
        else:
            self.pump_release_and_off()
            raise Exception(
                f"Input error, expected chessboard input point must be between 0 and 6, got {n}"
            )

    # Method to move to the observation posture
    def observe_posture(self):
        print(f"Move to observe position {self.angle_table['observe']}")
        self.send_angles(self.angle_table["observe"], self.ARM_SPEED)

    def drop_piece(self, column: int, puck_no: int):
        self.prepare()
        logger.debug(f"Picking up red puck number {puck_no}")
        self.hover_over_stack_red()
        self.get_disc(puck_no, "red")
        logger.debug(f"Moving to column {column}")
        self.prepare()
        # self.observe_posture()
        self.hover_over_chessboard_n(column)
        self.observe_posture()
        logger.debug(f"Returned to home position")

    def give_player_puck(self, puck_no: int):
        logger.debug("Giving player a puck")
        self.prepare()
        logger.debug(f"Picking up yellow puck number {puck_no}")
        self.hover_over_stack_yellow()
        self.get_disc(puck_no, "ylw")
        logger.debug("Puck picked up, moving to player position")
        self.prepare()
        # self.observe_posture()
        self.drop_in_window()
        logger.debug("At player position, releasing puck")
        self.observe_posture()
        logger.debug("Returned to home position")

    def reset(self):
        self.observe_posture()
        logger.debug("Robot reset to home position")
