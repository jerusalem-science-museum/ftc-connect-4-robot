"""
Robot location test: run the arm through a safe sequence, then enter edit mode
after each step (nudge X/Y/Z, release/lock motors, save to JSON, next).
Run from project root: python -m system_tests.test_robot_locations --port COM11 [--json-path PATH]
"""
import argparse
import json
import re
import sys
from pathlib import Path
import serial
from connect4_engine.hardware.arduino import ArduinoCommunicator
from connect4_engine.hardware.mock import ArduinoPumpNoOp
from connect4_engine.hardware.robot import RobotCommunicator
from connect4_engine.utils.config import resolve_port
from time import sleep
# Project root (parent of system_tests)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_JSON_PATH = PROJECT_ROOT / "connect4_engine" / "hardware" / "legacy_coords.json"

def get_puck_pickup_sequence(side="R"):
    """Sequence to mark each puck location in the stack, top to bottom.
    Picks up each puck, returns to hover, discards, then moves to next."""
    steps = []
    steps.append(("observe", "angles", ("angle_table", "observe"), 100, None))
    steps.append(("prepare", "angles", ("angle_table", "prepare"), 100, None))
    steps.append((f"stack-hover-{side}", "coords", ("angle_table", f"stack-hover-{side}"), 50, 0))
    for i in range(21):
        steps.append((f"stack-{side}-{i}", "coords", ("angle_table", f"stack-{side}-{i}"), 50, 1))
        steps.append(("pump-on", "pump", None, None, None))
        sleep(0.5)
        steps.append(("pump-off", "pump", None, None, None))
        steps.append((f"stack-hover-{side}", "coords", ("angle_table", f"stack-hover-{side}"), 50, 1))
        steps.append((f"discard-puck-{side}", "coords", ("angle_table", f"discard-puck-{side}"), 50, 0))
        steps.append(("pump-release", "pump", None, None, None))
        steps.append((f"stack-hover-{side}", "coords", ("angle_table", f"stack-hover-{side}"), 50, 0))
    return steps

def test_infinite_drop():
    """
    the big one. just try to play infinite times, reset and everything. simulate the whole game.
    """
    steps = []
    steps.append(("observe", "angles", ("angle_table", "observe"), 100, None))
    steps.append(("prepare", "angles", ("angle_table", "prepare"), 100, None))
    steps.append(("stack-hover-L", "coords", ("angle_table", "stack-hover-L"), 50, 0))
    steps.append(("stack-hover-L-pickup", "coords", ("angle_table", "stack-hover-L-pickup"), 50, 1))
    # for(i in range(30)):
    pass

def get_drop_table_sequence():
    steps = []
    steps.append(("prepare", "angles", ("angle_table", "prepare"), 100, None))
    steps.append(("observe", "angles", ("angle_table", "observe"), 100, None))
    for n in range(7):
        steps.append((f"chess_{n}", "coords", ("chess_table", n), 100, 0))
        steps.append((f"drop_{n}", "coords", ("drop_table", n), 100, 1))
        steps.append((f"chess_{n}_back", "coords", ("chess_table", n), 100, 0))
    steps.append(("observe", "angles", ("angle_table", "observe"), 100, None))
    steps.append(("handover-window", "coords", ("angle_table", "handover-window"), 100, 0))
    steps.append(("in-window", "coords", ("angle_table", "in-window"), 100, 1))
    steps.append(("handover-window_back", "coords", ("angle_table", "handover-window"), 100, 0))
    return steps

def get_puck_sequence():
    """Build the safe sequence of steps (name, kind, key, speed, mode)."""
    steps = []
    steps.append(("observe", "angles", ("angle_table", "observe"), 100, None))
    steps.append(("prepare", "angles", ("angle_table", "prepare"), 100, None))
    steps.append(("stack-hover-L", "coords", ("angle_table", "stack-hover-L"), 50, 0))
    steps.append(("stack-hover-L-pickup", "coords", ("angle_table", "stack-hover-L-pickup"), 50, 1))
    steps.append(("stack-hover-L", "coords", ("angle_table", "stack-hover-L"), 50, 1))
    steps.append(("prepare", "angles", ("angle_table", "prepare"), 100, None))
    steps.append(("stack-hover-R", "coords", ("angle_table", "stack-hover-R"), 50, 0))
    steps.append(("stack-hover-R-pickup", "coords", ("angle_table", "stack-hover-R-pickup"), 50, 0))
    steps.append(("stack-hover-R", "coords", ("angle_table", "stack-hover-R"), 50, 0))
    steps.append(("prepare", "angles", ("angle_table", "prepare"), 100, None))
    steps.append(("observe", "angles", ("angle_table", "observe"), 100, None))
    return steps


