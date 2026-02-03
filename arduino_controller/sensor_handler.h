#pragma once 

#include <SPI.h>
#include <stdint.h>
#include <string.h>

const int load_pin = 3;     //165 - read
const int latch_pin = 4;    //595 - write
const int btn_pin = 5;      //The start button

const int btn_ms_time = 1;  //Time for button to register a press
const int pump_pin = 8;
const int release_pump_pin = 7;
const int DEBOUNCE_MS = 1000;
unsigned long last_change_ms = 0;
byte solenoid_state = 0;

// Timing variables
unsigned long pumpStartTime = 0;
const unsigned long pumpTimeout = 30000UL;  // 30 seconds in ms
bool pumpRunning = false;

void setup_sensors()
{
  pinMode(latch_pin, OUTPUT);
  pinMode(load_pin, OUTPUT);
  pinMode(btn_pin, INPUT);
  pinMode(pump_pin, OUTPUT);
  pinMode(release_pump_pin, OUTPUT);
  digitalWrite(load_pin, HIGH);
  digitalWrite(latch_pin, HIGH);
  digitalWrite(pump_pin, LOW);
  digitalWrite(release_pump_pin, LOW);
}

void writeToSr(byte data) {
  digitalWrite(latch_pin, LOW);
  SPI.transfer(data);             // Send output byte
  digitalWrite(latch_pin, HIGH);  // Latch output
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
  digitalWrite(load_pin, LOW);
  delayMicroseconds(5);
  digitalWrite(load_pin, HIGH);
  delayMicroseconds(5);
}

void handleDiscDetection() {
  static byte last_data = 0;
  update165();
  byte data = SPI.transfer(0);
  data = (~data) & 0b01111111;
  //we have a rising edge
  if (data != 0 && last_data == 0) {
    Serial.println(data);
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


void handleButtonPress() {
  static int prevPressed = LOW;
  static unsigned long pressStart = 0;

  int pressed = digitalRead(btn_pin);

  if (pressed != prevPressed) {
    prevPressed = pressed;

    if (pressed == HIGH) {
      pressStart = millis();
    } else if (millis() - pressStart >= btn_ms_time) {
      Serial.println("START");
    }
  }
}


void reset_solenoids()
{
  for(int i=0;i<7;++i)
  {
    char msg[40];
    sprintf(msg,"LOG turn off solenoid %d",i);
    Serial.println(msg);
    writeToSr(1 << i);
    delay(3000); 
  }
  writeToSr(0);
  Serial.println("START"); // for now, restart immediatly. in future - button?
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
  if(cmd == "RESET")
    reset_solenoids();
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



