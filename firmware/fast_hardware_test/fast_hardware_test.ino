/*
  Fast High-Speed Hardware Test for 6-DOF Robotic Arm
  - Direct PWM target jumps (no slow step-by-step delays)
  - Full-speed CW (480) & CCW (140) sweeps for Base (Ch 0)
  - Active holding torque for MG995 Shoulder (Ch 1) & Elbow (Ch 2)
*/

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver(0x40);

// Calibrated 50Hz PWM Pulse Limits for MG995 & SG90 Servos
#define SERVOMIN   140 // 0 degrees (~0.7 ms)
#define SERVOMAX   580 // 180 degrees (~2.4 ms)
#define SERVO_FREQ 50  // 50 Hz

// Full Speed Continuous Rotation Pulses for Base (Ch 0)
#define BASE_FULL_CW   480  // Full speed Clockwise
#define BASE_FULL_CCW  140  // Full speed Counter-Clockwise
#define BASE_STOP      307  // Neutral stop pulse

int angleToPulse(int ang) {
  ang = constrain(ang, 0, 180);
  return map(ang, 0, 180, SERVOMIN, SERVOMAX);
}

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  Serial.begin(115200);
  while (!Serial && millis() < 2000) ;

  Serial.println(F("\n=============================================="));
  Serial.println(F("   FAST HIGH-SPEED ROBOTIC ARM TEST"));
  Serial.println(F("=============================================="));

  Wire.begin();
  delay(100);

  pwm.begin();
  pwm.setOscillatorFrequency(25000000); // 25MHz standard crystal
  pwm.setPWMFreq(SERVO_FREQ);
  delay(200);

  Serial.println(F("[+] Hardware ready! Starting fast motor motion sequence...\n"));
}

void loop() {
  digitalWrite(LED_BUILTIN, HIGH);

  // --- 1. CHANNEL 0: BASE (Full Speed 360° Rotation) ---
  Serial.println(F(">>> Base (Ch 0): Full Speed Clockwise (1.5s)..."));
  pwm.setPWM(0, 0, BASE_FULL_CW);
  delay(1500);

  Serial.println(F(">>> Base (Ch 0): Stop (0.5s)..."));
  pwm.setPWM(0, 0, BASE_STOP);
  delay(500);

  Serial.println(F(">>> Base (Ch 0): Full Speed Counter-Clockwise (1.5s)..."));
  pwm.setPWM(0, 0, BASE_FULL_CCW);
  delay(1500);

  Serial.println(F(">>> Base (Ch 0): Stop..."));
  pwm.setPWM(0, 0, BASE_STOP);
  delay(500);

  // --- 2. CHANNEL 1: SHOULDER (Fast Positional Move 135° -> 75° -> 135°) ---
  Serial.println(F(">>> Shoulder (Ch 1): Reaching Forward to 75 degrees..."));
  pwm.setPWM(1, 0, angleToPulse(75));
  delay(1500);

  Serial.println(F(">>> Shoulder (Ch 1): Returning to Home 135 degrees..."));
  pwm.setPWM(1, 0, angleToPulse(135));
  delay(1500);

  // --- 3. CHANNEL 2: ELBOW (Fast Positional Move 180° -> 120° -> 180°) ---
  Serial.println(F(">>> Elbow (Ch 2): Bending to 120 degrees..."));
  pwm.setPWM(2, 0, angleToPulse(120));
  delay(1500);

  Serial.println(F(">>> Elbow (Ch 2): Returning to Home 180 degrees..."));
  pwm.setPWM(2, 0, angleToPulse(180));
  delay(1500);

  // --- 4. CHANNEL 5: GRIPPER CLAW (Fast Move Open 30° -> Close -25°) ---
  Serial.println(F(">>> Gripper (Ch 5): Opening to 30 degrees..."));
  pwm.setPWM(5, 0, angleToPulse(30));
  delay(1200);

  Serial.println(F(">>> Gripper (Ch 5): Closing to -25 degrees..."));
  pwm.setPWM(5, 0, angleToPulse(-25));
  delay(1200);

  digitalWrite(LED_BUILTIN, LOW);
  delay(1000);
}
