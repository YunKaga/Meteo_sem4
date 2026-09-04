"""
Weather Station Server для Raspberry Pi
Принимает JSON от Arduino и Elbear через Bluetooth (rfcomm)
"""
import json
import threading
import time
import logging
import serial
import os
from datetime import datetime
from flask import Flask, jsonify, render_template_string
from flask_socketio import SocketIO

# Настройка логирования
LOG_FILE = "weather_station.log"
logger = logging.getLogger('server')
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s')
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Порты rfcomm, которые мы настроили в /etc/bluetooth/rfcomm.conf
PORT_ARDUINO = '/dev/rfcomm1'
PORT_ELBEAR  = '/dev/rfcomm0'

HTTP_PORT = 5000

# Flask приложение
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Глобальное хранилище данных
weather_data = {
    'arduino': {'temp': None, 'humid': None, 'press': None, 'timestamp': None},
    'elbear': {
        'THP80_temp': None, 'THP80_hum': None, 'THP80_press': None, 'L75_lux': None,
        'CLM60_red': None, 'CLM60_green': None, 'CLM60_blue': None, 'CLM60_clear': None, 'CLM60_proximity': None,
        'A6_accel_x': None, 'A6_accel_y': None, 'A6_accel_z': None,
        'A6_gyro_x': None, 'A6_gyro_y': None, 'A6_gyro_z': None,
        'CO30_eco2': None, 'CO30_tvoc': None, 'D20_distance': None, 'timestamp': None
    },
    'last_update': None
}

