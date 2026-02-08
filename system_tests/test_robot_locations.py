"""
Robot location test: run the arm through a safe sequence, then enter edit mode
after each step (nudge X/Y/Z, release/lock motors, save to JSON, next).
Run from project root: python -m system_tests.test_robot_locations --port COM11 [--json-path PATH]
"""
import argparse
import json
import sys
from pathlib import Path

# Project root (parent of system_tests)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_JSON_PATH = PROJECT_ROOT / "connect4_engine" / "hardware" / "legacy_coords.json"


def build_sequence():
    """Build the safe sequence of steps (name, kind, key, speed, mode)."""
    steps = []
    # kind = "angles" | "coords", key = ("angle_table", "prepare") or ("chess_table", 0), mode None for angles
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
    steps.append(("observe", "angles", ("angle_table", "observe"), 100, None))
    steps.append(("stack-hover-L", "coords", ("angle_table", "stack-hover-L"), 50, 1))
    steps.append(("stack-apro-L", "coords", ("angle_table", "stack-apro-L"), 100, 0))
    steps.append(("stack-hover-R", "coords", ("angle_table", "stack-hover-R"), 50, 1))
    steps.append(("stack-apro-R", "coords", ("angle_table", "stack-apro-R"), 100, 0))
    steps.append(("recovery", "angles", ("angle_table", "recovery"), 100, None))
    return steps


def get_value(coord_json, key):
    t, k = key
    return coord_json[t][k]


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
    value = get_value(coord_json, key)
    if kind == "angles":
        robot.send_angles(value, speed)
    else:
        robot.send_coords(value, speed, mode)
    return name, kind, key


def edit_mode_loop(robot, coord_json, step, json_path, step_index, nudge_mm=3):
    """Keyboard loop: nudge X/Y/Z, release, lock, save, next."""
    name, kind, key = step
    print(f"\n[Edit mode] Step: {name} (index {step_index})")
    print("  1/+X  2/-X  3/+Y  4/-Y  5/+Z  6/-Z  |  r=release  l=lock  v=save  n=next (no save)")
    while True:
        try:
            raw = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("Abort.")
            sys.exit(0)
        if not raw:
            continue
        cmd = raw[0]
        if cmd == "n":
            print("Next step (no save).")
            return
        if cmd == "v":
            if kind == "angles":
                current = robot.get_current_angles()
            else:
                current = robot.get_current_coords()
            if current is None:
                print("Could not read current position.")
                continue
            set_value(coord_json, key, current)
            with open(json_path, "w") as f:
                json.dump(coord_json, f, indent=2)
            print(f"Saved to {json_path}")
            return
        if cmd == "r":
            robot.release_servos()
            print("Servos released. Move arm by hand, then press 'l' to lock.")
            continue
        if cmd == "l":
            robot.lock_servos()
            print("Servos locked.")
            continue
        if cmd in "123456":
            if kind != "coords":
                print("Nudge only for coord steps. Use release/lock for angle steps.")
                continue
            current = list(robot.get_current_coords() or [0] * 6)
            idx = int(cmd) - 1
            # 0:+X 1:-X 2:+Y 3:-Y 4:+Z 5:-Z
            if idx == 0:
                current[0] += nudge_mm
            elif idx == 1:
                current[0] -= nudge_mm
            elif idx == 2:
                current[1] += nudge_mm
            elif idx == 3:
                current[1] -= nudge_mm
            elif idx == 4:
                current[2] += nudge_mm
            else:
                current[2] -= nudge_mm
            robot.send_coords(current, 50, 0)
            print("Nudged.")
            continue
        print("Unknown command. Use 1-6, r, l, v, n.")


def main():
    parser = argparse.ArgumentParser(description="Robot location test with edit mode after each step.")
    parser.add_argument("--port", default="COM11", help="Robot COM port")
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

    from connect4_engine.hardware.mock import ArduinoPumpNoOp
    from connect4_engine.hardware.robot import RobotCommunicator

    pump = ArduinoPumpNoOp()
    robot = RobotCommunicator(com_port=args.port, pump=pump, coord_json=coord_json)

    sequence = build_sequence()
    print(f"Running {len(sequence)} steps. Port={args.port}, JSON={json_path}")

    for i, step in enumerate(sequence):
        name, kind, key, speed, mode = step
        print(f"\n--- Step {i + 1}/{len(sequence)}: {name} ---")
        run_step(robot, coord_json, step)
        if not args.no_edit:
            edit_mode_loop(robot, coord_json, (name, kind, key), json_path, i, args.nudge_mm)

    print("\nSequence done.")


if __name__ == "__main__":
    main()
