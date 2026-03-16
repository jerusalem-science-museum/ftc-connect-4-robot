from abc import ABC, abstractmethod
import threading
import time
import json

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
    def __init__(self, com_port: str | None, pump: Arduino = None, coord_json: dict = None, json_path: str = None):
        if pump is None:
            raise ValueError("pump must be provided")
        self.pump = pump
        self.mc = MyCobot280(com_port)
        if coord_json is not None:
            self.coord_json = coord_json
        elif json_path is not None:
            with open(json_path, "r") as f:
                self.coord_json = json.load(f)
        else:
            self.coord_json = json.load(open("connect4_engine/hardware/legacy_coords.json"))
        self.ARM_SPEED = 100
        self.ARM_SPEED_PRECISE = 50
        self.MOVE_TIMEOUT = 1
        self.DISK_LEVEL_Y = self.coord_json['DISK_DELTA_FROM_HOVER_Y']
        self.DISK_LEVEL_R = self.coord_json['DISK_DELTA_FROM_HOVER_R']
        self.killswitch = threading.Event()
        robo_config = get_config()["hardware"]["robot"]
        self.pause_between_moves = robo_config['pause_between_moves']
        # Define angle tables for different positions
        self.angle_table = self.coord_json["angle_table"]

        # Define chess table for different positions
        self.chess_table = self.coord_json["chess_table"]
        
        # Define drop table for different positions
        self.drop_table = self.coord_json["drop_table"]
    
    # Method to send angles with retry logic
    def send_angles(self, angle, speed):
        self.check_exit()
        self.mc.sync_send_angles(angle, speed, self.MOVE_TIMEOUT)
        for tries in range(3):
            self.check_exit()
            if not self.mc.is_in_position(angle, 0):
                self.mc.sync_send_angles(angle, speed, self.MOVE_TIMEOUT)
        if(self.pause_between_moves):
            input('press <Enter> to proceed.')

    # check if you should ky
    def check_exit(self):
        if(self.killswitch.is_set()):
            logger.error("thread requested exit, going back to observe and exit.")
            # TODO: return puck to place if i'm still holding something.
            self.mc.sync_send_coords(self.angle_table["observe"], self.ARM_SPEED)
            self.killswitch.clear()
            logger.error("exit robot thread")
            raise SystemExit
        
    # Method to send coords with retry logic   
    @timed 
    def send_coords(self, target_coords, speed, mode = 0, step_per_mm = 50):
        """
        send coords in a synced fashion. use custom linear func for linear motion as mycobot's linear mode is bad.
        """
        self.check_exit()
        if(mode == 1):
            coordlist = self.get_coords_interpolated(target_coords, step_per_mm)
        else:
            coordlist = [target_coords]
        for waypoint in coordlist:
            self.mc.sync_send_coords(waypoint, speed, 0, self.MOVE_TIMEOUT)
            for tries in range(3):
                self.check_exit()
                is_in_pos = self.mc.is_in_position(waypoint, 1)
                if not is_in_pos:
                    logger.debug(f'try no {tries} bc mc in position gave {is_in_pos}')
                    self.mc.sync_send_coords(waypoint, speed, 0, self.MOVE_TIMEOUT)
            if(self.pause_between_moves):
                input('press <Enter> to proceed.')

    def get_coords_interpolated(self, target_coords, step_mm):
        """get list of interpolated waypoints from current position to target (incl.)
        Only interpolates x, y, z; rx, ry, rz are taken from target_coords.
        Computes number of waypoints so each step is ~step_mm apart.
        replaces the bad linear motion supplied by mycobot."""
        import math
        self.check_exit()
        start = self.get_current_coords()
        print(f'start: {start[:3]}\nend:   {list(target_coords[:3])}')
        dist = math.sqrt(sum((target_coords[j] - start[j]) ** 2 for j in range(3)))
        num_points = max(1, round(dist / step_mm))
        print(f'dist: {dist}. numpoints: {num_points}')
        self.check_exit()
        waypoints = []
        for i in range(1, num_points + 1):
            t = i / num_points
            waypoint = [
                start[j] + (target_coords[j] - start[j]) * t
                for j in range(3)
            ] + list(target_coords[3:])
            waypoints.append(waypoint)
        return waypoints

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
        self.send_coords(self.angle_table["stack-hover-L"], self.ARM_SPEED_PRECISE, 0)
    
    # Method to move to in front of left discs stack
    def apro_stack_red(self):
        self.send_coords(self.angle_table["stack-apro-L"], self.ARM_SPEED,0)

    # Method to move to the top of the right disks stack
    def hover_over_stack_yellow(self):
        self.send_coords(self.angle_table["stack-hover-R"], self.ARM_SPEED_PRECISE, 0)
        
    # Method to move to in front of right discs stack
    def apro_stack_yellow(self):
        self.send_coords(self.angle_table["stack-apro-R"], self.ARM_SPEED)
        # self.send_coords(self.angle_table["stack-apro-R"], self.ARM_SPEED,0)

    def _pump_on(self):
        print('pump on')
        self.pump.turn_on_pump()
    
    def _pump_off(self):
        print('pump off')
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
        print('pump release')
        self.pump.release_pump()
    # Method to pick up a disk form stakc level n with thickness t
    def get_disc_yellow(self, counter: int,thickness: int):
        self.temp_target_coords = self.angle_table["stack-hover-R"] 
        logger.info(f"picking up disk at delta {self.DISK_LEVEL_Y} from hover, plus {counter} * {thickness} = {self.DISK_LEVEL_Y + (counter*thickness)} from hover")
        self.disc_x_coord=self.temp_target_coords[0] + self.DISK_LEVEL_Y + (counter*thickness)
        self.temp_target_coords[0]=self.disc_x_coord
        self.send_coords(self.temp_target_coords, self.ARM_SPEED, 1)
        self._pump_on()
        time.sleep(1)
        self._pump_off()
        self.send_coords(self.angle_table["stack-hover-R"], self.ARM_SPEED,1)  
        #self.send_coord(Coord.X.value,self.STACK_ENTRY,self.ARM_SPEED_PRECISE)
	    
    # Method to pick up a disk form stack level n with thickness t
    def get_disc_red(self, counter: int,thickness: int):
        self.temp_target_coords = self.angle_table["stack-hover-L"] 
        logger.info(f"picking up disk at delta {self.DISK_LEVEL_R} from hover, plus {counter} * {thickness} = {self.DISK_LEVEL_R + (counter*thickness)} from hover")
        self.disc_x_coord = self.temp_target_coords[0] + self.DISK_LEVEL_R + (counter*thickness)
        self.temp_target_coords[0]=self.disc_x_coord
        logger.debug(f'current location: {self.mc.get_coords()}')
        logger.debug(f'next location: {self.temp_target_coords}')
        self.send_coords(self.temp_target_coords, self.ARM_SPEED, 1)
        self._pump_on()
        time.sleep(1)
        self._pump_off()
        self.send_coords(self.angle_table["stack-hover-L"], self.ARM_SPEED,1)
        #self.send_coord(Coord.X.value,self.STACK_ENTRY,self.ARM_SPEED_PRECISE)
                    
    # Method to move to the handover window and drop the disk
    def drop_in_window(self):
       #logger.debug("droping disc in window")
       self.send_coords(self.angle_table["handover-window"], self.ARM_SPEED)        
       self.send_coords(self.angle_table["in-window"], self.ARM_SPEED, 1, step_per_mm=30)
       self.pump_release_and_off()
       self.send_coords(self.angle_table["handover-window"], self.ARM_SPEED, 0) 


    # Method to move to the top of the chessboard
    def hover_over_chessboard_n(self, n: int):
        if n is not None and 0 <= n <= 6:
            # logger.debug(f"Move to chess position {n}, Coords: {self.chess_table[n]}")
            self.send_coords(self.chess_table[n], self.ARM_SPEED)
            self.send_coords(self.drop_table[n], self.ARM_SPEED, 1, step_per_mm=30)
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

    def drop_piece(self, column: int,  puck_no: int):

        self.prepare()
        logger.debug(f"Picking up red puck number {puck_no}")
        self.hover_over_stack_red()
        self.get_disc_red(puck_no,self.coord_json['red_puck_thickness'])
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
        self.get_disc_yellow(puck_no,self.coord_json['yellow_puck_thickness'])
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