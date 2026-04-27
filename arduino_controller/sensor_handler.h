#include "Arduino.h"
#pragma once

#include <SPI.h>
#include <stdint.h>
#include <string.h>
/*
*
*==========Arduino Nano pinout====== 
 *                            _______
 *                       TXD-|       |-Vin 
 *                       RXD-|       |-Gnd  
 *                       RST-|       |-RST
 *                       GND-|       |-+5V  
 *              PUMP_PIN  D2-|       |-A7  
 *               BTN_PIN  D3-|       |-A6  
 *          SOLENOID_PIN  D4-|       |-A5   
 *                        D5-|       |-A4  
 *                        D6-|       |-A3   
 *         LA_PIN (MISO)  D7-|       |-A2  
 *          ST_PIN (MOSI) D8-|       |-A1   
 *           LED_BTN_PIN  D9-|       |-A0   
   *                     D10-|       |-Ref
 *               SER_IN  D11-|       |-3.3V   
 *              SER_OUT  D12-|       |-D13 CLK (SPI)
 *                            --USB--        
 */

#define PUMP_PIN 2
#define BTN_PIN 3       //The start button
#define SOLENOID_PIN 4  // release pump w solenoid
#define LA_PIN 7        //165 - read from photoresistors
#define ST_PIN 8        //595 - write for solenoids
#define LED_BTN_PIN 9

const int DEBOUNCE_MS = 50;
const int ms_to_reset = 2000;  // no. of ms user needs to press button to reset the game.
unsigned long lastResetSolenoids = 0;
const int MAX_MS_TO_RESET_SOLENOIDS = 3000;
const int PUCK_DROPTIME_MS = 30;
const int COOLDOWN_PUCK_MS = 300;
const int COOLDOWN_BETWEEN_COLUMNS_MS = 500;
unsigned long last_change_ms = 0;
byte solenoid_state = 0;

// Timing variables
unsigned long pumpStartTime = 0;
unsigned long pumpReleaseTime = 0;
const unsigned long pumpTimeout = 30000UL;  // 30 seconds in ms
bool pumpRunning = false;
bool pumpReleasing = false;

void setup_sensors() {
  pinMode(ST_PIN, OUTPUT);
  pinMode(LA_PIN, OUTPUT);
  pinMode(BTN_PIN, INPUT_PULLUP);
  pinMode(PUMP_PIN, OUTPUT);
  pinMode(SOLENOID_PIN, OUTPUT);
  pinMode(LED_BTN_PIN, OUTPUT);
  digitalWrite(LA_PIN, HIGH);
  digitalWrite(ST_PIN, HIGH);
  digitalWrite(PUMP_PIN, LOW);
  digitalWrite(SOLENOID_PIN, LOW);
}

void turnOnPump() {
  digitalWrite(PUMP_PIN, HIGH);
  digitalWrite(SOLENOID_PIN, LOW);
  Serial.println("LOG: PUMP ON");
  pumpStartTime = millis();
  pumpRunning = true;
}

void shutOffPump() {

  digitalWrite(PUMP_PIN, LOW);
  digitalWrite(SOLENOID_PIN, LOW);
  pumpRunning = false;
  pumpReleasing = false;
  Serial.println("LOG: PUMP OFF");
}

void releasePump() {
  digitalWrite(PUMP_PIN, LOW);
  delay(100);
  digitalWrite(SOLENOID_PIN, HIGH);
  delay(100);
  pumpReleaseTime = millis();
  pumpReleasing = true;
  Serial.println("LOG: PUMP RELEASE");
}

void pump_on_off() {

  turnOnPump();
  Serial.println("pump on");
  delay(2000);
  releasePump();
  Serial.println("pump release");
  delay(2000);
  shutOffPump();
  Serial.println("LOG: PUMP ONOFF");
}

void led_on() {
  Serial.println("LOG: LED ON");
  digitalWrite(LED_BTN_PIN, HIGH);
}

void led_off() {
  Serial.println("LOG: LED OFF");
  digitalWrite(LED_BTN_PIN, LOW);
}

void led_strobe(int rounds = 1) {
  Serial.println("LOG: LED STROBE (SIN)");
  for (int round = 0; round < rounds; ++round)
    for (int i = -90; i <= 270; i++) {
      float angle = i * 0.0174533;           // Convert degrees to radians
      float val = (sin(angle) + 1) * 127.5;  // Sine value to 0-255 range
      analogWrite(LED_BTN_PIN, val);
      delay(1);  // Adjust for speed
    }
}


void handlePump() {
  if (pumpRunning && (millis() - pumpStartTime >= pumpTimeout)) {
    shutOffPump();
  }
}

