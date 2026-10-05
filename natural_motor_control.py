#!/usr/bin/env python3
"""
PostureGuard - Natural Language & Terminal Command Motor Tester

Listens for terminal commands in natural language or direct syntax.
If any motor is specified and able to move, it parses the intent and moves that motor.

Examples of accepted commands:
  - "move shoulder to 90" or "shoulder 90" or "ch 1 90"
  - "elbow 140" or "fold elbow to 180" or "ch 2 180"
  - "wrist pitch 120" or "pitch 90" or "ch 4 90"
  - "wrist roll 90" or "roll cw 200ms" or "ch 3 90"
  - "base 90" or "base cw 200" or "spin base left 300" or "ch 0 90"
  - "open claw" or "close gripper" or "claw 30" or "ch 5 -25"
  - "shoulder +10" or "elbow -15" or "claw +5"
  - "home", "block", "retrieve", "pickup", "putback", "stop", "status"
"""

import sys
import re
import time
import argparse
import serial
import serial.tools.list_ports

# Motor Metadata Mapping
MOTOR_ALIASES = {
    4: ["wrist pitch", "pitch", "wrist4", "wrist 4", "ch4", "ch 4", "channel 4", "channel4", "motor 4", "motor4"],
    3: ["wrist roll", "roll", "wrist3", "wrist 3", "ch3", "ch 3", "channel 3", "channel3", "motor 3", "motor3"],
    5: ["gripper", "claw", "grip", "hand", "ch5", "ch 5", "channel 5", "channel5", "motor 5", "motor5"],
    2: ["elbow", "forearm", "ch2", "ch 2", "channel 2", "channel2", "motor 2", "motor2"],
    1: ["shoulder", "ch1", "ch 1", "channel 1", "channel1", "motor 1", "motor1"],
    0: ["base", "waist", "pan", "ch0", "ch 0", "channel 0", "channel0", "motor 0", "motor0"],
}

MOTOR_LIMITS = {
    0: {"name": "Waist / Base", "min": 0, "max": 360, "default": 90},
    1: {"name": "Shoulder Joint", "min": 0, "max": 180, "default": 135},
    2: {"name": "Elbow Joint", "min": 0, "max": 180, "default": 180},
    3: {"name": "Wrist Roll", "min": 0, "max": 180, "default": 90},
    4: {"name": "Wrist Pitch", "min": 0, "max": 180, "default": 90},
    5: {"name": "Gripper Claw", "min": -25, "max": 110, "default": -25},
}

def detect_port(requested=None):
    if requested:
        return requested
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

