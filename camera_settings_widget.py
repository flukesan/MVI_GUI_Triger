"""
Camera Settings Widget — จัดการตั้งค่ากล้อง USB, RTSP, GigE
รองรับ เพิ่ม, แก้ไข, ลบ, บันทึก การตั้งค่า
"""
import json
from pathlib import Path

try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
        QComboBox, QLineEdit, QGroupBox, QGridLayout, QMessageBox,
        QDialog, QDialogButtonBox, QSpinBox, QTableWidget,
        QTableWidgetItem, QHeaderView, QAbstractItemView
    )
    from PyQt6.QtCore import Qt, pyqtSignal as Signal
    from PyQt6.QtGui import QFont
except ImportError:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
        QComboBox, QLineEdit, QGroupBox, QGridLayout, QMessageBox,
        QDialog, QDialogButtonBox, QSpinBox, QTableWidget,
        QTableWidgetItem, QHeaderView, QAbstractItemView
    )
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QFont


class CameraEditDialog(QDialog):
    """Dialog สำหรับเพิ่ม/แก้ไขการตั้งค่ากล้อง"""

    def __init__(self, parent=None, camera_data=None):
        super().__init__(parent)
        self.camera_data = camera_data  # None = เพิ่มใหม่, dict = แก้ไข
        self.setWindowTitle("Add Camera" if camera_data is None else "Edit Camera")
        self.setMinimumWidth(450)
        self.init_ui()

        if camera_data:
            self.populate_data(camera_data)

    def init_ui(self):
        layout = QVBoxLayout(self)

        # --- Camera Name ---
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Camera Name:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Camera 1, Top View, Side View")
        name_row.addWidget(self.name_input)
        layout.addLayout(name_row)

        # --- Camera ID ---
        id_row = QHBoxLayout()
        id_row.addWidget(QLabel("Camera ID:"))
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("e.g. cam1, cam2, cam_top")
        id_row.addWidget(self.id_input)
        layout.addLayout(id_row)

        # --- Camera Type ---
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["USB", "RTSP", "GigE"])
        self.type_combo.currentTextChanged.connect(self.on_type_changed)
        type_row.addWidget(self.type_combo)
        layout.addLayout(type_row)

        # --- USB Settings ---
        self.usb_group = QGroupBox("USB Settings")
        usb_layout = QGridLayout()

        usb_layout.addWidget(QLabel("Device Index:"), 0, 0)
        self.usb_index_spin = QSpinBox()
        self.usb_index_spin.setRange(0, 20)
        self.usb_index_spin.setValue(0)
        usb_layout.addWidget(self.usb_index_spin, 0, 1)

        self.usb_group.setLayout(usb_layout)
        layout.addWidget(self.usb_group)

        # --- RTSP Settings ---
        self.rtsp_group = QGroupBox("RTSP Settings")
        rtsp_layout = QGridLayout()

        rtsp_layout.addWidget(QLabel("URL:"), 0, 0)
        self.rtsp_url_input = QLineEdit()
        self.rtsp_url_input.setPlaceholderText("rtsp://user:pass@192.168.1.100:554/stream")
        rtsp_layout.addWidget(self.rtsp_url_input, 0, 1)

        rtsp_layout.addWidget(QLabel("Username:"), 1, 0)
        self.rtsp_user_input = QLineEdit()
        self.rtsp_user_input.setPlaceholderText("(optional)")
        rtsp_layout.addWidget(self.rtsp_user_input, 1, 1)

        rtsp_layout.addWidget(QLabel("Password:"), 2, 0)
        self.rtsp_pass_input = QLineEdit()
        self.rtsp_pass_input.setPlaceholderText("(optional)")
        self.rtsp_pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        rtsp_layout.addWidget(self.rtsp_pass_input, 2, 1)

        self.rtsp_group.setLayout(rtsp_layout)
        layout.addWidget(self.rtsp_group)

        # --- GigE Settings ---
        self.gige_group = QGroupBox("GigE Vision Settings")
        gige_layout = QGridLayout()

        gige_layout.addWidget(QLabel("IP Address:"), 0, 0)
        self.gige_ip_input = QLineEdit()
        self.gige_ip_input.setPlaceholderText("192.168.1.100")
        gige_layout.addWidget(self.gige_ip_input, 0, 1)

        gige_layout.addWidget(QLabel("Port:"), 1, 0)
        self.gige_port_spin = QSpinBox()
        self.gige_port_spin.setRange(1, 65535)
        self.gige_port_spin.setValue(3956)
        gige_layout.addWidget(self.gige_port_spin, 1, 1)

        gige_layout.addWidget(QLabel("Packet Size:"), 2, 0)
        self.gige_packet_spin = QSpinBox()
        self.gige_packet_spin.setRange(576, 16384)
        self.gige_packet_spin.setValue(8192)
        self.gige_packet_spin.setSingleStep(1024)
        gige_layout.addWidget(self.gige_packet_spin, 2, 1)

        self.gige_group.setLayout(gige_layout)
        layout.addWidget(self.gige_group)

        # --- Resolution ---
        res_group = QGroupBox("Resolution")
        res_layout = QHBoxLayout()

        res_layout.addWidget(QLabel("Width:"))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(320, 7680)
        self.width_spin.setValue(1280)
        self.width_spin.setSingleStep(160)
        res_layout.addWidget(self.width_spin)

        res_layout.addWidget(QLabel("Height:"))
        self.height_spin = QSpinBox()
        self.height_spin.setRange(240, 4320)
        self.height_spin.setValue(720)
        self.height_spin.setSingleStep(120)
        res_layout.addWidget(self.height_spin)

        res_group.setLayout(res_layout)
        layout.addWidget(res_group)

        # --- FPS ---
        fps_row = QHBoxLayout()
        fps_row.addWidget(QLabel("Stream FPS:"))
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 120)
        self.fps_spin.setValue(30)
        fps_row.addWidget(self.fps_spin)
        fps_row.addStretch()
        layout.addLayout(fps_row)

        # --- Buttons ---
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Show/hide groups based on initial type
        self.on_type_changed(self.type_combo.currentText())

        self.setStyleSheet("""
            QGroupBox { font-weight: bold; border: 1px solid #ccc; border-radius: 4px;
                         margin-top: 8px; padding-top: 8px; }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
            QLineEdit, QSpinBox, QComboBox { padding: 4px; }
        """)

    def on_type_changed(self, cam_type):
        self.usb_group.setVisible(cam_type == "USB")
        self.rtsp_group.setVisible(cam_type == "RTSP")
        self.gige_group.setVisible(cam_type == "GigE")
        self.adjustSize()

    def populate_data(self, data):
        self.name_input.setText(data.get("label", ""))
        self.id_input.setText(data.get("id", ""))
        self.id_input.setReadOnly(True)  # ID ห้ามเปลี่ยนตอนแก้ไข

        cam_type = data.get("type", "usb").upper()
        if cam_type == "USB":
            self.type_combo.setCurrentText("USB")
            self.usb_index_spin.setValue(data.get("index", 0))
        elif cam_type == "RTSP":
            self.type_combo.setCurrentText("RTSP")
            self.rtsp_url_input.setText(data.get("url", ""))
            self.rtsp_user_input.setText(data.get("username", ""))
            self.rtsp_pass_input.setText(data.get("password", ""))
        elif cam_type == "GIGE":
            self.type_combo.setCurrentText("GigE")
            self.gige_ip_input.setText(data.get("ip", ""))
            self.gige_port_spin.setValue(data.get("port", 3956))
            self.gige_packet_spin.setValue(data.get("packet_size", 8192))

        self.width_spin.setValue(data.get("width", 1280))
        self.height_spin.setValue(data.get("height", 720))
        self.fps_spin.setValue(data.get("fps", 30))

    def on_save(self):
        cam_id = self.id_input.text().strip()
        cam_name = self.name_input.text().strip()

        if not cam_id:
            QMessageBox.warning(self, "Warning", "Camera ID is required")
            return
        if not cam_name:
            QMessageBox.warning(self, "Warning", "Camera Name is required")
            return

        cam_type = self.type_combo.currentText()

        if cam_type == "RTSP" and not self.rtsp_url_input.text().strip():
            QMessageBox.warning(self, "Warning", "RTSP URL is required")
            return
        if cam_type == "GigE" and not self.gige_ip_input.text().strip():
            QMessageBox.warning(self, "Warning", "GigE IP Address is required")
            return

        self.result_data = {
            "id": cam_id,
            "label": cam_name,
            "type": cam_type.lower(),
            "width": self.width_spin.value(),
            "height": self.height_spin.value(),
            "fps": self.fps_spin.value(),
        }

        if cam_type == "USB":
            self.result_data["index"] = self.usb_index_spin.value()
        elif cam_type == "RTSP":
            self.result_data["url"] = self.rtsp_url_input.text().strip()
            user = self.rtsp_user_input.text().strip()
            pwd = self.rtsp_pass_input.text().strip()
            if user:
                self.result_data["username"] = user
            if pwd:
                self.result_data["password"] = pwd
        elif cam_type == "GigE":
            self.result_data["ip"] = self.gige_ip_input.text().strip()
            self.result_data["port"] = self.gige_port_spin.value()
            self.result_data["packet_size"] = self.gige_packet_spin.value()

        self.accept()

    def get_data(self):
        return getattr(self, 'result_data', None)


