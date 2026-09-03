#!/bin/bash

# MAC-адреса устройств (замените на свои)
ELBEAR_MAC="98:DA:50:04:2C:30"
ARDUINO_MAC="98:DA:50:04:2F:B8"

# Функция подключения
connect_device() {
    echo "Подключение к $1..."
    echo "connect $1" | bluetoothctl
    sleep 2
}

# Основной цикл
while true; do
    # Проверка подключения к Elbear
    if ! bluetoothctl info $ELBEAR_MAC | grep -q "Connected: yes"; then
        echo "Elbear не подключен. Подключаем..."
        connect_device $ELBEAR_MAC
    fi
    
    # Проверка подключения к Arduino
    if ! bluetoothctl info $ARDUINO_MAC | grep -q "Connected: yes"; then
        echo "Arduino не подключен. Подключаем..."
        connect_device $ARDUINO_MAC
    fi
    
    sleep 10
done
