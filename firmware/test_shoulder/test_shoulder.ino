/*
 * ============================================================================
 * SHOULDER MOTOR DIAGNOSTIC & TEST TOOL
 * ============================================================================
 * Purpose:
 *   Dedicated diagnostic tool to test the Shoulder motor (CH 1 on PCA9685).
 *   Moves +15° then -15°, testing different torque levels to determine
 *   if the motor is continuous (360°) or positional (180°), and whether
 *   it has sufficient power to move against friction/gravity.
 *
 * Hardware:
 *   - Arduino Uno (USB or Wall Charger)
 *   - PCA9685 at I2C address 0x40 (SDA=A4, SCL=A5)
 *   - Motor connected to Channel 1 (Shoulder)
 *   - NOTE: Ensure external 5V/6V power is connected to PCA9685 screw terminals!
 * ============================================================================
 */

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver(0x40);

int testChannel = 1; // Default: CH 1 (Shoulder)
bool pcaFound = false;

// Convert microseconds (us) to PCA9685 12-bit tick (0..4095 at 50Hz)
uint16_t usToTicks(uint16_t us) {
  uint32_t ticks = ((uint32_t)us * 4096UL) / 20000UL;
  if (ticks > 4095) ticks = 4095;
  return (uint16_t)ticks;
}

void setPulse(int ch, uint16_t pulseUs) {
  if (!pcaFound) return;
  pwm.setPWM(ch, 0, usToTicks(pulseUs));
}

void stopMotor(int ch) {
  setPulse(ch, 1500); // 1500 us = Neutral Stop
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println(F("\n=============================================="));
  Serial.println(F("    SHOULDER MOTOR (+15° / -15°) DIAGNOSTIC   "));
  Serial.println(F("=============================================="));

  // I2C Setup with bus timeout
  Wire.begin();
  Wire.setWireTimeout(3000, true);
  digitalWrite(A4, HIGH);
  digitalWrite(A5, HIGH);

  // Initialize PCA9685
  pwm.begin();
  pwm.setPWMFreq(50); // 50 Hz PWM

  Wire.beginTransmission(0x40);
  pcaFound = (Wire.endTransmission() == 0);

  if (pcaFound) {
    Serial.println(F("[I2C] PCA9685 detected and communicating at 0x40."));
  } else {
    Serial.println(F("[WARNING] PCA9685 NOT detected at 0x40!"));
    Serial.println(F("[WARNING] Check SDA/SCL wiring and PCA9685 power."));
  }

  // Stop all channels initially (neutral 1500 us)
  for (int i = 0; i < 6; i++) {
    stopMotor(i);
  }

  Serial.println(F("\n[INFO] Testing Channel: CH 1 (Shoulder Joint)"));
  Serial.println(F("[INFO] Important: Ensure PCA9685 screw terminals have 5V/6V power connected!"));
  Serial.println(F("[INFO] Starting automatic +15° / -15° cycle in 2 seconds...\n"));
  Serial.println(F("Commands you can type in Serial Monitor:"));
  Serial.println(F("  '0', '1', '2' -> Switch test channel to CH 0, 1, or 2"));
  Serial.println(F("  '+' or 'CW'   -> Jog forward"));
  Serial.println(F("  '-' or 'CCW'  -> Jog backward"));
  Serial.println(F("  'S' or 'STOP' -> Stop motor"));
  Serial.println(F("  'TEST'        -> Trigger one +15° / -15° test cycle"));
  Serial.println(F("----------------------------------------------"));

  delay(2000);
}