void writeToSr(byte data) {
  digitalWrite(ST_PIN, LOW);
  SPI.transfer(data);          // Send output byte
  digitalWrite(ST_PIN, HIGH);  // Latch output
}

void update165() {
  // Latch the inputs into the shift register
  digitalWrite(LA_PIN, LOW);
  delayMicroseconds(5);
  digitalWrite(LA_PIN, HIGH);
  delayMicroseconds(5);
}

void periodicResetSolenoids() {
  if (millis() - lastResetSolenoids > MAX_MS_TO_RESET_SOLENOIDS )
  {
    writeToSr(0);
    Serial.println("LOG: incremental reset solenoids");
    lastResetSolenoids = millis();
  }
}

void handleDiscDetection() {
  static byte last_data = 0;
  update165();
  byte data = SPI.transfer(0);
  data = (~data) & 0b01111111;
  //we have a rising edge
  if (data != 0 && last_data == 0) {
    Serial.print("DROP ");
    Serial.println(__builtin_ctz(data));
  } else if (data == 0 && last_data != 0) {
    Serial.println("LOG light renewed :)");
    char msg[40];
    sprintf(msg, "LOG prev data %d", last_data);
    Serial.println(msg);
  }
  last_data = data;
}

// register reset button after ms_to_reset milliseconds, so user gets response more immediatly than on release.
void handleButtonPress() {
  static bool wasPressed = false;
  static unsigned long pressStart = 0;
  static unsigned long dePressStart = 0;
  static bool sentStart = false;
  bool pressed = !digitalRead(BTN_PIN);  // pullup defaults to high except on press.
  // note - debouncing isn't so important since we assume user will keep pressing... doing it mostly for logging.
  if (pressed && !wasPressed && (millis() - dePressStart) > DEBOUNCE_MS) {
    Serial.println("LOG: PRESS STARTED");
    wasPressed = true;
    pressStart = millis();
  } else if (!pressed && wasPressed && (millis() - pressStart) > DEBOUNCE_MS) {
    Serial.println("LOG: PRESS RESET");
    wasPressed = false;
    sentStart = false;
    dePressStart = millis();
  } else if (wasPressed && !sentStart && (millis() - pressStart) > ms_to_reset) {
    Serial.println("START");
    sentStart = true;
    led_strobe(5);
  }
}


void reset_solenoids(String stackSizes) {
  bool customWait = false;
  if (stackSizes.length() > 0)
    customWait = true;
  for (int i = 0; i < 7; ++i) {
    char msg[40];
    int pucksToRemove = 6;
    if (customWait)
      pucksToRemove = stackSizes.substring(i, i + 1).toInt();  // take the current puck stack size and apply to multiplier
    sprintf(msg, "LOG turn off solenoid %d for %d pucks", i, pucksToRemove);
    Serial.println(msg);
    for(int puckno=0;puckno<pucksToRemove+1; ++puckno)
    {
      writeToSr(1 << i);
      delay(PUCK_DROPTIME_MS);
      writeToSr(0);
      delay(COOLDOWN_PUCK_MS);
    }
    delay(COOLDOWN_BETWEEN_COLUMNS_MS);
  }
  // fast sequence to make sure solenoids close (open and close each solenoid a bunch of times)
  // for (int i = 0; i < 7; ++i) {
  //   for (int j = 0; j < 10; ++j) {
  //     writeToSr(1 << i);
  //     delay(50);
  //     writeToSr(0);
  //     delay(50);
  //   }
  // }
  writeToSr(0);
}

void open_solenoids() {
  writeToSr(0x7f);
  Serial.println("LOG: OPEN ALL SOLENOIDS");
}


void close_solenoids() {
  writeToSr(0);
  Serial.println("LOG: CLOSE ALL SOLENOIDS");
}

// void ack(byte msg) {
//   Serial.write(msg | (0b1 << 7));
// }
void handle_cmd(String cmd) {
  if (cmd.startsWith("RESET"))
    reset_solenoids(cmd.substring(6));  // assuming we might get RESET 3025213
  else if (cmd == "PUMP ON")
    turnOnPump();
  else if (cmd == "PUMP OFF")
    shutOffPump();
  else if (cmd == "PUMP RELEASE")
    releasePump();
  else if (cmd == "PUMP ONOFF")
    pump_on_off();
  else if (cmd == "OPEN")
    open_solenoids();
  else if (cmd == "CLOSE")
    close_solenoids();
  else if (cmd == "LED ON")
    led_on();
  else if (cmd == "LED OFF")
    led_off();
  else if (cmd == "LED STROBE")
    led_strobe();
}
