#!/usr/bin/env python3
"""
Драйвер LCD дисплея MGB-LCD12864
Подключается по I2C
"""

import smbus2
import time
import logging

logger = logging.getLogger('display')


class LCDDisplay:
    """Класс для работы с LCD дисплеем"""
    
    def __init__(self, i2c_bus=1, i2c_addr=0x3F):
        self.bus = None
        self.addr = i2c_addr
        self.enabled = False
        
        try:
            self.bus = smbus2.SMBus(i2c_bus)
            self._init()
            self.enabled = True
            logger.info(f"LCD initialized at 0x{i2c_addr:02X}")
        except Exception as e:
            logger.error(f"LCD init error: {e}")
            self.enabled = False
    
    def _write_byte(self, data, mode=0):
        """Записать байт в дисплей"""
        if not self.bus:
            return
        try:
            self.bus.write_byte_data(self.addr, mode, data)
        except Exception as e:
            logger.error(f"LCD write error: {e}")
    
    def _send_command(self, cmd):
        """Отправить команду"""
        self._write_byte(cmd, 0x00)
    
    def _send_data(self, data):
        """Отправить данные"""
        self._write_byte(data, 0x40)
    
    def _init(self):
        """Инициализация дисплея"""
        time.sleep(0.05)
        
        # Последовательность инициализации для HD44780
        self._send_command(0x33)
        time.sleep(0.005)
        self._send_command(0x32)
        time.sleep(0.005)
        self._send_command(0x28)  # 4-bit mode, 2 lines, 5x8 font
        self._send_command(0x0C)  # Display on, cursor off
        self._send_command(0x06)  # Increment cursor
        self._send_command(0x01)  # Clear display
        time.sleep(0.002)
        
        logger.info("LCD initialized")
    
    def clear(self):
        """Очистить дисплей"""
        if self.enabled:
            self._send_command(0x01)
            time.sleep(0.002)
    
    def set_cursor(self, row, col):
        """Установить курсор"""
        if not self.enabled:
            return
        addr = 0x80 if row == 0 else 0xC0
        addr += col
        self._send_command(addr)
    
    def write_string(self, text):
        """Написать строку"""
        if not self.enabled:
            return
        for char in text[:16]:
            self._send_data(ord(char))
    
    def display_weather(self, data):
        """Отобразить данные погодной станции"""
        if not self.enabled:
            return
        
        self.clear()
        
        # Первая строка: Arduino данные
        arduino = data.get('arduino', {})
        temp = arduino.get('temp')
        humid = arduino.get('humid')
        
        if temp is not None and humid is not None:
            line1 = f"T:{temp:.1f}C H:{humid:.0f}%"
        else:
            line1 = "No Arduino data"
        
        self.set_cursor(0, 0)
        self.write_string(line1)
        
        # Вторая строка: Elbear данные
        elbear = data.get('elbear', {})
        temp_e = elbear.get('temp')
        press = elbear.get('press')
        
        if temp_e is not None and press is not None:
            line2 = f"E:{temp_e:.1f}C P:{press:.0f}"
        else:
            line2 = "No Elbear data"
        
        self.set_cursor(1, 0)
        self.write_string(line2)
    
    def update_loop(self, get_data_func, interval=5):
        """Цикл обновления дисплея"""
        logger.info("LCD update loop started")
        while True:
            try:
                data = get_data_func()
                self.display_weather(data)
            except Exception as e:
                logger.error(f"LCD update error: {e}")
            time.sleep(interval)
