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
 *         la_pin (MISO)  D3-|       |-A6  
 *         st_pin (MOSI)  D4-|       |-A5   
 *               btn_pin  D5-|       |-A4  
 *                        D6-|       |-A3   
 *      release_pump_pin  D7-|       |-A2  
 *              pump_pin  D8-|       |-A1   
 *                        D9-|       |-A0   
   *                     D10-|       |-Ref
 *               SER_IN  D11-|       |-3.3V   
 *              SER_OUT  D12-|       |-D13 CLK (SPI)
 *                            --USB--        
 */


#define la_pin 3     //165 - read from photoresistors
#define st_pin 4    //595 - write for solenoids
#define btn_pin 5      //The start button 
#define release_pump_pin 7 //
#define pump_pin 8
#define DEBOUNCE_MS 1000

const int ms_to_reset = 2000; // no. of ms user needs to press button to reset the game.
unsigned long last_change_ms = 0;
byte solenoid_state = 0;

// Timing variables
unsigned long pumpStartTime = 0;
const unsigned long pumpTimeout = 30000UL;  // 30 seconds in ms
bool pumpRunning = false;

void setup_sensors()
{
  pinMode(st_pin, OUTPUT);
  pinMode(la_pin, OUTPUT);
  pinMode(btn_pin, INPUT_PULLUP);
  pinMode(pump_pin, OUTPUT);
  pinMode(release_pump_pin, OUTPUT);
  digitalWrite(la_pin, HIGH);
  digitalWrite(st_pin, HIGH);
  digitalWrite(pump_pin, LOW);
  digitalWrite(release_pump_pin, LOW);
}

void writeToSr(byte data) {
  digitalWrite(st_pin, LOW);
  SPI.transfer(data);             // Send output byte
  digitalWrite(st_pin, HIGH);  // Latch output
}


void turnOnPump() {
  digitalWrite(pump_pin, HIGH);
  digitalWrite(release_pump_pin, LOW);
  Serial.println("LOG: PUMP ON");
  pumpStartTime = millis();
  pumpRunning = true;
}

void shutOffPump() {

  digitalWrite(pump_pin, LOW);
  digitalWrite(release_pump_pin, LOW);
  pumpRunning = false;
  Serial.println("LOG: PUMP OFF");

}

void releasePump() {
  digitalWrite(pump_pin, LOW);
  delay(100);
  digitalWrite(release_pump_pin, HIGH);
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
  digitalWrite(la_pin, LOW);
  delayMicroseconds(5);
  digitalWrite(la_pin, HIGH);
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
  bool pressed = !digitalRead(btn_pin); // pullup defaults to high except on press.
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



