"""
Example of how to use linear movement with send_angles in pymycobot.

Linear movement means the end effector moves in a straight line in Cartesian space,
rather than each joint moving independently (angular movement).
"""

from time import sleep
from pymycobot import MyCobot280 as MyCobot

# Initialize robot
robot = MyCobot("COM11")  # Adjust port as needed
robot.power_on()
sleep(1)

# Method 1: Set movement type globally, then use send_angles
print("Setting movement type to LINEAR (movel)")
robot.set_movement_type(1)  # 1 = linear movement (movel), 0 = angular (moveJ)

# Now all subsequent send_angles calls will use linear movement
target_angles = [0, 0, 0, 0, 0, 0]  # Example angles
robot.sync_send_angles(target_angles, 50)
print("Moved to target using linear movement")

# Switch back to angular movement if needed
print("Switching back to ANGULAR movement (moveJ)")
robot.set_movement_type(0)  # 0 = angular movement (default)
robot.sync_send_angles(target_angles, 50)
print("Moved to target using angular movement")

# Method 2: Check current movement type
current_type = robot.get_movement_type()
print(f"Current movement type: {current_type} (1=linear, 0=angular)")

# Method 3: Helper function to send angles with specified movement type
def send_angles_linear(robot, angles, speed=50, timeout=15):
    """Send angles with linear movement"""
    robot.set_movement_type(1)  # Set to linear
    try:
        robot.sync_send_angles(angles, speed, timeout)
    finally:
        robot.set_movement_type(0)  # Reset to angular (default)

def send_angles_angular(robot, angles, speed=50, timeout=15):
    """Send angles with angular movement (default)"""
    robot.set_movement_type(0)  # Set to angular
    robot.sync_send_angles(angles, speed, timeout)

# Example usage
angles1 = [10, 20, 30, 40, 50, 60]
angles2 = [15, 25, 35, 45, 55, 65]

# Move with linear interpolation
print("\nMoving with linear interpolation...")
send_angles_linear(robot, angles1, 50)

# Move with angular interpolation (default)
print("Moving with angular interpolation...")
send_angles_angular(robot, angles2, 50)

print("\nDone!")




