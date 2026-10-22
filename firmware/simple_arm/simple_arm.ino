/*
 * ============================================================================
 * Autonomous Radar & Reach Robotic Arm (Simple Standalone Firmware)
 * ============================================================================
 * Hardware:
 *   - Arduino Uno (Plugged into Wall Charger or USB)
 *   - PCA9685 16-Channel 12-bit PWM Driver (I2C 0x40: SDA -> A4, SCL -> A5)
 *   - 6x MG996R 360 Continuous Rotation Servos
 *   - HC-SR04 Ultrasonic Distance Sensor:
 *       VCC  -> 5V
 *       GND  -> GND
 *       TRIG -> Digital Pin 8
 *       ECHO -> Digital Pin 9
 *
 * Behavior:
 *   1. Starts at Home Pose (all joints at 90.0 deg neutral / stopped).
 *   2. Base sweeps slowly: Clockwise (to 170 deg), pauses, Counter-Clockwise (to 10 deg), pauses.
 *   3. Ultrasonic sensor continuously scans for obstacles between 15 cm and 25 cm.
 *   4. When obstacle detected (15 - 25 cm):
 *        - Base halts immediately at target azimuth.
 *        - Arm moves slowly to Move Pose:
 *            Shoulder:    95.0 deg
 *            Elbow:       97.5 deg
 *            Wrist Pitch: 94.0 deg
 *            Wrist Roll: 172.0 deg
 *            Claw:        90.0 deg
 *        - Holds this pose while obstacle is present.
 *   5. When obstacle is removed (> 27 cm or clear):
 *        - Arm retracts slowly back to Home Pose (all joints at 90.0 deg).
 *        - Base resumes slow sweeping.
 * ============================================================================
 */

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

// --- Pin Definitions ---
#define TRIG_PIN 8
#define ECHO_PIN 9

// --- Joint Channels on PCA9685 ---
#define CH_BASE         0
#define CH_SHOULDER     1
#define CH_ELBOW        2
#define CH_WRIST_PITCH  3
#define CH_WRIST_ROLL   4
#define CH_CLAW         5
#define NUM_JOINTS      6

// --- PCA9685 Hardware Configuration ---
Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver(0x40);

// Neutral 1500 us (Stop for MG996R 360 Continuous Rotation Servos)
// At 50 Hz (20,000 us period) with 12-bit resolution (4096 ticks):
// 1500 us * 4096 / 20000 = 307.2 ticks
#define PULSE_NEUTRAL_US 1500

uint16_t usToTicks(uint16_t us) {
  uint32_t ticks = ((uint32_t)us * 4096UL) / 20000UL;
  if (ticks > 4095) ticks = 4095;
  return (uint16_t)ticks;
}

// --- Target Poses ---
// Home Pose (All joints stationary at 90 deg)
const float POSE_HOME[NUM_JOINTS] = { 90.0f, 90.0f, 90.0f, 90.0f,  90.0f, 90.0f };

// Move Pose (When obstacle is detected in 15 - 25 cm range)
// Note: Base stays at detected azimuth; other joints move to:
const float POSE_MOVE[NUM_JOINTS] = { 90.0f, 95.0f, 97.5f, 94.0f, 172.0f, 90.0f };

// --- Joint State & Slow Calibrated Motion ---
struct Joint {
  float currentAngle;
  float targetAngle;
  float startAngle;
  bool isMoving;
  unsigned long motionStartMs;
  unsigned long motionEndMs;
};

Joint joints[NUM_JOINTS];

bool pcaFound = false;

// Set joint to stop (1500 us holding pulse)
void stopJoint(int ch) {
  joints[ch].isMoving = false;
  if (pcaFound) {
    pwm.setPWM(ch, 0, usToTicks(PULSE_NEUTRAL_US));
  }
}

