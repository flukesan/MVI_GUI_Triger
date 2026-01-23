"""
MVI Edge Inspection Trigger GUI
PyQt6/PySide6 GUI Application for triggering MVI inspections via MQTT
"""
import sys
import json
import os
from pathlib import Path

# Try to import PyQt6, fallback to PySide6 if not available
try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QComboBox, QLabel, QLineEdit, QDialog, QDialogButtonBox,
        QMessageBox, QGroupBox, QGridLayout, QStatusBar, QScrollArea, QTabWidget
    )
    from PyQt6.QtCore import Qt, QTimer, QSize, QRectF, QPointF
    from PyQt6.QtGui import QFont, QPalette, QColor, QPixmap, QPainter, QPen
    print("Using PyQt6")
except ImportError:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QComboBox, QLabel, QLineEdit, QDialog, QDialogButtonBox,
        QMessageBox, QGroupBox, QGridLayout, QStatusBar, QScrollArea, QTabWidget
    )
    from PySide6.QtCore import Qt, QTimer, QSize, QRectF, QPointF
    from PySide6.QtGui import QFont, QPalette, QColor, QPixmap, QPainter, QPen
    print("Using PySide6")

from mqtt_client import MQTTClient
from history_manager import HistoryManager
from history_widget import HistoryWidget


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
        self.history_manager = HistoryManager()  # Initialize history manager
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
        self.setMinimumSize(1100, 750)

        # Central widget with tabs
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Create tab widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #ccc;
                border-radius: 5px;
            }
            QTabBar::tab {
                background: #e9ecef;
                padding: 10px 30px;
                margin-right: 2px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }
            QTabBar::tab:selected {
                background: #007bff;
                color: white;
            }
        """)

        # Create Live tab
        self.live_widget = QWidget()
        self.init_live_tab()
        self.tabs.addTab(self.live_widget, "🔴 Live")

        # Create History tab
        self.history_widget = HistoryWidget()
        self.tabs.addTab(self.history_widget, "📋 History")

        main_layout.addWidget(self.tabs)

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

    def init_live_tab(self):
        """Initialize Live monitoring tab"""
        live_layout = QVBoxLayout(self.live_widget)

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
        live_layout.addWidget(connection_group)

        # ========== Topic Selection + Trigger Button ==========
        topic_group = QGroupBox("เลือก Topic สำหรับ Trigger")
        topic_layout = QHBoxLayout()

        self.topic_combo = QComboBox()
        self.topic_combo.setMinimumHeight(50)
        self.topic_combo.setFont(QFont("Arial", 12))
        self.update_topic_list()

        # Add/Remove topic buttons
        self.add_topic_btn = QPushButton("➕")
        self.add_topic_btn.setMinimumHeight(50)
        self.add_topic_btn.setMaximumWidth(50)
        self.add_topic_btn.setToolTip("เพิ่ม Topic")
        self.add_topic_btn.clicked.connect(self.add_topic)

        self.remove_topic_btn = QPushButton("➖")
        self.remove_topic_btn.setMinimumHeight(50)
        self.remove_topic_btn.setMaximumWidth(50)
        self.remove_topic_btn.setToolTip("ลบ Topic")
        self.remove_topic_btn.clicked.connect(self.remove_topic)

        # Trigger button (on the right)
        self.trigger_btn = QPushButton("🔘 TRIGGER")
        self.trigger_btn.setMinimumHeight(50)
        self.trigger_btn.setMinimumWidth(150)
        self.trigger_btn.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.trigger_btn.setStyleSheet(
            "QPushButton { background-color: #007bff; color: white; "
            "border-radius: 5px; }"
            "QPushButton:hover { background-color: #0056b3; }"
            "QPushButton:pressed { background-color: #004085; }"
            "QPushButton:disabled { background-color: #6c757d; }"
            "QPushButton:focus { border: 2px solid #80bdff; }"
        )
        self.trigger_btn.setToolTip("กด Space bar เพื่อ Trigger")
        self.trigger_btn.clicked.connect(self.trigger_inspection)
        self.trigger_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        topic_layout.addWidget(self.topic_combo, 7)
        topic_layout.addWidget(self.add_topic_btn)
        topic_layout.addWidget(self.remove_topic_btn)
        topic_layout.addWidget(self.trigger_btn, 2)
        topic_group.setLayout(topic_layout)
        live_layout.addWidget(topic_group)

        # ========== Dual Camera Display (Side by Side) ==========
        cameras_layout = QHBoxLayout()

        # Camera 1 (Left)
        camera1_widgets = self.create_camera_viewer("Camera 1", "cam1")
        self.cam1_image_id_label = camera1_widgets["image_id_label"]
        self.cam1_device_label = camera1_widgets["device_label"]
        self.cam1_zoom_reset_btn = camera1_widgets["zoom_reset_btn"]
        self.cam1_image_scroll = camera1_widgets["image_scroll"]
        self.cam1_image_label = camera1_widgets["image_label"]
        self.cam1_metadata_label = camera1_widgets["metadata_label"]
        self.cam1_status_label = camera1_widgets["status_label"]
        cameras_layout.addWidget(camera1_widgets["group"])

        # Camera 2 (Right)
        camera2_widgets = self.create_camera_viewer("Camera 2", "cam2")
        self.cam2_image_id_label = camera2_widgets["image_id_label"]
        self.cam2_device_label = camera2_widgets["device_label"]
        self.cam2_zoom_reset_btn = camera2_widgets["zoom_reset_btn"]
        self.cam2_image_scroll = camera2_widgets["image_scroll"]
        self.cam2_image_label = camera2_widgets["image_label"]
        self.cam2_metadata_label = camera2_widgets["metadata_label"]
        self.cam2_status_label = camera2_widgets["status_label"]
        cameras_layout.addWidget(camera2_widgets["group"])

        live_layout.addLayout(cameras_layout)

        # Initialize camera state variables
        self.cam1_pixmap = None
        self.cam1_zoom = 0.25
        self.cam1_device_id = None

        self.cam2_pixmap = None
        self.cam2_zoom = 0.25
        self.cam2_device_id = None

        self.latest_camera = None  # Track which camera received data last

        # Trigger timeout timer
        self.trigger_timer = QTimer()
        self.trigger_timer.timeout.connect(self.on_trigger_timeout)
        self.trigger_timer.setSingleShot(True)

    def create_camera_viewer(self, title, camera_id):
        """Create a camera viewer widget with metadata panel (left) and image (right)"""
        group = QGroupBox(title)
        layout = QVBoxLayout()

        # Top row: Device ID, Image ID and Controls
        top_row = QHBoxLayout()

        # Device ID label
        device_label = QLabel("Device: -")
        device_label.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        device_label.setStyleSheet("QLabel { color: #0056b3; padding: 3px; }")
        top_row.addWidget(device_label)

        # Image ID label
        image_id_label = QLabel("Image: -")
        image_id_label.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        image_id_label.setStyleSheet("QLabel { color: #495057; padding: 3px; }")
        top_row.addWidget(image_id_label)

        top_row.addStretch()

        # Zoom controls
        zoom_out_btn = QPushButton("🔍-")
        zoom_out_btn.setMaximumWidth(45)
        zoom_out_btn.setToolTip("Zoom Out")
        zoom_out_btn.clicked.connect(lambda: self.camera_zoom_out(camera_id))
        top_row.addWidget(zoom_out_btn)

        zoom_reset_btn = QPushButton("25%")
        zoom_reset_btn.setMaximumWidth(55)
        zoom_reset_btn.setToolTip("Reset Zoom to 25%")
        zoom_reset_btn.clicked.connect(lambda: self.camera_zoom_reset(camera_id))
        top_row.addWidget(zoom_reset_btn)

        zoom_in_btn = QPushButton("🔍+")
        zoom_in_btn.setMaximumWidth(45)
        zoom_in_btn.setToolTip("Zoom In")
        zoom_in_btn.clicked.connect(lambda: self.camera_zoom_in(camera_id))
        top_row.addWidget(zoom_in_btn)

        fullscreen_btn = QPushButton("⛶")
        fullscreen_btn.setMaximumWidth(45)
        fullscreen_btn.setToolTip("Full Screen")
        fullscreen_btn.clicked.connect(lambda: self.camera_show_fullscreen(camera_id))
        top_row.addWidget(fullscreen_btn)

        layout.addLayout(top_row)

        # Status label (hidden by default, shown when data received)
        status_label = QLabel()
        status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_label.setMinimumHeight(80)
        status_label.setFont(QFont("Arial", 32, QFont.Weight.Bold))
        status_label.setVisible(False)  # Hidden by default
        layout.addWidget(status_label)

        # Content row: Metadata (left) + Image (right)
        content_layout = QHBoxLayout()

        # Left: Metadata panel
        metadata_label = QLabel("ยังไม่มีข้อมูล")
        metadata_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        metadata_label.setWordWrap(True)
        metadata_label.setFont(QFont("Arial", 9))
        metadata_label.setStyleSheet(
            "QLabel { background-color: #f8f9fa; color: #212529; "
            "border: 1px solid #dee2e6; border-radius: 5px; padding: 10px; }"
        )
        metadata_label.setMinimumWidth(180)
        metadata_label.setMaximumWidth(200)
        metadata_label.setMinimumHeight(350)
        content_layout.addWidget(metadata_label)

        # Right: Image scroll area
        image_scroll = QScrollArea()
        image_scroll.setWidgetResizable(True)
        image_scroll.setMinimumHeight(350)
        image_scroll.setStyleSheet(
            "QScrollArea { background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 5px; }"
        )

        # Image label
        image_label = QLabel("ยังไม่มีภาพ")
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setStyleSheet(
            "QLabel { background-color: #e9ecef; color: #6c757d; "
            "border: 1px solid #dee2e6; border-radius: 5px; "
            "padding: 20px; font-size: 12px; }"
        )
        image_label.setMinimumSize(400, 300)
        image_label.setScaledContents(False)

        image_scroll.setWidget(image_label)
        content_layout.addWidget(image_scroll, 1)  # Give image more space

        layout.addLayout(content_layout)
        group.setLayout(layout)

        return {
            "group": group,
            "device_label": device_label,
            "image_id_label": image_id_label,
            "zoom_reset_btn": zoom_reset_btn,
            "image_scroll": image_scroll,
            "image_label": image_label,
            "metadata_label": metadata_label,
            "status_label": status_label
        }

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

            # Debug: Print received JSON to console
            print("\n" + "="*60)
            print(f"📨 MQTT Message received from topic: {topic}")
            print("="*60)
            print(json.dumps(data, indent=2, ensure_ascii=False))
            print("="*60 + "\n")

            # Extract and display image (metadata and status will be updated inside display_image)
            self.display_image(data)

        except json.JSONDecodeError:
            # Not JSON, just log it
            print(f"⚠️ Non-JSON message: {payload}")
            self.statusBar.showMessage(f"ได้รับข้อความจาก {topic}", 3000)

    def trigger_inspection(self):
        """Trigger MVI inspection"""
        current_topic = self.topic_combo.currentText()
        if not current_topic:
            QMessageBox.warning(self, "Warning", "กรุณาเลือก topic")
            return

        # Change button text to "กำลังตรวจสอบ"
        self.trigger_btn.setText("⏳ กำลังตรวจสอบ")
        self.trigger_btn.setEnabled(False)  # Disable during inspection

        # Start timeout timer (30 seconds)
        self.trigger_timer.start(30000)  # 30000ms = 30 seconds

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
            # Reset button if failed
            self.trigger_timer.stop()
            self.trigger_btn.setText("🔘 TRIGGER")
            self.trigger_btn.setEnabled(True)

    def update_camera_status(self, camera_id, data):
        """Update status label for specific camera based on Overall Result"""
        # Get Overall Result
        result = data.get("Overall Result", data.get("result", "")).lower()

        # Get the appropriate status label
        if camera_id == "cam1":
            status_label = self.cam1_status_label
        else:  # cam2
            status_label = self.cam2_status_label

        # Update status based on result
        if result == "pass":
            status_label.setText("✓ PASS")
            status_label.setStyleSheet(
                "QLabel { background-color: #28a745; color: white; "
                "border-radius: 8px; padding: 15px; }"
            )
            status_label.setVisible(True)
            print(f"✓ {camera_id.upper()}: PASS")
            # Reset trigger button
            self.reset_trigger_button()
        elif result == "fail":
            status_label.setText("✗ FAIL")
            status_label.setStyleSheet(
                "QLabel { background-color: #dc3545; color: white; "
                "border-radius: 8px; padding: 15px; }"
            )
            status_label.setVisible(True)
            print(f"✗ {camera_id.upper()}: FAIL")
            # Reset trigger button
            self.reset_trigger_button()
        else:
            # Try case-insensitive search
            found = False
            for key in data.keys():
                if key.lower() in ["overall result", "result"]:
                    result_val = str(data[key]).lower()
                    if result_val == "pass":
                        status_label.setText("✓ PASS")
                        status_label.setStyleSheet(
                            "QLabel { background-color: #28a745; color: white; "
                            "border-radius: 8px; padding: 15px; }"
                        )
                        status_label.setVisible(True)
                        print(f"✓ {camera_id.upper()}: PASS")
                        found = True
                        break
                    elif result_val == "fail":
                        status_label.setText("✗ FAIL")
                        status_label.setStyleSheet(
                            "QLabel { background-color: #dc3545; color: white; "
                            "border-radius: 8px; padding: 15px; }"
                        )
                        status_label.setVisible(True)
                        print(f"✗ {camera_id.upper()}: FAIL")
                        found = True
                        break

            # Reset trigger button whether result was found or not
            # This prevents button from being stuck if no result field exists
            self.reset_trigger_button()

            if not found:
                print(f"⚠️ {camera_id.upper()}: No result field found, but resetting trigger button")

    def reset_trigger_button(self):
        """Reset trigger button to default state"""
        # Stop timeout timer if running
        if self.trigger_timer.isActive():
            self.trigger_timer.stop()

        self.trigger_btn.setText("🔘 TRIGGER")
        self.trigger_btn.setEnabled(True)
        print("🔄 Trigger button reset")

    def on_trigger_timeout(self):
        """Handle trigger timeout (no response received)"""
        print("⏱️ Trigger timeout - no response received within 30 seconds")
        self.trigger_btn.setText("🔘 TRIGGER")
        self.trigger_btn.setEnabled(True)
        self.statusBar.showMessage("⚠️ Timeout: ไม่ได้รับผลลัพธ์จาก MVI", 5000)

        # Show popup with troubleshooting guide
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("⚠️ Trigger Timeout")
        msg_box.setText("ไม่ได้รับผลการตรวจสอบภายใน 30 วินาที")
        msg_box.setInformativeText(
            "กรุณาตรวจสอบสาเหตุที่อาจทำให้เกิดปัญหา:\n\n"
            "1. ตรวจสอบการเชื่อมต่อ MQTT\n"
            "   - ตรวจสอบว่า MQTT Broker ทำงานอยู่หรือไม่\n"
            "   - ตรวจสอบ IP Address และ Port ใน config.json\n\n"
            "2. ตรวจสอบ Login เข้าหน้าเว็บ Maximo Visual Inspection Edge\n"
            "   - ตรวจสอบว่า Login เข้าระบบได้หรือไม่\n"
            "   - ตรวจสอบ Session ยังคงใช้งานได้อยู่\n\n"
            "3. ตรวจสอบสถานะ Enabled Inspection Status\n"
            "   - ตรวจสอบว่า Inspection ถูกเปิดใช้งานในระบบ MVI Edge\n"
            "   - ตรวจสอบว่า Model พร้อมใช้งานและไม่มี Error"
        )
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()

    def display_metadata(self, camera_id, data):
        """Display metadata from MVI inspection result for specific camera"""
        # Define metadata fields to display (in Thai)
        # Each field can have multiple possible keys (case-insensitive)
        metadata_fields = {
            "Device ID": ["Device ID", "device_id", "DeviceID", "deviceId"],
            "Image ID": ["ImageID", "image_id", "imageId", "Image ID"],
            "Station": ["Station name", "station_name", "StationName", "station", "Station"],
            "Inspection": ["Inspection name", "inspection_name", "InspectionName", "inspection"],
            "วันที่": ["Capture date", "capture_date", "Date sent", "date"],
            "เวลา": ["Capture time", "capture_time", "Time sent", "time"]
        }

        # Build metadata display text
        metadata_text = ""
        metadata_found = False

        # Collect all possible nested structures
        nested_objects = [
            data,  # Main level
            data.get("mvidata", {}),  # MVI Server metadata
            data.get("Alert", {}),  # Alert structure
            data.get("Inherited metadata", {}),  # Inherited metadata
            data.get("metadata", {}),  # Generic metadata
        ]

        # Search for each field in all nested structures
        for thai_label, possible_keys in metadata_fields.items():
            value = None

            # Try each possible key in each nested object
            for nested_obj in nested_objects:
                if not isinstance(nested_obj, dict):
                    continue

                for key in possible_keys:
                    if key in nested_obj and nested_obj[key]:
                        value = nested_obj[key]
                        break

                if value:
                    break

            if value:
                metadata_found = True
                # Format the value (truncate if too long)
                value_str = str(value)
                if len(value_str) > 60:
                    value_str = value_str[:57] + "..."
                metadata_text += f"<b>{thai_label}:</b> {value_str}<br>"

        # Always check for Rule Results array (whether other metadata found or not)
        if "Rule Results" in data:
            rule_results = data.get("Rule Results", [])
            if isinstance(rule_results, list) and len(rule_results) > 0:
                metadata_found = True

                # Add separator if there's already metadata
                if metadata_text:
                    metadata_text += "<br>"

                metadata_text += "<b>Rules:</b><br>"

                for i, rule in enumerate(rule_results, 1):
                    if isinstance(rule, dict):
                        rule_name = rule.get("Rule Name", "Unknown")
                        result_type = rule.get("Result Type", "unknown")

                        # Shorten rule name if too long (remove common prefixes)
                        display_name = rule_name.replace("Check_", "").replace("_", " ")
                        if len(display_name) > 25:
                            display_name = display_name[:22] + "..."

                        # Color code the result
                        if result_type.lower() == "pass":
                            color = "#28a745"  # Green
                            icon = "✓"
                        elif result_type.lower() == "fail":
                            color = "#dc3545"  # Red
                            icon = "✗"
                        else:
                            color = "#6c757d"  # Gray
                            icon = "?"

                        metadata_text += f'  <span style="color: {color}; font-weight: bold;">{icon}</span> {display_name}<br>'

        # If still no metadata found, show default message
        if not metadata_found:
            metadata_text = "<i>ยังไม่มีข้อมูล</i>"
            print(f"⚠️ {camera_id.upper()}: ไม่พบ metadata ที่ตรงกัน")

        # Get the appropriate metadata label for this camera
        if camera_id == "cam1":
            metadata_label = self.cam1_metadata_label
        else:  # cam2
            metadata_label = self.cam2_metadata_label

        # Update metadata label with HTML formatting
        metadata_label.setText(metadata_text)

    def display_image(self, data):
        """Display image from MVI inspection result with dual camera support"""
        # Get Device ID to determine which camera
        device_id = data.get("Device ID", "")

        # Get Image ID
        image_id = data.get("Image ID", "")

        # Get Image Path
        image_path = data.get("Image Path", "")

        # Get Detected Objects
        detected_objects = data.get("Detected Objects", [])

        # Determine which camera to update based on Device ID
        # If no device ID mapping exists, assign to first available camera
        camera_id = None

        if device_id:
            # Check if this device_id is already assigned to a camera
            if self.cam1_device_id == device_id:
                camera_id = "cam1"
            elif self.cam2_device_id == device_id:
                camera_id = "cam2"
            elif self.cam1_device_id is None:
                # Assign to camera 1 if empty
                camera_id = "cam1"
                self.cam1_device_id = device_id
            elif self.cam2_device_id is None:
                # Assign to camera 2 if empty
                camera_id = "cam2"
                self.cam2_device_id = device_id
            else:
                # Both cameras occupied, use camera 1 as default
                camera_id = "cam1"
                self.cam1_device_id = device_id
        else:
            # No device ID provided, use camera 1 as default
            camera_id = "cam1"

        print(f"📷 Displaying on {camera_id.upper()}: Device={device_id}, Image={image_id}")

        # Get the appropriate widgets for this camera
        if camera_id == "cam1":
            image_label = self.cam1_image_label
            image_id_label = self.cam1_image_id_label
            device_label = self.cam1_device_label
            zoom_reset_btn = self.cam1_zoom_reset_btn
        else:  # cam2
            image_label = self.cam2_image_label
            image_id_label = self.cam2_image_id_label
            device_label = self.cam2_device_label
            zoom_reset_btn = self.cam2_zoom_reset_btn

        # Update labels
        if device_id:
            device_label.setText(f"Device: {device_id}")
        else:
            device_label.setText("Device: -")

        if image_id:
            image_id_label.setText(f"Image: {image_id}")
        else:
            image_id_label.setText("Image: -")

        # Update metadata for this camera
        self.display_metadata(camera_id, data)

        # Update status for this camera
        self.update_camera_status(camera_id, data)

        # Track latest camera
        self.latest_camera = camera_id

        # Save to history (will save after image is loaded)
        image_pixmap_for_history = None

        # Try to load and display image
        if image_path and os.path.exists(image_path):
            try:
                pixmap = QPixmap(image_path)

                if not pixmap.isNull():
                    # Draw bounding boxes if detected objects exist
                    if detected_objects and isinstance(detected_objects, list) and len(detected_objects) > 0:
                        pixmap = self.draw_bounding_boxes(pixmap, detected_objects)
                        print(f"✓ วาด bounding boxes: {len(detected_objects)} วัตถุ")

                    # Save pixmap for history
                    image_pixmap_for_history = pixmap

                    # Store original pixmap and reset zoom to 25%
                    if camera_id == "cam1":
                        self.cam1_pixmap = pixmap
                        self.cam1_zoom = 0.25
                    else:
                        self.cam2_pixmap = pixmap
                        self.cam2_zoom = 0.25

                    zoom_reset_btn.setText("25%")

                    # Apply current zoom level
                    self.camera_apply_zoom(camera_id)

                    print(f"✓ โหลดภาพสำเร็จ: {image_path} (ขนาดต้นฉบับ: {pixmap.width()}x{pixmap.height()})")
                else:
                    image_label.clear()
                    image_label.setText(f"ไม่สามารถโหลดภาพได้\n{image_path}")
                    print(f"⚠️ ไม่สามารถโหลดภาพ: {image_path}")

            except Exception as e:
                image_label.clear()
                image_label.setText(f"เกิดข้อผิดพลาดในการโหลดภาพ\n{str(e)}")
                print(f"❌ Error loading image: {e}")

        elif image_path:
            # Path provided but file doesn't exist
            image_label.clear()
            image_label.setText(f"ไม่พบไฟล์ภาพ\n{image_path}")
            image_label.setStyleSheet(
                "QLabel { background-color: #e9ecef; color: #6c757d; "
                "border: 1px solid #dee2e6; border-radius: 5px; "
                "padding: 20px; font-size: 12px; }"
            )
            print(f"⚠️ ไม่พบไฟล์ภาพ: {image_path}")

        else:
            # No image path provided
            image_label.clear()
            image_label.setText("ยังไม่มีภาพ")
            image_label.setStyleSheet(
                "QLabel { background-color: #e9ecef; color: #6c757d; "
                "border: 1px solid #dee2e6; border-radius: 5px; "
                "padding: 20px; font-size: 12px; }"
            )
            print("ℹ️ ไม่มี Image Path ในข้อมูล MQTT")

        # Save to history database
        try:
            self.history_manager.save_inspection(data, image_pixmap_for_history)
            # Refresh history tab if it's visible
            if self.tabs.currentIndex() == 1:  # History tab
                self.history_widget.load_history()
        except Exception as e:
            print(f"⚠️ Failed to save to history: {e}")

    def draw_bounding_boxes(self, pixmap, detected_objects):
        """Draw bounding boxes, labels, and scores on image"""
        # Create a copy of pixmap to draw on
        result_pixmap = QPixmap(pixmap)
        painter = QPainter(result_pixmap)

        try:
            # Enable antialiasing for smoother lines
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            for obj in detected_objects:
                if not isinstance(obj, dict):
                    continue

                # Get bounding box coordinates
                rectangle = obj.get("rectangle", {})
                min_point = rectangle.get("min", {})
                max_point = rectangle.get("max", {})

                x1 = min_point.get("x", 0)
                y1 = min_point.get("y", 0)
                x2 = max_point.get("x", 0)
                y2 = max_point.get("y", 0)

                # Get label and score
                label = obj.get("label", "Unknown")
                score = obj.get("score", 0.0)

                # Calculate width and height
                width = x2 - x1
                height = y2 - y1

                if width <= 0 or height <= 0:
                    continue

                # Choose color based on score (red for low, yellow for medium, green for high)
                if score >= 0.8:
                    color = QColor(40, 167, 69)  # Green #28a745
                elif score >= 0.5:
                    color = QColor(255, 193, 7)  # Yellow #ffc107
                else:
                    color = QColor(220, 53, 69)  # Red #dc3545

                # Draw bounding box
                pen = QPen(color, 3)  # 3px thick line
                painter.setPen(pen)
                painter.drawRect(int(x1), int(y1), int(width), int(height))

                # Prepare label text
                label_text = f"{label} {score:.2f}"

                # Draw label background (filled rectangle)
                font = QFont("Arial", 12, QFont.Weight.Bold)
                painter.setFont(font)
                metrics = painter.fontMetrics()
                text_width = metrics.horizontalAdvance(label_text) + 10
                text_height = metrics.height() + 6

                # Position label above box (or below if near top edge)
                label_y = int(y1) - text_height if y1 > text_height + 5 else int(y1) + int(height) + text_height

                # Draw label background
                painter.fillRect(int(x1), label_y - text_height + 3, text_width, text_height, color)

                # Draw label text
                painter.setPen(QPen(Qt.GlobalColor.white))
                painter.drawText(int(x1) + 5, label_y - 3, label_text)

        finally:
            painter.end()

        return result_pixmap

    def camera_apply_zoom(self, camera_id):
        """Apply current zoom level to camera image"""
        if camera_id == "cam1":
            pixmap = self.cam1_pixmap
            zoom_level = self.cam1_zoom
            image_label = self.cam1_image_label
            zoom_reset_btn = self.cam1_zoom_reset_btn
        else:  # cam2
            pixmap = self.cam2_pixmap
            zoom_level = self.cam2_zoom
            image_label = self.cam2_image_label
            zoom_reset_btn = self.cam2_zoom_reset_btn

        if pixmap and not pixmap.isNull():
            # Calculate new size based on zoom level
            new_width = int(pixmap.width() * zoom_level)
            new_height = int(pixmap.height() * zoom_level)

            # Scale pixmap
            scaled_pixmap = pixmap.scaled(
                new_width, new_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            image_label.setPixmap(scaled_pixmap)
            image_label.setStyleSheet(
                "QLabel { background-color: #e9ecef; "
                "border: 1px solid #dee2e6; border-radius: 5px; }"
            )
            image_label.resize(scaled_pixmap.size())

            # Update zoom button text
            zoom_reset_btn.setText(f"{int(zoom_level * 100)}%")

    def camera_zoom_in(self, camera_id):
        """Zoom in on camera image"""
        if camera_id == "cam1":
            if self.cam1_pixmap:
                self.cam1_zoom = min(self.cam1_zoom + 0.25, 5.0)  # Max 500%
                self.camera_apply_zoom(camera_id)
                print(f"🔍 CAM1 Zoom In: {int(self.cam1_zoom * 100)}%")
        else:  # cam2
            if self.cam2_pixmap:
                self.cam2_zoom = min(self.cam2_zoom + 0.25, 5.0)  # Max 500%
                self.camera_apply_zoom(camera_id)
                print(f"🔍 CAM2 Zoom In: {int(self.cam2_zoom * 100)}%")

    def camera_zoom_out(self, camera_id):
        """Zoom out on camera image"""
        if camera_id == "cam1":
            if self.cam1_pixmap:
                self.cam1_zoom = max(self.cam1_zoom - 0.25, 0.25)  # Min 25%
                self.camera_apply_zoom(camera_id)
                print(f"🔍 CAM1 Zoom Out: {int(self.cam1_zoom * 100)}%")
        else:  # cam2
            if self.cam2_pixmap:
                self.cam2_zoom = max(self.cam2_zoom - 0.25, 0.25)  # Min 25%
                self.camera_apply_zoom(camera_id)
                print(f"🔍 CAM2 Zoom Out: {int(self.cam2_zoom * 100)}%")

    def camera_zoom_reset(self, camera_id):
        """Reset camera zoom to 25%"""
        if camera_id == "cam1":
            if self.cam1_pixmap:
                self.cam1_zoom = 0.25
                self.camera_apply_zoom(camera_id)
                print(f"🔍 CAM1 Zoom Reset: 25%")
        else:  # cam2
            if self.cam2_pixmap:
                self.cam2_zoom = 0.25
                self.camera_apply_zoom(camera_id)
                print(f"🔍 CAM2 Zoom Reset: 25%")

    def camera_show_fullscreen(self, camera_id):
        """Show camera image in fullscreen mode"""
        if camera_id == "cam1":
            pixmap = self.cam1_pixmap
            image_id = self.cam1_image_id_label.text()
            device_id = self.cam1_device_label.text()
        else:  # cam2
            pixmap = self.cam2_pixmap
            image_id = self.cam2_image_id_label.text()
            device_id = self.cam2_device_label.text()

        if pixmap and not pixmap.isNull():
            fullscreen_dialog = FullscreenImageDialog(pixmap, f"{device_id} | {image_id}", self)
            fullscreen_dialog.exec()

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        # Space bar triggers inspection when trigger button has focus
        if event.key() == Qt.Key.Key_Space and self.trigger_btn.hasFocus():
            self.trigger_inspection()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        """Handle window close event"""
        if self.mqtt_client:
            self.mqtt_client.disconnect()
        event.accept()


class FullscreenImageDialog(QDialog):
    """Fullscreen dialog for displaying image"""

    def __init__(self, pixmap, image_id, parent=None):
        super().__init__(parent)
        self.pixmap = pixmap
        self.zoom_level = 1.0

        # Mouse drag variables
        self.dragging = False
        self.last_pos = None

        self.setWindowTitle("Full Screen View")
        self.setModal(True)

        # Set to fullscreen
        self.showMaximized()

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Top toolbar
        toolbar = QHBoxLayout()

        # Image ID
        id_label = QLabel(image_id)
        id_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        id_label.setStyleSheet("QLabel { color: #495057; }")
        toolbar.addWidget(id_label)

        toolbar.addStretch()

        # Zoom controls
        zoom_out_btn = QPushButton("🔍-")
        zoom_out_btn.setMaximumWidth(50)
        zoom_out_btn.clicked.connect(self.zoom_out)
        toolbar.addWidget(zoom_out_btn)

        self.zoom_label = QPushButton("100%")
        self.zoom_label.setMaximumWidth(60)
        self.zoom_label.clicked.connect(self.zoom_reset)
        toolbar.addWidget(self.zoom_label)

        zoom_in_btn = QPushButton("🔍+")
        zoom_in_btn.setMaximumWidth(50)
        zoom_in_btn.clicked.connect(self.zoom_in)
        toolbar.addWidget(zoom_in_btn)

        # Close button
        close_btn = QPushButton("✕ Close")
        close_btn.setMaximumWidth(80)
        close_btn.clicked.connect(self.close)
        toolbar.addWidget(close_btn)

        layout.addLayout(toolbar)

        # Scroll area for image
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)  # Allow manual scrolling
        self.scroll_area.setStyleSheet(
            "QScrollArea { background-color: #2b2b2b; border: none; }"
        )
        # Enable mouse tracking for drag functionality
        self.scroll_area.setMouseTracking(True)
        self.scroll_area.viewport().setMouseTracking(True)

        # Image label
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("QLabel { background-color: #2b2b2b; }")
        self.image_label.setScaledContents(False)
        self.image_label.setMouseTracking(True)

        self.scroll_area.setWidget(self.image_label)
        layout.addWidget(self.scroll_area)

        # Display image
        self.apply_zoom()

        # Set dark style
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
            }
            QPushButton {
                background-color: #444;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #555;
            }
        """)

    def apply_zoom(self):
        """Apply zoom to fullscreen image"""
        if self.pixmap and not self.pixmap.isNull():
            new_width = int(self.pixmap.width() * self.zoom_level)
            new_height = int(self.pixmap.height() * self.zoom_level)

            scaled_pixmap = self.pixmap.scaled(
                new_width, new_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            self.image_label.setPixmap(scaled_pixmap)
            self.image_label.resize(scaled_pixmap.size())
            self.zoom_label.setText(f"{int(self.zoom_level * 100)}%")

    def zoom_in(self):
        """Zoom in"""
        self.zoom_level = min(self.zoom_level + 0.25, 10.0)  # Max 1000% in fullscreen
        self.apply_zoom()

    def zoom_out(self):
        """Zoom out"""
        self.zoom_level = max(self.zoom_level - 0.25, 0.1)  # Min 10%
        self.apply_zoom()

    def zoom_reset(self):
        """Reset zoom"""
        self.zoom_level = 1.0
        self.apply_zoom()

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        elif event.key() == Qt.Key.Key_Plus or event.key() == Qt.Key.Key_Equal:
            self.zoom_in()
        elif event.key() == Qt.Key.Key_Minus:
            self.zoom_out()
        elif event.key() == Qt.Key.Key_0:
            self.zoom_reset()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        """Handle mouse press for drag start"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.last_pos = event.pos()
            self.scroll_area.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging"""
        if self.dragging and self.last_pos:
            # Calculate the delta movement
            delta = event.pos() - self.last_pos
            self.last_pos = event.pos()

            # Get current scroll bar positions
            h_scroll = self.scroll_area.horizontalScrollBar()
            v_scroll = self.scroll_area.verticalScrollBar()

            # Update scroll positions (negative delta because dragging moves content in opposite direction)
            h_scroll.setValue(h_scroll.value() - delta.x())
            v_scroll.setValue(v_scroll.value() - delta.y())

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release for drag end"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.scroll_area.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseReleaseEvent(event)


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    window = MVITriggerGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
