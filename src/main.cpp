#include "Arduino.h"

void setup() {
  pinMode(2, INPUT_PULLUP);
  Serial.begin(9600);
}

int min_value = 0;
int max_value = 1023;

void loop() {
  Serial.println(!digitalRead(2));
 
  float value = (analogRead(A0) - (double)min_value)/(max_value-min_value);
  
  //Serial.println(analogRead(A0));
  Serial.println(value);
  Serial.println();
  delay(100);
}
