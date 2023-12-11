import psutil
import paho.mqtt.client as mqtt
import smtplib
import time
import sqlite3

# Conectar a la base de datos
conn = sqlite3.connect('rendimiento.db')

# Crear una tabla para almacenar los datos
conn.execute('''CREATE TABLE IF NOT EXISTS rendimiento
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
             uso_cpu REAL,
             uso_memoria REAL,
             rendimiento_red REAL,
             fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

# Configurar los detalles del servidor SMTP de Hotmail
smtp_server = "smtp-mail.outlook.com"
port = 587  # Puerto de SMTP
sender_email = "jd.viracucha@hotmail.com"
password = "davidvira12"

# Crear el objeto SMTP
server = smtplib.SMTP(smtp_server, port)
server.starttls()
server.login(sender_email, password)

def enviar_correo():
    uso_memoria = psutil.virtual_memory().percent
    if uso_memoria > 60:
        message = f"El rendimiento de la MEMORIA es: {uso_memoria}%"
        receiver_email = "jdviracucha@uce.edu.ec"
        subject = "Advertencia: Rendimiento de la MEMORIA"
        body = f"Subject: {subject}\n\n{message}"

        # Enviar el mensaje de correo electrónico
        server.sendmail(sender_email, receiver_email, body)
        print("Correo electrónico enviado exitosamente!")

def comparar_metadatos(client1, client2):
    metadata1 = obtener_metadatos(client1)
    metadata2 = obtener_metadatos(client2)

    diferencia = {}

    for clave, valor1 in metadata1.items():
        if clave in metadata2:
            valor2 = metadata2[clave]
            if valor1 != valor2:
                diferencia[clave] = f"{valor1} (Cliente 1) - {valor2} (Cliente 2)"

    # Imprimir la diferencia en la consola
    print("Diferencia de metadatos:")
    for clave, valor in diferencia.items():
        print(f"{clave}: {valor}")

    # Publicar la diferencia en el servidor MQTT
    mensaje_diferencia = "\n".join([f"{clave}: {valor}" for clave, valor in diferencia.items()])
    client1.publish("Prueba", mensaje_diferencia, qos=0)

def obtener_metadatos(client):
    memoria_disponible = psutil.virtual_memory().available / (1024 * 1024)
    memoria_usada = psutil.virtual_memory().percent

    try:
        temperatura_cpu = psutil.sensors_temperatures()['coretemp'][0].current
    except AttributeError:
        temperatura_cpu = "No disponible en esta plataforma"

    # Obtener estadísticas de la interfaz de red
    estadisticas_red = psutil.net_io_counters()
    rendimiento_mb = estadisticas_red.bytes_sent / (1024 * 1024)

    return {
        "Memoria Disponible": memoria_disponible,
        "Porcentaje de Memoria Usada": memoria_usada,
        "Temperatura del CPU": temperatura_cpu,
        "Rendimiento de la RED": rendimiento_mb
    }

def on_connect(client, userdata, flags, rc):
    print("Conectado con resultado code " + str(rc))
    client.subscribe("Prueba")

def on_message(client, userdata, msg):
    print(msg.topic + " " + str(msg.payload))

client = mqtt.Client(transport="websockets")
client.on_connect = on_connect
client.on_message = on_message

client.tls_set()  # Habilitar el cifrado TLS

client.connect("mqtt-dashboard.com", 8884, 60)  # Conectar al broker a través de WebSockets


while True:
    uso_cpu = psutil.cpu_percent()
    uso_memoria = psutil.virtual_memory().percent
    estadisticas_red = psutil.net_io_counters()
    rendimiento_mb = estadisticas_red.bytes_sent / (1024 * 1024)
    fecha_hora = time.strftime('%Y-%m-%d %H:%M:%S')


    # Enviar los datos al servidor MQTT
    client.publish("Prueba", f"El rendimiento de la CPU es: {uso_cpu}%", qos=0)
    client.publish("Prueba", f"El rendimiento de la MEMORIA es: {uso_memoria}%", qos=0)
    client.publish("Prueba", f"El rendimiento de la RED es: {rendimiento_mb:.2f} (MB/s)", qos=0)

    # Comparar metadatos
    comparar_metadatos(client, client)

    # Esperar 30 segundos antes de enviar los siguientes datos
    time.sleep(10)

    # Enviar correo electrónico cada 30 segundos
    enviar_correo()
    time.sleep(10)  # Esperar 30 segundos antes de enviar el siguiente correo electrónico

    # Insertar los datos en la tabla
    conn.execute("INSERT INTO rendimiento (uso_cpu, uso_memoria, rendimiento_red) VALUES (?, ?, ?)",
                 (uso_cpu, uso_memoria, rendimiento_mb))
    conn.commit()

    # Esperar 30 segundos antes de enviar los siguientes datos
    time.sleep(10)

# Cerrar la conexión SMTP al salir del bucle
server.quit()
