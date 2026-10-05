#!/usr/bin/env python3
"""
PostureGuard - Instant Motor Controller for Channels 0, 1, and 2

Fast interactive controller dedicated strictly to:
  - Channel 0: Base / Waist Pan (360° Continuous)
  - Channel 1: Shoulder Joint (MG995 180°)
  - Channel 2: Elbow Joint (MG995 180°)

Usage:
  python3 run_ch0_1_2.py [--port /dev/ttyACM0]
"""

import sys
import time
import argparse
import serial
import serial.tools.list_ports

def detect_port(requested=None):
    if requested:
        return requested
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        if "ttyACM" in p.device or "ttyUSB" in p.device:
            return p.device
    if ports:
        return ports[0].device
    return "/dev/ttyACM0"

def send_cmd(ser, cmd, timeout=3.0):
    ser.reset_input_buffer()
    ser.write((cmd.strip() + "\n").encode("ascii"))
    ser.flush()
    time.sleep(0.05)

    lines = []
    start = time.time()
    while time.time() - start < timeout:
        if ser.in_waiting:
            line = ser.readline().decode("ascii", errors="replace").strip()
            if line:
                lines.append(line)
                if any(kw in line for kw in ["_OK", "STATE_", "ERROR_"]):
                    break
        time.sleep(0.02)
    return lines

def print_menu():
    print("\n" + "=" * 62)
    print(" 🚀 INSTANT MOTOR CONTROLLER — CHANNELS 0, 1 & 2")
    print("=" * 62)
    print(" QUICK RUN PRESETS:")
    print("  [a] Sweep Channel 0 (Spin Base CW & CCW)")
    print("  [b] Move Channel 1 (Shoulder: 135° -> 90° -> 135°)")
    print("  [c] Move Channel 2 (Elbow: 180° -> 120° -> 180°)")
    print("  [all] Run All 3 Motors in Sequence")
    print("-" * 62)
    print(" MANUAL CONTROLS:")
    print("  0 cw <ms>   : Spin Base CW (e.g. '0 cw 500')")
    print("  0 ccw <ms>  : Spin Base CCW (e.g. '0 ccw 500')")
    print("  1 <angle>   : Set Shoulder angle 0..180 (e.g. '1 90', '1 135')")
    print("  2 <angle>   : Set Elbow angle 0..180 (e.g. '2 140', '2 180')")
    print("  stop        : Emergency Stop (Cut PWM)")
    print("  q           : Exit")
    print("=" * 62)

def main():
    parser = argparse.ArgumentParser(description="Run Channels 0, 1, and 2 Motors")
    parser.add_argument("--port", type=str, default=None, help="Serial port")

    args = parser.parse_args()
    port = detect_port(args.port)

    print(f"Connecting to Arduino on {port}...")
    try:
        ser = serial.Serial(port, 115200, timeout=1.0)
    except Exception as e:
        print(f"[!] Could not open serial port {port}: {e}")
        sys.exit(1)

    print("Waiting 2.5s for Arduino to settle...")
    time.sleep(2.5)

    while ser.in_waiting:
        line = ser.readline().decode("ascii", errors="replace").strip()
        if line:
            print(f"  [Boot] {line}")

    try:
        while True:
            print_menu()
            try:
                cmd = input("\nEnter command (a/b/c/all/0 cw 500/1 90/2 140/q): ").strip()
            except (KeyboardInterrupt, EOFError):
                break

            if not cmd:
                continue

            cmd_lower = cmd.lower()
            if cmd_lower in ["q", "quit", "exit"]:
                print("Exiting...")
                break

            if cmd_lower == "a":
                print("\n>>> Running Channel 0 Base Sweep...")
                print("  Spinning CW 800ms...")
                resp = send_cmd(ser, "0 CW 800")
                print(f"  Response: {', '.join(resp)}")
                time.sleep(1.2)
                print("  Spinning CCW 800ms...")
                resp = send_cmd(ser, "0 CCW 800")
                print(f"  Response: {', '.join(resp)}")

            elif cmd_lower == "b":
                print("\n>>> Moving Channel 1 Shoulder (135° -> 90° -> 135°)...")
                resp = send_cmd(ser, "1 90")
                print(f"  Response: {', '.join(resp)}")
                time.sleep(2.0)
                resp = send_cmd(ser, "1 135")
                print(f"  Response: {', '.join(resp)}")

            elif cmd_lower == "c":
                print("\n>>> Moving Channel 2 Elbow (180° -> 120° -> 180°)...")
                resp = send_cmd(ser, "2 120")
                print(f"  Response: {', '.join(resp)}")
                time.sleep(2.0)
                resp = send_cmd(ser, "2 180")
                print(f"  Response: {', '.join(resp)}")

            elif cmd_lower in ["all", "run"]:
                print("\n>>> Running Channels 0, 1 & 2 Sequential Movement...")
                print("  Step 1: Base Spin...")
                send_cmd(ser, "0 CW 600")
                time.sleep(1.0)
                send_cmd(ser, "0 CCW 600")
                time.sleep(1.0)
                print("  Step 2: Shoulder Reach...")
                send_cmd(ser, "1 90")
                time.sleep(1.5)
                send_cmd(ser, "1 135")
                time.sleep(1.0)
                print("  Step 3: Elbow Bend...")
                send_cmd(ser, "2 120")
                time.sleep(1.5)
                send_cmd(ser, "2 180")
                print("  [+] All 3 motors executed!")

            elif cmd_lower == "stop":
                resp = send_cmd(ser, "STOP")
                print(f"  Response: {', '.join(resp)}")

            else:
                print(f"\n>>> Sending Command: '{cmd}'")
                resp = send_cmd(ser, cmd)
                print(f"  Response: {', '.join(resp)}")

            time.sleep(0.1)

    finally:
        ser.close()
        print("Serial port closed.")

if __name__ == "__main__":
    main()
