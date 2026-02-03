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
  Serial.println("START");

  // Serial.println("START");  // later on will only turn on when button is pressed.

}

void detectAnalogDrop() {
  static float prev_value = analogRead(PUCK_ANALOG_PIN);
  static bool is_light = true;
  float value = analogRead(PUCK_ANALOG_PIN);
  if (prev_value - value > 200 && is_light) {
    Serial.println("puck covered");
    Serial.println(value);
    is_light = false;
    prev_value = value;
  }
  else if (value - prev_value > 200 & !is_light) {
    Serial.println("puck uncovered");
    Serial.println(value);
    is_light = true;
    prev_value = value;
  }

}

void loop() {
  handleDiscDetection();
  if (Serial.available()) {
    handle_cmd(Serial.readStringUntil('\n'));
  }
}