#include "Sensors.h"

Sensors sensors;

void setup() {
    while (!Serial) delay(1000);
    Serial.begin(38400);
    Serial1.begin(9600);
    sensors.begin();
}

void loop() {
    String data = sensors.readData();
    Serial.println(data);
    Serial1.println(data);
    delay(5000);
}
