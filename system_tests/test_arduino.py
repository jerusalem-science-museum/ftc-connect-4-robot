"""
Arduino component tests: LED detection (serial monitor) and solenoids (OPEN/CLOSE/RESET).
Run from project root:
  python -m system_tests.test_arduino led --port COM5
  python -m system_tests.test_arduino solenoids --port COM5 [--reset]
"""
import argparse
import sys
import time

import serial


def cmd_led(port: str):
    """Read serial and print every line (highlight DROP/START)."""
    print(f"Listening on {port}. Trigger drops or START button. Ctrl+C to exit.")
    with serial.Serial(port, 115200) as ser:
        while True:
            try:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
            except KeyboardInterrupt:
                break
            if not line:
                continue
            if line.startswith("DROP "):
                print(f"  >>> DROP: column {line.split()[1]}")
            elif line == "START":
                print("  >>> START")
            else:
                print(f"  {line}")


def cmd_solenoids(port: str, do_reset: bool):
    """Send OPEN, wait, CLOSE; optionally RESET."""
    with serial.Serial(port, 115200, timeout=1) as ser:
        def send(msg: str):
            ser.write(f"{msg}\n".encode("utf-8"))
            print(f"Sent: {msg}")

        send("OPEN")
        time.sleep(2)
        # Drain any LOG lines
        while ser.in_waiting:
            ser.readline()
        send("CLOSE")
        time.sleep(1)
        if do_reset:
            send("RESET 0000000")
            time.sleep(0.5)
            while ser.in_waiting:
                print(ser.readline().decode("utf-8", errors="ignore").strip())
    print("Done.")


def main():
    parser = argparse.ArgumentParser(description="Arduino tests: LED detection or solenoids.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    led_p = sub.add_parser("led", help="Serial monitor for DROP/START (LED detection)")
    led_p.add_argument("--port", required=True, help="Arduino COM port")
    sol_p = sub.add_parser("solenoids", help="Test OPEN/CLOSE (and optional RESET)")
    sol_p.add_argument("--port", required=True, help="Arduino COM port")
    sol_p.add_argument("--reset", action="store_true", help="Send RESET 0000000 after CLOSE")

    args = parser.parse_args()
    if args.cmd == "led":
        cmd_led(args.port)
    else:
        cmd_solenoids(args.port, args.reset)


if __name__ == "__main__":
    main()
