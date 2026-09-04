#include "ElbearSensorHub.h"

ElbearSensorHub sensorHub;

void setup() {
    sensorHub.begin();
    delay(2000);
}

void loop() {
    sensorHub.readAllSensors();
    delay(5000);
}
