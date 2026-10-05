#!/usr/bin/env python3
"""
PostureGuard - Numbered Interactive Motor Control Studio

An easy-to-use numbered menu CLI tool to control individual servo motors on the 6-DOF Robotic Arm:
  [1] Channel 0: Waist / Base (360° Continuous Servo)
  [2] Channel 1: Shoulder Joint (MG995 180° Positional)
  [3] Channel 2: Elbow Joint (MG995 180° Positional)
  [4] Channel 3: Wrist Roll (SG90 Servo)
  [5] Channel 4: Wrist Pitch (SG90 180° Positional)
  [6] Channel 5: Gripper Claw (MG90S 180° Metal-Gear)
  [7] Home Arm (Park to resting position)
  [8] Open Gripper Claw
  [9] Close Gripper Claw
  [10] Deploy Screen Blocker Sequence
  [11] Retrieve Blocker Sequence
  [12] Pickup Cardboard
  [13] Putback Cardboard
  [14] Emergency Stop (Cut PWM Power)
  [0 / q] Quit

Usage:
  python3 interactive_motor_control.py [--port /dev/ttyUSB0] [--baud 115200]
"""

import sys
import time
import argparse
import serial
import serial.tools.list_ports

CHANNEL_INFO = {
    0: {"name": "Waist / Base", "type": "360° Continuous", "default": 90, "min": 0, "max": 360},
    1: {"name": "Shoulder", "type": "180° Positional (MG995)", "default": 135, "min": 0, "max": 180},
    2: {"name": "Elbow", "type": "180° Positional (MG995)", "default": 180, "min": 0, "max": 180},
    3: {"name": "Wrist Roll", "type": "SG90 Servo", "default": 90, "min": 0, "max": 180},
    4: {"name": "Wrist Pitch", "type": "180° Positional (SG90)", "default": 90, "min": 0, "max": 180},
    5: {"name": "Gripper Claw", "type": "180° Metal (MG90S)", "default": -25, "min": -25, "max": 110},
}

def detect_port(requested_port=None):
    if requested_port:
        return requested_port
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        if "ttyUSB" in p.device or "ttyACM" in p.device:
            return p.device
    for p in ports:
        if p.device.upper() in ["COM13", "COM14"]:
            return p.device
    for p in ports:
        desc = (p.description or "").lower()
        if any(kw in desc for kw in ["ch340", "arduino", "usb", "serial"]):
            return p.device
    if ports:
        return ports[0].device
    return "/dev/ttyUSB0"

class NumberedArmController:
    def __init__(self, port, baud=115200):
        self.port = port
        self.baud = baud
        self.ser = None
        self.positions = {ch: info["default"] for ch, info in CHANNEL_INFO.items()}

    def connect(self):
        print(f"Connecting to Arduino on {self.port} at {self.baud} baud...")
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=1.0)
        except Exception as e:
            print(f"[!] Failed to open serial port {self.port}: {e}")
            return False

        print("Initializing connection. Waiting 2.5s...")
        time.sleep(2.5)

        # Drain boot banner
        while self.ser.in_waiting:
            line = self.ser.readline().decode("ascii", errors="replace").strip()
            if line:
                print(f"  [Arduino] {line}")

        print("[+] Connection established successfully!\n")
        return True

    def send_command(self, cmd, timeout=3.0):
        if not self.ser or not self.ser.is_open:
            print("[!] Serial port not open.")
            return []

        self.ser.reset_input_buffer()
        self.ser.write((cmd.strip() + "\n").encode("ascii"))
        self.ser.flush()

        responses = []
        start = time.time()
        while time.time() - start < timeout:
            if self.ser.in_waiting:
                line = self.ser.readline().decode("ascii", errors="replace").strip()
                if line:
                    responses.append(line)
                    if any(kw in line for kw in ["_OK", "STATE_", "ERROR_"]):
                        break
            time.sleep(0.02)
        return responses

    def set_channel_angle(self, channel, angle):
        info = CHANNEL_INFO[channel]
        clamped = max(info["min"], min(info["max"], angle))

        cmd = f"{channel} {clamped}"
        print(f"\n>>> Moving Channel {channel} ({info['name']}) to {clamped}°")
        resp = self.send_command(cmd)
        if resp:
            print(f"    Arduino Response: {', '.join(resp)}")
            self.positions[channel] = clamped
            return True
        return False

    def spin_continuous(self, channel, direction, duration_ms):
        dir_str = "CW" if direction > 0 else "CCW"
        cmd = f"{channel} {dir_str} {duration_ms}"
        print(f"\n>>> Spinning Channel {channel} ({CHANNEL_INFO[channel]['name']}) {dir_str} for {duration_ms} ms")
        resp = self.send_command(cmd)
        if resp:
            print(f"    Arduino Response: {', '.join(resp)}")

    def home(self):
        print("\n>>> Moving Arm to Calibrated Home Position...")
        resp = self.send_command("HOME", timeout=5.0)
        print(f"    Arduino Response: {', '.join(resp)}")
        for ch, info in CHANNEL_INFO.items():
            self.positions[ch] = info["default"]

    def open_gripper(self):
        print("\n>>> Opening Gripper Claw (Channel 5)...")
        resp = self.send_command("OPEN")
        print(f"    Arduino Response: {', '.join(resp)}")
        self.positions[5] = 30

    def close_gripper(self):
        print("\n>>> Closing Gripper Claw (Channel 5)...")
        resp = self.send_command("CLOSE")
        print(f"    Arduino Response: {', '.join(resp)}")
        self.positions[5] = -25

    def stop_all(self):
        print("\n>>> Cutting PWM power to all motors (Emergency Stop)...")
        resp = self.send_command("STOP")
        print(f"    Arduino Response: {', '.join(resp)}")

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("Serial connection closed.")