def get_value(coord_json, key):
    t, k = key
    try:
        return coord_json[t][k]
    except (KeyError, IndexError):
        return None


def set_value(coord_json, key, value):
    t, k = key
    if t not in coord_json:
        coord_json[t] = {}
    if isinstance(coord_json[t], list):
        coord_json[t][k] = list(value)
    else:
        coord_json[t][k] = list(value) if isinstance(value, (list, tuple)) else value


def run_step(robot, coord_json, step):
    name, kind, key, speed, mode = step
    if kind == "pump":
        if name == "pump-on":
            robot._pump_on()
        elif name == "pump-release":
            robot.pump_release_and_off()
        elif name == "pump-off":
            robot._pump_off()
        return name, kind, key, True
    value = get_value(coord_json, key)
    if value is None:
        print(f"  (no saved position for {key[1]} — skipping move)")
        return name, kind, key, False
    if kind == "angles":
        robot.send_angles(value, speed)
    else:
        robot.send_coords(value, speed, mode)
    return name, kind, key, True


def edit_mode_loop(robot: RobotCommunicator, coord_json, step, json_path, step_index, nudge_mm=3, moved=True):
    """Keyboard loop: nudge X/Y/Z, release, lock, save, next."""
    name, kind, key = step
    print(f"\n[Edit mode] Step: {name} (index {step_index})")
    print("  1/u/+X  2/d/-X  3/r/+Y  4/l/-Y  5/i/+Z  6/o/-Z  |  x/y/z[+-]<mm>[l]  |  'l'=linear  g=get pos  R=release  L=lock  v=save  n=next  N=next (no move)")

    # Initialize base coordinate from JSON (or current robot pos if we skipped the move)
    if kind == "coords":
        saved = get_value(coord_json, key)
        base = list(saved) if (moved and saved is not None) else list(robot.get_current_coords())
        offset = [0, 0, 0]  # Accumulated offset for X, Y, Z only
    else:
        base = None
        offset = None

    # Track last direction per axis for repeat nudge
    last_sign = {0: 1, 1: 1, 2: 1}  # x, y, z
    
    while True:
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("Abort.")
            sys.exit(0)
        if not raw:
            continue
        cmd = raw[0]
        if cmd == "n":
            print("Next step (no save).")
            return
        if cmd == "N":
            print("Next step (no move, no save).")
            return "skip_move"
        if cmd.lower() == "v":
            if kind == "angles":
                current = robot.get_current_angles()
            else:
                # For coords, save base + accumulated offset instead of reading from robot
                target = base.copy()
                for i in range(3):
                    target[i] = base[i] + offset[i]
                current = target
            if current is None:
                print("Could not read current position.")
                continue
            set_value(coord_json, key, current)
            with open(json_path, "w") as f:
                json.dump(coord_json, f, indent=2)
            print(f"Saved to {json_path}")
            return
        if cmd.lower() == "g":
            if kind == "angles":
                pos = robot.get_current_angles()
                label = "Angles"
            else:
                pos = robot.get_current_coords()
                label = "Coords"
            if pos is None:
                print("Could not read current position.")
            else:
                print(f"{label}: {pos}")
            continue
        if cmd == "R":
            robot.release_servos()
            print("Servos released. Move arm by hand, then press 'L' to lock.")
            continue
        if cmd == "L":
            robot.lock_servos()
            print("Servos locked.")
            continue
        # Map spatial keys: u/d=X+/-, r/l=Y+/-, i/o=Z+/-
        spatial_map = {"u": "1", "d": "2", "r": "3", "l": "4", "i": "5", "o": "6"}
        cmd_lower = cmd.lower()
        if cmd_lower in spatial_map:
            cmd = spatial_map[cmd_lower]
        # Parse axis nudge: x/y/z[+-][mm] or [lrudio][mm]
        axis_match = re.match(r'^([xyz])([+-]?)(\d*\.?\d*)(l?)$', raw, re.IGNORECASE)
        spatial_nudge = re.match(r'^([lrudio])(\d*\.?\d*)(l?)$', raw.lower())
        if axis_match or spatial_nudge or cmd in "123456":
            if kind != "coords":
                print("Nudge only for coord steps. Use release/lock for angle steps.")
                continue

            if axis_match:
                axis_char, sign_char, amount_str, linear_flag = axis_match.groups()
                axis_idx = {"x": 0, "y": 1, "z": 2}[axis_char.lower()]
                if sign_char:
                    last_sign[axis_idx] = 1 if sign_char == "+" else -1
                amount = float(amount_str) if amount_str else nudge_mm
                move_mode = 1 if linear_flag.lower() == "l" else 0
                offset[axis_idx] += last_sign[axis_idx] * amount
            elif spatial_nudge:
                key_char, amount_str, linear_flag = spatial_nudge.groups()
                # l=-Y r=+Y u=+X d=-X i=+Z o=-Z
                spatial_axis = {"u": (0, 1), "d": (0, -1), "r": (1, 1), "l": (1, -1), "i": (2, 1), "o": (2, -1)}
                axis_idx, sign = spatial_axis[key_char]
                last_sign[axis_idx] = sign
                amount = float(amount_str) if amount_str else nudge_mm
                move_mode = 1 if linear_flag == "l" else 0
                offset[axis_idx] += sign * amount
            else:
                idx = int(cmd) - 1
                # 0:+X 1:-X 2:+Y 3:-Y 4:+Z 5:-Z
                axis_idx = idx // 2
                sign = 1 if idx % 2 == 0 else -1
                last_sign[axis_idx] = sign
                offset[axis_idx] += sign * nudge_mm
                move_mode = 0

            # Compute target as base + accumulated offset
            target = base.copy()
            for i in range(3):
                target[i] = base[i] + offset[i]

            if move_mode == 1:
                robot.send_coords_interpolated(target, 50)
            else:
                robot.send_coords(target, 50, 0)
            mode_label = " [interpolated]" if move_mode == 1 else ""
            print(f"Nudged{mode_label}. Offset: X={offset[0]:+.1f} Y={offset[1]:+.1f} Z={offset[2]:+.1f} | Target: {target[:3]}")
            continue
        print("Unknown command. Use 1-6/u d r l i o, x/y/z[+-][mm], R=release, L=lock, v, n.")


