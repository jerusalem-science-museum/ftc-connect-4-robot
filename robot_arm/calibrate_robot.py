import json
from time import sleep
from pymycobot import MyCobot280 as MyCobot

import serial
import sys
import msvcrt
import threading
from pathlib import Path

# Add connect4_engine directory to path so "from utils.logger" resolves correctly
# This mimics how main.py works when run from connect4_engine/
connect4_engine_path = Path(__file__).parent.parent / "connect4_engine"
if str(connect4_engine_path) not in sys.path:
    sys.path.insert(0, str(connect4_engine_path))

from hardware.arduino import ArduinoCommunicator as Arduino

class Calibration:
    def __init__(self, robot: MyCobot):
        self.robot = robot
        self.pump = Arduino(serial.Serial("COM4", 115200))
        self.calibration_data = {}
        self.toggle_f6 = True
        self.toggle_f5 = True
        self.toggle_c = True
    
    def coords_to_angles(self, target_coords):
        """
        Convert coordinates to angles using robot's local reference frame.
        
        Args:
            robot: MyCobot robot instance
            target_coords: [x, y, z, rx, ry, rz] target coordinates
            
        Returns:
            List of 6 joint angles, or None if IK solution failed
        """
        try:
            current_angles = self.robot.get_angles()
            if not current_angles:
                print("Error: Could not get current angles")
                return None
                
            target_angles = self.robot.solve_inv_kinematics(target_coords, current_angles)
            return target_angles
        except Exception as e:
            print(f"Error solving inverse kinematics: {e}")
            return None

    def mark_location(self, name):
        """
        lets user move robot arm to named location then logs location there.
        After marking, saves data, goes to home, and tries to go to the marked location
        using send_angles to verify the angles are valid.
        
        For puck locations (red_first, yellow_first), it will first go to the top of the stack,
        then home, then the desired location to avoid hitting the rim.
        """
        self.robot.power_on()
        sleep(1)
        angles_coords = self.robot.get_angles_coords()
        angles = angles_coords[:6]
        coords = angles_coords[6:]
        self.calibration_data[name] = {
            "angles": angles,
            "coords": coords
        }
        print(f"Marked location '{name}': angles: {angles}, coords: {coords}")
        
        # Save calibration data
        self.save_calibration_data()
        print(f"Calibration data saved")
        
        # Helper function to move to a location by name, with smart routing for puck locations
        
        def _move_to_coords(from_name, to_name, speed=50):
            coords = self.calibration_data[to_name]["coords"]
            if ('red' in from_name or 'yellow' in from_name) and ('red' in to_name or 'yellow' in to_name):
                mode = 1
                mode_name = "linear"
            else:
                mode = 0
                mode_name = "angular"
            print(f"Moving to {to_name} from {from_name}... using mode {mode_name}")
            try:
                self.robot.set_movement_type(mode)
                self.robot.send_coords(coords, speed)
                self.robot.set_movement_type(0)
                sleep(2)  # Wait for movement to complete
                print(f"Arrived at {to_name}")
                return True
            except Exception as e:
                print(f"Error moving to {to_name}: {e}")
                return False

        def move_to_location(loc_name, description, from_location=None):
            """
            Move to a location, automatically routing through 'top' when moving to/from 'first' locations.
            
            Args:
                loc_name: Name of target location
                description: Human-readable description
                from_location: Name of current location (for routing decisions)
            """
            if loc_name not in self.calibration_data:
                print(f"{description} not found, skipping")
                return False
            
            # Check if target is a "first" location
            color = None
            if loc_name in ["red_first", "yellow_first"]:
                color = loc_name.split("_")[0]
            elif from_location in ["red_first", "yellow_first"]:
                color = from_location.split("_")[0]


            if color:
                top_name = f"{color}_top"
                print(f'routing through {color} top of stack')
                success = _move_to_coords(from_location, top_name)
                if not success:
                    return False
                from_location = top_name
            return _move_to_coords(from_location, loc_name)
            
        
        # First, go from current location to home (with smart routing if needed)
        current_location = name  # We're currently at the location we just marked
        move_to_location("home", "home position", from_location=current_location)
        
        # Try to go to the desired location using send_angles (with smart routing)
        print(f"Attempting to move to '{name}' using send_angles...")
        try:
            # Use smart routing when going to the location
            success = move_to_location(name, f"'{name}'", from_location="home")
            
            if success:
                # Verify we reached the location
                actual_angles = self.robot.get_angles()
                if actual_angles:
                    # Check if angles are close (within 5 degrees for each joint)
                    angle_errors = [abs(actual_angles[i] - angles[i]) for i in range(6)]
                    max_error = max(angle_errors)
                    if max_error < 5.0:
                        print(f"✓ Successfully moved to '{name}' (max angle error: {max_error:.1f}°)")
                    else:
                        print(f"⚠ Warning: Movement to '{name}' may have failed (max angle error: {max_error:.1f}°)")
                        print(f"  Target angles: {angles}")
                        print(f"  Actual angles: {actual_angles}")
                else:
                    print(f"⚠ Could not verify movement to '{name}' (could not get angles)")
            else:
                print(f"✗ Failed to move to '{name}' - location may not exist or movement failed")
        except Exception as e:
            print(f"✗ Error moving to '{name}' using send_angles: {e}")
            print(f"  This may indicate impossible angles were recorded")
            import traceback
            traceback.print_exc()
            success = False
            
        self.robot.power_on()
        return success

    def free_arm_except_6(self):
        """
        lets user move robot arm freely.
        """
        self.robot.power_on()
        for i in range(5):
            self.robot.release_servo(i + 1) # release all servos except the last one (servo 6)
            sleep(0.1)

    
    def move_with_keyboard(self, step_size=5.0, rotation_step=5.0):
        """
        Allows user to move robot in xyz plane and adjust head orientation using keyboard controls.
        Position Controls:
        - 'q'/'a': move in -x/+x direction
        - 'w'/'s': move in +y/-y direction  
        - 'e'/'d': move in +z/-z direction
        - Arrow keys: same as above (up=w, down=s, left=q, right=a)
        
        Head Orientation Controls:
        - 'u': Head facing UP
        - 'j': Head facing FORWARD
        - 'm': Head facing DOWN
        - 'i'/'k': adjust rx rotation (+/-)
        - 'o'/'l': adjust ry rotation (+/-)
        - 'p'/';': adjust rz rotation (+/-)
        - 'f': free J5
        
        Other:
        - 'Enter': mark current location
        - 'x': exit keyboard control mode
        
        Args:
            step_size: Step size in mm for xyz movement (default 5.0mm)
            rotation_step: Step size in degrees for rotation adjustment (default 5.0 degrees)
        """
        self.robot.power_on()
        sleep(0.5)
        
        # Get initial position
        current_coords = self.robot.get_coords()
        if not current_coords or len(current_coords) < 6:
            print("Error: Could not get current coordinates")
            return None
        
        # Track movement state
        movement_lock = threading.Lock()
        movement_in_progress = False
        target_coords = current_coords.copy()
        stop_movement_thread = False
        
        def movement_worker():
            """Worker thread that continuously processes movement requests"""
            nonlocal movement_in_progress, target_coords
            last_sent_coords = None
            while not stop_movement_thread:
                coords_to_move = None
                with movement_lock:
                    if not movement_in_progress:
                        # Only move if coordinates have changed (compare values, not list objects)
                        coords_changed = False
                        if last_sent_coords is None:
                            coords_changed = True
                        else:
                            # Check if any coordinate differs by more than 0.1 (to account for floating point)
                            for i in range(6):
                                if abs(target_coords[i] - last_sent_coords[i]) > 0.1:
                                    coords_changed = True
                                    break
                        
                        if coords_changed:
                            coords_to_move = target_coords.copy()
                            movement_in_progress = True
                
                if coords_to_move is not None:
                    try:
                        print(f"[MOVING] x={coords_to_move[0]:.1f}, y={coords_to_move[1]:.1f}, z={coords_to_move[2]:.1f}, "
                              f"rx={coords_to_move[3]:.1f}°, ry={coords_to_move[4]:.1f}°, rz={coords_to_move[5]:.1f}°")
                        
                        # Try different methods to ensure rotation is set correctly
                        # Method 1: Try with mode parameter (mode=1 might be needed for rotation control)
                        rotation_set = False
                        try:
                            # Try mode=1 first (some robots need this for rotation)
                            self.robot.send_coords(coords_to_move, 30, 1)
                            self.robot.send_coords(coords_to_move, 30, 1)
                            self.robot.send_coords(coords_to_move, 30, 1)
                            self.robot.send_coords(coords_to_move, 30, 1)
                            rotation_set = True
                        except TypeError:
                            try:
                                # Try mode=0
                                self.robot.send_coords(coords_to_move, 30, 0)
                                self.robot.send_coords(coords_to_move, 30, 0)
                                self.robot.send_coords(coords_to_move, 30, 0)
                                self.robot.send_coords(coords_to_move, 30, 0)
                                rotation_set = True
                            except TypeError:
                                # If mode parameter doesn't exist, try without it
                                self.robot.send_coords(coords_to_move, 30)
                                self.robot.send_coords(coords_to_move, 30)
                                self.robot.send_coords(coords_to_move, 30)
                                rotation_set = True
                        
                        # Wait a bit for movement to complete
                        sleep(0.5)
                        
                        # Optional: Check if robot reports being in position (non-blocking)
                        # Note: This check might be too strict, so we rely on actual position check below
                        try:
                            if hasattr(self.robot, 'is_in_position'):
                                # Check if robot is in position (mode 1 = coordinate mode)
                                # This is just informational - we'll do actual position check below
                                if not self.robot.is_in_position(coords_to_move, 1):
                                    print("[INFO] Robot reports not in position, will verify with actual coordinates...")
                        except (AttributeError, Exception) as e:
                            # is_in_position not available or failed, skip this check
                            # We'll rely on actual position verification below
                            pass
                        
                        # Get actual position to verify
                        actual_coords = self.robot.get_coords()
                        if actual_coords and len(actual_coords) >= 6:
                            # Check position error (sum of absolute differences in xyz)
                            position_error = (
                                abs(actual_coords[0] - coords_to_move[0]) +
                                abs(actual_coords[1] - coords_to_move[1]) +
                                abs(actual_coords[2] - coords_to_move[2])
                            )
                            # Check rotation error (sum of absolute differences in rx, ry, rz)
                            rotation_error = (
                                abs(actual_coords[3] - coords_to_move[3]) +
                                abs(actual_coords[4] - coords_to_move[4]) +
                                abs(actual_coords[5] - coords_to_move[5])
                            )
                            
                            # Check both position and rotation errors
                            # Position threshold: 15mm total error
                            # Rotation threshold: 10° (strict, since we want correct orientation)
                            position_ok = position_error <= 15
                            rotation_ok = rotation_error <= 10
                            
                            if not position_ok:
                                print(f"[ERROR] Large position error detected!")
                                print(f"  Target: {coords_to_move}")
                                print(f"  Actual: {actual_coords}")
                                print(f"  Position error: {position_error:.1f}mm, Rotation error: {rotation_error:.1f}°")
                                # Don't update last_sent_coords so it will retry
                                raise Exception(f"Position error too large: {position_error:.1f}mm")
                            
                            if not rotation_ok:
                                print(f"[WARNING] Rotation not matching target (error: {rotation_error:.1f}°)")
                                print(f"  Target rotation: rx={coords_to_move[3]:.1f}°, ry={coords_to_move[4]:.1f}°, rz={coords_to_move[5]:.1f}°")
                                print(f"  Actual rotation: rx={actual_coords[3]:.1f}°, ry={actual_coords[4]:.1f}°, rz={actual_coords[5]:.1f}°")
                                
                                # Try to fix rotation by sending coordinates again with different mode or method
                                print("[RETRY] Attempting to correct rotation...")
                                try:
                                    # Try sending again with explicit rotation values
                                    # Some robots need the rotation sent separately or with different mode
                                    retry_coords = actual_coords.copy()
                                    retry_coords[3] = coords_to_move[3]  # rx
                                    retry_coords[4] = coords_to_move[4]  # ry
                                    retry_coords[5] = coords_to_move[5]  # rz
                                    
                                    # Try mode=1 for rotation control
                                    try:
                                        self.robot.send_coords(retry_coords, 30, 1)
                                        self.robot.send_coords(retry_coords, 30, 1)
                                        self.robot.send_coords(retry_coords, 30, 1)
                                        self.robot.send_coords(retry_coords, 30, 1)
                                        self.robot.send_coords(retry_coords, 30, 0)
                                        self.robot.send_coords(retry_coords, 30, 0)
                                        self.robot.send_coords(retry_coords, 30, 0)
                                        self.robot.send_coords(retry_coords, 30, 0)
                                    except TypeError:
                                        try:
                                            self.robot.send_coords(retry_coords, 30, 0)
                                            self.robot.send_coords(retry_coords, 30, 0)
                                            self.robot.send_coords(retry_coords, 30, 0)
                                            self.robot.send_coords(retry_coords, 30, 0)
                                        except TypeError:
                                            self.robot.send_coords(retry_coords, 30)
                                            self.robot.send_coords(retry_coords, 30)
                                            self.robot.send_coords(retry_coords, 30)
                                    
                                    sleep(0.5)
                                    
                                    # Check again
                                    actual_coords_retry = self.robot.get_coords()
                                    if actual_coords_retry and len(actual_coords_retry) >= 6:
                                        rotation_error_retry = (
                                            abs(actual_coords_retry[3] - coords_to_move[3]) +
                                            abs(actual_coords_retry[4] - coords_to_move[4]) +
                                            abs(actual_coords_retry[5] - coords_to_move[5])
                                        )
                                        
                                        if rotation_error_retry > 10:
                                            print(f"[ERROR] Rotation still incorrect after retry (error: {rotation_error_retry:.1f}°)")
                                            print(f"  This may indicate the robot cannot set rotation via coordinates")
                                            print(f"  You may need to use angles instead of coordinates for rotation control")
                                            # Don't fail completely, but warn
                                        else:
                                            print(f"[OK] Rotation corrected (error: {rotation_error_retry:.1f}°)")
                                            actual_coords = actual_coords_retry
                                except Exception as e:
                                    print(f"[ERROR] Failed to correct rotation: {e}")
                                    raise Exception(f"Rotation error too large: {rotation_error:.1f}°")
                        
                        last_sent_coords = coords_to_move.copy()
                        print(f"[OK] Movement completed x={coords_to_move[0]:.1f}, y={coords_to_move[1]:.1f}, z={coords_to_move[2]:.1f}, "
                              f"rx={coords_to_move[3]:.1f}°, ry={coords_to_move[4]:.1f}°, rz={coords_to_move[5]:.1f}°")
                        print(f'current coords: {actual_coords}')
                    except Exception as e:
                        print(f"[ERROR] Could not move to position: {e}")
                        import traceback
                        traceback.print_exc()
                        # Revert to actual position
                        try:
                            actual_coords = self.robot.get_coords()
                            if actual_coords and len(actual_coords) >= 6:
                                with movement_lock:
                                    target_coords[:] = actual_coords
                                    last_sent_coords = actual_coords.copy()
                        except Exception as e2:
                            print(f"[ERROR] Could not get actual coordinates: {e2}")
                    finally:
                        with movement_lock:
                            movement_in_progress = False
                
                # Small delay between checks (movement itself is blocking, so this only matters between movements)
                sleep(0.05)
        
        # Start movement worker thread
        movement_thread = threading.Thread(target=movement_worker)
        movement_thread.daemon = True
        movement_thread.start()
        print("[INFO] Movement worker thread started")
        
        # Preset orientations (rx, ry, rz)
        # To flip the head direction, we need to flip the last joint (rz) by 180 degrees
        # and adjust ry to point the arm up/down
        ORIENTATION_PRESETS = {
            'u': [0, 0, 90],        # Head facing UP: ry=90, rz will be flipped 180° from forward
            'j': [0, 0, -45],          # Head facing FORWARD: baseline orientation
            'm': [0, 0, -90],       # Head facing DOWN: ry=-90, rz will be flipped 180° from forward
        }
        
        print("\n=== Keyboard Control Mode ===")
        print("Position Controls:")
        print("  q/a or ←/→ : Move in -x/+x direction")
        print("  w/s or ↑/↓ : Move in +y/-y direction")
        print("  e/d         : Move in +z/-z direction")
        print("\nHead Orientation Controls:")
        print("  u           : Head facing UP")
        print("  j           : Head facing FORWARD")
        print("  m           : Head facing DOWN")
        print("  i/k         : Adjust rx rotation (+/-)")
        print("  o/l         : Adjust ry rotation (+/-)")
        print("  [/]         : Adjust rz rotation (+/-)")
        print("  Space       : Enter rx ry rz values directly")
        print("\nOther:")
        print("  z           : Release head turning joint (servo 6) for manual adjustment")
        print("  f           : Free J5 for fixing rotation")
        print("  p           : Print current coordinates")
        print("  Enter       : Mark current location")
        print("  c           : Free all servos")
        print("  x           : Exit keyboard control")
        print(f"\nStep size: {step_size} mm, Rotation step: {rotation_step}°")
        print(f"Current position: x={current_coords[0]:.1f}, y={current_coords[1]:.1f}, z={current_coords[2]:.1f}")
        print(f"Current rotation: rx={current_coords[3]:.1f}°, ry={current_coords[4]:.1f}°, rz={current_coords[5]:.1f}°")
        print("Press a key to move...\n")
        
        while True:
            try:
                # Wait for key press (non-blocking)
                if msvcrt.kbhit():
                    key = msvcrt.getch()
                    
                    moved = False
                    
                    # Handle arrow keys (they start with \xe0)
                    if key == b'\xe0':
                        arrow = msvcrt.getch()
                        if arrow == b'K':  # Left arrow
                            with movement_lock:
                                target_coords[0] -= step_size
                            moved = True
                        elif arrow == b'M':  # Right arrow
                            with movement_lock:
                                target_coords[0] += step_size
                            moved = True
                        elif arrow == b'H':  # Up arrow
                            with movement_lock:
                                target_coords[1] += step_size
                            moved = True
                        elif arrow == b'P':  # Down arrow
                            with movement_lock:
                                target_coords[1] -= step_size
                            moved = True
                    # Handle regular characters
                    elif key == b'q':
                        with movement_lock:
                            target_coords[0] -= step_size
                        moved = True
                    elif key == b'a':
                        with movement_lock:
                            target_coords[0] += step_size
                        moved = True
                    elif key == b'w':
                        with movement_lock:
                            target_coords[1] += step_size
                        moved = True
                    elif key == b's':
                        with movement_lock:
                            target_coords[1] -= step_size
                        moved = True
                    elif key == b'e':
                        with movement_lock:
                            target_coords[2] += step_size
                        moved = True
                    elif key == b'd':
                        with movement_lock:
                            target_coords[2] -= step_size
                        moved = True
                    # Head orientation presets
                    elif key == b'u':  # Head UP
                        with movement_lock:
                            # Use preset values directly
                            target_coords[3] = ORIENTATION_PRESETS['u'][0]  # rx
                            target_coords[4] = ORIENTATION_PRESETS['u'][1]  # ry
                            target_coords[5] = ORIENTATION_PRESETS['u'][2]  # rz
                        moved = True
                        print(f"Head orientation: UP (rx={target_coords[3]:.1f}°, ry={target_coords[4]:.1f}°, rz={target_coords[5]:.1f}°)")
                    elif key == b'j':  # Head FORWARD
                        with movement_lock:
                            target_coords[3] = ORIENTATION_PRESETS['j'][0]
                            target_coords[4] = ORIENTATION_PRESETS['j'][1]
                            target_coords[5] = ORIENTATION_PRESETS['j'][2]
                        moved = True
                        print("Head orientation: FORWARD")
                    elif key == b'm':  # Head DOWN
                        with movement_lock:
                            # Use preset values directly
                            target_coords[3] = ORIENTATION_PRESETS['m'][0]  # rx
                            target_coords[4] = ORIENTATION_PRESETS['m'][1]  # ry
                            target_coords[5] = ORIENTATION_PRESETS['m'][2]  # rz
                        moved = True
                        print(f"Head orientation: DOWN (rx={target_coords[3]:.1f}°, ry={target_coords[4]:.1f}°, rz={target_coords[5]:.1f}°)")
                    # Fine rotation adjustments
                    elif key == b'i':  # Increase rx
                        with movement_lock:
                            target_coords[3] += rotation_step
                        moved = True
                    elif key == b'k':  # Decrease rx
                        with movement_lock:
                            target_coords[3] -= rotation_step
                        moved = True
                    elif key == b'o':  # Increase ry
                        with movement_lock:
                            target_coords[4] += rotation_step
                        moved = True
                    elif key == b'l':  # Decrease ry
                        with movement_lock:
                            target_coords[4] -= rotation_step
                        moved = True
                    elif key == b'[':  # Increase rz
                        with movement_lock:
                            target_coords[5] += rotation_step
                        moved = True
                    elif key == b']':  # Decrease rz
                        with movement_lock:
                            target_coords[5] -= rotation_step
                        moved = True
                    elif key == b' ':  # Space - enter rx ry rz values directly
                        # Switch to blocking input mode to get three values
                        print("\nEnter rx ry rz values (separated by spaces): ", end='', flush=True)
                        try:
                            # Use regular input() for this since we need to read multiple values
                            user_input = input().strip()
                            if user_input:
                                values = user_input.split()
                                if len(values) == 3:
                                    try:
                                        rx_val = float(values[0])
                                        ry_val = float(values[1])
                                        rz_val = float(values[2])
                                        with movement_lock:
                                            target_coords[3] = rx_val
                                            target_coords[4] = ry_val
                                            target_coords[5] = rz_val
                                        moved = True
                                        print(f"Set rotation: rx={rx_val:.1f}°, ry={ry_val:.1f}°, rz={rz_val:.1f}°")
                                    except ValueError:
                                        print("Error: Invalid number format. Please enter three numbers.")
                                else:
                                    print(f"Error: Expected 3 values, got {len(values)}")
                            else:
                                print("Cancelled - no input provided")
                        except EOFError:
                            print("Cancelled")
                        except KeyboardInterrupt:
                            print("\nCancelled")
                    elif key == b'z':  # Release head turning joint (servo 6)
                        try:
                            if self.toggle_f6:
                                # Release servo 6 (the last joint, head turning joint)
                                self.robot.release_servo(6)
                                print("Head turning joint (servo 6) released - you can now manually rotate it")
                                print("Note: Joint will re-engage when you send a movement command")
                            else:
                                self.robot.power_on()
                                print("Head turning joint (servo 6) locked")
                            self.toggle_f6 = not self.toggle_f6
                        except Exception as e:
                            print(f"Error releasing servo 6: {e}")
                            # Try alternative method if release_servo doesn't exist
                            print("Note: You may need to use 'free_arm()' to release all servos")
                    elif key == b'f':  # Free J5 for fixing rotation
                        try:                            
                            if self.toggle_f5:
                                self.robot.free_servo(5)
                                print("J5 freed for fixing rotation")
                            else:
                                self.robot.power_on()
                                print("J5 calibrated")
                            self.toggle_f5 = not self.toggle_f5
                        except Exception as e:
                            print(f"Error freeing J5: {e}")
                    elif key == b'c':  # Free all servos
                        try:
                            if self.toggle_c:
                                self.free_arm_except_6()
                                print("All servos freed")
                            else:
                                self.robot.power_on()
                                print("All servos locked")
                            self.toggle_c = not self.toggle_c
                        except Exception as e:
                            print(f"Error freeing all servos: {e}")
                    elif key == b'p':  # Print current coordinates
                        # Get actual current position from robot
                        try:
                            actual_coords = self.robot.get_coords()
                            actual_angles = self.robot.get_angles()
                            if actual_coords and len(actual_coords) >= 6:
                                print(f"\n=== Current Robot Position ===")
                                print(f"Position: x={actual_coords[0]:.1f}, y={actual_coords[1]:.1f}, z={actual_coords[2]:.1f}")
                                print(f"Rotation: rx={actual_coords[3]:.1f}°, ry={actual_coords[4]:.1f}°, rz={actual_coords[5]:.1f}°")
                                print(f"Full coords: {actual_coords}\n")
                                print(f"Full angles: {actual_angles}\n")
                            else:
                                print("Error: Could not get current coordinates from robot")
                        except Exception as e:
                            print(f"Error getting coordinates: {e}")
                        # Don't set moved = True, so no movement happens
                    elif key == b'\r' or key == b'\n':  # Enter
                        # Wait for any movement to complete
                        while movement_in_progress:
                            sleep(0.1)
                        with movement_lock:
                            final_coords = target_coords.copy()
                        print("\nLocation marked!")
                        stop_movement_thread = True
                        movement_thread.join(timeout=1.0)
                        return final_coords
                    elif key == b'x':
                        # Wait for any movement to complete
                        while movement_in_progress:
                            sleep(0.1)
                        print("\nExiting keyboard control mode")
                        stop_movement_thread = True
                        movement_thread.join(timeout=1.0)
                        return None
                    
                    if moved:
                        with movement_lock:
                            print(f"Position: x={target_coords[0]:.1f}, y={target_coords[1]:.1f}, z={target_coords[2]:.1f}, "
                                  f"rx={target_coords[3]:.1f}°, ry={target_coords[4]:.1f}°, rz={target_coords[5]:.1f}°")
                        # Target updated, movement worker thread will pick it up
                
                sleep(0.05)  # Small delay to prevent excessive CPU usage
                
            except KeyboardInterrupt:
                print("\nKeyboard control interrupted")
                stop_movement_thread = True
                movement_thread.join(timeout=1.0)
                return None
    
    def save_calibration_data(self, filename="robot_coords.json"):
        """
        saves calibration data to a json file.
        """
        with open(filename, "w") as f:
            json.dump(self.calibration_data, f, indent=4)
    
    def load_calibration_data(self, filename="robot_arm/robot_coords.json"):
        """
        loads calibration data from a json file.
        """
        with open(filename, "r") as f:
            self.calibration_data = json.load(f)
    
    def test_move_to(self, name, mode):
        """
        moves robot arm to a named location.
        """
        if name == "pump on":
            self.pump.turn_on_pump()
            return
        elif name == "pump release":
            self.pump.release_pump()
            return
        elif name == "pump off":
            self.pump.turn_off_pump()
            return
        if name not in self.calibration_data:
            print(f"Location '{name}' not found in calibration data.")
            return
        coords = self.calibration_data[name]
        print(f"Moving to location '{name}': {coords}")
        self.robot.power_on()

        if mode == "angles":
            self.robot.sync_send_angles(coords["angles"], 50)
        elif mode == "coords":
            self.robot.sync_send_coords(coords["coords"], 50)
        else:
            print("Invalid mode")
            return

    
    def _calibrate_location(self, name, prompt, use_keyboard, step_size, use_angles=False):
        """
        Helper function to calibrate a single location.
        
        Args:
            name: Name of the location to mark
            prompt: Prompt message to display
            use_keyboard: If True, use keyboard controls
            step_size: Step size for keyboard movement
            use_angles: If True, use sync_send_angles instead of sync_send_coords
        """
        print(prompt)
        if use_keyboard:
            coords = self.move_with_keyboard(step_size)
            if coords:
                if use_angles:
                    self.robot.sync_send_angles(coords, 50)
                else:
                    self.robot.synck_send_coords(coords, 50)
                sleep(0.5)
                self.mark_location(name)
            else:
                print(f"Skipping {name}")
        else:
            self.free_arm_except_6()
            while True:
                input(f"Press Enter when ready to mark {name}")
                success = self.mark_location(name)
                if success:
                    break
    
    def calibrate(self, use_keyboard=False, step_size=5.0):
        """
        Calibrate robot positions.
        
        Args:
            use_keyboard: If True, use keyboard controls to move robot. If False, use manual movement.
            step_size: Step size in mm for keyboard movement (default 5.0mm)
        """
        # Define all calibration steps as a list of dicts
        calibration_steps = [
            {
                "section": "Calibrating robot...",
                "locations": [
                    {"name": "home", "prompt": "Move arm to home position", "use_angles": True}
                ]
            },
            {
                "section": "Now marking puck stack positions...",
                "locations": [
                    {"name": "red_top", "prompt": "Move arm to red top of stack position"},
                    {"name": "red_first", "prompt": "Move arm to red first disk position"},
                    {"name": "yellow_top", "prompt": "Move arm to yellow top of stack position"},
                    {"name": "yellow_first", "prompt": "Move arm to yellow first disk position"},
                ]
            },
            {
                "section": "Marking player dropoff location...",
                "locations": [
                    {"name": "player_dropoff", "prompt": "Move arm to player dropoff position"}
                ]
            },
            {
                "section": "Now marking column positions...",
                "locations": [
                    {"name": f"column_{i}", "prompt": f"Move arm to column {i} position"}
                    for i in range(7)
                ]
            }
        ]
        
        try:
            for step_group in calibration_steps:
                print(f"\n{step_group['section']}")
                for location in step_group["locations"]:
                    self._calibrate_location(
                        location["name"],
                        location["prompt"],
                        use_keyboard,
                        step_size,
                        use_angles=location.get("use_angles", False)
                    )

            self.save_calibration_data()
            print("\nCalibration data saved to robot_coords.json")
        except KeyboardInterrupt:
            print("\nCalibration interrupted")
            self.robot.release_all_servos()
            self.save_calibration_data()
            print("Calibration data saved to robot_coords.json")
            return
    
    def play(self, mode="angles"):
        self.load_calibration_data()
        print(f"Playing in {mode} mode")
        print("Press Enter to move to next location")
        print("Press Ctrl+C to stop")
        input()
        while True:
            try:
                loc = input("Enter location to move to (or 'exit' to quit): ")
                if loc.lower() == 'exit':
                    break
                self.test_move_to(loc, mode)
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    m = MyCobot("COM11")  # adjust port as needed
    calibration = Calibration(m)
    calibration.calibrate()
    # todo: understand why get_angles() can give you angles that you can't send back to the robot.
    # calibration.play()