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
        QMessageBox, QGroupBox, QGridLayout, QStatusBar, QScrollArea
    )
    from PyQt6.QtCore import Qt, QTimer, QSize, QRectF, QPointF
    from PyQt6.QtGui import QFont, QPalette, QColor, QPixmap, QPainter, QPen
    print("Using PyQt6")
except ImportError:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QComboBox, QLabel, QLineEdit, QDialog, QDialogButtonBox,
        QMessageBox, QGroupBox, QGridLayout, QStatusBar, QScrollArea
    )
    from PySide6.QtCore import Qt, QTimer, QSize, QRectF, QPointF
    from PySide6.QtGui import QFont, QPalette, QColor, QPixmap, QPainter, QPen
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
        self.setMinimumSize(1100, 750)

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

        # ========== Info & Image Display (Side by Side) ==========
        info_image_layout = QHBoxLayout()

        # Left: Metadata Display
        metadata_group = QGroupBox("ข้อมูลการตรวจสอบ")
        metadata_layout = QVBoxLayout()

        self.metadata_label = QLabel("ยังไม่มีข้อมูล")
        self.metadata_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.metadata_label.setWordWrap(True)
        self.metadata_label.setFont(QFont("Arial", 11))
        self.metadata_label.setStyleSheet(
            "QLabel { background-color: #f8f9fa; color: #212529; "
            "border: 1px solid #dee2e6; border-radius: 5px; padding: 15px; }"
        )
        self.metadata_label.setMinimumHeight(400)
        self.metadata_label.setMaximumWidth(400)

        metadata_layout.addWidget(self.metadata_label)
        metadata_group.setLayout(metadata_layout)
        info_image_layout.addWidget(metadata_group)

        # Right: Image Display
        image_group = QGroupBox("ภาพที่ตรวจสอบ")
        image_layout = QVBoxLayout()

        # Top row: Image ID and Controls
        top_row = QHBoxLayout()

        # Image ID label
        self.image_id_label = QLabel("Image ID: -")
        self.image_id_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.image_id_label.setStyleSheet("QLabel { color: #495057; padding: 5px; }")
        top_row.addWidget(self.image_id_label)

        top_row.addStretch()

        # Zoom controls
        self.zoom_out_btn = QPushButton("🔍-")
        self.zoom_out_btn.setMaximumWidth(50)
        self.zoom_out_btn.setToolTip("Zoom Out")
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        top_row.addWidget(self.zoom_out_btn)

        self.zoom_reset_btn = QPushButton("25%")
        self.zoom_reset_btn.setMaximumWidth(60)
        self.zoom_reset_btn.setToolTip("Reset Zoom to 25%")
        self.zoom_reset_btn.clicked.connect(self.zoom_reset)
        top_row.addWidget(self.zoom_reset_btn)

        self.zoom_in_btn = QPushButton("🔍+")
        self.zoom_in_btn.setMaximumWidth(50)
        self.zoom_in_btn.setToolTip("Zoom In")
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        top_row.addWidget(self.zoom_in_btn)

        self.fullscreen_btn = QPushButton("⛶")
        self.fullscreen_btn.setMaximumWidth(50)
        self.fullscreen_btn.setToolTip("Full Screen")
        self.fullscreen_btn.clicked.connect(self.show_fullscreen)
        top_row.addWidget(self.fullscreen_btn)

        image_layout.addLayout(top_row)

        # Scroll area for image (to support zoom)
        self.image_scroll = QScrollArea()
        self.image_scroll.setWidgetResizable(True)
        self.image_scroll.setMinimumHeight(400)
        self.image_scroll.setStyleSheet(
            "QScrollArea { background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 5px; }"
        )

        # Image label
        self.image_label = QLabel("ยังไม่มีภาพ")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet(
            "QLabel { background-color: #e9ecef; color: #6c757d; "
            "border: 1px solid #dee2e6; border-radius: 5px; "
            "padding: 20px; font-size: 14px; }"
        )
        self.image_label.setMinimumSize(500, 400)
        self.image_label.setScaledContents(False)

        self.image_scroll.setWidget(self.image_label)
        image_layout.addWidget(self.image_scroll)
        image_group.setLayout(image_layout)
        info_image_layout.addWidget(image_group, 1)  # Give more space to image

        main_layout.addLayout(info_image_layout)

        # Initialize zoom and image variables
        self.current_pixmap = None  # Original pixmap with bounding boxes
        self.zoom_level = 0.25  # Default zoom 25%

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

            # Debug: Print received JSON to console
            print("\n" + "="*60)
            print(f"📨 MQTT Message received from topic: {topic}")
            print("="*60)
            print(json.dumps(data, indent=2, ensure_ascii=False))
            print("="*60 + "\n")

            # Check for "Overall Result" first (MVI format), then fallback to "result"
            result = data.get("Overall Result", data.get("result", "")).lower()

            # Extract and display metadata
            self.display_metadata(data)

            # Extract and display image
            self.display_image(data)

            if result == "pass":
                self.show_pass()
            elif result == "fail":
                self.show_fail()
            else:
                # If result not found, try case-insensitive search
                for key in data.keys():
                    if key.lower() in ["overall result", "result"]:
                        result = str(data[key]).lower()
                        if result == "pass":
                            self.show_pass()
                            return
                        elif result == "fail":
                            self.show_fail()
                            return

                # If still no result found, display as text
                self.status_label.setText(f"ไม่พบผลลัพธ์\n{payload}")
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

        # Reset status, metadata, and image
        self.status_label.setText("กำลังตรวจสอบ...")
        self.status_label.setStyleSheet(
            "QLabel { background-color: #ffc107; color: black; "
            "border-radius: 10px; padding: 20px; }"
        )
        self.metadata_label.setText("<i>กำลังรอผลลัพธ์...</i>")
        self.image_id_label.setText("Image ID: -")
        self.image_label.clear()
        self.image_label.setText("กำลังรอภาพ...")
        self.image_label.setStyleSheet(
            "QLabel { background-color: #e9ecef; color: #6c757d; "
            "padding: 40px; font-size: 14px; }"
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

    def display_metadata(self, data):
        """Display metadata from MVI inspection result"""
        # Define metadata fields to display (in Thai)
        # Each field can have multiple possible keys (case-insensitive)
        metadata_fields = {
            "กฎการตรวจสอบ": ["Rule", "rule", "RuleName", "rule_name"],
            "ชื่อไฟล์ต้นฉบับ": ["Original file name", "original_file_name", "filename", "FileName"],
            "วันที่บันทึก": ["Capture date", "capture_date", "Date sent", "date"],
            "เวลาที่บันทึก": ["Capture time", "capture_time", "Time sent", "time"],
            "ชื่อสถานี": ["Station name", "station_name", "StationName", "station"],
            "ชื่อการตรวจสอบ": ["Inspection name", "inspection_name", "InspectionName", "inspection"],
            "ชื่อแหล่งข้อมูล": ["Input source name", "input_source_name", "InputSourceName"],
            "ประเภทแหล่งข้อมูล": ["Input source type", "input_source_type", "InputSourceType"],
            "ประเภทการทริกเกอร์": ["Trigger type", "trigger_type", "TriggerType"],
            "Dataset ID": ["DatasetID", "dataset_id", "datasetId"],
            "Image ID": ["ImageID", "image_id", "imageId"]
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

        # If no standard metadata found, check for Rule Results array
        if not metadata_found and "Rule Results" in data:
            rule_results = data.get("Rule Results", [])
            if isinstance(rule_results, list) and len(rule_results) > 0:
                metadata_found = True
                metadata_text += "<b>กฎที่ตรวจสอบ:</b><br>"

                for i, rule in enumerate(rule_results, 1):
                    if isinstance(rule, dict):
                        rule_name = rule.get("Rule Name", "Unknown")
                        result_type = rule.get("Result Type", "unknown")

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

                        metadata_text += f"  {i}. {rule_name} "
                        metadata_text += f'<span style="color: {color}; font-weight: bold;">({icon} {result_type})</span><br>'

        # If still no metadata found, show default message
        if not metadata_found:
            metadata_text = "<i>ยังไม่มีข้อมูล</i>"
            print("⚠️ ไม่พบ metadata ที่ตรงกัน - ตรวจสอบ console log ด้านบน")

        # Update metadata label with HTML formatting
        self.metadata_label.setText(metadata_text)

    def display_image(self, data):
        """Display image from MVI inspection result"""
        # Try to get Image ID
        image_id = data.get("Image ID", "")

        # Try to get Image Path
        image_path = data.get("Image Path", "")

        # Try to get Detected Objects
        detected_objects = data.get("Detected Objects", [])

        # Update Image ID label
        if image_id:
            self.image_id_label.setText(f"Image ID: {image_id}")
        else:
            self.image_id_label.setText("Image ID: -")

        # Try to load and display image
        if image_path and os.path.exists(image_path):
            try:
                pixmap = QPixmap(image_path)

                if not pixmap.isNull():
                    # Draw bounding boxes if detected objects exist
                    if detected_objects and isinstance(detected_objects, list) and len(detected_objects) > 0:
                        pixmap = self.draw_bounding_boxes(pixmap, detected_objects)
                        print(f"✓ วาด bounding boxes: {len(detected_objects)} วัตถุ")

                    # Store original pixmap and reset zoom to 25%
                    self.current_pixmap = pixmap
                    self.zoom_level = 0.25
                    self.zoom_reset_btn.setText("25%")

                    # Apply current zoom level
                    self.apply_zoom()

                    print(f"✓ โหลดภาพสำเร็จ: {image_path} (ขนาดต้นฉบับ: {pixmap.width()}x{pixmap.height()})")
                else:
                    self.image_label.clear()
                    self.image_label.setText(f"ไม่สามารถโหลดภาพได้\n{image_path}")
                    print(f"⚠️ ไม่สามารถโหลดภาพ: {image_path}")

            except Exception as e:
                self.image_label.clear()
                self.image_label.setText(f"เกิดข้อผิดพลาดในการโหลดภาพ\n{str(e)}")
                print(f"❌ Error loading image: {e}")

        elif image_path:
            # Path provided but file doesn't exist
            self.image_label.clear()
            self.image_label.setText(f"ไม่พบไฟล์ภาพ\n{image_path}")
            self.image_label.setStyleSheet(
                "QLabel { background-color: #e9ecef; color: #6c757d; "
                "border: 1px solid #dee2e6; border-radius: 5px; "
                "padding: 20px; font-size: 14px; }"
            )
            print(f"⚠️ ไม่พบไฟล์ภาพ: {image_path}")

        else:
            # No image path provided
            self.image_label.clear()
            self.image_label.setText("ยังไม่มีภาพ")
            self.image_label.setStyleSheet(
                "QLabel { background-color: #e9ecef; color: #6c757d; "
                "border: 1px solid #dee2e6; border-radius: 5px; "
                "padding: 20px; font-size: 14px; }"
            )
            print("ℹ️ ไม่มี Image Path ในข้อมูล MQTT")

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

    def apply_zoom(self):
        """Apply current zoom level to image"""
        if self.current_pixmap and not self.current_pixmap.isNull():
            # Calculate new size based on zoom level
            new_width = int(self.current_pixmap.width() * self.zoom_level)
            new_height = int(self.current_pixmap.height() * self.zoom_level)

            # Scale pixmap
            scaled_pixmap = self.current_pixmap.scaled(
                new_width, new_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            self.image_label.setPixmap(scaled_pixmap)
            self.image_label.setStyleSheet(
                "QLabel { background-color: #e9ecef; "
                "border: 1px solid #dee2e6; border-radius: 5px; }"
            )
            self.image_label.resize(scaled_pixmap.size())

            # Update zoom button text
            self.zoom_reset_btn.setText(f"{int(self.zoom_level * 100)}%")

    def zoom_in(self):
        """Zoom in on image"""
        if self.current_pixmap:
            self.zoom_level = min(self.zoom_level + 0.25, 5.0)  # Max 500%
            self.apply_zoom()
            print(f"🔍 Zoom In: {int(self.zoom_level * 100)}%")

    def zoom_out(self):
        """Zoom out on image"""
        if self.current_pixmap:
            self.zoom_level = max(self.zoom_level - 0.25, 0.25)  # Min 25%
            self.apply_zoom()
            print(f"🔍 Zoom Out: {int(self.zoom_level * 100)}%")

    def zoom_reset(self):
        """Reset zoom to 25%"""
        if self.current_pixmap:
            self.zoom_level = 0.25
            self.apply_zoom()
            print(f"🔍 Zoom Reset: 25%")

    def show_fullscreen(self):
        """Show image in fullscreen mode"""
        if self.current_pixmap and not self.current_pixmap.isNull():
            fullscreen_dialog = FullscreenImageDialog(self.current_pixmap, self.image_id_label.text(), self)
            fullscreen_dialog.exec()

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
