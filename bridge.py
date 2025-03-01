#!/usr/bin/python3

import os
import asyncio
import jsonpickle
import hashlib
import ssl
import time
from myPyllant.api import MyPyllantAPI
from paho.mqtt import client as mqtt_client

# MQTT-Konfiguration
mqtt_id = os.getenv('MQTT_ID')
mqtt_passw = os.getenv('MQTT_PASS')
mqtt_host = os.getenv('MQTT_HOST')
mqtt_port = int(os.getenv('MQTT_PORT', '1883'))
mqtt_topic = os.getenv('MQTT_TOPIC', 'test/vaillant')
mqtt_topic_lwt = mqtt_topic + '/LWT'
mqtt_topic_state = mqtt_topic + '/state'
mqtt_use_ssl = os.getenv('MQTT_USE_SSL', '').lower() in ['true', '1', 'yes']
mqtt_trusted_fingerprint = os.getenv('MQTT_TRUSTED_FINGERPRINT') or None

# Vaillant API-Konfiguration
vaillant_user = os.getenv('MYVAILLANT_USER')
vaillant_pass = os.getenv('MYVAILLANT_PASS')
vaillant_brand = os.getenv('MYVAILLANT_BRAND', 'vaillant')
vaillant_country = os.getenv('MYVAILLANT_COUNTRY', 'germany')

last_values = {}  # Speichert die letzten gesendeten Werte
visited_objects = set()  # Set zum Erkennen von bereits verarbeiteten Objekten

# Callback, um gespeicherte Werte aus MQTT zu laden
def on_message(client, userdata, msg):
    topic = msg.topic
    last_values[topic] = msg.payload.decode()

def load_last_values_from_mqtt(client):
    """Abonniert alle relevanten Topics, um die letzten Werte aus MQTT zu laden."""
    client.on_message = on_message
    client.subscribe(f"{mqtt_topic}/#")  # Alle relevanten Topics abonnieren
    client.loop_start()
    time.sleep(1)  # Kurz warten, bis alle Messages empfangen wurden
    client.loop_stop()

def get_ssl_certificate(client):
    """Tries to extract the server certificate from the MQTT-SSL-connection."""
    try:
        sock = client.socket()
        if isinstance(sock, ssl.SSLSocket):
            return sock.getpeercert(binary_form=True)
        else:
            print("MQTT socket is not using SSL.")
            return None
    except Exception as e:
        print(f"Failed to retrieve SSL certificate: {e}")
        return None

def get_certificate_fingerprint(cert):
    """Validates the certificate's SHA256-hash."""
    return hashlib.sha256(cert).hexdigest()

def validate_certificate(client):
    """Validates the certificate by TOFU."""
    global mqtt_trusted_fingerprint
    
    cert = get_ssl_certificate(client)
    if not cert:
        print("No certificate!")
        return False
    
    current_fingerprint = get_certificate_fingerprint(cert)
    
    if mqtt_trusted_fingerprint is None:
        mqtt_trusted_fingerprint = current_fingerprint
        print(f"No fingerprint set. The current certificate has following fingerprint: {mqtt_trusted_fingerprint}")
        return False
    
    if current_fingerprint == mqtt_trusted_fingerprint:
        print("Certificate fingerprint matches. Connection trusted.")
        return True
    else:
        print("Certificate fingerprint mismatch! Connection rejected.")
        return False

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Connected to MQTT Broker")
        if mqtt_use_ssl and not validate_certificate(client):
            client.disconnect()
    else:
        print(f"Failed to connect to MQTT Broker, return code {reason_code}")

def init_mqtt_client():
    client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2)
    client.username_pw_set(mqtt_id, mqtt_passw)
    client.will_set(mqtt_topic_lwt, payload='Offline', qos=0, retain=True)
    client.on_connect = on_connect
    
    if mqtt_use_ssl:
        print("Using TLS...")
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False  # Deaktiviere Hostnamenprüfung
        ssl_context.verify_mode = ssl.CERT_NONE  # Verhindert automatische Ablehnung
        client.tls_set_context(ssl_context)
    else:
        print("Using unencrypted connection...")
    
    client.connect(mqtt_host, mqtt_port, 60)
    client.loop_start()  # WICHTIG: Startet die MQTT-Schleife, die `on_connect` triggert
    client.publish(mqtt_topic_lwt, payload='Online', retain=True)
    return client

def publish_to_mqtt1(client, data):
    msg = jsonpickle.encode(data, unpicklable=False)
    msg_info = client.publish(mqtt_topic_state, msg, qos=0, retain=True)
    status = msg_info.rc  # Anpassung für Kompatibilität
    if status == 0:
        print(f"Message published successfully to topic `{mqtt_topic_state}`")
    else:
        print(f"Failed to publish message to topic `{mqtt_topic_state}`")

def publish_to_mqtt(client, data, topic_prefix=mqtt_topic, depth=0, max_depth=10):
    """
    Wandelt ein beliebiges Objekt in einen MQTT-Topic-Baum um und veröffentlicht nur geänderte Werte.
    Vermeidet Endlosschleifen durch zyklische Referenzen und begrenzt die Rekursionstiefe.
    """
    global visited_objects

    if depth > max_depth:
        return  # Stoppe, um Rekursionstiefe zu begrenzen

    if "__objclass__" in topic_prefix:
        return  # Ignoriere dieses Topic komplett

    if isinstance(data, dict):
        for key, value in data.items():
            publish_to_mqtt(client, value, f"{topic_prefix}/{key}", depth+1, max_depth)
    
    elif isinstance(data, list):
        for index, value in enumerate(data):
            publish_to_mqtt(client, value, f"{topic_prefix}/{index}", depth+1, max_depth)
    
    elif hasattr(data, "__dict__"):  # Falls es ein Objekt mit Attributen ist
        if id(data) in visited_objects:
            return  # Verhindert Endlosschleifen durch zyklische Referenzen
        visited_objects.add(id(data))

        for key, value in vars(data).items():
            publish_to_mqtt(client, value, f"{topic_prefix}/{key}", depth+1, max_depth)

        visited_objects.remove(id(data))  # Nach der Verarbeitung wieder entfernen
    
    else:
        value_str = jsonpickle.encode(data, unpicklable=False) if isinstance(data, (dict, list)) else str(data)

        # Nur senden, wenn sich der Wert geändert hat
        if last_values.get(topic_prefix) != value_str:
            msg_info = client.publish(topic_prefix, value_str, qos=0, retain=True)
            status = msg_info.rc  # Anpassung für Kompatibilität
            if status == 0:
                print(f"Message published successfully to topic `{topic_prefix}`")
            else:
                print(f"Failed to publish message to topic `{topic_prefix}`")

            last_values[topic_prefix] = value_str

async def main():
    client = init_mqtt_client()

    # Lade vorherige Werte aus MQTT-Retained Messages
    load_last_values_from_mqtt(client)

    async with MyPyllantAPI(vaillant_user, vaillant_pass, vaillant_brand, vaillant_country) as api:
        async for system in api.get_systems():
            publish_to_mqtt(client, system)
            print('done.')

if __name__ == "__main__":
    asyncio.run(main())
