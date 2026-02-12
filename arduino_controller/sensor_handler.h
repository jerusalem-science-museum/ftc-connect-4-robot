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
 *                        D2-|       |-A7  
 *         LA_PIN (MISO)  D3-|       |-A6  
 *         ST_PIN (MOSI)  D4-|       |-A5   
 *               BTN_PIN  D5-|       |-A4  
 *                        D6-|       |-A3   
 *          SOLENOID_PIN  D7-|       |-A2  
 *              PUMP_PIN  D8-|       |-A1   
 *                        D9-|       |-A0   
   *                     D10-|       |-Ref
 *               SER_IN  D11-|       |-3.3V   
 *              SER_OUT  D12-|       |-D13 CLK (SPI)
 *                            --USB--        
 */


#define LA_PIN 3     //165 - read from photoresistors
#define ST_PIN 4    //595 - write for solenoids
#define BTN_PIN 5      //The start button 
#define SOLENOID_PIN 7 // release pump w solenoid
#define PUMP_PIN 8


const int DEBOUNCE_MS = 1000;
const int ms_to_reset = 2000; // no. of ms user needs to press button to reset the game.
unsigned long last_change_ms = 0;
byte solenoid_state = 0;

// Timing variables
unsigned long pumpStartTime = 0;
const unsigned long pumpTimeout = 30000UL;  // 30 seconds in ms
bool pumpRunning = false;

void setup_sensors()
{
  pinMode(ST_PIN, OUTPUT);
  pinMode(LA_PIN, OUTPUT);
  pinMode(BTN_PIN, INPUT_PULLUP);
  pinMode(PUMP_PIN, OUTPUT);
  pinMode(SOLENOID_PIN, OUTPUT);
  digitalWrite(LA_PIN, HIGH);
  digitalWrite(ST_PIN, HIGH);
  digitalWrite(PUMP_PIN, LOW);
  digitalWrite(SOLENOID_PIN, LOW);
}

void writeToSr(byte data) {
  digitalWrite(ST_PIN, LOW);
  SPI.transfer(data);             // Send output byte
  digitalWrite(ST_PIN, HIGH);  // Latch output
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
  Serial.println("LOG: PUMP OFF");

}

void releasePump() {
  digitalWrite(PUMP_PIN, LOW);
  delay(100);
  digitalWrite(SOLENOID_PIN, HIGH);
  delay(100);
  pumpRunning = false;
  Serial.println("LOG: PUMP RELEASE");
}

void pump_on_off()
{
  
  turnOnPump();
  Serial.println("pump on");
  delay(2000);
  releasePump();
  Serial.println("pump release");
  delay(2000);
  shutOffPump();
  Serial.println("LOG: PUMP ONOFF");
}



void handlePump() {
  if (pumpRunning && (millis() - pumpStartTime >= pumpTimeout)) {
    shutOffPump();

    // //Transmit that the pump has been turned off
    // byte msg = build_message_byte(PUMP_CMD, 0, 0);
    // Serial.write(msg);
  }
}
void update165() {
  // Latch the inputs into the shift register
  digitalWrite(LA_PIN, LOW);
  delayMicroseconds(5);
  digitalWrite(LA_PIN, HIGH);
  delayMicroseconds(5);
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
  }
  else if (data == 0 && last_data != 0) {
    Serial.println("LOG light renewed :)");
    char msg[40];
    sprintf(msg,"LOG prev data %d",last_data);
    Serial.println(msg);
  }
  last_data = data;
}


int bit_index(byte x) {
  // int i = 0;
  // while (x >>= 1) i++;
  // return i;

  //Like the code above, but apparently native, counts trailing zeros
  return __builtin_ctz(x);
}

// register reset button after ms_to_reset milliseconds, so user gets response more immediatly than on release.
void handleButtonPress() {
  static bool wasPressed = false;
  static unsigned long pressStart = 0;
  static bool sentStart = false;
  bool pressed = !digitalRead(BTN_PIN); // pullup defaults to high except on press.
  if (pressed && !wasPressed) 
  {
    wasPressed = true;
    pressStart = millis();
  }
  else if (!pressed)
  {
    wasPressed = false;
    sentStart = false;
  }
  else if (wasPressed && !sentStart && (millis() - pressStart) > ms_to_reset)
  {
    Serial.println("START");
    sentStart = true;
  }
}


void reset_solenoids(String stackSizes)
{
  bool customWait = false;
  if(stackSizes.length() > 0)
    customWait = true;
  for(int i=0;i<7;++i)
  {
    char msg[40];
    writeToSr(1 << i);
    int pucksToRemove = 6;
    if(customWait)
      pucksToRemove = stackSizes.substring(i,i+1).toInt(); // take the current puck stack size and apply to multiplier
    sprintf(msg,"LOG turn off solenoid %d for %d pucks", i, pucksToRemove);
    Serial.println(msg);
    delay(500 * pucksToRemove); 
  }
  writeToSr(0);
}

void open_solenoids()
{
  writeToSr(0x7f);
  Serial.println("LOG: OPEN ALL SOLENOIDS");
}


void close_solenoids()
{
  writeToSr(0);
  Serial.println("LOG: CLOSE ALL SOLENOIDS");
}

// void ack(byte msg) {
//   Serial.write(msg | (0b1 << 7));
// }
void handle_cmd(String cmd) {
  if(cmd.startsWith("RESET"))
    reset_solenoids(cmd.substring(6)); // assuming we might get RESET 3025213
  else if(cmd == "PUMP ON")
    turnOnPump();
  else if(cmd == "PUMP OFF")
    shutOffPump();
  else if(cmd == "PUMP RELEASE")
    releasePump();
  else if(cmd == "PUMP ONOFF")
    pump_on_off();
  else if (cmd == "OPEN")
    open_solenoids();
  else if (cmd == "CLOSE")
    close_solenoids();
}