// Command a joint to move slowly to a target angle
void moveJoint(int ch, float targetAngle) {
  joints[ch].targetAngle = targetAngle;
  joints[ch].startAngle = joints[ch].currentAngle;
  float delta = targetAngle - joints[ch].currentAngle;

  if (fabs(delta) < 0.8f) {
    joints[ch].currentAngle = targetAngle;
    stopJoint(ch);
    return;
  }

  bool cw = (delta > 0.0f);

  // Controlled pulse offsets for MG996R 360 continuous servos:
  // Must be outside the ~50-80us deadband so gears reliably engage,
  // but well below max (+-450us) so motion remains calm and controlled.
  uint16_t offsetUs = 140;
  float speedDps = 28.0f; // degrees per second

  switch (ch) {
    case CH_BASE:
      offsetUs = 150;           // Steady, smooth turntable sweep
      speedDps = 28.0f;
      break;
    case CH_SHOULDER:
      offsetUs = cw ? 260 : 130;// 260us to lift against arm weight, 130us to lower
      speedDps = cw ? 22.0f : 32.0f;
      break;
    case CH_ELBOW:
      offsetUs = cw ? 240 : 130;// 240us to lift against forearm weight, 130us to lower
      speedDps = cw ? 22.0f : 32.0f;
      break;
    case CH_WRIST_PITCH:
      offsetUs = 140;
      speedDps = 30.0f;
      break;
    case CH_WRIST_ROLL:
      offsetUs = 140;
      speedDps = 35.0f;
      break;
    case CH_CLAW:
      offsetUs = 150;
      speedDps = 40.0f;
      break;
  }

  // Calculate run duration in milliseconds based on calibrated speed
  unsigned long durationMs = (unsigned long)((fabs(delta) / speedDps) * 1000.0f);
  if (durationMs < 80) durationMs = 80; // Minimum duration to overcome static gear friction

  joints[ch].motionStartMs = millis();
  joints[ch].motionEndMs = joints[ch].motionStartMs + durationMs;
  joints[ch].isMoving = true;

  // Apply calibrated drive pulse
  uint16_t pulseUs = cw ? (PULSE_NEUTRAL_US + offsetUs) : (PULSE_NEUTRAL_US - offsetUs);
  if (pcaFound) {
    pwm.setPWM(ch, 0, usToTicks(pulseUs));
  }

  Serial.print(F("[MOTOR] CH "));
  Serial.print(ch);
  Serial.print(F(" -> "));
  Serial.print(targetAngle, 1);
  Serial.print(F(" deg ("));
  Serial.print(durationMs);
  Serial.print(F(" ms, pulse: "));
  Serial.print(pulseUs);
  Serial.println(F(" us)"));
}

// Update timed movements for all joints
void updateJoints() {
  unsigned long now = millis();
  for (int ch = 0; ch < NUM_JOINTS; ch++) {
    if (joints[ch].isMoving) {
      if (now >= joints[ch].motionEndMs) {
        joints[ch].currentAngle = joints[ch].targetAngle;
        stopJoint(ch);
        Serial.print(F("[STOP] CH "));
        Serial.print(ch);
        Serial.println(F(" reached target."));
      } else {
        unsigned long elapsed = now - joints[ch].motionStartMs;
        unsigned long total = joints[ch].motionEndMs - joints[ch].motionStartMs;
        if (total > 0) {
          float frac = (float)elapsed / (float)total;
          joints[ch].currentAngle = joints[ch].startAngle + frac * (joints[ch].targetAngle - joints[ch].startAngle);
        }
      }
    }
  }
}

// Check if all arm joints have finished moving
bool allArmJointsDone() {
  for (int ch = 1; ch < NUM_JOINTS; ch++) {
    if (joints[ch].isMoving) return false;
  }
  return true;
}

// Move arm joints (CH 1 to 5) to specified pose
void moveArmToPose(const float pose[NUM_JOINTS]) {
  for (int ch = 1; ch < NUM_JOINTS; ch++) {
    moveJoint(ch, pose[ch]);
  }
}

// --- Ultrasonic Sensor Reading ---
float readUltrasonicCm() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  unsigned long duration = pulseIn(ECHO_PIN, HIGH, 18000UL); // 18ms max (~300cm)
  if (duration == 0) return -1.0f;
  float dist = ((float)duration * 0.0343f) / 2.0f;
  if (dist < 2.0f || dist > 300.0f) return -1.0f;
  return dist;
}

// --- Standalone Autonomous State Machine ---
enum RobotState {
  STATE_INIT,         // Startup delay (servos settle at Home)
  STATE_SWEEP_CW,     // Base rotating clockwise towards 170 deg (+80 deg)
  STATE_PAUSE_CW,     // Delay at CW endpoint before turning back
  STATE_SWEEP_CCW,    // Base rotating counter-clockwise towards 10 deg (-80 deg)
  STATE_PAUSE_CCW,    // Delay at CCW endpoint before turning back
  STATE_REACHING,     // Obstacle detected! Arm moving slowly to Move Pose
  STATE_HOLDING,      // Arm holding Move Pose while obstacle is present
  STATE_RETRACTING    // Obstacle removed! Arm returning slowly to Home Pose
};

