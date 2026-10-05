#!/usr/bin/env python3
"""
Dedicated Motor Diagnostic Test Script for Channel 0, 1, and 2.

Exercises:
  - Channel 0: Waist / Base (360° Continuous Rotation Servo)
  - Channel 1: Shoulder Joint (MG995 180° Positional Servo)
  - Channel 2: Elbow Joint (MG995 180° Positional Servo)

Usage:
  python3 test_ch0_1_2.py [--port /dev/ttyACM0]
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

def send_cmd(ser, cmd, timeout=4.0):
    ser.reset_input_buffer()
    ser.write((cmd.strip() + "\n").encode("ascii"))
    ser.flush()
    time.sleep(0.1)

    lines = []
    start = time.time()
    while time.time() - start < timeout:
        if ser.in_waiting:
            line = ser.readline().decode("ascii", errors="replace").strip()
            if line:
                lines.append(line)
                if any(kw in line for kw in ["_OK", "STATE_", "ERROR_", "COMPLETE"]):
                    break
        time.sleep(0.02)
    return lines

def main():
    parser = argparse.ArgumentParser(description="Test Motor Channels 0, 1, and 2")
    parser.add_argument("--port", type=str, default=None, help="Serial port (auto-detected)")

    args = parser.parse_args()
    port = detect_port(args.port)

    print("=" * 65)
    print(f" TESTING CHANNELS 0 (Base), 1 (Shoulder), 2 (Elbow) ON {port}")
    print("=" * 65)

    try:
        ser = serial.Serial(port, 115200, timeout=1.0)
    except Exception as e:
        print(f"[!] Could not open port {port}: {e}")
        sys.exit(1)

    print("Waiting 2.5s for Arduino to settle...")
    time.sleep(2.5)

    while ser.in_waiting:
        line = ser.readline().decode("ascii", errors="replace").strip()
        if line:
            print(f"  [Boot Output] {line}")

    try:
        print("\n--- TEST 1: CHANNEL 0 (Waist / Base Pan 360°) ---")
        print("  Sending: 0 CW 300 (Spin Clockwise 300ms)...")
        resp = send_cmd(ser, "0 CW 300")
        print(f"  Response: {', '.join(resp)}")
        time.sleep(1.5)

        print("  Sending: 0 CCW 300 (Spin Counter-Clockwise 300ms)...")
        resp = send_cmd(ser, "0 CCW 300")
        print(f"  Response: {', '.join(resp)}")
        time.sleep(1.5)

        print("\n--- TEST 2: CHANNEL 1 (Shoulder Joint MG995) ---")
        print("  Sending: 1 100 (Reaching Forward)...")
        resp = send_cmd(ser, "1 100")
        print(f"  Response: {', '.join(resp)}")
        time.sleep(2.0)

        print("  Sending: 1 135 (Returning to Home 135°)...")
        resp = send_cmd(ser, "1 135")
        print(f"  Response: {', '.join(resp)}")
        time.sleep(1.5)

        print("\n--- TEST 3: CHANNEL 2 (Elbow Joint MG995) ---")
        print("  Sending: 2 140 (Forearm Bend)...")
        resp = send_cmd(ser, "2 140")
        print(f"  Response: {', '.join(resp)}")
        time.sleep(2.0)

        print("  Sending: 2 180 (Returning to Home 180°)...")
        resp = send_cmd(ser, "2 180")
        print(f"  Response: {', '.join(resp)}")
        time.sleep(1.5)

        print("\n--- TEST 4: FIRMWARE INTEGRATED SWEEP (TEST012) ---")
        print("  Sending firmware macro: TEST012 ...")
        resp = send_cmd(ser, "TEST012", timeout=8.0)
        print(f"  Response: {', '.join(resp)}")

        print("\n" + "=" * 65)
        print(" [+] CHANNEL 0, 1, 2 TEST COMPLETE!")
        print("=" * 65)
    finally:
        ser.close()

if __name__ == "__main__":
    main()
