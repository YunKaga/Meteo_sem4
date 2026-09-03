#!/usr/bin/env python3
"""
Bluetooth клиент для Raspberry Pi
Использует D-Bus интерфейс BlueZ для подключения к HC-05
"""

import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib
import threading
import time
import logging

logger = logging.getLogger('bluetooth')

# SPP UUID для HC-05
SPP_UUID = "00001101-0000-1000-8000-00805F9B34FB"


class BluetoothDevice:
    """Класс для работы с Bluetooth устройством через D-Bus"""
    
    def __init__(self, mac, name, callback):
        self.mac = mac
        self.name = name
        self.callback = callback
        self.bus = None
        self.device = None
        self.device_path = None
        self.running = False
        self.connected = False
        
    def init_dbus(self):
        """Инициализация D-Bus соединения"""
        try:
            dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
            self.bus = dbus.SystemBus()
            self.device_path = f"/org/bluez/hci0/dev_{self.mac.replace(':', '_')}"
            logger.info(f"[{self.name}] D-Bus initialized, path: {self.device_path}")
            return True
        except Exception as e:
            logger.error(f"[{self.name}] D-Bus init error: {e}")
            return False
    
    def get_device(self):
        """Получить объект устройства"""
        try:
            self.device = dbus.Interface(
                self.bus.get_object('org.bluez', self.device_path),
                'org.bluez.Device1'
            )
            return True
        except Exception as e:
            logger.error(f"[{self.name}] Get device error: {e}")
            return False
    
    def connect(self):
        """Подключиться к устройству"""
        try:
            if not self.device:
                if not self.get_device():
                    return False
            
            logger.info(f"[{self.name}] Connecting to {self.mac}...")
            self.device.Connect()
            self.connected = True
            logger.info(f"[{self.name}] Connected")
            return True
        except dbus.exceptions.DBusException as e:
            logger.error(f"[{self.name}] Connect error: {e}")
            self.connected = False
            return False
        except Exception as e:
            logger.error(f"[{self.name}] Connect error: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Отключиться от устройства"""
        try:
            if self.device and self.connected:
                self.device.Disconnect()
                self.connected = False
                logger.info(f"[{self.name}] Disconnected")
        except Exception as e:
            logger.error(f"[{self.name}] Disconnect error: {e}")
    
    def read_loop(self):
        """Цикл чтения данных"""
        self.running = True
        
        while self.running:
            try:
                if not self.connected:
                    if not self.connect():
                        time.sleep(5)
                        continue
                
                # Читаем свойства устройства
                props = dbus.Interface(
                    self.bus.get_object('org.bluez', self.device_path),
                    'org.freedesktop.DBus.Properties'
                )
                
                # Проверяем статус подключения
                connected = props.Get('org.bluez.Device1', 'Connected')
                if not connected:
                    logger.warning(f"[{self.name}] Disconnected unexpectedly")
                    self.connected = False
                    time.sleep(2)
                    continue
                
                # Пробуем читать через subprocess и rfcomm
                import subprocess
                
                # Находим номер rfcomm устройства
                rfcomm_num = self._get_rfcomm_number()
                if rfcomm_num is None:
                    logger.warning(f"[{self.name}] No rfcomm device found")
                    time.sleep(2)
                    continue
                
                # Читаем из устройства
                try:
                    with open(f'/dev/rfcomm{rfcomm_num}', 'r') as f:
                        f.settimeout(5.0)
                        while self.running and self.connected:
                            try:
                                line = f.readline()
                                if line:
                                    line = line.strip()
                                    if line:
                                        self.callback(self.name, line)
                            except Exception as e:
                                logger.error(f"[{self.name}] Read error: {e}")
                                break
                except Exception as e:
                    logger.error(f"[{self.name}] Open rfcomm error: {e}")
                    time.sleep(2)
                    
            except Exception as e:
                logger.error(f"[{self.name}] Loop error: {e}")
                time.sleep(5)
    
    def _get_rfcomm_number(self):
        """Найти номер rfcomm устройства для этого MAC"""
        try:
            import subprocess
            result = subprocess.run(
                ['rfcomm'],
                capture_output=True,
                text=True
            )
            for line in result.stdout.split('\n'):
                if self.mac in line:
                    # Формат: rfcomm0: 98:DA:50:04:2F:B8 channel 1 clean
                    parts = line.split(':')
                    if parts:
                        num_str = parts[0].replace('rfcomm', '').strip()
                        return int(num_str)
        except Exception as e:
            logger.error(f"[{self.name}] Get rfcomm number error: {e}")
        return None
    
    def stop(self):
        """Остановить чтение"""
        self.running = False
        self.disconnect()


class BluetoothManager:
    """Менеджер Bluetooth устройств"""
    
    def __init__(self):
        self.devices = {}
        self.threads = []
        
    def add_device(self, mac, name, callback):
        """Добавить устройство"""
        device = BluetoothDevice(mac, name, callback)
        self.devices[name] = device
        return device
    
    def start_all(self):
        """Запустить все устройства"""
        for name, device in self.devices.items():
            if device.init_dbus():
                thread = threading.Thread(
                    target=device.read_loop,
                    daemon=True
                )
                thread.start()
                self.threads.append(thread)
                logger.info(f"[{name}] Thread started")
    
    def stop_all(self):
        """Остановить все устройства"""
        for name, device in self.devices.items():
            device.stop()
            logger.info(f"[{name}] Stopped")
