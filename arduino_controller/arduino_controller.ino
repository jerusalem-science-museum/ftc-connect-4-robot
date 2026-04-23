#include <SPI.h>
#include <stdint.h>
#include "sensor_handler.h"

#define PUCK_ANALOG_PIN A2

void setup() {
  Serial.begin(115200);
  Serial.println("LOG setting up");
  setup_sensors();

  SPI.begin();
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
  close_solenoids();
  delay(1000);
  Serial.println("LOG set up");
  // Serial.println("START");
}


void loop() {
  handleDiscDetection();
  handleButtonPress();
  handleResetSolenoids();                  
  if (Serial.available()) {
    handle_cmd(Serial.readStringUntil('\n'));
  }
}