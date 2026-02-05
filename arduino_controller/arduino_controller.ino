#include <SPI.h>
#include <stdint.h>
#include "sensor_handler.h"

#define PUCK_ANALOG_PIN A2

void setup() {
  Serial.begin(115200);
  Serial.println("LOG setting up");
  pinMode(PUCK_ANALOG_PIN, INPUT);
  pinMode(latch_pin, OUTPUT);
  pinMode(load_pin, OUTPUT);
  pinMode(btn_pin, INPUT);
  pinMode(pump_pin, OUTPUT);
  pinMode(release_pump_pin, OUTPUT);

  digitalWrite(load_pin, HIGH);
  digitalWrite(latch_pin, HIGH);
  digitalWrite(pump_pin, LOW);
  digitalWrite(release_pump_pin, LOW);

  SPI.begin();
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
  close_solenoids();
  delay(1000);
  Serial.println("LOG set up");
}


void loop() {
  handleDiscDetection();
  handleButtonPress();
  if (Serial.available()) {
    handle_cmd(Serial.readStringUntil('\n'));
  }
}