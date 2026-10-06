/*
  Direct Hardware Test Sketch for Robotic Arm
  - Scans I2C bus for PCA9685 (0x40)
  - Continuously sweeps Channel 0 (Base), Channel 1 (Shoulder), Channel 2 (Elbow), Channel 5 (Gripper)
  - Keeps ACTIVE PWM holding pulses on (no 0 pulse cutoff) so motors physically move & hold position
*/

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver(0x40);

#define SERVOMIN   140 // 0 deg
#define SERVOMAX   580 // 180 deg
#define SERVO_FREQ 50  // 50 Hz

int angleToPulse(int ang) {
  ang = constrain(ang, 0, 180);
  return map(ang, 0, 180, SERVOMIN, SERVOMAX);
}

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  Serial.begin(115200);
  while (!Serial && millis() < 2000) ;

  Serial.println(F("\n=============================================="));
  Serial.println(F("   DIRECT ROBOTIC ARM HARDWARE DIAGNOSTIC"));
  Serial.println(F("=============================================="));

  Wire.begin();
  delay(100);

  // 1. Scan I2C Bus
  Serial.println(F("[1/3] Scanning I2C Bus..."));
  byte error, address;
  int devices = 0;
  for (address = 1; address < 127; address++) {
    Wire.beginTransmission(address);
    error = Wire.endTransmission();
    if (error == 0) {
      Serial.print(F(" -> FOUND I2C Device at 0x"));
      if (address < 16) Serial.print(F("0"));
      Serial.println(address, HEX);
      devices++;
    }
  }
  if (devices == 0) {
    Serial.println(F("[!] ERROR: No I2C devices found! Check SDA (A4) & SCL (A5) wiring!"));
  } else {
    Serial.println(F("[+] I2C Bus Communication OK!"));
  }

  // 2. Initialize PCA9685
  Serial.println(F("[2/3] Initializing PCA9685 PWM Servo Driver @ 50Hz..."));
  pwm.begin();
  pwm.setOscillatorFrequency(25000000);
  pwm.setPWMFreq(SERVO_FREQ);
  delay(200);

  Serial.println(F("[3/3] Starting Active Motor Motion Loop..."));
  Serial.println(F("==============================================\n"));
}

void loop() {
  digitalWrite(LED_BUILTIN, HIGH);

  // --- Move Channel 1 (Shoulder) ---
  Serial.println(F(">>> Moving Channel 1 (Shoulder) to 90 degrees..."));
  pwm.setPWM(1, 0, angleToPulse(90));
  delay(1500);

  Serial.println(F(">>> Moving Channel 1 (Shoulder) to 135 degrees..."));
  pwm.setPWM(1, 0, angleToPulse(135));
  delay(1500);

  // --- Move Channel 2 (Elbow) ---
  Serial.println(F(">>> Moving Channel 2 (Elbow) to 120 degrees..."));
  pwm.setPWM(2, 0, angleToPulse(120));
  delay(1500);

  Serial.println(F(">>> Moving Channel 2 (Elbow) to 180 degrees..."));
  pwm.setPWM(2, 0, angleToPulse(180));
  delay(1500);

  // --- Move Channel 0 (Base Continuous Spin) ---
  Serial.println(F(">>> Spinning Channel 0 (Base) CW..."));
  pwm.setPWM(0, 0, 400); // CW pulse
  delay(1000);
  pwm.setPWM(0, 0, 307); // Neutral pulse
  delay(500);

  Serial.println(F(">>> Spinning Channel 0 (Base) CCW..."));
  pwm.setPWM(0, 0, 210); // CCW pulse
  delay(1000);
  pwm.setPWM(0, 0, 307); // Neutral pulse
  delay(500);

  // --- Move Channel 5 (Gripper Claw) ---
  Serial.println(F(">>> Moving Channel 5 (Gripper) to Open (30 deg)..."));
  pwm.setPWM(5, 0, angleToPulse(30));
  delay(1200);

  Serial.println(F(">>> Moving Channel 5 (Gripper) to Close (0 deg)..."));
  pwm.setPWM(5, 0, angleToPulse(0));
  delay(1200);

  digitalWrite(LED_BUILTIN, LOW);
  delay(1000);
}