FONT_5x8 = [
    [0x00,0x00,0x00,0x00,0x00],[0x00,0x00,0x2F,0x00,0x00],[0x00,0x07,0x00,0x07,0x00],[0x14,0x7F,0x14,0x7F,0x14],
    [0x24,0x2A,0x7F,0x2A,0x12],[0x23,0x13,0x08,0x64,0x62],[0x36,0x49,0x55,0x22,0x50],[0x00,0x05,0x03,0x00,0x00],
    [0x00,0x1C,0x22,0x41,0x00],[0x00,0x41,0x22,0x1C,0x00],[0x14,0x08,0x3E,0x08,0x14],[0x08,0x08,0x3E,0x08,0x08],
    [0x00,0x50,0x30,0x00,0x00],[0x08,0x08,0x08,0x08,0x08],[0x00,0x30,0x30,0x00,0x00],[0x20,0x10,0x08,0x04,0x02],
    [0x3E,0x51,0x49,0x45,0x3E],[0x00,0x42,0x7F,0x40,0x00],[0x42,0x61,0x51,0x49,0x46],[0x21,0x41,0x45,0x4B,0x31],
    [0x18,0x14,0x12,0x7F,0x10],[0x27,0x45,0x45,0x45,0x39],[0x3C,0x4A,0x49,0x49,0x30],[0x01,0x71,0x09,0x05,0x03],
    [0x36,0x49,0x49,0x49,0x36],[0x06,0x49,0x49,0x29,0x1E],[0x00,0x36,0x36,0x00,0x00],[0x00,0x56,0x36,0x00,0x00],
    [0x08,0x14,0x22,0x41,0x00],[0x14,0x14,0x14,0x14,0x14],[0x00,0x41,0x22,0x14,0x08],[0x02,0x01,0x51,0x09,0x06],
    [0x32,0x49,0x79,0x41,0x3E],[0x7E,0x11,0x11,0x11,0x7E],[0x7F,0x49,0x49,0x49,0x36],[0x3E,0x41,0x41,0x41,0x22],
    [0x7F,0x41,0x41,0x22,0x1C],[0x7F,0x49,0x49,0x49,0x41],[0x7F,0x09,0x09,0x09,0x01],[0x3E,0x41,0x49,0x49,0x7A],
    [0x7F,0x08,0x08,0x08,0x7F],[0x00,0x41,0x7F,0x41,0x00],[0x20,0x40,0x41,0x3F,0x01],[0x7F,0x08,0x14,0x22,0x41],
    [0x7F,0x40,0x40,0x40,0x40],[0x7F,0x02,0x0C,0x02,0x7F],[0x7F,0x04,0x08,0x10,0x7F],[0x3E,0x41,0x41,0x41,0x3E],
    [0x3F,0x09,0x09,0x09,0x06],[0x3E,0x41,0x51,0x21,0x5E],[0x7F,0x09,0x19,0x29,0x46],[0x46,0x49,0x49,0x49,0x31],
    [0x01,0x01,0x7F,0x01,0x01],[0x3F,0x40,0x40,0x40,0x3F],[0x1F,0x20,0x40,0x20,0x1F],[0x3F,0x40,0x30,0x40,0x3F],
    [0x63,0x14,0x08,0x14,0x63],[0x07,0x08,0x70,0x08,0x07],[0x61,0x51,0x49,0x45,0x43],[0x00,0x7F,0x41,0x41,0x00],
    [0x02,0x04,0x08,0x10,0x20],[0x00,0x41,0x41,0x7F,0x00],[0x04,0x02,0x01,0x02,0x04],[0x40,0x40,0x40,0x40,0x40],
    [0x00,0x01,0x02,0x04,0x00],[0x20,0x54,0x54,0x54,0x78],[0x7F,0x50,0x48,0x48,0x30],[0x38,0x44,0x44,0x44,0x20],
    [0x38,0x44,0x44,0x48,0x7F],[0x38,0x54,0x54,0x54,0x18],[0x08,0x7E,0x09,0x01,0x02],[0x0C,0x52,0x52,0x52,0x3E],
    [0x7F,0x08,0x04,0x04,0x78],[0x00,0x44,0x7D,0x40,0x00],[0x20,0x40,0x44,0x3D,0x00],[0x7F,0x10,0x28,0x44,0x00],
    [0x00,0x41,0x7F,0x40,0x00],[0x7C,0x04,0x18,0x04,0x78],[0x7C,0x08,0x04,0x04,0x78],[0x38,0x44,0x44,0x44,0x38],
    [0x7C,0x14,0x14,0x14,0x08],[0x08,0x14,0x14,0x08,0x7C],[0x7C,0x08,0x04,0x04,0x08],[0x48,0x54,0x54,0x54,0x20],
    [0x04,0x3F,0x44,0x40,0x20],[0x3C,0x40,0x40,0x20,0x7C],[0x1C,0x20,0x40,0x20,0x1C],[0x3C,0x40,0x30,0x40,0x3C],
    [0x44,0x28,0x10,0x28,0x44],[0x0C,0x50,0x50,0x50,0x3C],[0x44,0x64,0x54,0x4C,0x44],[0x00,0x08,0x36,0x41,0x00],
    [0x00,0x00,0x7F,0x00,0x00],[0x00,0x41,0x36,0x08,0x00],[0x30,0x08,0x10,0x20,0x18],[0x7F,0x55,0x49,0x55,0x7F]
]

