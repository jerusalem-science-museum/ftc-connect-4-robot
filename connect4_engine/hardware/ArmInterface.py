import time
from typing import *
import logging
import json
import serial

from pymycobot import MyCobot280 as MyCobot

from connect4_engine.hardware.arduino import ArduinoCommunicator as Arduino
# from core.logger import get_logger

# logger = get_logger(__name__)

class ArmInterface:
    def __init__(self, port: str, baudrate: int):
        # Define arm speeds
        self.pump = Arduino(serial.Serial("COM5", 115200))
        self.ARM_SPEED = 100
        self.ARM_SPEED_PRECISE = 50
        self.DISC_LEVEL = 145
        self.ENTRY_PLANE = 256
        self.STACK_ENTRY = 125
        self.BOARD_PLANE = 312
        self.MOVE_TIMEOUT = 1
        self.port = port
       

        # Define solonoides and LED controlling card pins and constants
        self.SR_St_Pin = 21 # 74HC565 shift register strob pin (12) - active high (low/hig/low pulse shift Sr vector to outputs)make sure set low during "push"data in
        self.SR_Data_Pin = 23 # 74HC565 Data in pin (14)
        self.SR_Clk_Pin = 22 # 74HC565 shift clock pin (11) - active high (low/hig/low pulse shift data in) make sure initaly set to low
        #self.En_Pin = 19 # 74HC565 out put enable pin (13) - active low active low (not need to be used, pull Down resistor on board)
        
        self.LED_ON_TIME = 0.1 # sec 
        self.LED_OFF_TIME = 0.1 # sec
        self.LED_BLINK_NUMBER = 10 #
        self.SOLENOIDE_ON_TIME = 0.5 # sec 
        self.SOLENOIDE_SPACE_TIME = 1 # sec, the time between on each soleoide 

        self.NUMBER_OF_SOLENOIDS = 7
        self.LED_SWITCH = 0x07 # switch led is the last output - most right on PCB, far from input connector
        self.current_state = 0x00 # used to remember and keep current outputs when change only part of the IOs 

        # Define of start button pins
        self.LED_pin = 21
        self.button_pin = 18 #used to get input from the user to start the game

        # Define Pump operations constants and M5 controller ("Basic") IO pins
        self.VACCUM_BUILD_TIME = 0.1 #seconds
        self.VACCUM_DROP_TIME = 0.2 #seconds
        
        self.coord_json = json.load(open('connect4_engine/hardware/legacy_coords.json'))
        # Define angle tables for different positions
        self.angle_table = self.coord_json["angle_table"]

        # Define chess table for different positions
        self.chess_table = self.coord_json["chess_table"]
        
        # Define drop table for different positions
        self.drop_table = self.coord_json["drop_table"]
        

        # Define retry count
        self.retry = 5
        
        # Define discs count
        self.ylw_disc_taken = 0
        self.red_disc_taken = 0

        # Initialize MyCobot instance
        self.mc = MyCobot(port, baudrate, timeout=0.5, debug=True)

        # counter mycobot module contaminating the root logger
        # logging.getLogger().setLevel(logging.CRITICAL)
        self.mc.log.setLevel(logging.DEBUG)
        self.mc.log.propagate = False

        # Set up log to file
        mc_file_hdlr = logging.FileHandler("logs/robot.log")
        mc_file_hdlr.setFormatter(
            logging.Formatter("%(levelname)s - %(asctime)s - %(name)s - %(message)s")
        )
        self.mc.log.addHandler(mc_file_hdlr)

        self.mc.set_fresh_mode(0) #1 - Always execute the latest command first. 0 - Execute instructions sequentially in the form of a queue.
        self.mc.set_movement_type(0)

        #setup of IOs

    # On byte - this routin only update the state but NOT change ouptut 
    def on_current_state_bit(self, out_number):
        digit_position = 0x01
        digit_position = digit_position << out_number # rotate left 
        self.current_state = (self.current_state | digit_position) #bitwise OR operator

    # Off byte -this routin only update the state but NOT change ouptut 
    def off_current_state_bit(self, out_number):
        digit_position = 0x01
        digit_position = digit_position << out_number # rotate left 
        self.current_state = (self.current_state &(~digit_position)) #bitwise AND and NOT operators

    # Method to send angles with retry logic
    def send_angles(self, angle, speed):
        self.mc.sync_send_angles(angle, speed, self.MOVE_TIMEOUT)
        for tries in range(3):
            if not self.mc.is_in_position(angle, 0):
                self.mc.sync_send_angles(angle, speed, self.MOVE_TIMEOUT)
        
    # Method to send coords with retry logic
    def send_coords(self, coords, speed, mode = 0):

        self.mc.sync_send_coords(coords, speed, mode, self.MOVE_TIMEOUT)
        for tries in range(3):
            if not self.mc.is_in_position(coords, 1):
                self.mc.sync_send_coords(coords, speed, mode, self.MOVE_TIMEOUT)
    # Method to set basic output with retry logic
    def set_basic_output(self, val1, val2):
        self.mc.set_basic_output(val1, val2)

    # Method to send coordinates with retry logic
    def send_coord(self, arm_id, coord, speed):
        self.mc.send_coord(arm_id, coord, speed)       

    # Method to pass to the prepare position
    def prepare(self):
        self.send_angles(self.angle_table["prepare"], self.ARM_SPEED)
                
    # Method to return to the initial position
    def recovery(self):
        self.send_angles(self.angle_table["recovery"], self.ARM_SPEED)

    # Method to move to the top of the left discs stack
    def hover_over_stack_left(self):
        self.send_coords(self.angle_table["stack-hover-L"], self.ARM_SPEED_PRECISE, 1)
    
    # Method to move to in front of left discs stack
    def apro_stack_left(self):
        self.send_coords(self.angle_table["stack-apro-L"], self.ARM_SPEED,0)

    # Method to move to the top of the right disks stack
    def hover_over_stack_right(self):
        self.send_coords(self.angle_table["stack-hover-R"], self.ARM_SPEED_PRECISE, 1)
        
    # Method to move to in front of right discs stack
    def apro_stack_right(self):
        self.send_angles(self.angle_table["stack-apro-R-angles"], self.ARM_SPEED)
        # self.send_coords(self.angle_table["stack-apro-R"], self.ARM_SPEED,0)

    def pump_on(self):
        print('pump on')
        self.pump.turn_on_pump()
    
    def pump_off(self):
        print('pump off')
        self.pump.turn_off_pump()
    
    def pump_release(self):
        print('pump release')
        self.pump.release_pump()
    # Method to pick up a disk form stakc level n with thickness t
    def get_disc_yellow(self, counter: int,thickness: int):
        self.temp_target_coords = self.angle_table["stack-hover-R"] 
        self.disc_x_coord=self.DISC_LEVEL+(counter*thickness)
        self.temp_target_coords[0]=self.disc_x_coord
        self.send_coords(self.temp_target_coords, self.ARM_SPEED, 1)
        self.pump_on()
        self.send_coords(self.angle_table["stack-apro-R"], self.ARM_SPEED,1)  
        #self.send_coord(Coord.X.value,self.STACK_ENTRY,self.ARM_SPEED_PRECISE)
	    
    # Method to pick up a disk form stack level n with thickness t
    def get_disc_red(self, counter: int,thickness: int):
        self.temp_target_coords = self.angle_table["stack-hover-L"] 
        self.disc_x_coord=self.DISC_LEVEL+(counter*thickness)
        self.temp_target_coords[0]=self.disc_x_coord
        self.send_coords(self.temp_target_coords, self.ARM_SPEED, 1)
        self.pump_on()
        self.send_coords(self.angle_table["stack-apro-L"], self.ARM_SPEED,1)
        #self.send_coord(Coord.X.value,self.STACK_ENTRY,self.ARM_SPEED_PRECISE)
                    
    # Method to move to the handover window and drop the disk
    def drop_in_window(self):
       #logger.debug("droping disc in window")
       self.send_coords(self.angle_table["handover-window"], self.ARM_SPEED)        
       self.send_coords(self.angle_table["in-window"], self.ARM_SPEED, 1)
       self.pump.release_pump()
       time.sleep(0.5)
       self.pump.turn_off_pump()
       time.sleep(0.5)
       self.send_coords(self.angle_table["handover-window"], self.ARM_SPEED,0) 


    # Method to move to the top of the chessboard
    def hover_over_chessboard_n(self, n: int):
        if n is not None and 0 <= n <= 6:
            # logger.debug(f"Move to chess position {n}, Coords: {self.chess_table[n]}")
            self.send_coords(self.chess_table[n], self.ARM_SPEED)
            self.send_coords(self.drop_table[n], self.ARM_SPEED, 1)
            self.pump_release()
            time.sleep(0.5)
            self.send_coords(self.chess_table[n], self.ARM_SPEED)
        else:
            self.pump_release()
            raise Exception(
                f"Input error, expected chessboard input point must be between 0 and 6, got {n}"
            )

    # Method to move to the observation posture
    def observe_posture(self):
        print(f"Move to observe position {self.angle_table['observe']}")
        self.send_angles(self.angle_table["observe"], self.ARM_SPEED)

    # Method to move the arm
    def move(self, action: str):
        print(f"Action move: {action} Angles {self.angle_table[action]}")
        self.mc.send_angles(self.angle_table[action], self.ARM_SPEED)

    # Method to drop the chess piece
    def drop_piece(self):
        print(f"Dropping piece at {self.mc.get_angles()}")
        self.mc.move_round()

    # Method to Clear the column n
    def clear_column(self, column:int):
        print(f"opening pin under column {column}")
        self.on_current_state_bit(column) # only update the state but NOT change ouptut 
        self.drive_output(self.current_state) # now change outputs 
        time.sleep (self.SOLENOIDE_ON_TIME) 
        self.off_current_state_bit(column) # only update the state but NOT change ouptut 
        self.drive_output(self.current_state) # now change outputs 
        time.sleep(self.SOLENOIDE_SPACE_TIME)

    def check_angles(self):
        self.mc.release_all_servos()
        input("move robot to desired location and press ENTER")
        self.mc.power_on()
        print(self.mc.get_angles())

    def check_coords(self):
        self.mc.release_all_servos()
        input("move robot to desired location and press ENTER")
        self.mc.power_on()
        print(self.mc.get_coords())


    # Method to Clear all colums
    def clear_board(self):
        print(f"clearing board")
        for col in range(7):
            self.clear_column(col)
        self.ylw_disc_taken = 0 
        self.red_disc_taken = 0 

    # method to change head color
    def set_color(self, r:int, g:int, b:int):
        self.mc.set_color(r, g, b)

def test_arm():
    arm = ArmInterface("COM11", 115200)
    arm.mc.power_on()
    arm.prepare()
    input()
    arm.apro_stack_left()
    input()
    arm.get_disc_red(2, 10)
    arm.pump_on()
    input()
    arm.apro_stack_left()
    arm.pump_off()
    arm.prepare()
    arm.observe_posture()
    input()
    arm.hover_over_chessboard_n(0)
    input()
    arm.prepare()
    input()