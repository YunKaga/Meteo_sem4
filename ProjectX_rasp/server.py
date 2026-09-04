"""
Weather Station Server для Raspberry Pi
Принимает JSON от Arduino и Elbear через Bluetooth (rfcomm)
"""
import json
import threading
import time
import logging
import serial
from datetime import datetime
from flask import Flask, jsonify, render_template_string
from flask_socketio import SocketIO

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')
logger = logging.getLogger('server')

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
# Добавьте этот класс в server.py (после импортов)

class LCDDisplay:
    """Класс для работы с LCD дисплеем 16x2 через I2C"""
    def __init__(self, i2c_bus=1, i2c_addr=0x3F):
        self.enabled = False
        try:
            import smbus2
            self.bus = smbus2.SMBus(i2c_bus)
            self.addr = i2c_addr
            self._init()
            self.enabled = True
            logger.info("LCD дисплей инициализирован")
        except Exception as e:
            logger.error(f"Ошибка инициализации LCD: {e}")
            self.enabled = False
    
    def _write_byte(self, data, mode=0):
        """Запись байта в дисплей"""
        if not self.bus:
            return
        try:
            self.bus.write_byte_data(self.addr, mode, data)
            time.sleep(0.001)
        except:
            pass
    
    def _send_command(self, cmd):
        """Отправка команды"""
        self._write_byte(cmd, 0x00)
    
    def _send_data(self, data):
        """Отправка данных"""
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
    
    def clear(self):
        """Очистка дисплея"""
        if self.enabled:
            self._send_command(0x01)
            time.sleep(0.002)
    
    def set_cursor(self, row, col):
        """Установка курсора (row: 0 или 1, col: 0-15)"""
        if not self.enabled:
            return
        addr = 0x80 if row == 0 else 0xC0
        addr += col
        self._send_command(addr)
    
    def write_string(self, text):
        """Вывод строки"""
        if not self.enabled:
            return
        for char in text[:16]:  # Максимум 16 символов
            self._send_data(ord(char))
    
    def display_data(self, weather_data):
        """Отображение данных на дисплее"""
        if not self.enabled:
            return
        
        self.clear()
        
        # Первая строка: Arduino данные
        arduino = weather_data.get('arduino', {})
        temp = arduino.get('temp')
        humid = arduino.get('humid')
        
        if temp is not None and humid is not None:
            line1 = f"A:{temp:.1f}C H:{humid:.0f}%"
        else:
            line1 = "Arduino: No data"
        
        self.set_cursor(0, 0)
        self.write_string(line1)
        
        # Вторая строка: Elbear данные
        elbear = weather_data.get('elbear', {})
        temp_e = elbear.get('THP80_temp')
        press = elbear.get('THP80_press')
        
        if temp_e is not None and press is not None:
            line2 = f"E:{temp_e:.1f}C P:{press:.0f}"
        else:
            line2 = "Elbear: No data"
        
        self.set_cursor(1, 0)
        self.write_string(line2)

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
                'press': data.get('press'),
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
    lcd = LCDDisplay()
    
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
