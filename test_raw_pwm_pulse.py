#!/usr/bin/env python3
"""
Diagnostic Test Script 2: Low-Level Raw PCA9685 PWM Pulse Test

Sends direct raw PWM pulse widths (e.g., pulse = 150, 300, 450) to the PCA9685
channel without any degree math or soft constraint filters.

This tests if the PCA9685 PWM chip & Servo Power Rail are physically operating.

Usage:
  python3 test_raw_pwm_pulse.py [--channel 5] [--port /dev/ttyUSB1]
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
                if any(kw in line for kw in ["_OK", "STATE_", "ERROR_"]):
                    break
        time.sleep(0.02)
    return lines

def main():
    parser = argparse.ArgumentParser(description="Low-Level Raw PWM Pulse Test")
    parser.add_argument("--port", type=str, default=None, help="Serial port")
    parser.add_argument("--channel", type=int, default=5, help="PCA9685 channel to test (default: 5 - Gripper)")

    args = parser.parse_args()
    port = detect_port(args.port)
    ch = args.channel

    print(f"Connecting to Arduino on {port}...")
    try:
        ser = serial.Serial(port, 115200, timeout=1.0)
    except Exception as e:
        print(f"[!] Could not open {port}: {e}")
        sys.exit(1)

    print("Waiting 2.5s for Arduino to settle...")
    time.sleep(2.5)

    while ser.in_waiting:
        line = ser.readline().decode("ascii", errors="replace").strip()
        if line:
            print(f"  [Boot] {line}")

    print("\n" + "=" * 65)
    print(f" RAW PCA9685 PWM PULSE DIAGNOSTIC TEST (Channel {ch})")
    print("=" * 65)
    print(" This sends raw 12-bit PWM pulse ticks (140 = 0.7ms, 350 = 1.5ms, 520 = 2.3ms).")
    print(" Standard 50Hz Servo Range: ~140 (min) to ~550 (max)")
    print("-" * 65)

    pulses_to_test = [180, 300, 420, 300]
    for p in pulses_to_test:
        print(f" -> Sending raw PWM pulse width {p} to Channel {ch}...")
        resp = send_cmd(ser, f"PULSE {ch} {p}")
        if not resp:
            # Fallback to direct channel command
            resp = send_cmd(ser, f"{ch} {p}")
        print(f"    Arduino Response: {', '.join(resp)}")
        time.sleep(1.5)

    print("\n[+] Raw PWM pulse test finished. Did the servo move during pulse changes?")
    ser.close()

if __name__ == "__main__":
    main()
