#!/usr/bin/env python3
"""
PostureGuard - Interactive Web App for 6-DOF Robotic Arm Motor Control

Serves a modern web dashboard with interactive sliders for all 6 motor channels:
  - Channel 0: Waist / Base (360° Continuous)
  - Channel 1: Shoulder Joint (0°..180°)
  - Channel 2: Elbow Joint (0°..180°)
  - Channel 3: Wrist Roll (0°..180°)
  - Channel 4: Wrist Pitch (0°..180°)
  - Channel 5: Gripper Claw (-25°..110°)

Features:
  - Live interactive angle sliders
  - Instant motor movement on slider adjustment
  - Quick action buttons: Home, Open Claw, Close Claw, Emergency Stop, System Sequences
  - Real-time Arduino response log window

Usage:
  python3 motor_web_app.py [--port 5000] [--serial-port /dev/ttyUSB1]
"""

import os
import sys
import time
import json
import argparse
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import serial
import serial.tools.list_ports

CHANNEL_INFO = {
    0: {"name": "Base / Waist Pan", "type": "360° Continuous", "min": 0, "max": 360, "default": 90},
    1: {"name": "Shoulder Joint", "type": "180° Positional (MG995)", "min": 0, "max": 180, "default": 135},
    2: {"name": "Elbow Joint", "type": "180° Positional (MG995)", "min": 0, "max": 180, "default": 180},
    3: {"name": "Wrist Roll", "type": "SG90 Servo", "min": 0, "max": 180, "default": 90},
    4: {"name": "Wrist Pitch", "type": "180° Positional (SG90)", "min": 0, "max": 180, "default": 90},
    5: {"name": "Gripper Claw", "type": "180° Metal (MG90S)", "min": -25, "max": 110, "default": -25},
}

def detect_serial_port(requested=None):
    if requested:
        return requested
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        if "ttyUSB" in p.device or "ttyACM" in p.device:
            return p.device
    for p in ports:
        if p.device.upper() in ["COM13", "COM14"]:
            return p.device
    if ports:
        return ports[0].device
    return "/dev/ttyUSB1"

class ArmHardwareManager:
    def __init__(self, port, baud=115200):
        self.port = port
        self.baud = baud
        self.ser = None
        self.positions = {ch: info["default"] for ch, info in CHANNEL_INFO.items()}
        self.connected = False

    def connect(self):
        print(f"Connecting to Arduino on {self.port} at {self.baud} baud...")
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=1.0)
            time.sleep(2.5)
            # Drain boot lines
            while self.ser.in_waiting:
                self.ser.readline()
            self.connected = True
            print(f"[+] Connected to Arduino on {self.port}!")
            return True
        except Exception as e:
            print(f"[!] Serial connection failed on {self.port}: {e}")
            self.connected = False
            return False

    def send_cmd(self, cmd, timeout=3.0):
        if not self.ser or not self.ser.is_open:
            return ["ERROR_SERIAL_CLOSED"]

        try:
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
            return lines if lines else ["OK"]
        except Exception as e:
            return [f"ERROR: {e}"]

    def move_channel(self, ch, angle):
        if ch not in CHANNEL_INFO:
            return ["ERROR_INVALID_CHANNEL"]
        info = CHANNEL_INFO[ch]
        clamped = max(info["min"], min(info["max"], angle))
        resp = self.send_cmd(f"{ch} {clamped}")
        self.positions[ch] = clamped
        return resp

    def spin_continuous(self, ch, direction, duration_ms):
        dir_str = "CW" if direction > 0 else "CCW"
        return self.send_cmd(f"{ch} {dir_str} {duration_ms}")

    def home(self):
        resp = self.send_cmd("HOME", timeout=5.0)
        for ch, info in CHANNEL_INFO.items():
            self.positions[ch] = info["default"]
        return resp

    def open_gripper(self):
        resp = self.send_cmd("OPEN")
        self.positions[5] = 30
        return resp

    def close_gripper(self):
        resp = self.send_cmd("CLOSE")
        self.positions[5] = -25
        return resp

    def stop_all(self):
        return self.send_cmd("STOP")

    def execute_macro(self, macro_name):
        return self.send_cmd(macro_name.upper(), timeout=8.0)

ARM_HARDWARE = None

INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PostureGuard — Robotic Arm Motor Studio</title>
  <style>
    :root {
      --bg: #0f172a;
      --card-bg: #1e293b;
      --accent: #38bdf8;
      --accent-hover: #0284c7;
      --text: #f8fafc;
      --muted: #94a3b8;
      --danger: #ef4444;
      --success: #10b981;
      --border: #334155;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; }
    body { background: var(--bg); color: var(--text); padding: 20px; display: flex; justify-content: center; min-height: 100vh; }
    .container { width: 100%; max-width: 1000px; display: flex; flex-direction: column; gap: 20px; }
    
    header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid var(--border); padding-bottom: 15px; }
    h1 { font-size: 1.5rem; font-weight: 700; color: var(--accent); display: flex; align-items: center; gap: 10px; }
    .status-badge { font-size: 0.85rem; padding: 6px 12px; border-radius: 20px; font-weight: 600; display: flex; align-items: center; gap: 6px; }
    .status-badge.connected { background: rgba(16, 185, 129, 0.15); color: var(--success); border: 1px solid var(--success); }
    .status-badge.disconnected { background: rgba(239, 68, 68, 0.15); color: var(--danger); border: 1px solid var(--danger); }
    .dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; }

    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(450px, 1fr)); gap: 20px; }
    .card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
    .card-title { font-size: 1.1rem; font-weight: 600; margin-bottom: 15px; color: var(--text); border-bottom: 1px solid var(--border); padding-bottom: 8px; }

    .motor-row { margin-bottom: 20px; }
    .motor-header { display: flex; justify-content: space-between; font-weight: 600; font-size: 0.95rem; margin-bottom: 6px; }
    .motor-type { color: var(--muted); font-size: 0.8rem; font-weight: 400; }
    .degree-readout { background: rgba(56, 189, 248, 0.1); color: var(--accent); padding: 2px 8px; border-radius: 6px; font-family: monospace; font-weight: 700; font-size: 1rem; }

    input[type=range] {
      width: 100%;
      height: 8px;
      border-radius: 4px;
      background: var(--border);
      outline: none;
      -webkit-appearance: none;
      cursor: pointer;
    }
    input[type=range]::-webkit-slider-thumb {
      -webkit-appearance: none;
      width: 22px;
      height: 22px;
      border-radius: 50%;
      background: var(--accent);
      cursor: pointer;
      box-shadow: 0 0 10px rgba(56, 189, 248, 0.5);
      transition: transform 0.1s;
    }
    input[type=range]::-webkit-slider-thumb:hover { transform: scale(1.15); }

    .btn-group { display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
    button {
      background: var(--border);
      color: var(--text);
      border: none;
      padding: 8px 14px;
      border-radius: 8px;
      cursor: pointer;
      font-weight: 600;
      font-size: 0.85rem;
      transition: all 0.15s ease;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    button:hover { background: #475569; transform: translateY(-1px); }
    button.primary { background: var(--accent); color: #0f172a; }
    button.primary:hover { background: var(--accent-hover); }
    button.danger { background: var(--danger); color: #fff; }
    button.danger:hover { background: #dc2626; }
    button.success { background: var(--success); color: #0f172a; }

    .log-box {
      background: #020617;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px;
      height: 150px;
      overflow-y: auto;
      font-family: monospace;
      font-size: 0.85rem;
      color: #38bdf8;
    }
    .log-entry { margin-bottom: 4px; border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 2px; }
    .log-time { color: var(--muted); margin-right: 8px; font-size: 0.75rem; }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>🤖 PostureGuard — Robotic Arm Studio</h1>
      <div id="statusBadge" class="status-badge disconnected">
        <span class="dot"></span> <span id="statusText">Checking...</span>
      </div>
    </header>

    <div class="grid">
      <!-- Motor Sliders Panel -->
      <div class="card">
        <div class="card-title">🎛️ Individual Servo Motor Sliders</div>

        <!-- Ch 0: Base -->
        <div class="motor-row">
          <div class="motor-header">
            <span>Ch 0: Base / Waist Pan <span class="motor-type">(360° Continuous)</span></span>
            <span class="degree-readout" id="val-0">90°</span>
          </div>
          <input type="range" id="slider-0" min="0" max="360" value="90" oninput="updateReadout(0, this.value)" onchange="sendMotorAngle(0, this.value)">
          <div class="btn-group">
            <button onclick="spinMotor(0, 1, 200)">🔄 Spin CW (200ms)</button>
            <button onclick="spinMotor(0, -1, 200)">🔄 Spin CCW (200ms)</button>
          </div>
        </div>

        <!-- Ch 1: Shoulder -->
        <div class="motor-row">
          <div class="motor-header">
            <span>Ch 1: Shoulder Joint <span class="motor-type">(MG995 180°)</span></span>
            <span class="degree-readout" id="val-1">135°</span>
          </div>
          <input type="range" id="slider-1" min="0" max="180" value="135" oninput="updateReadout(1, this.value)" onchange="sendMotorAngle(1, this.value)">
        </div>

        <!-- Ch 2: Elbow -->
        <div class="motor-row">
          <div class="motor-header">
            <span>Ch 2: Elbow Joint <span class="motor-type">(MG995 180°)</span></span>
            <span class="degree-readout" id="val-2">180°</span>
          </div>
          <input type="range" id="slider-2" min="0" max="180" value="180" oninput="updateReadout(2, this.value)" onchange="sendMotorAngle(2, this.value)">
        </div>

        <!-- Ch 3: Wrist Roll -->
        <div class="motor-row">
          <div class="motor-header">
            <span>Ch 3: Wrist Roll <span class="motor-type">(SG90 Servo)</span></span>
            <span class="degree-readout" id="val-3">90°</span>
          </div>
          <input type="range" id="slider-3" min="0" max="180" value="90" oninput="updateReadout(3, this.value)" onchange="sendMotorAngle(3, this.value)">
          <div class="btn-group">
            <button onclick="spinMotor(3, 1, 150)">🔄 Roll CW</button>
            <button onclick="spinMotor(3, -1, 150)">🔄 Roll CCW</button>
          </div>
        </div>

        <!-- Ch 4: Wrist Pitch -->
        <div class="motor-row">
          <div class="motor-header">
            <span>Ch 4: Wrist Pitch <span class="motor-type">(SG90 180°)</span></span>
            <span class="degree-readout" id="val-4">90°</span>
          </div>
          <input type="range" id="slider-4" min="0" max="180" value="90" oninput="updateReadout(4, this.value)" onchange="sendMotorAngle(4, this.value)">
        </div>

        <!-- Ch 5: Gripper Claw -->
        <div class="motor-row">
          <div class="motor-header">
            <span>Ch 5: Gripper Claw <span class="motor-type">(MG90S Metal)</span></span>
            <span class="degree-readout" id="val-5">-25°</span>
          </div>
          <input type="range" id="slider-5" min="-25" max="110" value="-25" oninput="updateReadout(5, this.value)" onchange="sendMotorAngle(5, this.value)">
          <div class="btn-group">
            <button class="success" onclick="sendQuickAction('open')">🖐️ Open Claw (30°)</button>
            <button class="primary" onclick="sendQuickAction('close')">✊ Close Claw (-25°)</button>
          </div>
        </div>
      </div>

      <!-- Controls & System Macros Panel -->
      <div style="display: flex; flex-direction: column; gap: 20px;">
        <div class="card">
          <div class="card-title">⚡ System Quick Controls & Macros</div>
          <div class="btn-group" style="flex-direction: column; gap: 10px;">
            <button class="primary" style="padding: 12px; justify-content: center; font-size: 1rem;" onclick="sendQuickAction('home')">🏠 Park Arm Home (Resting Position)</button>
            <button class="danger" style="padding: 12px; justify-content: center; font-size: 1rem;" onclick="sendQuickAction('stop')">🛑 Emergency Stop (Cut PWM Power)</button>
          </div>

          <div style="margin-top: 20px; font-weight: 600; font-size: 0.9rem; margin-bottom: 8px;">System Sequence Presets:</div>
          <div class="btn-group">
            <button onclick="sendQuickAction('block')">🛡️ Deploy Blocker</button>
            <button onclick="sendQuickAction('retrieve')">↩️ Retrieve Blocker</button>
            <button onclick="sendQuickAction('pickup')">📦 Pickup Card</button>
            <button onclick="sendQuickAction('putback')">📥 Putback Card</button>
          </div>
        </div>

        <!-- Terminal Output Log -->
        <div class="card" style="flex-grow: 1;">
          <div class="card-title">📟 Live Arduino Response Log</div>
          <div class="log-box" id="logBox">
            <div class="log-entry"><span class="log-time">[System]</span> Connected to Web Studio. Ready to send commands.</div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    function updateReadout(ch, val) {
      document.getElementById('val-' + ch).innerText = val + '°';
    }

    function addLog(msg) {
      const box = document.getElementById('logBox');
      const timeStr = new Date().toLocaleTimeString();
      const div = document.createElement('div');
      div.className = 'log-entry';
      div.innerHTML = `<span class="log-time">[${timeStr}]</span> ${msg}`;
      box.appendChild(div);
      box.scrollTop = box.scrollHeight;
    }

    function updateStatus() {
      fetch('/api/status')
        .then(res => res.json())
        .then(data => {
          const badge = document.getElementById('statusBadge');
          const text = document.getElementById('statusText');
          if (data.connected) {
            badge.className = 'status-badge connected';
            text.innerText = 'Arduino Connected (' + data.port + ')';
          } else {
            badge.className = 'status-badge disconnected';
            text.innerText = 'Arduino Disconnected';
          }

          // Sync slider values from server
          if (data.positions) {
            for (const ch in data.positions) {
              const slider = document.getElementById('slider-' + ch);
              const readout = document.getElementById('val-' + ch);
              if (slider && document.activeElement !== slider) {
                slider.value = data.positions[ch];
                if (readout) readout.innerText = data.positions[ch] + '°';
              }
            }
          }
        })
        .catch(err => console.error(err));
    }

    function sendMotorAngle(ch, angle) {
      addLog(`Sending: Move Channel ${ch} -> ${angle}°`);
      fetch('/api/move', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel: parseInt(ch), angle: parseInt(angle) })
      })
      .then(res => res.json())
      .then(data => {
        addLog(`Arduino: ${data.response.join(', ')}`);
      });
    }

    function spinMotor(ch, dir, ms) {
      addLog(`Sending: Spin Channel ${ch} ${dir > 0 ? 'CW' : 'CCW'} for ${ms}ms`);
      fetch('/api/spin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel: parseInt(ch), direction: dir, ms: ms })
      })
      .then(res => res.json())
      .then(data => {
        addLog(`Arduino: ${data.response.join(', ')}`);
      });
    }

    function sendQuickAction(action) {
      addLog(`Sending Action: ${action.toUpperCase()}`);
      fetch('/api/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: action })
      })
      .then(res => res.json())
      .then(data => {
        addLog(`Arduino: ${data.response.join(', ')}`);
        updateStatus();
      });
    }

    setInterval(updateStatus, 3000);
    updateStatus();
  </script>
</body>
</html>
"""

class WebStudioHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return  # Suppress default HTTP logging to keep console clean

    def _set_json_headers(self, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def _set_html_headers(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/" or parsed.path == "/index.html":
            self._set_html_headers()
            self.wfile.write(INDEX_HTML.encode("utf-8"))
        elif parsed.path == "/api/status":
            self._set_json_headers()
            status_data = {
                "connected": ARM_HARDWARE.connected if ARM_HARDWARE else False,
                "port": ARM_HARDWARE.port if ARM_HARDWARE else None,
                "positions": ARM_HARDWARE.positions if ARM_HARDWARE else {}
            }
            self.wfile.write(json.dumps(status_data).encode("utf-8"))
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        data = json.loads(body.decode("utf-8")) if body else {}

        if parsed.path == "/api/move":
            ch = data.get("channel")
            ang = data.get("angle")
            resp = ARM_HARDWARE.move_channel(ch, ang) if ARM_HARDWARE else ["ERROR_NO_HW"]
            self._set_json_headers()
            self.wfile.write(json.dumps({"success": True, "response": resp}).encode("utf-8"))

        elif parsed.path == "/api/spin":
            ch = data.get("channel")
            dir_val = data.get("direction")
            ms = data.get("ms", 200)
            resp = ARM_HARDWARE.spin_continuous(ch, dir_val, ms) if ARM_HARDWARE else ["ERROR_NO_HW"]
            self._set_json_headers()
            self.wfile.write(json.dumps({"success": True, "response": resp}).encode("utf-8"))

        elif parsed.path == "/api/action":
            action = data.get("action", "").lower()
            if action == "home":
                resp = ARM_HARDWARE.home()
            elif action == "open":
                resp = ARM_HARDWARE.open_gripper()
            elif action == "close":
                resp = ARM_HARDWARE.close_gripper()
            elif action == "stop":
                resp = ARM_HARDWARE.stop_all()
            elif action in ["block", "retrieve", "pickup", "putback"]:
                resp = ARM_HARDWARE.execute_macro(action)
            else:
                resp = ["ERROR_UNKNOWN_ACTION"]

            self._set_json_headers()
            self.wfile.write(json.dumps({"success": True, "response": resp}).encode("utf-8"))
        else:
            self.send_error(404, "Not Found")

def main():
    global ARM_HARDWARE
    parser = argparse.ArgumentParser(description="PostureGuard Robotic Arm Web Studio")
    parser.add_argument("--port", type=int, default=5000, help="Web server port (default: 5000)")
    parser.add_argument("--serial-port", type=str, default=None, help="Serial port (auto-detected by default)")

    args = parser.parse_args()
    serial_port = detect_serial_port(args.serial_port)

    print("=" * 65)
    print("      POSTUREGUARD — ROBOTIC ARM WEB DASHBOARD STUDIO")
    print("=" * 65)

    ARM_HARDWARE = ArmHardwareManager(serial_port)
    ARM_HARDWARE.connect()

    server_address = ("", args.port)
    httpd = HTTPServer(server_address, WebStudioHandler)

    print(f"\n[+] Web App Dashboard is LIVE at:")
    print(f"    👉 http://localhost:{args.port}")
    print(f"    👉 http://127.0.0.1:{args.port}\n")
    print("Open the link above in your web browser to control motors with sliders!")
    print("Press Ctrl+C in terminal to stop the web app.\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Web Server...")
    finally:
        if ARM_HARDWARE:
            ARM_HARDWARE.close()

if __name__ == "__main__":
    main()