RobotState robotState = STATE_INIT;
unsigned long stateTimer = 0;
int detectCount = 0;
int clearCount = 0;
float currentDist = -1.0f;
unsigned long lastSonarTime = 0;

// --- Setup ---
void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println(F("\n=========================================="));
  Serial.println(F(" Autonomous Radar & Reach Robotic Arm"));
  Serial.println(F("=========================================="));

  // Ultrasonic Pins
  pinMode(TRIG_PIN, OUTPUT);
  digitalWrite(TRIG_PIN, LOW);
  pinMode(ECHO_PIN, INPUT);

  // Initialize I2C with timeout and internal pullups
  Wire.begin();
  Wire.setWireTimeout(3000, true);
  digitalWrite(A4, HIGH);
  digitalWrite(A5, HIGH);

  // Initialize PCA9685 driver
  pwm.begin();
  pwm.setPWMFreq(50); // 50 Hz servo PWM

  Wire.beginTransmission(0x40);
  pcaFound = (Wire.endTransmission() == 0);
  if (pcaFound) {
    Serial.println(F("[PCA9685] Detected and initialized at 0x40."));
  } else {
    Serial.println(F("[PCA9685] Retrying detection at 0x40..."));
  }

  // Initialize all joints at Home Pose (90 deg stationary stop)
  for (int ch = 0; ch < NUM_JOINTS; ch++) {
    joints[ch].currentAngle = POSE_HOME[ch];
    joints[ch].targetAngle = POSE_HOME[ch];
    joints[ch].isMoving = false;
    stopJoint(ch);
  }

  robotState = STATE_INIT;
  stateTimer = millis();
  Serial.println(F("[INIT] Servos stabilized at Home Pose (90 deg)."));
}

unsigned long lastPrintTime = 0;
unsigned long lastPcaRetryTime = 0;

