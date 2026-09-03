#include "ElbearSensorHub.h"

ElbearSensorHub::ElbearSensorHub() {
}

void ElbearSensorHub::begin() {
    Serial.begin(9600);
    while (!Serial) delay(10);
    
    Serial1.begin(BLUETOOTH_BAUD);
    Wire.begin();

    Serial.println("=== Elbear Sensor Hub v3.0 (Pure I2C) ===");
    Serial.println("Инициализация I2C датчиков...");
    Serial1.println("Elbear Sensor Hub v3.0");

    // BME280 (0x77)
    if (bme280.begin(ADDR_BME280)) {
        bme280_ok = true;
        Serial.println("[OK] MGS-THP80 (BME280) найден на 0x77");
    } else {
        Serial.println("[FAIL] MGS-THP80 не найден");
    }

    // BH1750 (0x23)
    if (lightMeter.begin(BH1750::CONTINUOUS_HIGH_RES_MODE)) {
        bh1750_ok = true;
        Serial.println("[OK] MGS-L75 (BH1750) найден на 0x23");
    } else {
        Serial.println("[FAIL] MGS-L75 не найден");
    }

    // VL53L0X (0x29)
    if (vl53.begin()) {
        vl53_ok = true;
        Serial.println("[OK] MGS-D20 (VL53L0X) найден на 0x29");
    } else {
        Serial.println("[FAIL] MGS-D20 не найден");
    }

    // APDS-9960 (0x39) - ПРИОРИТЕТ над датчиком пламени
    if (apds.begin(ADDR_APDS9960)) {
        apds_ok = true;
        apds.enableProximity(true);
        apds.enableColor(true);
        Serial.println("[OK] MGS-CLM60 (APDS-9960) найден на 0x39");
    } else {
        Serial.println("[FAIL] MGS-CLM60 не найден");
    }
    Serial.println("[INFO] Датчик пламени отключен (конфликт адреса 0x39)");

    // SGP30 (0x58)
    if (sgp30.begin()) {
        sgp30_ok = true;
        sgp30.setIAQBaseline(0x8973, 0x8AAE);
        Serial.println("[OK] MGS-CO30 (SGP30) найден на 0x58");
    } else {
        Serial.println("[FAIL] MGS-CO30 не найден");
    }

    // MPU6050 (0x69) - ЯВНАЯ передача адреса!
    if (mpu.begin(ADDR_MPU6050)) {
        mpu_ok = true;
        mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
        mpu.setGyroRange(MPU6050_RANGE_500_DEG);
        Serial.println("[OK] MGS-A6 (MPU6050) найден на 0x69");
    } else {
        Serial.println("[FAIL] MGS-A6 не найден");
        // Пробуем адрес 0x68
        if (mpu.begin(0x68)) {
            mpu_ok = true;
            mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
            mpu.setGyroRange(MPU6050_RANGE_500_DEG);
            Serial.println("[OK] MGS-A6 (MPU6050) найден на 0x68");
        }
    }

    Serial.println("===============================");
    Serial.println("Все I2C датчики инициализированы!");
    Serial1.println("Все датчики инициализированы");
}

void ElbearSensorHub::readAllSensors() {
    String data = "{";
    bool first = true;

    // BME280
    if (bme280_ok) {
        if (!first) data += ",";
        data += "\"THP80_temp\": " + String(bme280.readTemperature(), 1);
        data += ",\"THP80_hum\": " + String(bme280.readHumidity(), 1);
        data += ",\"THP80_press\": " + String(bme280.readPressure() / 133.322, 1);
        first = false;
    }

    // BH1750
    if (bh1750_ok) {
        if (!first) data += ",";
        data += "\"L75_lux\": " + String(lightMeter.readLightLevel(), 1);
        first = false;
    }

    // Датчик пламени - отключен
    if (!first) data += ",";
    data += "\"FR403_flame\": \"DISABLED_CONFLICT\"";
    first = false;

    // APDS-9960
    if (apds_ok) {
        if (!first) data += ",";
        if (apds.colorDataReady()) {
            uint16_t r, g, b, c;
            apds.getColorData(&r, &g, &b, &c);
            data += "\"CLM60_red\": " + String(r);
            data += ",\"CLM60_green\": " + String(g);
            data += ",\"CLM60_blue\": " + String(b);
            data += ",\"CLM60_clear\": " + String(c);
        }
        data += ",\"CLM60_proximity\": " + String(apds.readProximity());
        first = false;
    }

    // MPU6050
    if (mpu_ok) {
        if (!first) data += ",";
        sensors_event_t a, g, temp;
        mpu.getEvent(&a, &g, &temp);
        data += "\"A6_accel_x\": " + String(a.acceleration.x, 2);
        data += ",\"A6_accel_y\": " + String(a.acceleration.y, 2);
        data += ",\"A6_accel_z\": " + String(a.acceleration.z, 2);
        data += ",\"A6_gyro_x\": " + String(g.gyro.x, 2);
        data += ",\"A6_gyro_y\": " + String(g.gyro.y, 2);
        data += ",\"A6_gyro_z\": " + String(g.gyro.z, 2);
        first = false;
    }

    // SGP30
    if (sgp30_ok) {
        if (!first) data += ",";
        if (sgp30.IAQmeasure()) {
            data += "\"CO30_eco2\": " + String(sgp30.eCO2);
            data += ",\"CO30_tvoc\": " + String(sgp30.TVOC);
        } else {
            data += "\"CO30_eco2\": 0,\"CO30_tvoc\": 0";
        }
        first = false;
    }

    // VL53L0X
    if (vl53_ok) {
        if (!first) data += ",";
        VL53L0X_RangingMeasurementData_t measure;
        vl53.rangingTest(&measure, false);
        if (measure.RangeStatus != 4) {
            data += "\"D20_distance\": " + String(measure.RangeMilliMeter);
        } else {
            data += "\"D20_distance\": -1";
        }
    }

    data += "}";

    Serial1.println(data);
    Serial.println(data);
}
