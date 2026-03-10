#!/usr/bin/env python3
"""
Serial Middleman - a transparent proxy between a real serial port (Arduino)
and a PTY (for your Python app), with CLI injection capability.

Usage:
    python serial_middleman.py /dev/ttyUSB0 [--baud 115200]

Your Python app connects to the PTY path printed at startup instead of
the real serial port. Everything is forwarded both ways transparently.

CLI commands (type into stdin while running):
    >hello world     → send "hello world\n" to Arduino
    <hello world     → send "hello world\n" to Python app (via PTY)
    (no prefix)      → defaults to sending to Arduino

    quit / exit      → shut down
"""

import argparse
import os
import pty
import select
import sys
import time
import termios
import tty
import serial


def create_pty():
    """Create a PTY pair and return (master_fd, slave_path)."""
    master_fd, slave_fd = pty.openpty()
    slave_path = os.ttyname(slave_fd)
    os.close(slave_fd)  # the Python app will open it by path
    return master_fd, slave_path


def log(direction: str, data: bytes):
    """Print a readable log line."""
    try:
        text = data.decode("utf-8", errors="replace").rstrip("\r\n")
    except Exception:
        text = repr(data)
    if text:
        label = {"ard→py": "\033[34m ARD→PY \033[0m",
                 "py→ard": "\033[32m PY→ARD \033[0m",
                 "cli→ard": "\033[33m CLI→ARD\033[0m",
                 "cli→py":  "\033[35m CLI→PY \033[0m"}
        print(f"  {label.get(direction, direction)}  {text}")


def run(port: str, baud: int):
    # Open real serial port to Arduino
    ser = serial.Serial(port, baud, timeout=0)
    print(f"Opened Arduino on {port} @ {baud}")

    # Create PTY for the Python app
    master_fd, slave_path = create_pty()
    input("now connect to app")
    print(f"Python app should connect to: \033[1;36m{slave_path}\033[0m")
    print()
    print("Commands:  >msg  → send to Arduino")
    print("           <msg  → send to Python app")
    print("           msg   → send to Arduino (default)")
    print("           quit  → exit")
    print()

    # Make stdin non-blocking-friendly
    stdin_fd = sys.stdin.fileno()

    try:
        while True:
            # Wait for data from any source
            readable, _, _ = select.select(
                [ser.fileno(), master_fd, stdin_fd], [], [], 0.1
            )

            for fd in readable:
                if fd == ser.fileno():
                    # Arduino → Python app
                    data = ser.read(ser.in_waiting or 1)
                    if data:
                        os.write(master_fd, data)
                        log("ard→py", data)

                elif fd == master_fd:
                    # Python app → Arduino
                    try:
                        data = os.read(master_fd, 4096)
                    except OSError:
                        # Slave side not connected yet, back off
                        input("connect app plz")
                        time.sleep(0.5)
                        continue
                    if data:
                        ser.write(data)
                        log("py→ard", data)

                elif fd == stdin_fd:
                    # CLI injection
                    line = sys.stdin.readline()
                    if not line:
                        continue
                    line = line.rstrip("\n")

                    if line.lower() in ("quit", "exit"):
                        print("Shutting down.")
                        return

                    if line.startswith("<"):
                        # Send to Python app
                        msg = line[1:].encode("utf-8") + b"\n"
                        os.write(master_fd, msg)
                        log("cli→py", msg)
                    elif line.startswith(">"):
                        # Send to Arduino
                        msg = line[1:].encode("utf-8") + b"\n"
                        ser.write(msg)
                        log("cli→ard", msg)
                    else:
                        # Default: send to Arduino
                        msg = line.encode("utf-8") + b"\n"
                        ser.write(msg)
                        log("cli→ard", msg)

    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        ser.close()
        os.close(master_fd)
        print("Closed all ports.")


def main():
    parser = argparse.ArgumentParser(description="Serial middleman proxy")
    parser.add_argument("port", nargs="?", default="/dev/ttyUSB0", help="Serial port (default: /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 9600)")
    args = parser.parse_args()
    run(args.port, args.baud)


if __name__ == "__main__":
    main()
