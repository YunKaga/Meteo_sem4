"""
Weather Station Server для Raspberry Pi
Принимает JSON от Arduino и Elbear через Bluetooth
"""

import json
import threading
import time
import subprocess
import logging
from datetime import datetime
from flask import Flask, jsonify, render_template_string
from flask_socketio import SocketIO
import smbus2

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('/tmp/weather_station.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('server')

# MAC адреса
MAC_ARDUINO = "98:DA:50:03:A8:14"
MAC_ELBEAR  = "98:DA:50:04:2C:30"

HTTP_PORT = 5000
TCP_PORT  = 5001

# Flask приложение
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Глобальное хранилище данных
weather_data = {
    'arduino': {
        'temp': None,
        'humid': None,
        'press': None,
        'timestamp': None
    },
    'elbear': {
        'THP80_temp': None,
        'THP80_hum': None,
        'THP80_press': None,
        'L75_lux': None,
        'FR403_flame': None,
        'CLM60_red': None,
        'CLM60_green': None,
        'CLM60_blue': None,
        'CLM60_clear': None,
        'CLM60_proximity': None,
        'A6_accel_x': None,
        'A6_accel_y': None,
        'A6_accel_z': None,
        'A6_gyro_x': None,
        'A6_gyro_y': None,
        'A6_gyro_z': None,
        'CO30_eco2': None,
        'CO30_tvoc': None,
        'D20_distance': None,
        'timestamp': None
    },
    'last_update': None
}

# ==================== Bluetooth клиент ====================
# ==================== Bluetooth клиент ====================
class BluetoothClient:
    """Читает данные с HC-05 через активное подключение bluetoothctl + rfcomm"""
    
    def __init__(self, mac, name, rfcomm_num):
        self.mac = mac
        self.name = name
        self.rfcomm_num = rfcomm_num
        self.running = False
        
    def connect(self):
        """Активное подключение к устройству"""
        try:
            logger.info(f"[{self.name}] Connecting to {self.mac} via bluetoothctl...")
            
            # 1. Принудительно подключаемся через bluetoothctl
            subprocess.run(
                ['sudo', 'bluetoothctl', 'connect', self.mac],
                capture_output=True, text=True, timeout=15
            )
            time.sleep(2)
            
            # 2. Проверяем, удалось ли подключение
            check = subprocess.run(
                ['bluetoothctl', 'info', self.mac],
                capture_output=True, text=True
            )
            if "Connected: yes" not in check.stdout:
                logger.warning(f"[{self.name}] bluetoothctl connection failed.")
                return False
                
            # 3. Привязываем RFCOMM порт для чтения как файл
            subprocess.run(
                ['sudo', 'rfcomm', 'bind', str(self.rfcomm_num), self.mac, '1'],
                capture_output=True, timeout=5
            )
            time.sleep(1)
            
            logger.info(f"[{self.name}] Successfully connected and bound to /dev/rfcomm{self.rfcomm_num}")
            return True
            
        except Exception as e:
            logger.error(f"[{self.name}] Connection error: {e}")
            return False

    def connect_and_read(self, callback):
        """Основной цикл подключения и чтения"""
        self.running = True
        
        while self.running:
            try:
                if not self.connect():
                    # Если не подключились, ждем и пробуем снова
                    time.sleep(5)
                    continue
                
                device_path = f'/dev/rfcomm{self.rfcomm_num}'
                logger.info(f"[{self.name}] Opening {device_path} for reading...")
                
                with open(device_path, 'r') as f:
                    while self.running:
                        line = f.readline()
                        if line:
                            line = line.strip()
                            if line:
                                callback(self.name, line)
                                
            except Exception as e:
                logger.error(f"[{self.name}] Read/Connection error: {e}")
            
            # При ошибке или разрыве связи очищаем состояние и пробуем снова
            subprocess.run(['sudo', 'bluetoothctl', 'disconnect', self.mac], capture_output=True)
            subprocess.run(['sudo', 'rfcomm', 'release', str(self.rfcomm_num)], capture_output=True)
            time.sleep(5)
    
    def stop(self):
        self.running = False
        subprocess.run(['sudo', 'bluetoothctl', 'disconnect', self.mac], capture_output=True)
        subprocess.run(['sudo', 'rfcomm', 'release', str(self.rfcomm_num)], capture_output=True)

# ==================== Парсинг данных ====================
def parse_arduino_json(json_str):
    """Парсинг JSON от Arduino (с одинарными кавычками)"""
    try:
        # Заменяем одинарные кавычки на двойные
        json_str = json_str.replace("'", '"')
        data = json.loads(json_str)
        
        weather_data['arduino'] = {
            'temp': data.get('temp'),
            'humid': data.get('humid'),
            'press': data.get('press'),
            'timestamp': datetime.now().isoformat()
        }
        weather_data['last_update'] = datetime.now().isoformat()
        
        logger.info(f"[Arduino] Parsed: temp={data.get('temp')}, humid={data.get('humid')}, press={data.get('press')}")
        return True
    except json.JSONDecodeError as e:
        logger.error(f"Arduino JSON parse error: {e}")
        return False
    except Exception as e:
        logger.error(f"Arduino parse error: {e}")
        return False

def parse_elbear_json(json_str):
    """Парсинг JSON от Elbear (валидный JSON с двойными кавычками)"""
    try:
        data = json.loads(json_str)
        
        # Обновляем все поля Elbear
        weather_data['elbear'] = {
            'THP80_temp': data.get('THP80_temp'),
            'THP80_hum': data.get('THP80_hum'),
            'THP80_press': data.get('THP80_press'),
            'L75_lux': data.get('L75_lux'),
            'FR403_flame': data.get('FR403_flame'),
            'CLM60_red': data.get('CLM60_red'),
            'CLM60_green': data.get('CLM60_green'),
            'CLM60_blue': data.get('CLM60_blue'),
            'CLM60_clear': data.get('CLM60_clear'),
            'CLM60_proximity': data.get('CLM60_proximity'),
            'A6_accel_x': data.get('A6_accel_x'),
            'A6_accel_y': data.get('A6_accel_y'),
            'A6_accel_z': data.get('A6_accel_z'),
            'A6_gyro_x': data.get('A6_gyro_x'),
            'A6_gyro_y': data.get('A6_gyro_y'),
            'A6_gyro_z': data.get('A6_gyro_z'),
            'CO30_eco2': data.get('CO30_eco2'),
            'CO30_tvoc': data.get('CO30_tvoc'),
            'D20_distance': data.get('D20_distance'),
            'timestamp': datetime.now().isoformat()
        }
        weather_data['last_update'] = datetime.now().isoformat()
        
        logger.info(f"[Elbear] Parsed: temp={data.get('THP80_temp')}, hum={data.get('THP80_hum')}, press={data.get('THP80_press')}")
        return True
    except json.JSONDecodeError as e:
        logger.error(f"Elbear JSON parse error: {e}")
        return False
    except Exception as e:
        logger.error(f"Elbear parse error: {e}")
        return False

def handle_bluetooth_data(source, data):
    """Обработчик данных от Bluetooth"""
    logger.info(f"[{source}] Raw: {data}")
    
    updated = False
    if source == 'Arduino':
        updated = parse_arduino_json(data)
    elif source == 'Elbear':
        updated = parse_elbear_json(data)
    
    if updated:
        socketio.emit('data_update', weather_data)

# ==================== LCD дисплей ====================
class LCDDisplay:
    def __init__(self, i2c_bus=1, i2c_addr=0x3F):
        self.enabled = True
        try:
            self.bus = smbus2.SMBus(i2c_bus)
            self.addr = i2c_addr
            self._init()
        except Exception as e:
            logger.error(f"LCD init error: {e}")
            self.enabled = False
    
    def _cmd(self, cmd):
        if self.bus:
            self.bus.write_byte(self.addr, cmd)
    
    def _init(self):
        self._cmd(0x33); self._cmd(0x32); self._cmd(0x28)
        self._cmd(0x0C); self._cmd(0x06); self._cmd(0x01)
        time.sleep(0.002)
    
    def _write_line(self, line_num, text):
        if not self.bus:
            return
        addr = 0x80 if line_num == 0 else 0xC0
        self._cmd(addr)
        for ch in text[:16]:
            self.bus.write_byte_data(self.addr, 0x40, ord(ch))
    
    def update(self, data):
        if not self.enabled:
            return
        a = data.get('arduino', {})
        t, h, p = a.get('temp'), a.get('humid'), a.get('press')
        l1 = f"T:{t:.1f}C H:{h:.0f}%" if t is not None and h is not None else "No data"
        l2 = f"P:{p:.0f}mmHg" if p is not None else "No data"
        self._write_line(0, l1)
        self._write_line(1, l2)

def lcd_loop():
    lcd = LCDDisplay()
    while True:
        try:
            lcd.update(weather_data)
        except Exception as e:
            logger.error(f"LCD error: {e}")
        time.sleep(5)

# ==================== TCP сервер ====================
def tcp_server():
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', TCP_PORT))
    sock.listen(5)
    logger.info(f"TCP server on port {TCP_PORT}")
    
    while True:
        try:
            conn, addr = sock.accept()
            def handle_client(c):
                try:
                    while True:
                        data = c.recv(1024).decode('utf-8')
                        if not data:
                            break
                        data = data.strip()
                        if data.startswith('{'):
                            # Определяем источник по содержимому
                            if 'THP80_temp' in data:
                                handle_bluetooth_data('Elbear', data)
                            else:
                                handle_bluetooth_data('Arduino', data)
                except Exception as e:
                    logger.error(f"TCP client error: {e}")
                finally:
                    c.close()
            threading.Thread(target=handle_client, args=(conn,), daemon=True).start()
        except Exception as e:
            logger.error(f"TCP server error: {e}")
            time.sleep(1)

# ==================== Web интерфейс ====================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Weather Station</title>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f0f0f0; }
        .container { max-width: 1200px; margin: 0 auto; }
        .box { background: white; padding: 20px; margin: 10px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        h1 { color: #333; }
        h2 { color: #666; border-bottom: 2px solid #ddd; padding-bottom: 10px; }
        .row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #eee; }
        .label { font-weight: bold; }
        .value { color: #2196F3; }
        .no-data { color: #999; font-style: italic; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🌤️ Weather Station</h1>
        <div>Last update: <span id="ts">-</span></div>
        
        <div class="box">
            <h2> Arduino Mega</h2>
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
            const fmt = v => v !== null && v !== undefined ? v.toFixed(1) : 'N/A';
            const fmtInt = v => v !== null && v !== undefined ? Math.round(v) : 'N/A';
            const fmtStr = v => v !== null && v !== undefined ? v : 'N/A';
            
            // Arduino
            document.getElementById('arduino').innerHTML = `
                <div class="row"><span class="label">Temperature:</span><span class="value">${fmt(a.temp)} °C</span></div>
                <div class="row"><span class="label">Humidity:</span><span class="value">${fmt(a.humid)} %</span></div>
                <div class="row"><span class="label">Pressure:</span><span class="value">${fmtInt(a.press)} mmHg</span></div>
            `;
            
            // Elbear
            document.getElementById('elbear').innerHTML = `
                <h3>Environment</h3>
                <div class="row"><span class="label">Temperature (THP80):</span><span class="value">${fmt(e.THP80_temp)} °C</span></div>
                <div class="row"><span class="label">Humidity (THP80):</span><span class="value">${fmt(e.THP80_hum)} %</span></div>
                <div class="row"><span class="label">Pressure (THP80):</span><span class="value">${fmtInt(e.THP80_press)} mmHg</span></div>
                <div class="row"><span class="label">Light (L75):</span><span class="value">${fmt(e.L75_lux)} lux</span></div>
                <div class="row"><span class="label">Flame (FR403):</span><span class="value">${fmtStr(e.FR403_flame)}</span></div>
                
                <h3>Color & Proximity (CLM60)</h3>
                <div class="row"><span class="label">Red:</span><span class="value">${fmtInt(e.CLM60_red)}</span></div>
                <div class="row"><span class="label">Green:</span><span class="value">${fmtInt(e.CLM60_green)}</span></div>
                <div class="row"><span class="label">Blue:</span><span class="value">${fmtInt(e.CLM60_blue)}</span></div>
                <div class="row"><span class="label">Clear:</span><span class="value">${fmtInt(e.CLM60_clear)}</span></div>
                <div class="row"><span class="label">Proximity:</span><span class="value">${fmtInt(e.CLM60_proximity)}</span></div>
                
                <h3>Motion (A6)</h3>
                <div class="row"><span class="label">Accel X:</span><span class="value">${fmt(e.A6_accel_x)} m/s²</span></div>
                <div class="row"><span class="label">Accel Y:</span><span class="value">${fmt(e.A6_accel_y)} m/s²</span></div>
                <div class="row"><span class="label">Accel Z:</span><span class="value">${fmt(e.A6_accel_z)} m/s²</span></div>
                <div class="row"><span class="label">Gyro X:</span><span class="value">${fmt(e.A6_gyro_x)} °/s</span></div>
                <div class="row"><span class="label">Gyro Y:</span><span class="value">${fmt(e.A6_gyro_y)} °/s</span></div>
                <div class="row"><span class="label">Gyro Z:</span><span class="value">${fmt(e.A6_gyro_z)} °/s</span></div>
                
                <h3>Air Quality (CO30)</h3>
                <div class="row"><span class="label">eCO2:</span><span class="value">${fmtInt(e.CO30_eco2)} ppm</span></div>
                <div class="row"><span class="label">TVOC:</span><span class="value">${fmtInt(e.CO30_tvoc)} ppb</span></div>
                
                <h3>Distance (D20)</h3>
                <div class="row"><span class="label">Distance:</span><span class="value">${fmtInt(e.D20_distance)} mm</span></div>
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

@app.route('/api/arduino')
def get_arduino():
    return jsonify(weather_data['arduino'])

@app.route('/api/elbear')
def get_elbear():
    return jsonify(weather_data['elbear'])

# ==================== Запуск ====================
def main():
    logger.info("=" * 50)
    logger.info("Weather Station Server Starting")
    logger.info("=" * 50)
    logger.info(f"Arduino MAC: {MAC_ARDUINO}")
    logger.info(f"Elbear MAC:  {MAC_ELBEAR}")
    
    # Bluetooth клиенты
    arduino_bt = BluetoothClient(MAC_ARDUINO, 'Arduino', 0)
    elbear_bt  = BluetoothClient(MAC_ELBEAR,  'Elbear',  1)
    
    # Запускаем потоки чтения
    threading.Thread(target=arduino_bt.connect_and_read, args=(handle_bluetooth_data,), daemon=True).start()
    threading.Thread(target=elbear_bt.connect_and_read,  args=(handle_bluetooth_data,), daemon=True).start()
    
    # LCD
    threading.Thread(target=lcd_loop, daemon=True).start()
    
    # TCP сервер
    threading.Thread(target=tcp_server, daemon=True).start()
    
    # Flask
    logger.info(f"Web server on http://0.0.0.0:{HTTP_PORT}")
    socketio.run(app, host='0.0.0.0', port=HTTP_PORT, debug=False)

if __name__ == '__main__':
    main()
