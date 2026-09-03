#ifndef ELBEAR_SENSOR_HUB_H
#define ELBEAR_SENSOR_HUB_H

#include <Arduino.h>
#include <Wire.h>
#include "Adafruit_SGP30.h"
#include "Adafruit_APDS9960.h"
#include "Adafruit_VL53L0X.h"
#include "Adafruit_BME280.h"
#include "BH1750.h"
#include "Adafruit_MPU6050.h"

#define ADDR_BME280   0x77
#define ADDR_BH1750   0x23
#define ADDR_VL53L0X  0x29
#define ADDR_APDS9960 0x39
#define ADDR_SGP30    0x58
#define ADDR_MPU6050  0x69

#define BLUETOOTH_BAUD 9600

class ElbearSensorHub {
public:
    ElbearSensorHub();
    void begin();
    void readAllSensors();

private:
    Adafruit_SGP30 sgp30;
    Adafruit_APDS9960 apds;
    Adafruit_VL53L0X vl53;
    Adafruit_BME280 bme280;
    BH1750 lightMeter;
    Adafruit_MPU6050 mpu;

    bool bme280_ok = false;
    bool bh1750_ok = false;
    bool vl53_ok = false;
    bool apds_ok = false;
    bool sgp30_ok = false;
    bool mpu_ok = false;

    int readSoundI2C();
    bool readLeakI2C();
};

#endif