def print_numbered_menu(controller):
    print("\n" + "=" * 65)
    print("      POSTUREGUARD - NUMBERED MOTOR CONTROL MENU")
    print("=" * 65)
    print(" INDIVIDUAL MOTOR CHANNELS:")
    for num, ch in enumerate([0, 1, 2, 3, 4, 5], start=1):
        info = CHANNEL_INFO[ch]
        pos = controller.positions.get(ch, info["default"])
        print(f"  [{num}] Channel {ch}: {info['name']:<18} (Range: {info['min']}°..{info['max']}°) | Current: {pos}°")
    print("-" * 65)
    print(" SYSTEM PRESET ACTIONS:")
    print("  [7]  Home Arm (Park to resting position)")
    print("  [8]  Open Gripper Claw (30°)")
    print("  [9]  Close Gripper Claw (-25°)")
    print("  [10] Deploy Screen Blocker Sequence")
    print("  [11] Retrieve Blocker Sequence")
    print("  [12] Execute Cardboard Pickup Routine")
    print("  [13] Execute Cardboard Putback Routine")
    print("  [14] Emergency Stop (Cut PWM Power to all motors)")
    print("  [0 / q] Quit")
    print("=" * 65)

def handle_individual_motor_selection(controller, ch):
    info = CHANNEL_INFO[ch]
    pos = controller.positions.get(ch, info["default"])
    print(f"\n--- Selected: [{ch+1}] Channel {ch} - {info['name']} (Current: {pos}°) ---")

    if ch in [0, 3]:
        print(" Options:")
        print("   • Enter target angle (e.g. 90, 120, 180)")
        print("   • Enter relative step (e.g. +10, -10, +5)")
        print("   • Enter continuous spin (e.g. 'cw 200', 'ccw 300')")
    else:
        print(f" Options: Enter angle between {info['min']}° and {info['max']}° (or relative +10, -5)")

    val = input(f" Enter value for Channel {ch}: ").strip()
    if not val:
        return

    val_lower = val.lower()
    if val_lower.startswith("cw "):
        try:
            ms = int(val.split()[1])
            controller.spin_continuous(ch, 1, ms)
        except Exception:
            print("[!] Invalid ms. Example: 'cw 200'")
    elif val_lower.startswith("ccw "):
        try:
            ms = int(val.split()[1])
            controller.spin_continuous(ch, -1, ms)
        except Exception:
            print("[!] Invalid ms. Example: 'ccw 200'")
    elif val.startswith("+") and val[1:].isdigit():
        delta = int(val[1:])
        controller.set_channel_angle(ch, pos + delta)
    elif val.startswith("-") and val[1:].isdigit():
        delta = int(val[1:])
        controller.set_channel_angle(ch, pos - delta)
    elif val.lstrip("-").isdigit():
        ang = int(val)
        controller.set_channel_angle(ch, ang)
    else:
        # Direct raw command fallback
        resp = controller.send_command(f"{ch} {val}")
        print(f"    Arduino Response: {', '.join(resp)}")

def interactive_numbered_loop(controller):
    while True:
        print_numbered_menu(controller)
        try:
            choice = input("\nSelect option number (0-14): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break

        if not choice:
            continue

        if choice in ["0", "q", "quit", "exit"]:
            print("Exiting motor controller studio.")
            break

        # Check Motor numbers [1] to [6]
        if choice in ["1", "2", "3", "4", "5", "6"]:
            ch = int(choice) - 1  # Map option 1->ch0, 2->ch1, etc.
            handle_individual_motor_selection(controller, ch)
        elif choice == "7":
            controller.home()
        elif choice == "8":
            controller.open_gripper()
        elif choice == "9":
            controller.close_gripper()
        elif choice == "10":
            print("\n>>> Executing BLOCK sequence...")
            resp = controller.send_command("BLOCK", timeout=8.0)
            print(f"    Arduino Response: {', '.join(resp)}")
        elif choice == "11":
            print("\n>>> Executing RETRIEVE sequence...")
            resp = controller.send_command("RETRIEVE", timeout=8.0)
            print(f"    Arduino Response: {', '.join(resp)}")
        elif choice == "12":
            print("\n>>> Executing PICKUP sequence...")
            resp = controller.send_command("PICKUP", timeout=8.0)
            print(f"    Arduino Response: {', '.join(resp)}")
        elif choice == "13":
            print("\n>>> Executing PUTBACK sequence...")
            resp = controller.send_command("PUTBACK", timeout=8.0)
            print(f"    Arduino Response: {', '.join(resp)}")
        elif choice == "14":
            controller.stop_all()
        else:
            print("[!] Invalid option number. Please select a number between 0 and 14.")

        time.sleep(0.1)

def main():
    parser = argparse.ArgumentParser(description="PostureGuard Numbered Motor Control Menu")
    parser.add_argument("--port", type=str, default=None, help="Serial port (default: auto-detected)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")

    args = parser.parse_args()
    port = detect_port(args.port)

    controller = NumberedArmController(port, args.baud)
    if not controller.connect():
        sys.exit(1)

    try:
        interactive_numbered_loop(controller)
    finally:
        controller.close()

if __name__ == "__main__":
    main()
