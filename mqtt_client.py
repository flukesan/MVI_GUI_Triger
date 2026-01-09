"""
MQTT Client for MVI Edge Inspection Trigger
Handles MQTT connection, publishing triggers, and receiving results
"""
import paho.mqtt.client as mqtt
from PyQt6.QtCore import QObject, pyqtSignal
import json


class MQTTClient(QObject):
    """MQTT Client with Qt signals for GUI integration"""

    # Qt Signals
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    message_received = pyqtSignal(str, str)  # topic, payload
    connection_error = pyqtSignal(str)

    def __init__(self, broker, port, username="", password="", qos=1):
        super().__init__()
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.qos = qos

        self.client = mqtt.Client(client_id="MVI_GUI_Trigger")
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        if username and password:
            self.client.username_pw_set(username, password)

        self.is_connected = False
        self.subscribe_topics = []

    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            self.is_connected = True
            self.connected.emit()
            # Subscribe to result topics
            for topic in self.subscribe_topics:
                self.client.subscribe(topic, self.qos)
        else:
            self.connection_error.emit(f"Connection failed with code {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker"""
        self.is_connected = False
        self.disconnected.emit()

    def _on_message(self, client, userdata, msg):
        """Callback when message received"""
        try:
            payload = msg.payload.decode('utf-8')
            self.message_received.emit(msg.topic, payload)
        except Exception as e:
            print(f"Error processing message: {e}")

    def connect(self):
        """Connect to MQTT broker"""
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
        except Exception as e:
            self.connection_error.emit(str(e))

    def disconnect(self):
        """Disconnect from MQTT broker"""
        if self.is_connected:
            self.client.loop_stop()
            self.client.disconnect()

    def subscribe(self, topic):
        """Subscribe to a topic"""
        if topic not in self.subscribe_topics:
            self.subscribe_topics.append(topic)
            if self.is_connected:
                self.client.subscribe(topic, self.qos)

    def publish(self, topic, payload):
        """Publish message to topic"""
        if self.is_connected:
            try:
                if isinstance(payload, dict):
                    payload = json.dumps(payload)
                self.client.publish(topic, payload, qos=self.qos)
                return True
            except Exception as e:
                print(f"Error publishing message: {e}")
                return False
        return False
