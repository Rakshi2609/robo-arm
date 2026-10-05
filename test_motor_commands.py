#!/usr/bin/env python3
"""
Unit Test Suite for Natural Motor Control Parser
Verifies that natural text inputs correctly resolve to motor channels and angles.
"""

import sys
from natural_motor_control import NaturalArmTester

class DummyTester(NaturalArmTester):
    def __init__(self):
        super().__init__(port=None)
        self.last_move = None
        self.last_spin = None
        self.last_raw = None

    def send_raw(self, cmd, timeout=3.0):
        self.last_raw = cmd
        return ["TEST_OK"]

    def move_motor(self, ch, target_angle):
        self.last_move = (ch, target_angle)
        self.positions[ch] = target_angle
        return True

    def spin_continuous(self, ch, direction, ms):
        self.last_spin = (ch, direction, ms)

def run_tests():
    t = DummyTester()
    
    test_cases = [
        ("move shoulder to 90", ("move", 1, 90)),
        ("shoulder 120", ("move", 1, 120)),
        ("elbow 180", ("move", 2, 180)),
        ("fold elbow to 140", ("move", 2, 140)),
        ("pitch 90", ("move", 4, 90)),
        ("wrist pitch 120", ("move", 4, 120)),
        ("wrist roll 90", ("move", 3, 90)),
        ("claw 30", ("move", 5, 30)),
        ("1 90", ("move", 1, 90)),
        ("2 150", ("move", 2, 150)),
        ("5 -25", ("move", 5, -25)),
        ("open claw", ("raw", "OPEN")),
        ("close gripper", ("raw", "CLOSE")),
        ("home", ("raw", "HOME")),
        ("stop", ("raw", "STOP")),
        ("base cw 200ms", ("spin", 0, 1, 200)),
        ("roll cw 150", ("spin", 3, 1, 150)),
    ]

    passed = 0
    for text, expected in test_cases:
        t.last_move = None
        t.last_spin = None
        t.last_raw = None

        t.parse_and_execute(text)

        exp_type = expected[0]
        if exp_type == "move":
            ok = (t.last_move == (expected[1], expected[2]))
        elif exp_type == "spin":
            ok = (t.last_spin == (expected[1], expected[2], expected[3]))
        elif exp_type == "raw":
            ok = (t.last_raw == expected[1])

        if ok:
            print(f"  [PASS] '{text}' => {expected}")
            passed += 1
        else:
            print(f"  [FAIL] '{text}' => got move={t.last_move}, spin={t.last_spin}, raw={t.last_raw}")

    print(f"\nTest Summary: {passed}/{len(test_cases)} test cases passed successfully.")
    return passed == len(test_cases)

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
