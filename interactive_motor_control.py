#!/usr/bin/env python3
"""
PostureGuard - Interactive Individual Motor Control Tool

An interactive CLI tool to control and test individual servo motors on the 6-DOF Robotic Arm:
- Channel 0: Waist / Base (360° Continuous Rotation Servo)
- Channel 1: Shoulder Joint (MG995 180° Positional Servo)
- Channel 2: Elbow Joint (MG995 180° Positional Servo)
- Channel 3: Wrist Roll (SG90 Servo)
- Channel 4: Wrist Pitch (SG90 180° Positional Servo)
- Channel 5: Gripper Claw (MG90S 180° Metal-Gear Servo)

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
    # Priority for standard Linux and Windows device names
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

class ArmController:
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

        print("Waiting 2.5s for Arduino initialization & boot recovery...")
        time.sleep(2.5)

        # Drain boot lines
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
        cmd_str = cmd.strip() + "\n"
        self.ser.write(cmd_str.encode("ascii"))
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
        if channel not in CHANNEL_INFO:
            print(f"[!] Invalid channel {channel}. Choose 0 through 5.")
            return False

        info = CHANNEL_INFO[channel]
        angle = max(info["min"], min(info["max"], angle))

        cmd = f"{channel} {angle}"
        print(f">>> Moving Channel {channel} ({info['name']}) to {angle}°")
        resp = self.send_command(cmd)
        if resp:
            print(f"    Response: {', '.join(resp)}")
            self.positions[channel] = angle
            return True
        return False

    def move_channel_relative(self, channel, delta):
        current = self.positions.get(channel, CHANNEL_INFO[channel]["default"])
        target = current + delta
        return self.set_channel_angle(channel, target)

    def spin_base(self, direction, duration_ms):
        """Channel 0 CW/CCW continuous rotation"""
        dir_str = "CW" if direction > 0 else "CCW"
        cmd = f"0 {dir_str} {duration_ms}"
        print(f">>> Spinning Base (Channel 0) {dir_str} for {duration_ms} ms")
        resp = self.send_command(cmd)
        if resp:
            print(f"    Response: {', '.join(resp)}")

    def spin_wrist3(self, direction, duration_ms):
        """Channel 3 CW/CCW rotation"""
        dir_str = "CW" if direction > 0 else "CCW"
        cmd = f"3 {dir_str} {duration_ms}"
        print(f">>> Spinning Wrist Roll (Channel 3) {dir_str} for {duration_ms} ms")
        resp = self.send_command(cmd)
        if resp:
            print(f"    Response: {', '.join(resp)}")

    def open_gripper(self):
        print(">>> Opening Gripper Claw (Channel 5)...")
        resp = self.send_command("OPEN")
        print(f"    Response: {', '.join(resp)}")

    def close_gripper(self):
        print(">>> Closing Gripper Claw (Channel 5)...")
        resp = self.send_command("CLOSE")
        print(f"    Response: {', '.join(resp)}")

    def home(self):
        print(">>> Moving Arm to Calibrated Home Dock...")
        resp = self.send_command("HOME", timeout=5.0)
        print(f"    Response: {', '.join(resp)}")
        for ch, info in CHANNEL_INFO.items():
            self.positions[ch] = info["default"]

    def stop_all(self):
        print(">>> Stopping all motors (PWM Cutoff)...")
        resp = self.send_command("STOP")
        print(f"    Response: {', '.join(resp)}")

    def get_status(self):
        resp = self.send_command("STATUS")
        print(f"    Arm Status: {', '.join(resp)}")

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("Serial connection closed.")

def print_menu(controller):
    print("=" * 65)
    print("      POSTUREGUARD - INDIVIDUAL MOTOR CONTROL STUDIO")
    print("=" * 65)
    print(" MOTOR CHANNELS & CURRENT KNOWN ANGLES:")
    for ch in range(6):
        info = CHANNEL_INFO[ch]
        pos = controller.positions.get(ch, info["default"])
        print(f"  Ch {ch}: {info['name']:<18} | Type: {info['type']:<22} | Current: {pos}°")
    print("-" * 65)
    print(" INDIVIDUAL MOTOR CONTROL COMMANDS:")
    print("  <ch> <angle>       : Set channel (0-5) to angle (e.g., '1 90', '5 30')")
    print("  <ch> +<deg>        : Increase angle by degrees (e.g., '1 +10', '4 +5')")
    print("  <ch> -<deg>        : Decrease angle by degrees (e.g., '2 -10', '5 -5')")
    print("  0 cw <ms>          : Spin Base (Ch 0) Clockwise for MS (e.g., '0 cw 200')")
    print("  0 ccw <ms>         : Spin Base (Ch 0) Counter-Clockwise for MS (e.g., '0 ccw 200')")
    print("  3 cw <ms>          : Spin Wrist (Ch 3) CW for MS (e.g., '3 cw 150')")
    print("  3 ccw <ms>         : Spin Wrist (Ch 3) CCW for MS (e.g., '3 ccw 150')")
    print("  open / close       : Open (30°) or Close (-25°) Gripper Claw (Ch 5)")
    print("-" * 65)
    print(" MACRO / PRESET SYSTEM COMMANDS:")
    print("  home               : Park all motors to resting home position")
    print("  block              : Run posture correction blocking sequence")
    print("  retrieve           : Retract arm & return blocker sheet to dock")
    print("  pickup             : Execute cardboard pickup routine")
    print("  putback            : Execute cardboard putback routine")
    print("  stop               : Cut PWM power to all motors immediately")
    print("  status             : Query Arduino arm state")
    print("  q / quit           : Exit controller")
    print("=" * 65)

def interactive_loop(controller):
    while True:
        print_menu(controller)
        try:
            line = input("\nEnter command: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break

        if not line:
            continue

        cmd_lower = line.lower()
        if cmd_lower in ["q", "quit", "exit"]:
            break

        if cmd_lower == "home":
            controller.home()
        elif cmd_lower == "stop":
            controller.stop_all()
        elif cmd_lower == "open":
            controller.open_gripper()
        elif cmd_lower == "close":
            controller.close_gripper()
        elif cmd_lower == "status":
            controller.get_status()
        elif cmd_lower in ["block", "retrieve", "pickup", "putback"]:
            print(f">>> Executing system macro: {line.upper()}")
            resp = controller.send_command(line.upper(), timeout=8.0)
            print(f"    Response: {', '.join(resp)}")
        elif cmd_lower.startswith("0 cw "):
            try:
                ms = int(line.split()[2])
                controller.spin_base(1, ms)
            except Exception:
                print("[!] Syntax error. Usage: 0 cw <ms>")
        elif cmd_lower.startswith("0 ccw "):
            try:
                ms = int(line.split()[2])
                controller.spin_base(-1, ms)
            except Exception:
                print("[!] Syntax error. Usage: 0 ccw <ms>")
        elif cmd_lower.startswith("3 cw "):
            try:
                ms = int(line.split()[2])
                controller.spin_wrist3(1, ms)
            except Exception:
                print("[!] Syntax error. Usage: 3 cw <ms>")
        elif cmd_lower.startswith("3 ccw "):
            try:
                ms = int(line.split()[2])
                controller.spin_wrist3(-1, ms)
            except Exception:
                print("[!] Syntax error. Usage: 3 ccw <ms>")
        else:
            # Check for <ch> <angle> or <ch> +<delta> / <ch> -<delta>
            parts = line.split()
            if len(parts) == 2 and parts[0].isdigit():
                ch = int(parts[0])
                val_str = parts[1]
                if val_str.startswith("+") and val_str[1:].isdigit():
                    controller.move_channel_relative(ch, int(val_str[1:]))
                elif val_str.startswith("-") and val_str[1:].isdigit():
                    controller.move_channel_relative(ch, -int(val_str[1:]))
                elif val_str.lstrip("-").isdigit():
                    controller.set_channel_angle(ch, int(val_str))
                else:
                    print(f"[!] Unrecognized angle format '{val_str}'")
            else:
                # Raw command fallback to Arduino
                print(f">>> Sending raw command to Arduino: '{line}'")
                resp = controller.send_command(line)
                print(f"    Response: {', '.join(resp)}")

        time.sleep(0.1)

def main():
    parser = argparse.ArgumentParser(description="PostureGuard Interactive Individual Motor Control Tool")
    parser.add_argument("--port", type=str, default=None, help="Serial port (default: auto-detected)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--channel", type=int, choices=range(6), help="One-shot: channel to move")
    parser.add_argument("--angle", type=int, help="One-shot: angle to set")
    parser.add_argument("--home", action="store_true", help="One-shot: send arm home")
    parser.add_argument("--stop", action="store_true", help="One-shot: cut motor power")

    args = parser.parse_args()
    port = detect_port(args.port)

    controller = ArmController(port, args.baud)
    if not controller.connect():
        sys.exit(1)

    try:
        if args.home:
            controller.home()
        elif args.stop:
            controller.stop_all()
        elif args.channel is not None and args.angle is not None:
            controller.set_channel_angle(args.channel, args.angle)
        else:
            interactive_loop(controller)
    finally:
        controller.close()

if __name__ == "__main__":
    main()
