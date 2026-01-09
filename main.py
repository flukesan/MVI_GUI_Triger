"""
MVI Edge Inspection Trigger GUI
PyQt6/PySide6 GUI Application for triggering MVI inspections via MQTT
"""
import sys
import json
from pathlib import Path

# Try to import PyQt6, fallback to PySide6 if not available
try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QComboBox, QLabel, QLineEdit, QDialog, QDialogButtonBox,
        QMessageBox, QGroupBox, QGridLayout, QStatusBar
    )
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QFont, QPalette, QColor
    print("Using PyQt6")
except ImportError:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QComboBox, QLabel, QLineEdit, QDialog, QDialogButtonBox,
        QMessageBox, QGroupBox, QGridLayout, QStatusBar
    )
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QFont, QPalette, QColor
    print("Using PySide6")

from mqtt_client import MQTTClient


class AddTopicDialog(QDialog):
    """Dialog for adding new MQTT topic"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("เพิ่ม Topic")
        self.setModal(True)
        self.setMinimumWidth(400)

        layout = QVBoxLayout()

        # Topic input
        topic_label = QLabel("Topic:")
        self.topic_input = QLineEdit()
        self.topic_input.setPlaceholderText("เช่น: mvi/model3/trigger")

        layout.addWidget(topic_label)
        layout.addWidget(self.topic_input)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(button_box)
        self.setLayout(layout)

    def get_topic(self):
        """Get the entered topic"""
        return self.topic_input.text().strip()


class MVITriggerGUI(QMainWindow):
    """Main GUI window for MVI Edge Inspection Trigger"""

    def __init__(self):
        super().__init__()
        self.config_file = Path("config.json")
        self.config = self.load_config()
        self.mqtt_client = None
        self.init_ui()
        self.init_mqtt()

    def load_config(self):
        """Load configuration from JSON file"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"ไม่สามารถโหลด config.json: {e}")
            sys.exit(1)

    def save_config(self):
        """Save configuration to JSON file"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"ไม่สามารถบันทึก config: {e}")

    def init_ui(self):
        """Initialize user interface"""
        self.setWindowTitle("MVI Edge Inspection Trigger")
        self.setMinimumSize(800, 600)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # ========== MQTT Connection Status ==========
        connection_group = QGroupBox("MQTT Connection")
        connection_layout = QHBoxLayout()

        self.connection_label = QLabel("Disconnected")
        self.connection_label.setStyleSheet(
            "QLabel { background-color: #dc3545; color: white; padding: 10px; "
            "border-radius: 5px; font-weight: bold; }"
        )

        connection_layout.addWidget(self.connection_label)
        connection_group.setLayout(connection_layout)
        main_layout.addWidget(connection_group)

        # ========== Topic Selection ==========
        topic_group = QGroupBox("เลือก Topic สำหรับ Trigger")
        topic_layout = QHBoxLayout()

        self.topic_combo = QComboBox()
        self.topic_combo.setMinimumHeight(40)
        self.topic_combo.setFont(QFont("Arial", 12))
        self.update_topic_list()

        # Add/Remove topic buttons
        self.add_topic_btn = QPushButton("➕ เพิ่ม")
        self.add_topic_btn.setMinimumHeight(40)
        self.add_topic_btn.clicked.connect(self.add_topic)

        self.remove_topic_btn = QPushButton("➖ ลบ")
        self.remove_topic_btn.setMinimumHeight(40)
        self.remove_topic_btn.clicked.connect(self.remove_topic)

        topic_layout.addWidget(self.topic_combo, 3)
        topic_layout.addWidget(self.add_topic_btn, 1)
        topic_layout.addWidget(self.remove_topic_btn, 1)
        topic_group.setLayout(topic_layout)
        main_layout.addWidget(topic_group)

        # ========== Trigger Button ==========
        self.trigger_btn = QPushButton("🔘 TRIGGER MVI INSPECTION")
        self.trigger_btn.setMinimumHeight(80)
        self.trigger_btn.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.trigger_btn.setStyleSheet(
            "QPushButton { background-color: #007bff; color: white; "
            "border-radius: 10px; }"
            "QPushButton:hover { background-color: #0056b3; }"
            "QPushButton:pressed { background-color: #004085; }"
            "QPushButton:disabled { background-color: #6c757d; }"
        )
        self.trigger_btn.clicked.connect(self.trigger_inspection)
        main_layout.addWidget(self.trigger_btn)

        # ========== Status Display ==========
        status_group = QGroupBox("สถานะการตรวจสอบ")
        status_layout = QVBoxLayout()

        self.status_label = QLabel("รอการตรวจสอบ")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setMinimumHeight(200)
        self.status_label.setFont(QFont("Arial", 48, QFont.Weight.Bold))
        self.status_label.setStyleSheet(
            "QLabel { background-color: #6c757d; color: white; "
            "border-radius: 10px; padding: 20px; }"
        )

        status_layout.addWidget(self.status_label)
        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)

        # ========== Status Bar ==========
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("พร้อมใช้งาน")

        # Style
        self.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                border: 2px solid #ccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)

    def update_topic_list(self):
        """Update topic combo box with current topics"""
        self.topic_combo.clear()
        self.topic_combo.addItems(self.config.get("topics", []))

    def add_topic(self):
        """Add new topic to the list"""
        dialog = AddTopicDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_topic = dialog.get_topic()
            if new_topic:
                if new_topic not in self.config["topics"]:
                    self.config["topics"].append(new_topic)
                    self.save_config()
                    self.update_topic_list()
                    self.topic_combo.setCurrentText(new_topic)
                    self.statusBar.showMessage(f"เพิ่ม topic: {new_topic}", 3000)
                else:
                    QMessageBox.warning(self, "Warning", "Topic นี้มีอยู่แล้ว")

    def remove_topic(self):
        """Remove selected topic from the list"""
        current_topic = self.topic_combo.currentText()
        if current_topic:
            reply = QMessageBox.question(
                self, "ยืนยัน", f"ต้องการลบ topic '{current_topic}' หรือไม่?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.config["topics"].remove(current_topic)
                self.save_config()
                self.update_topic_list()
                self.statusBar.showMessage(f"ลบ topic: {current_topic}", 3000)

    def init_mqtt(self):
        """Initialize MQTT client"""
        mqtt_config = self.config.get("mqtt", {})
        self.mqtt_client = MQTTClient(
            broker=mqtt_config.get("broker", "localhost"),
            port=mqtt_config.get("port", 1883),
            username=mqtt_config.get("username", ""),
            password=mqtt_config.get("password", ""),
            qos=mqtt_config.get("qos", 1)
        )

        # Connect signals
        self.mqtt_client.connected.connect(self.on_mqtt_connected)
        self.mqtt_client.disconnected.connect(self.on_mqtt_disconnected)
        self.mqtt_client.message_received.connect(self.on_mqtt_message)
        self.mqtt_client.connection_error.connect(self.on_mqtt_error)

        # Subscribe to result topic
        subscribe_topic = self.config.get("subscribe_topic", "mvi/+/result")
        self.mqtt_client.subscribe(subscribe_topic)

        # Connect to broker
        self.mqtt_client.connect()

    def on_mqtt_connected(self):
        """Callback when MQTT connected"""
        self.connection_label.setText("Connected")
        self.connection_label.setStyleSheet(
            "QLabel { background-color: #28a745; color: white; padding: 10px; "
            "border-radius: 5px; font-weight: bold; }"
        )
        self.trigger_btn.setEnabled(True)
        self.statusBar.showMessage("เชื่อมต่อ MQTT สำเร็จ", 3000)

    def on_mqtt_disconnected(self):
        """Callback when MQTT disconnected"""
        self.connection_label.setText("Disconnected")
        self.connection_label.setStyleSheet(
            "QLabel { background-color: #dc3545; color: white; padding: 10px; "
            "border-radius: 5px; font-weight: bold; }"
        )
        self.trigger_btn.setEnabled(False)
        self.statusBar.showMessage("MQTT ถูกตัดการเชื่อมต่อ")

    def on_mqtt_error(self, error_msg):
        """Callback when MQTT error occurs"""
        QMessageBox.critical(self, "MQTT Error", f"เกิดข้อผิดพลาด: {error_msg}")
        self.statusBar.showMessage(f"Error: {error_msg}")

    def on_mqtt_message(self, topic, payload):
        """Callback when MQTT message received"""
        try:
            # Try to parse JSON
            data = json.loads(payload)
            result = data.get("result", "").lower()

            if result == "pass":
                self.show_pass()
            elif result == "fail":
                self.show_fail()
            else:
                # If not JSON or unknown result, display as text
                self.status_label.setText(f"ผลลัพธ์:\n{payload}")
                self.statusBar.showMessage(f"ได้รับข้อความจาก {topic}", 3000)

        except json.JSONDecodeError:
            # Not JSON, display as text
            self.status_label.setText(f"{payload}")
            self.statusBar.showMessage(f"ได้รับข้อความจาก {topic}", 3000)

    def trigger_inspection(self):
        """Trigger MVI inspection"""
        current_topic = self.topic_combo.currentText()
        if not current_topic:
            QMessageBox.warning(self, "Warning", "กรุณาเลือก topic")
            return

        # Reset status
        self.status_label.setText("กำลังตรวจสอบ...")
        self.status_label.setStyleSheet(
            "QLabel { background-color: #ffc107; color: black; "
            "border-radius: 10px; padding: 20px; }"
        )

        # Prepare trigger message
        trigger_msg = {
            "action": "trigger",
            "timestamp": QTimer().singleShot(0, lambda: None)  # Current time
        }

        # Publish trigger
        success = self.mqtt_client.publish(current_topic, trigger_msg)
        if success:
            self.statusBar.showMessage(f"ส่ง trigger ไปยัง {current_topic}", 3000)
        else:
            QMessageBox.warning(self, "Error", "ไม่สามารถส่ง trigger ได้")
            self.status_label.setText("รอการตรวจสอบ")
            self.status_label.setStyleSheet(
                "QLabel { background-color: #6c757d; color: white; "
                "border-radius: 10px; padding: 20px; }"
            )

    def show_pass(self):
        """Show PASS status"""
        self.status_label.setText("✓ PASS")
        self.status_label.setStyleSheet(
            "QLabel { background-color: #28a745; color: white; "
            "border-radius: 10px; padding: 20px; }"
        )
        self.statusBar.showMessage("ผลการตรวจสอบ: PASS", 5000)

    def show_fail(self):
        """Show FAIL status"""
        self.status_label.setText("✗ FAIL")
        self.status_label.setStyleSheet(
            "QLabel { background-color: #dc3545; color: white; "
            "border-radius: 10px; padding: 20px; }"
        )
        self.statusBar.showMessage("ผลการตรวจสอบ: FAIL", 5000)

    def closeEvent(self, event):
        """Handle window close event"""
        if self.mqtt_client:
            self.mqtt_client.disconnect()
        event.accept()


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    window = MVITriggerGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
