#!/usr/bin/env python3
"""
Diagnostic Test Script 1: Individual Servo Channel Sweep Test

Tests each motor channel (0 to 5) one by one by moving it gently back and forth.
This helps isolate which specific motor or channel is responding.

Usage:
  python3 test_motor_sweep.py [--channel 1] [--port /dev/ttyUSB1]
"""

import sys
import time
import argparse
import serial
import serial.tools.list_ports

CHANNEL_INFO = {
    0: {"name": "Waist / Base (360° Continuous)", "start": 90, "test_cw": 200, "test_ccw": 200},
    1: {"name": "Shoulder Joint (180° Positional)", "start": 135, "min_test": 110, "max_test": 140},
    2: {"name": "Elbow Joint (180° Positional)", "start": 180, "min_test": 150, "max_test": 180},
    3: {"name": "Wrist Roll (SG90)", "start": 90, "min_test": 70, "max_test": 110},
    4: {"name": "Wrist Pitch (SG90 180°)", "start": 90, "min_test": 70, "max_test": 110},
    5: {"name": "Gripper Claw (MG90S 180°)", "start": -25, "min_test": -25, "max_test": 30},
}

def detect_port(requested=None):
    if requested:
        return requested
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        if "ttyUSB" in p.device or "ttyACM" in p.device:
            return p.device
    if ports:
        return ports[0].device
    return "/dev/ttyUSB1"

def send_cmd(ser, cmd, timeout=2.5):
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
                if any(kw in line for kw in ["_OK", "STATE_", "ERROR_"]):
                    break
        time.sleep(0.02)
    return lines

def test_channel(ser, ch):
    info = CHANNEL_INFO[ch]
    print("\n" + "=" * 60)
    print(f" TESTING CHANNEL {ch}: {info['name']}")
    print("=" * 60)

    if ch == 0:
        # Base continuous rotation test
        print(" -> Action 1: Spin Base CW for 300ms...")
        resp = send_cmd(ser, "0 CW 300")
        print(f"    Arduino Response: {', '.join(resp)}")
        time.sleep(1.0)

        print(" -> Action 2: Spin Base CCW for 300ms...")
        resp = send_cmd(ser, "0 CCW 300")
        print(f"    Arduino Response: {', '.join(resp)}")
        time.sleep(1.0)
    else:
        # Positional servo sweep test
        min_ang = info["min_test"]
        max_ang = info["max_test"]

        print(f" -> Move 1: Setting Channel {ch} to {min_ang}°...")
        resp = send_cmd(ser, f"{ch} {min_ang}")
        print(f"    Arduino Response: {', '.join(resp)}")
        time.sleep(1.2)

        print(f" -> Move 2: Setting Channel {ch} to {max_ang}°...")
        resp = send_cmd(ser, f"{ch} {max_ang}")
        print(f"    Arduino Response: {', '.join(resp)}")
        time.sleep(1.2)

        print(f" -> Move 3: Returning Channel {ch} to starting angle ({info['start']}°)...")
        resp = send_cmd(ser, f"{ch} {info['start']}")
        print(f"    Arduino Response: {', '.join(resp)}")
        time.sleep(1.0)

    print(f"[+] Channel {ch} test complete. Did you see/hear the motor move? (y/n)")

def main():
    parser = argparse.ArgumentParser(description="Individual Servo Sweep Diagnostic Test")
    parser.add_argument("--port", type=str, default=None, help="Serial port")
    parser.add_argument("--channel", type=int, choices=range(6), help="Test single channel (0-5)")

    args = parser.parse_args()
    port = detect_port(args.port)

    print(f"Connecting to Arduino on {port}...")
    try:
        ser = serial.Serial(port, 115200, timeout=1.0)
    except Exception as e:
        print(f"[!] Failed to open {port}: {e}")
        sys.exit(1)

    print("Waiting 2.5s for Arduino initialization...")
    time.sleep(2.5)

    # Drain startup logs
    while ser.in_waiting:
        line = ser.readline().decode("ascii", errors="replace").strip()
        if line:
            print(f"  [Boot Output] {line}")

    try:
        if args.channel is not None:
            test_channel(ser, args.channel)
        else:
            print("\nStarting full sweep diagnostic for all 6 motor channels...")
            for ch in range(6):
                test_channel(ser, ch)
                time.sleep(1.0)

            print("\n" + "=" * 60)
            print(" DIAGNOSTIC TEST COMPLETE!")
            print("=" * 60)
    finally:
        ser.close()
        print("Serial port closed.")

if __name__ == "__main__":
    main()
