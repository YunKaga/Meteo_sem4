#include "Sensors.h"

Sensors::Sensors() : dht22(5) {
}

void Sensors::begin() {
    Wire.begin();
    bmp.begin();
}

String Sensors::readData() {
    // Считываем данные
    float tmp_lm75 = temperature.readTemperatureC();
    float hum_dht = dht22.getHumidity();
    float tmp_dht = dht22.getTemperature();
    
    // BME280 возвращает давление в Паскалях. Переводим в мм.рт.ст. (mmHg)
    float press_bmp = bmp.readPressure();
    float tmp_bmp = bmp.readTemperature();

    // Формируем пакет для Raspberry Pi сервера:
    String packet = "{\"temp\": " + String(tmp_lm75, 1) + ", ";
    packet += "\"humid\": " + String(hum_dht, 1) + ", ";
    packet += "\"press\": " + String(press_bmp, 1) + "}";

    return packet;
}