def main():
    parser = argparse.ArgumentParser(description="Robot location test with edit mode after each step.")
    robot_port = resolve_port("robot")
    parser.add_argument("--port", default=robot_port, help="Robot COM port")
    parser.add_argument("--json-path", type=Path, default=None, help="Locations JSON (default: connect4_engine/hardware/legacy_coords.json)")
    parser.add_argument("--no-edit", action="store_true", help="Run sequence without entering edit mode")
    parser.add_argument("--nudge-mm", type=float, default=3, help="Nudge step in mm (default 3)")
    args = parser.parse_args()

    json_path = args.json_path or DEFAULT_JSON_PATH
    if not json_path.exists():
        print(f"JSON not found: {json_path}")
        sys.exit(1)

    with open(json_path, "r") as f:
        coord_json = json.load(f)

    seq = input("which sequence? \n1. get puck sequence\n2. drop positions\n3. puck pickup (R)\n4. puck pickup (L)\n")
    needs_pump = seq in ('3', '4')
    if needs_pump:
        ard_port = resolve_port("arduino")
        pump = ArduinoCommunicator(ser=serial.Serial(ard_port, 115200))
        robot = RobotCommunicator(com_port=args.port, pump=pump, coord_json=coord_json)
    else:
        pump = ArduinoPumpNoOp()
        robot = RobotCommunicator(com_port=args.port, coord_json=coord_json)

    if (seq == '1'):
        sequence = get_puck_sequence()
    if (seq == '2'):
        sequence = get_drop_table_sequence()
    if (seq == '3'):
        sequence = get_puck_pickup_sequence("R")
    if (seq == '4'):
        sequence = get_puck_pickup_sequence("L")
    print(f"Running {len(sequence)} steps. Port={args.port}, JSON={json_path}")

    skip_move = False
    for i, step in enumerate(sequence):
        name, kind, key, speed, mode = step
        print(f"\n--- Step {i + 1}/{len(sequence)}: {name} ---")
        if skip_move:
            print("(skipped move — nudging from current position)")
            moved = False
            skip_move = False
        else:
            *_, moved = run_step(robot, coord_json, step)
        if not args.no_edit and kind != "pump":
            result = edit_mode_loop(robot, coord_json, (name, kind, key), json_path, i, moved=moved)
            if result == "skip_move":
                skip_move = True

    print("\nSequence done.")


if __name__ == "__main__":
    main()