class GraphicalLCDDisplay:
    """Класс для работы с графическим LCD 128x64 (KS0108) через I2C расширитель MCP23017"""
    
    # Регистры MCP23017
    IODIRA = 0x00
    IODIRB = 0x01
    GPIOA  = 0x12
    GPIOB  = 0x13

    # Пины порта A (Управление) - согласно вашей схеме из C++ кода
    LCD_LIGHT  = 0x01
    LCD_CS1    = 0x04  # Левая половина экрана
    LCD_CS2    = 0x08  # Правая половина экрана
    LCD_RESET  = 0x10
    LCD_DATA   = 0x20  # 1 = данные, 0 = команда
    LCD_ENABLE = 0x80

    # Команды KS0108
    LCD_ON       = 0x3F
    LCD_SET_ADD  = 0x40  # Адрес X (0-63)
    LCD_SET_PAGE = 0xB8  # Страница Y (0-7, по 8 пикселей)

    def __init__(self, i2c_bus=1, i2c_addr=0x20):
        self.enabled = False
        self.addr = i2c_addr
        
        try:
            import smbus2
            self.bus = smbus2.SMBus(i2c_bus)
            
            # Настраиваем порты A и B на выход
            self.bus.write_byte_data(self.addr, self.IODIRA, 0x00)
            self.bus.write_byte_data(self.addr, self.IODIRB, 0x00)
            
            # Аппаратный сброс (дергаем RESET)
            self._write_port_a(0x00)
            time.sleep(0.01)
            self._write_port_a(self.LCD_RESET | self.LCD_LIGHT)
            time.sleep(0.05)
            
            # Включаем оба чипа KS0108
            self._cmd(self.LCD_ON, self.LCD_CS1)
            self._cmd(self.LCD_ON, self.LCD_CS2)
            
            self.clear()
            self.enabled = True
            logger.info("Графический LCD 128x64 (MCP23017) успешно инициализирован")
        except Exception as e:
            logger.error(f"Ошибка инициализации LCD: {e}. Проверьте адрес (обычно 0x20) и подключение I2C.")
            self.enabled = False

    def _write_port_a(self, val):
        self.bus.write_byte_data(self.addr, self.GPIOA, val)

    def _write_port_b(self, val):
        self.bus.write_byte_data(self.addr, self.GPIOB, val)

    def _send(self, data, rs, cs):
        """Отправка байта с формированием импульса Enable"""
        base = self.LCD_RESET | self.LCD_LIGHT | rs | cs
        
        self._write_port_b(data)               # Кладем данные на порт B
        self._write_port_a(base | self.LCD_ENABLE) # Поднимаем Enable
        time.sleep(0.000002)                   # Задержка 2 мкс (KS0108 требует >450нс)
        self._write_port_a(base)               # Опускаем Enable

    def _cmd(self, data, cs):
        self._send(data, 0x00, cs)

    def _data(self, data, cs):
        self._send(data, self.LCD_DATA, cs)

    def gotoxy(self, x, y):
        """Установка курсора (x: 0-127, y: 0-63)"""
        if x >= 64:
            cs = self.LCD_CS2
            x -= 64
        else:
            cs = self.LCD_CS1
        
        page = y >> 3  # Делим на 8, так как страница = 8 пикселей по высоте
        self._cmd(self.LCD_SET_PAGE | page, cs)
        self._cmd(self.LCD_SET_ADD | (x & 0x3F), cs)

    def clear(self):
        """Очистка экрана (заполнение нулями)"""
        for page in range(8):
            # Очищаем левую половину (CS1)
            self._cmd(self.LCD_SET_PAGE | page, self.LCD_CS1)
            self._cmd(self.LCD_SET_ADD | 0, self.LCD_CS1)
            for _ in range(64):
                self._data(0x00, self.LCD_CS1)
            
            # Очищаем правую половину (CS2)
            self._cmd(self.LCD_SET_PAGE | page, self.LCD_CS2)
            self._cmd(self.LCD_SET_ADD | 0, self.LCD_CS2)
            for _ in range(64):
                self._data(0x00, self.LCD_CS2)
        self.gotoxy(0, 0)

    def draw_char(self, x, y, char):
        """Вывод одного символа"""
        if ord(char) < 32 or ord(char) > 126:
            char = '?'
        idx = ord(char) - 32
        glyph = FONT_5x8[idx]
        
        for i in range(5):
            if x >= 128: break
            self.gotoxy(x, y)
            cs = self.LCD_CS2 if x >= 64 else self.LCD_CS1
            self._data(glyph[i], cs)
            x += 1
        
        # 1 пиксель отступа между символами
        if x < 128:
            self.gotoxy(x, y)
            cs = self.LCD_CS2 if x >= 64 else self.LCD_CS1
            self._data(0x00, cs)

    def draw_text(self, x, y, text):
        """Вывод строки"""
        for char in text:
            self.draw_char(x, y, char)
            x += 6  # 5 пикселей ширина + 1 пиксель отступ

    def display_data(self, data):
        """Отображение данных на графическом дисплее"""
        if not self.enabled: return
        self.clear()
        
        # Заголовок
        self.draw_text(0, 0, "Weather Station")
        
        # Данные Arduino (Y=16)
        arduino = data.get('arduino', {})
        temp = arduino.get('temp')
        humid = arduino.get('humid')
        if temp is not None and humid is not None:
            line1 = f"Arduino: {temp:.1f}C {humid:.0f}%"
        else:
            line1 = "Arduino: No data"
        self.draw_text(0, 16, line1)

        # Данные Elbear (Y=32)
        elbear = data.get('elbear', {})
        temp_e = elbear.get('THP80_temp')
        press = elbear.get('THP80_press')
        if temp_e is not None and press is not None:
            line2 = f"Elbear: {temp_e:.1f}C {press:.0f}mm"
        else:
            line2 = "Elbear: No data"
        self.draw_text(0, 32, line2)
        
        # Статус (Y=48)
        last_upd = data.get('last_update')
        if last_upd:
            # Выводим только время (последние 8 символов)
            time_str = last_upd.split('T')[1][:8] if 'T' in last_upd else last_upd[:8]
            self.draw_text(0, 48, f"Updated: {time_str}")
        else:
            self.draw_text(0, 48, "Waiting for data...")