class CameraSettingsWidget(QWidget):
    """Widget จัดการตั้งค่ากล้อง — เพิ่ม/แก้ไข/ลบ/บันทึก"""

    camera_config_changed = Signal()  # emit เมื่อ config เปลี่ยน

    def __init__(self, config_file="config.json"):
        super().__init__()
        self.config_file = Path(config_file)
        self.config = self.load_config()
        self.init_ui()
        self.refresh_table()

    def load_config(self):
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {"camera": {"sources": {}}}

    def save_config(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Cannot save config: {e}")

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Camera Configuration")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #212529; padding: 5px;")
        layout.addWidget(title)

        desc = QLabel("Manage camera sources — USB, RTSP (IP Camera), GigE Vision")
        desc.setStyleSheet("color: #6c757d; padding-bottom: 10px;")
        layout.addWidget(desc)

        # Toolbar
        toolbar = QHBoxLayout()

        self.add_btn = QPushButton("+ Add Camera")
        self.add_btn.setStyleSheet(
            "QPushButton { background-color: #28a745; color: white; padding: 8px 16px; "
            "font-weight: bold; border-radius: 4px; }"
            "QPushButton:hover { background-color: #218838; }")
        self.add_btn.clicked.connect(self.on_add_camera)
        toolbar.addWidget(self.add_btn)

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setStyleSheet(
            "QPushButton { background-color: #007bff; color: white; padding: 8px 16px; "
            "border-radius: 4px; }"
            "QPushButton:hover { background-color: #0056b3; }")
        self.edit_btn.clicked.connect(self.on_edit_camera)
        toolbar.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setStyleSheet(
            "QPushButton { background-color: #dc3545; color: white; padding: 8px 16px; "
            "border-radius: 4px; }"
            "QPushButton:hover { background-color: #c82333; }")
        self.delete_btn.clicked.connect(self.on_delete_camera)
        toolbar.addWidget(self.delete_btn)

        toolbar.addStretch()

        self.test_btn = QPushButton("Test Connection")
        self.test_btn.setStyleSheet(
            "QPushButton { background-color: #17a2b8; color: white; padding: 8px 16px; "
            "border-radius: 4px; }"
            "QPushButton:hover { background-color: #138496; }")
        self.test_btn.clicked.connect(self.on_test_connection)
        toolbar.addWidget(self.test_btn)

        layout.addLayout(toolbar)

        # Camera Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Camera ID", "Name", "Type", "Source", "Resolution", "FPS"
        ])
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self.on_edit_camera)

        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #dee2e6; border-radius: 4px;
                gridline-color: #e9ecef; font-size: 13px;
            }
            QTableWidget::item { padding: 6px; }
            QTableWidget::item:selected {
                background-color: #007bff; color: white;
            }
            QHeaderView::section {
                background-color: #343a40; color: white;
                padding: 8px; font-weight: bold; border: none;
            }
            QTableWidget::item:alternate { background-color: #f8f9fa; }
        """)

        layout.addWidget(self.table, 1)

        # Info box
        info_group = QGroupBox("Connection Info")
        info_layout = QVBoxLayout()

        self.info_label = QLabel(
            "USB: Connect via device index (0, 1, 2...)\n"
            "RTSP: Connect via URL rtsp://[user:pass@]ip:port/path\n"
            "GigE: Connect via IP address (requires GigE Vision driver)"
        )
        self.info_label.setStyleSheet("color: #495057; font-size: 12px;")
        self.info_label.setWordWrap(True)
        info_layout.addWidget(self.info_label)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

    def refresh_table(self):
        sources = self.config.get("camera", {}).get("sources", {})
        self.table.setRowCount(len(sources))

        for row, (cam_id, cam_data) in enumerate(sources.items()):
            cam_type = cam_data.get("type", "usb").upper()
            label = cam_data.get("label", cam_id)

            # Source display
            if cam_type == "USB":
                source_text = f"Device Index: {cam_data.get('index', 0)}"
            elif cam_type == "RTSP":
                url = cam_data.get("url", "")
                source_text = url if url else "No URL"
            elif cam_type == "GIGE":
                ip = cam_data.get("ip", "")
                port = cam_data.get("port", 3956)
                source_text = f"{ip}:{port}"
            else:
                source_text = str(cam_data)

            width = cam_data.get("width", self.config.get("camera", {}).get("resolution", {}).get("width", 1280))
            height = cam_data.get("height", self.config.get("camera", {}).get("resolution", {}).get("height", 720))
            fps = cam_data.get("fps", self.config.get("camera", {}).get("stream_fps", 30))

            self.table.setItem(row, 0, QTableWidgetItem(cam_id))
            self.table.setItem(row, 1, QTableWidgetItem(label))

            type_item = QTableWidgetItem(cam_type)
            type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 2, type_item)

            self.table.setItem(row, 3, QTableWidgetItem(source_text))

            res_item = QTableWidgetItem(f"{width} x {height}")
            res_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 4, res_item)

            fps_item = QTableWidgetItem(str(fps))
            fps_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 5, fps_item)

    def _get_selected_cam_id(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        return self.table.item(row, 0).text()

    def on_add_camera(self):
        dialog = CameraEditDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if data:
                cam_id = data.pop("id")

                sources = self.config.setdefault("camera", {}).setdefault("sources", {})
                if cam_id in sources:
                    QMessageBox.warning(self, "Warning",
                                        f"Camera ID '{cam_id}' already exists.\nPlease use a different ID.")
                    return

                sources[cam_id] = data
                self.save_config()
                self.refresh_table()
                self.camera_config_changed.emit()

    def on_edit_camera(self):
        cam_id = self._get_selected_cam_id()
        if not cam_id:
            QMessageBox.information(self, "Info", "Please select a camera to edit")
            return

        sources = self.config.get("camera", {}).get("sources", {})
        cam_data = sources.get(cam_id, {})
        cam_data["id"] = cam_id

        dialog = CameraEditDialog(self, cam_data)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if data:
                data.pop("id", None)
                sources[cam_id] = data
                self.save_config()
                self.refresh_table()
                self.camera_config_changed.emit()

    def on_delete_camera(self):
        cam_id = self._get_selected_cam_id()
        if not cam_id:
            QMessageBox.information(self, "Info", "Please select a camera to delete")
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete camera '{cam_id}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            sources = self.config.get("camera", {}).get("sources", {})
            sources.pop(cam_id, None)
            self.save_config()
            self.refresh_table()
            self.camera_config_changed.emit()

    def on_test_connection(self):
        cam_id = self._get_selected_cam_id()
        if not cam_id:
            QMessageBox.information(self, "Info", "Please select a camera to test")
            return

        sources = self.config.get("camera", {}).get("sources", {})
        cam_data = sources.get(cam_id, {})
        cam_type = cam_data.get("type", "usb")

        self.test_btn.setText("Testing...")
        self.test_btn.setEnabled(False)
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()

        try:
            import cv2
            source = self._build_cv2_source(cam_data)
            cap = cv2.VideoCapture(source)

            if cap.isOpened():
                ret, frame = cap.read()
                cap.release()
                if ret:
                    h, w = frame.shape[:2]
                    QMessageBox.information(
                        self, "Success",
                        f"Camera '{cam_id}' connected successfully!\n"
                        f"Type: {cam_type.upper()}\n"
                        f"Frame: {w} x {h}")
                else:
                    QMessageBox.warning(
                        self, "Warning",
                        f"Camera '{cam_id}' opened but cannot read frame.")
            else:
                QMessageBox.critical(
                    self, "Failed",
                    f"Cannot connect to camera '{cam_id}'\n"
                    f"Source: {source}")
        except Exception as e:
            QMessageBox.critical(
                self, "Error",
                f"Connection test failed:\n{str(e)}")
        finally:
            self.test_btn.setText("Test Connection")
            self.test_btn.setEnabled(True)

    def _build_cv2_source(self, cam_data):
        """สร้าง source สำหรับ cv2.VideoCapture จาก camera config"""
        cam_type = cam_data.get("type", "usb")

        if cam_type == "usb":
            return cam_data.get("index", 0)
        elif cam_type == "rtsp":
            url = cam_data.get("url", "")
            user = cam_data.get("username", "")
            pwd = cam_data.get("password", "")
            if user and pwd and "@" not in url.split("//")[-1]:
                # rtsp://user:pass@host:port/path
                protocol, rest = url.split("://", 1)
                url = f"{protocol}://{user}:{pwd}@{rest}"
            return url
        elif cam_type == "gige":
            ip = cam_data.get("ip", "")
            # GigE cameras ผ่าน OpenCV ใช้ IP โดยตรง หรือ GStreamer pipeline
            return ip
        return 0

    def get_camera_sources(self):
        """Return camera sources dict สำหรับใช้กับ CameraManager"""
        return self.config.get("camera", {}).get("sources", {})

    def get_source_for_camera(self, cam_id):
        """Return cv2-compatible source สำหรับ camera_id"""
        sources = self.get_camera_sources()
        cam_data = sources.get(cam_id)
        if cam_data:
            return self._build_cv2_source(cam_data)
        return None