class NaturalArmTester:
    def __init__(self, port, baud=115200):
        self.port = port
        self.baud = baud
        self.ser = None
        self.positions = {ch: data["default"] for ch, data in MOTOR_LIMITS.items()}

    def connect(self):
        print(f"Connecting to Arduino on {self.port} ({self.baud} baud)...")
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=1.0)
        except Exception as e:
            print(f"[!] Serial connection failed on {self.port}: {e}")
            return False

        print("Initializing serial connection. Waiting 2.5s...")
        time.sleep(2.5)

        # Drain startup banner
        while self.ser.in_waiting:
            b = self.ser.readline().decode("ascii", errors="ignore").strip()
            if b:
                print(f"  [Arduino Boot] {b}")

        print("[+] Connected and ready to process commands!\n")
        return True

    def send_raw(self, cmd, timeout=3.0):
        if not self.ser or not self.ser.is_open:
            print("[!] Serial port is not active.")
            return []

        self.ser.reset_input_buffer()
        self.ser.write((cmd.strip() + "\n").encode("ascii"))
        self.ser.flush()

        lines = []
        start = time.time()
        while time.time() - start < timeout:
            if self.ser.in_waiting:
                line = self.ser.readline().decode("ascii", errors="replace").strip()
                if line:
                    lines.append(line)
                    if any(kw in line for kw in ["_OK", "STATE_", "ERROR_"]):
                        break
            time.sleep(0.02)
        return lines

    def move_motor(self, ch, target_angle):
        limits = MOTOR_LIMITS[ch]
        clamped = max(limits["min"], min(limits["max"], target_angle))
        if clamped != target_angle:
            print(f"[i] Angle {target_angle}° clamped to motor limits ({limits['min']}° .. {limits['max']}°)")
        
        cmd = f"{ch} {clamped}"
        print(f">>> Moving {limits['name']} (Channel {ch}) to {clamped}°")
        resp = self.send_raw(cmd)
        if resp:
            print(f"    Response: {', '.join(resp)}")
            self.positions[ch] = clamped
            return True
        else:
            print("    [!] No response from Arduino.")
            return False

    def spin_continuous(self, ch, direction, ms):
        dir_name = "CW" if direction > 0 else "CCW"
        cmd = f"{ch} {dir_name} {ms}"
        name = MOTOR_LIMITS[ch]["name"]
        print(f">>> Spinning {name} (Channel {ch}) {dir_name} for {ms}ms")
        resp = self.send_raw(cmd)
        if resp:
            print(f"    Response: {', '.join(resp)}")

    def parse_and_execute(self, user_text):
        text = user_text.strip().lower()
        if not text:
            return

        # 1. Macro & Preset Commands
        if text in ["home", "base position", "rest", "reset"]:
            print(">>> Sending Arm to Calibrated Home Dock...")
            resp = self.send_raw("HOME", timeout=5.0)
            print(f"    Response: {', '.join(resp)}")
            for ch, info in MOTOR_LIMITS.items():
                self.positions[ch] = info["default"]
            return

        if text in ["open", "open claw", "open gripper"]:
            print(">>> Opening Gripper Claw (Channel 5)...")
            resp = self.send_raw("OPEN")
            print(f"    Response: {', '.join(resp)}")
            self.positions[5] = 30
            return

        if text in ["close", "close claw", "close gripper", "clamp"]:
            print(">>> Closing Gripper Claw (Channel 5)...")
            resp = self.send_raw("CLOSE")
            print(f"    Response: {', '.join(resp)}")
            self.positions[5] = -25
            return

        if text in ["stop", "relax", "off", "power off"]:
            print(">>> Disabling PWM Power (Stopping all motors)...")
            resp = self.send_raw("STOP")
            print(f"    Response: {', '.join(resp)}")
            return

        if text in ["status", "state"]:
            resp = self.send_raw("STATUS")
            print(f"    Arm Status: {', '.join(resp)}")
            return

        if text in ["block", "retrieve", "pickup", "putback"]:
            print(f">>> Executing system macro command: {text.upper()}")
            resp = self.send_raw(text.upper(), timeout=8.0)
            print(f"    Response: {', '.join(resp)}")
            return

        # 2. Check for direct numerical pattern "<channel> <angle>" e.g. "1 90", "5 30"
        m_direct = re.match(r"^([0-5])\s+([+-]?\d+)$", text)
        if m_direct:
            ch = int(m_direct.group(1))
            val = int(m_direct.group(2))
            self.move_motor(ch, val)
            return

        # 3. Check for motor name match
        matched_ch = None
        for ch, aliases in MOTOR_ALIASES.items():
            for alias in aliases:
                if alias in text:
                    matched_ch = ch
                    break
            if matched_ch is not None:
                break

        if matched_ch is not None:
            # Check for CW/CCW continuous rotation for Base (0) or Wrist Roll (3)
            if "cw" in text or "right" in text:
                m_ms = re.search(r"(\d+)\s*(ms|milliseconds)?", text)
                ms = int(m_ms.group(1)) if m_ms else 200
                self.spin_continuous(matched_ch, 1, ms)
                return
            elif "ccw" in text or "left" in text:
                m_ms = re.search(r"(\d+)\s*(ms|milliseconds)?", text)
                ms = int(m_ms.group(1)) if m_ms else 200
                self.spin_continuous(matched_ch, -1, ms)
                return

            # Check for relative delta: e.g. "shoulder +10", "elbow -5"
            m_delta = re.search(r"([+-]\d+)", text)
            if m_delta:
                delta = int(m_delta.group(1))
                curr = self.positions[matched_ch]
                self.move_motor(matched_ch, curr + delta)
                return

            # Check for absolute angle number: e.g. "move shoulder to 90 degrees", "elbow 140"
            m_angle = re.search(r"(-?\d+)", text)
            if m_angle:
                angle = int(m_angle.group(1))
                self.move_motor(matched_ch, angle)
                return

            # Special action words per motor
            if matched_ch == 5:
                if "open" in text:
                    self.send_raw("OPEN")
                    self.positions[5] = 30
                    return
                elif "close" in text:
                    self.send_raw("CLOSE")
                    self.positions[5] = -25
                    return

            print(f"[?] Recognized motor '{MOTOR_LIMITS[matched_ch]['name']}', but could not parse target angle from '{user_text}'.")
            print(f"    Example: '{MOTOR_ALIASES[matched_ch][0]} 90'")
            return

        # Fallback: send raw command string to Arduino
        print(f">>> Sending raw string to Arduino: '{user_text}'")
        resp = self.send_raw(user_text)
        print(f"    Response: {', '.join(resp)}")

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("Connection closed.")

def print_help():
    print("=" * 68)
    print("   POSTUREGUARD — NATURAL TERMINAL MOTOR TESTER")
    print("=" * 68)
    print(" SAY ANYTHING IN TERMINAL TO TEST MOTOR MOVEMENT:")
    print("  • Shoulder: 'move shoulder to 90', 'shoulder 120', 'shoulder +10', '1 90'")
    print("  • Elbow   : 'elbow 150', 'fold elbow 180', 'elbow -10', '2 180'")
    print("  • Base    : 'pan base to 90', 'base cw 200ms', 'base left 300', '0 90'")
    print("  • Pitch   : 'wrist pitch 90', 'pitch 120', '4 90'")
    print("  • Roll    : 'wrist roll 90', 'roll cw 150', '3 90'")
    print("  • Gripper : 'open claw', 'close gripper', 'claw 30', '5 -25'")
    print("  • Macros  : 'home', 'block', 'retrieve', 'pickup', 'putback', 'stop'")
    print("  • Quit    : Type 'q', 'quit', or press Ctrl+C")
    print("=" * 68)

def main():
    parser = argparse.ArgumentParser(description="Natural Terminal Motor Tester")
    parser.add_argument("--port", type=str, default=None, help="Serial port (auto-detected by default)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")

    args = parser.parse_args()
    port = detect_port(args.port)

    tester = NaturalArmTester(port, args.baud)
    if not tester.connect():
        sys.exit(1)

    print_help()

    try:
        while True:
            try:
                user_input = input("\nSay anything > ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nExiting...")
                break

            if not user_input:
                continue

            if user_input.lower() in ["q", "quit", "exit"]:
                break

            tester.parse_and_execute(user_input)
            time.sleep(0.05)
    finally:
        tester.close()

if __name__ == "__main__":
    main()