def lcd_update_loop(lcd, interval=5):
    """Периодическое обновление LCD дисплея"""
    logger.info("Запуск цикла обновления LCD")
    while True:
        try:
            lcd.display_data(weather_data)
            time.sleep(interval)
        except Exception as e:
            logger.error(f"Ошибка обновления LCD: {e}")
            time.sleep(interval)

# ==================== Bluetooth клиент (Serial) ====================
class BluetoothSerialClient:
    """Читает данные из виртуального COM-порта (rfcomm)"""
    def __init__(self, port, name):
        self.port = port
        self.name = name
        self.ser = None
        self.running = False

    def connect_and_read(self, callback):
        self.running = True
        while self.running:
            try:
                # Подключаемся к порту, если еще не подключены
                if not self.ser or not self.ser.is_open:
                    self.ser = serial.Serial(self.port, 9600, timeout=1)
                    logger.info(f"[{self.name}] Успешно открыт порт {self.port}")
                
                # Читаем строку
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    callback(self.name, line)
                    
            except serial.SerialException as e:
                logger.warning(f"[{self.name}] Ошибка порта {self.port}: {e}. Переподключение через 3 сек...")
                if self.ser and self.ser.is_open:
                    self.ser.close()
                time.sleep(3)
            except Exception as e:
                logger.error(f"[{self.name}] Непредвиденная ошибка: {e}")
                time.sleep(2)

    def stop(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()

# ==================== Парсинг данных ====================
def handle_bluetooth_data(source, json_str):
    """Обработчик данных от Bluetooth"""
    try:
        # Оба устройства теперь шлют валидный JSON с двойными кавычками
        data = json.loads(json_str)
        now = datetime.now().isoformat()
        
        if source == 'Arduino':
            weather_data['arduino'].update({
                'temp': data.get('temp'),
                'humid': data.get('humid'),
                'press': data.get('press') / 133.3,
                'timestamp': now
            })
            logger.info(f"[Arduino] Temp: {data.get('temp')}, Hum: {data.get('humid')}")
            
        elif source == 'Elbear':
            # Обновляем все поля Elbear
            weather_data['elbear'].update(data)
            weather_data['elbear']['timestamp'] = now
            logger.info(f"[Elbear] Temp: {data.get('THP80_temp')}, Lux: {data.get('L75_lux')}")
            
        weather_data['last_update'] = now
        
        # Отправляем обновление на веб-страницу через WebSocket
        socketio.emit('data_update', weather_data)
        
    except json.JSONDecodeError:
        logger.warning(f"[{source}] Получена не-JSON строка: {json_str}")
    except Exception as e:
        logger.error(f"[{source}] Ошибка парсинга: {e}")

# ==================== Web интерфейс ====================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Weather Station</title>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f4f4f9; }
        .container { max-width: 1200px; margin: 0 auto; display: flex; gap: 20px; flex-wrap: wrap; }
        .box { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); flex: 1; min-width: 300px; }
        h1 { text-align: center; color: #333; }
        h2 { color: #2c3e50; border-bottom: 2px solid #eee; padding-bottom: 10px; }
        .row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f8f9fa; }
        .label { font-weight: bold; color: #555; }
        .value { color: #2980b9; font-weight: bold; }
        .status { text-align: center; color: #7f8c8d; margin-bottom: 20px; }
    </style>
</head>
<body>
    <h1>🌤️ Weather Station Dashboard</h1>
    <div class="status">Last update: <span id="ts">-</span></div>
    <div class="container">
        <div class="box">
            <h2>🔌 Arduino MEGA</h2>
            <div id="arduino">Loading...</div>
        </div>
        <div class="box">
            <h2>🤖 Elbear (МГБот)</h2>
            <div id="elbear">Loading...</div>
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script>
        const socket = io();
        socket.on('data_update', d => render(d));
        fetch('/api/data').then(r=>r.json()).then(render);

        function render(d) {
            const a = d.arduino, e = d.elbear;
            const fmt = v => (v !== null && v !== undefined) ? Number(v).toFixed(1) : 'N/A';
            const fmtInt = v => (v !== null && v !== undefined) ? Math.round(v) : 'N/A';

            document.getElementById('arduino').innerHTML = `
                <div class="row"><span class="label">Temperature:</span><span class="value">${fmt(a.temp)} °C</span></div>
                <div class="row"><span class="label">Humidity:</span><span class="value">${fmt(a.humid)} %</span></div>
                <div class="row"><span class="label">Pressure:</span><span class="value">${fmt(a.press)} mmHg</span></div>
            `;

            document.getElementById('elbear').innerHTML = `
                <h3>Environment</h3>
                <div class="row"><span class="label">Temp (THP80):</span><span class="value">${fmt(e.THP80_temp)} °C</span></div>
                <div class="row"><span class="label">Hum (THP80):</span><span class="value">${fmt(e.THP80_hum)} %</span></div>
                <div class="row"><span class="label">Press (THP80):</span><span class="value">${fmt(e.THP80_press)} mmHg</span></div>
                <div class="row"><span class="label">Light (L75):</span><span class="value">${fmt(e.L75_lux)} lux</span></div>
                <h3>Motion & Distance</h3>
                <div class="row"><span class="label">Accel X/Y/Z:</span><span class="value">${fmt(e.A6_accel_x)} / ${fmt(e.A6_accel_y)} / ${fmt(e.A6_accel_z)}</span></div>
                <div class="row"><span class="label">Distance (D20):</span><span class="value">${fmtInt(e.D20_distance)} mm</span></div>
                <h3>Air Quality</h3>
                <div class="row"><span class="label">eCO2:</span><span class="value">${fmtInt(e.CO30_eco2)} ppm</span></div>
                <div class="row"><span class="label">TVOC:</span><span class="value">${fmtInt(e.CO30_tvoc)} ppb</span></div>
            `;
            document.getElementById('ts').textContent = d.last_update || '-';
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/data')
def get_data():
    return jsonify(weather_data)

# ==================== Запуск ====================
def main():
    logger.info("=" * 50)
    logger.info("Weather Station Server Starting")
    logger.info("=" * 50)

    # Создаем клиенты для чтения из rfcomm портов
    arduino_bt = BluetoothSerialClient(PORT_ARDUINO, 'Arduino')
    elbear_bt  = BluetoothSerialClient(PORT_ELBEAR,  'Elbear')

    # Инициализация LCD дисплея
    lcd = GraphicalLCDDisplay(i2c_addr=0x20)
    # Запуск потока обновления LCD
    if lcd.enabled:
        lcd_thread = threading.Thread(
            target=lcd_update_loop,
            args=(lcd, 5),  # Обновление каждые 5 секунд
            daemon=True
        )
        lcd_thread.start()
        logger.info("LCD дисплей активен")

    # Запускаем потоки чтения
    threading.Thread(target=arduino_bt.connect_and_read, args=(handle_bluetooth_data,), daemon=True).start()
    threading.Thread(target=elbear_bt.connect_and_read,  args=(handle_bluetooth_data,), daemon=True).start()

    # Запуск Flask и WebSocket
    logger.info(f"Web server on http://0.0.0.0:{HTTP_PORT}")
    socketio.run(app, host='0.0.0.0', port=HTTP_PORT, debug=False, allow_unsafe_werkzeug=True)

if __name__ == '__main__':
    main()
