#!/usr/bin/env python3
"""
Diagnostic Test Script 3: Serial Communication & Arduino Hardware Status Test

Sends basic query commands (STATUS, GETGRIPPER, GETPICKUP) over Serial
to verify Arduino microcontroller response and EEPROM state.

Usage:
  python3 test_i2c_pca9685.py [--port /dev/ttyUSB1]
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
                if any(kw in line for kw in ["_OK", "STATE_", "ERROR_", "GRIPPER_", "PICKUP_"]):
                    break
        time.sleep(0.02)
    return lines

def main():
    parser = argparse.ArgumentParser(description="Arduino Serial & EEPROM Status Test")
    parser.add_argument("--port", type=str, default=None, help="Serial port")

    args = parser.parse_args()
    port = detect_port(args.port)

    print(f"Connecting to Arduino on {port}...")
    try:
        ser = serial.Serial(port, 115200, timeout=1.0)
    except Exception as e:
        print(f"[!] Could not open {port}: {e}")
        sys.exit(1)

    print("Waiting 2.5s for Arduino to settle...")
    time.sleep(2.5)

    print("\n" + "=" * 65)
    print(" ARDUINO SERIAL & HARDWARE STATE DIAGNOSTICS")
    print("=" * 65)

    # 1. Query Arm State
    print(" 1. Querying Arm Operational State (STATUS)...")
    resp = send_cmd(ser, "STATUS")
    print(f"    Arduino Response: {', '.join(resp)}")

    # 2. Query Gripper Calibration
    print("\n 2. Querying Gripper Calibration (GETGRIPPER)...")
    resp = send_cmd(ser, "GETGRIPPER")
    print(f"    Arduino Response: {', '.join(resp)}")

    # 3. Query Cardboard Pickup Calibration
    print("\n 3. Querying Dock Pickup Angles (GETPICKUP)...")
    resp = send_cmd(ser, "GETPICKUP")
    print(f"    Arduino Response: {', '.join(resp)}")

    print("\n" + "=" * 65)
    if resp:
        print("[+] SUCCESS: Arduino is responding properly over Serial link!")
    else:
        print("[!] WARNING: Arduino did not send back data. Check USB cable.")
    print("=" * 65)

    ser.close()

if __name__ == "__main__":
    main()