// Test motion: Forward for duration, Pause, Reverse for duration, Stop
void runMotionTest(int ch, int powerLevel) {
  uint16_t offsetUs = 150;
  const char* levelName = "Gentle";

  if (powerLevel == 1) {
    offsetUs = 160;  // Medium-low
    levelName = "Medium (1660 / 1340 us)";
  } else if (powerLevel == 2) {
    offsetUs = 280;  // High torque (for overcoming arm gravity)
    levelName = "High Torque (1780 / 1220 us)";
  } else if (powerLevel == 3) {
    offsetUs = 450;  // Maximum torque
    levelName = "MAX POWER (1950 / 1050 us)";
  }

  Serial.print(F("\n>>> [CYCLE START] Testing CH "));
  Serial.print(ch);
  Serial.print(F(" with Power: "));
  Serial.println(levelName);

  // STEP 1: Move +15° (Forward / Up)
  Serial.print(F("  -> [STEP 1] Moving +15° (CW): pulse "));
  Serial.print(1500 + offsetUs);
  Serial.println(F(" us for 600 ms..."));
  setPulse(ch, 1500 + offsetUs);
  delay(600); // 600 ms burst

  // STEP 2: Stop & Hold
  Serial.println(F("  -> [STOP] Holding neutral (1500 us) for 1000 ms..."));
  stopMotor(ch);
  delay(1000);

  // STEP 3: Move -15° (Reverse / Down)
  Serial.print(F("  -> [STEP 2] Moving -15° (CCW): pulse "));
  Serial.print(1500 - offsetUs);
  Serial.println(F(" us for 600 ms..."));
  setPulse(ch, 1500 - offsetUs);
  delay(600); // 600 ms burst

  // STEP 4: Stop & Hold
  Serial.println(F("  -> [STOP] Holding neutral (1500 us) for 1500 ms..."));
  stopMotor(ch);
  delay(1500);

  Serial.println(F(">>> [CYCLE COMPLETE]\n"));
}

int currentPower = 1;
unsigned long lastAutoCycleMs = 0;
bool autoCycleActive = true;

void loop() {
  unsigned long now = millis();

  // 1. Process Serial Commands from User
  while (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    cmd.toUpperCase();

    if (cmd.length() == 0) continue;

    Serial.print(F("[COMMAND] "));
    Serial.println(cmd);

    if (cmd == "0" || cmd == "CH0") {
      testChannel = 0;
      Serial.println(F("[SWITCH] Switched test to CH 0 (Base)"));
    } else if (cmd == "1" || cmd == "CH1") {
      testChannel = 1;
      Serial.println(F("[SWITCH] Switched test to CH 1 (Shoulder)"));
    } else if (cmd == "2" || cmd == "CH2") {
      testChannel = 2;
      Serial.println(F("[SWITCH] Switched test to CH 2 (Elbow)"));
    } else if (cmd == "+" || cmd == "CW" || cmd == "FWD") {
      autoCycleActive = false;
      Serial.print(F("[JOG] Running CH "));
      Serial.print(testChannel);
      Serial.println(F(" FORWARD (1780 us)..."));
      setPulse(testChannel, 1780);
    } else if (cmd == "-" || cmd == "CCW" || cmd == "REV") {
      autoCycleActive = false;
      Serial.print(F("[JOG] Running CH "));
      Serial.print(testChannel);
      Serial.println(F(" REVERSE (1220 us)..."));
      setPulse(testChannel, 1220);
    } else if (cmd == "S" || cmd == "STOP" || cmd == "HOLD") {
      autoCycleActive = false;
      Serial.print(F("[STOP] Stopping CH "));
      Serial.println(testChannel);
      stopMotor(testChannel);
    } else if (cmd == "AUTO") {
      autoCycleActive = true;
      lastAutoCycleMs = now;
      Serial.println(F("[MODE] Automatic cycle resumed."));
    } else if (cmd == "TEST" || cmd == "RUN") {
      runMotionTest(testChannel, currentPower);
      lastAutoCycleMs = now;
    } else if (cmd == "P1") {
      currentPower = 1;
      Serial.println(F("[POWER] Set to Level 1 (Medium: +-160 us)"));
    } else if (cmd == "P2") {
      currentPower = 2;
      Serial.println(F("[POWER] Set to Level 2 (High: +-280 us)"));
    } else if (cmd == "P3") {
      currentPower = 3;
      Serial.println(F("[POWER] Set to Level 3 (MAX: +-450 us)"));
    }
  }

  // 2. Automated Test Cycle: every 5 seconds, run +15° / -15° test
  if (autoCycleActive && (now - lastAutoCycleMs >= 5000UL)) {
    lastAutoCycleMs = now;

    // Cycle through power levels: Level 1 (Medium) -> Level 2 (High) -> Level 3 (Max)
    runMotionTest(testChannel, currentPower);

    // Alternate power level so user can see which torque level moves the motor
    currentPower++;
    if (currentPower > 3) currentPower = 1;
  }
}
