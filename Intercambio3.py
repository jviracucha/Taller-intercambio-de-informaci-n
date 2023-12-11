import psutil
import platform
import os
import paho.mqtt.client as mqtt
import sqlite3
import json
import time
import socket  # Se agrega la importación de la biblioteca socket

# Configuración MQTT
MQTT_BROKER = "mqtt-dashboard.com"
MQTT_PORT = 8883  # Puerto para Websockets (cambia si es necesario)
MQTT_TOPIC = "Prueba"

# Configuración SQLite
DB_FILE = "sensor_data.db"

def on_connect(client, userdata, flags, rc):
    print(f"Conectado al broker con código de resultado {rc}")
    client.subscribe(MQTT_TOPIC)

def on_message(client, userdata, msg):
    try:
        # Decodificar el mensaje JSON recibido
        data = json.loads(msg.payload.decode())
        print(f"Mensaje recibido de {data['host']}: {data}")

        # Extraer los datos del mensaje
        cpu_usage = data.get("cpu_usage")
        memory_usage = data.get("memory_usage")
        bytes_sent = data.get("bytes_sent")
        bytes_recv = data.get("bytes_recv")
        temperature = data.get("temperature")

        # Insertar los datos en la base de datos SQLite
        insert_data_into_database(data['host'], cpu_usage, memory_usage, bytes_sent, bytes_recv, temperature)

    except Exception as e:
        print(f"Error al procesar el mensaje: {e}")

def get_cpu_usage():
    return psutil.cpu_percent(interval=1)

def get_memory_usage():
    memory = psutil.virtual_memory()
    return memory.percent

def get_network_usage():
    network = psutil.net_io_counters()
    return network.bytes_sent, network.bytes_recv

def get_temperature():
    if platform.system().lower() == 'linux':
        try:
            if os.system('command -v sensors >/dev/null 2>&1') == 0:
                temperature_info = os.popen('sensors').read()
                temperature_lines = [line for line in temperature_info.split('\n') if 'Core 0' in line]
                if temperature_lines:
                    return float(temperature_lines[0].split('+')[1].split('°C')[0].strip())
        except Exception as e:
            print(f"Error al obtener la temperatura: {e}")
    return None

def on_publish(client, userdata, mid):
    print(f"Mensaje publicado con éxito en el tema {MQTT_TOPIC}")

def create_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Crea la tabla si no existe
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            host TEXT,
            cpu_usage REAL,
            memory_usage REAL,
            bytes_sent INTEGER,
            bytes_recv INTEGER,
            temperature REAL
        )
    ''')

    conn.commit()
    conn.close()

def insert_data_into_database(host, cpu, memory, sent, recv, temperature):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO sensor_data (host, cpu_usage, memory_usage, bytes_sent, bytes_recv, temperature)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (host, cpu, memory, sent, recv, temperature))

    conn.commit()
    conn.close()

def main():
    create_database()

    try:
        client = mqtt.Client()
        client.on_connect = on_connect
        client.on_message = on_message
        client.on_publish = on_publish
        # Usar TLS para conexiones seguras con Websockets
        client.tls_set()
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()

        while True:
            cpu_usage = get_cpu_usage()
            memory_usage = get_memory_usage()
            network_usage = get_network_usage()
            temperature = get_temperature()

            # Crear un diccionario con los datos y agregar el nombre del host
            data = {
                "host": socket.gethostname(),
                "cpu_usage": cpu_usage,
                "memory_usage": memory_usage,
                "bytes_sent": network_usage[0],
                "bytes_recv": network_usage[1],
                "temperature": temperature
            }

            # Convertir el diccionario a formato JSON
            json_data = json.dumps(data)

            # Publicar el mensaje en el tema MQTT
            client.publish(MQTT_TOPIC, json_data)

            # Publicar cada 10 segundos (ajustar según sea necesario)
            time.sleep(10)

    except Exception as e:
        print(f"Error principal: {e}")

if __name__ == "__main__":
    main()