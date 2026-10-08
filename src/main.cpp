#include "Arduino.h"

void setup() {
  pinMode(2, INPUT_PULLUP);
  Serial.begin(9600);
}

int min_value = 550;
int max_value = 990;

float getValue() {
  float value = (analogRead(A0) - (double)min_value) / (max_value - min_value);
  if (value > 1.0) return 1;
  if (value < 0.0) return 0;
  return value;
}

void loop() {
  //Serial.println(!digitalRead(2));
  Serial.print(analogRead(A0));
  Serial.print("|");
  Serial.println(!digitalRead(2));
  //Serial.println();
  delay(20);
}