// --- Main Control Loop ---
void loop() {
  unsigned long now = millis();

  // Auto-detect / recover PCA9685 if powered up after Arduino
  if (!pcaFound && (now - lastPcaRetryTime >= 1000)) {
    lastPcaRetryTime = now;
    Wire.beginTransmission(0x40);
    if (Wire.endTransmission() == 0) {
      pwm.begin();
      pwm.setPWMFreq(50);
      pcaFound = true;
      Serial.println(F("[PCA9685] Connected and initialized!"));
      // Ensure all joints hold neutral stop
      for (int ch = 0; ch < NUM_JOINTS; ch++) {
        stopJoint(ch);
      }
    }
  }

  // 1. Update timed joint motor pulses
  updateJoints();

  // 2. Read Ultrasonic Sensor every 60 ms
  if (now - lastSonarTime >= 60) {
    lastSonarTime = now;
    currentDist = readUltrasonicCm();
  }

  // 2b. Periodic Status Print every 1.5 seconds
  if (now - lastPrintTime >= 1500) {
    lastPrintTime = now;
    Serial.print(F("[STATUS] Dist: "));
    if (currentDist >= 0) {
      Serial.print(currentDist, 1);
      Serial.print(F(" cm"));
    } else {
      Serial.print(F("Clear"));
    }
    Serial.print(F(" | State: "));
    switch (robotState) {
      case STATE_INIT:      Serial.print(F("INIT")); break;
      case STATE_SWEEP_CW:  Serial.print(F("SWEEP_CW (Base: ")); Serial.print(joints[CH_BASE].currentAngle, 0); Serial.print(F(")")); break;
      case STATE_PAUSE_CW:  Serial.print(F("PAUSE_CW")); break;
      case STATE_SWEEP_CCW: Serial.print(F("SWEEP_CCW (Base: ")); Serial.print(joints[CH_BASE].currentAngle, 0); Serial.print(F(")")); break;
      case STATE_PAUSE_CCW: Serial.print(F("PAUSE_CCW")); break;
      case STATE_REACHING:  Serial.print(F("REACHING_TARGET")); break;
      case STATE_HOLDING:   Serial.print(F("HOLDING_TARGET")); break;
      case STATE_RETRACTING:Serial.print(F("RETRACTING_HOME")); break;
    }
    Serial.println();
  }

  // 3. Autonomous State Machine
  switch (robotState) {

    case STATE_INIT:
      // Wait 2.0 seconds after power-on to let all servos stabilize
      if (now - stateTimer >= 2000) {
        Serial.println(F("[START] Starting slow radar sweep..."));
        robotState = STATE_SWEEP_CW;
        moveJoint(CH_BASE, 170.0f); // Sweep CW towards +80 deg
      }
      break;

    case STATE_SWEEP_CW:
    case STATE_SWEEP_CCW:
      // --- Obstacle Detection Check (15 cm to 25 cm) ---
      if (currentDist >= 15.0f && currentDist <= 25.0f) {
        detectCount++;
        if (detectCount >= 2) { // 2 consecutive verified samples (~100ms)
          // OBJECT DETECTED!
          stopJoint(CH_BASE);   // Stop base rotation instantly at target azimuth
          Serial.print(F("[DETECTED] Object at "));
          Serial.print(currentDist, 1);
          Serial.println(F(" cm! Reaching target pose..."));

          // Move arm to Move Pose
          moveArmToPose(POSE_MOVE);

          detectCount = 0;
          clearCount = 0;
          stateTimer = now;
          robotState = STATE_REACHING;
          break;
        }
      } else {
        detectCount = 0;
      }

      // --- Sweeping Motion Management ---
      if (robotState == STATE_SWEEP_CW) {
        if (!joints[CH_BASE].isMoving) {
          // Reached CW limit (170 deg) -> pause before reversing
          stopJoint(CH_BASE);
          stateTimer = now;
          robotState = STATE_PAUSE_CW;
        }
      } else if (robotState == STATE_SWEEP_CCW) {
        if (!joints[CH_BASE].isMoving) {
          // Reached CCW limit (10 deg) -> pause before reversing
          stopJoint(CH_BASE);
          stateTimer = now;
          robotState = STATE_PAUSE_CCW;
        }
      }
      break;

    case STATE_PAUSE_CW:
      // Pause 800 ms at CW end, then sweep CCW
      if (now - stateTimer >= 800) {
        robotState = STATE_SWEEP_CCW;
        moveJoint(CH_BASE, 10.0f); // Sweep CCW towards -80 deg
      }
      break;

    case STATE_PAUSE_CCW:
      // Pause 800 ms at CCW end, then sweep CW
      if (now - stateTimer >= 800) {
        robotState = STATE_SWEEP_CW;
        moveJoint(CH_BASE, 170.0f); // Sweep CW towards +80 deg
      }
      break;

    case STATE_REACHING:
      // Wait until all arm joints have slowly completed their motion
      if (allArmJointsDone() || (now - stateTimer >= 3000)) {
        Serial.println(F("[HOLDING] In Move Pose. Waiting for object removal..."));
        robotState = STATE_HOLDING;
        clearCount = 0;
      }
      break;

    case STATE_HOLDING:
      // While obstacle remains in 13 - 27 cm, hold pose.
      // If obstacle is removed (outside range or > 27 cm):
      if (currentDist < 13.0f || currentDist > 27.0f || currentDist < 0.0f) {
        clearCount++;
        if (clearCount >= 4) { // 4 consecutive clear samples (~200ms)
          Serial.println(F("[CLEAR] Object removed! Returning to Home Pose..."));
          moveArmToPose(POSE_HOME);
          clearCount = 0;
          detectCount = 0;
          stateTimer = now;
          robotState = STATE_RETRACTING;
        }
      } else {
        clearCount = 0;
      }
      break;

    case STATE_RETRACTING:
      // Wait until all arm joints have slowly returned to Home Pose
      if (allArmJointsDone() || (now - stateTimer >= 3000)) {
        Serial.println(F("[RESUME] Home reached. Resuming slow radar sweep..."));
        // Resume sweeping in the direction of available range
        if (joints[CH_BASE].currentAngle < 160.0f) {
          robotState = STATE_SWEEP_CW;
          moveJoint(CH_BASE, 170.0f);
        } else {
          robotState = STATE_SWEEP_CCW;
          moveJoint(CH_BASE, 10.0f);
        }
      }
      break;
  }
}
