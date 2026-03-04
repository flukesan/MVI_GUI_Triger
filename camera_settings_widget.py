"""
Camera Profiles Dialog — จัดการ Camera Profiles
รองรับ USB, RTSP/IP Camera, GigE Vision
เพิ่ม/แก้ไข/ลบ/ตั้งค่าเริ่มต้น/เชื่อมต่อ

Based on yolo_inspection_system camera_profiles_dialog.py
"""
import json
from pathlib import Path

try:
    from PyQt6.QtWidgets import (
        QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
        QPushButton, QListWidget, QListWidgetItem,
        QGroupBox, QLineEdit, QComboBox, QSpinBox,
        QMessageBox, QFileDialog
    )
    from PyQt6.QtCore import Qt, pyqtSignal as Signal
    from PyQt6.QtGui import QFont
except ImportError:
    from PySide6.QtWidgets import (
        QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
        QPushButton, QListWidget, QListWidgetItem,
        QGroupBox, QLineEdit, QComboBox, QSpinBox,
        QMessageBox, QFileDialog
    )
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QFont


PROFILES_FILE = "camera_profiles.json"


def load_profiles():
    """โหลด camera profiles จากไฟล์"""
    try:
        with open(PROFILES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"profiles": {}, "active_profile": None}


def save_profiles(data):
    """บันทึก camera profiles ลงไฟล์"""
    with open(PROFILES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class CameraProfilesDialog(QDialog):
    """Dialog สำหรับจัดการ Camera Profiles (รองรับ USB/RTSP/IP/GigE Vision)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.modified = False
        self.selected_profile = None  # เก็บ profile ที่เลือกเชื่อมต่อ
        self.profiles_data = load_profiles()
        self.setup_ui()
        self.load_profiles()

    def setup_ui(self):
        self.setWindowTitle("จัดการ Camera Profiles")
        self.setMinimumSize(900, 700)

        layout = QVBoxLayout()

        # Title
        title_label = QLabel("จัดการ Camera Profiles")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Main content: left list + right details
        content_layout = QHBoxLayout()

        # ─── Left: Profile List ───
        left_layout = QVBoxLayout()

        list_label = QLabel("Camera Profiles ที่บันทึกไว้:")
        left_layout.addWidget(list_label)

        self.profile_list = QListWidget()
        self.profile_list.itemClicked.connect(self.on_profile_selected)
        left_layout.addWidget(self.profile_list)

        # Buttons row
        button_layout = QHBoxLayout()

        self.add_btn = QPushButton("+ เพิ่ม")
        self.add_btn.clicked.connect(self.on_add_profile)
        button_layout.addWidget(self.add_btn)

        self.delete_btn = QPushButton("ลบ")
        self.delete_btn.clicked.connect(self.on_delete_profile)
        self.delete_btn.setEnabled(False)
        button_layout.addWidget(self.delete_btn)

        self.set_default_btn = QPushButton("ตั้งเป็นค่าเริ่มต้น")
        self.set_default_btn.clicked.connect(self.on_set_default)
        self.set_default_btn.setEnabled(False)
        button_layout.addWidget(self.set_default_btn)

        left_layout.addLayout(button_layout)

        # Connect button
        self.connect_btn = QPushButton("เชื่อมต่อด้วย Profile นี้")
        self.connect_btn.clicked.connect(self.on_connect_profile)
        self.connect_btn.setEnabled(False)
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; color: white;
                font-weight: bold; padding: 10px;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #cccccc; color: #666666; }
        """)
        left_layout.addWidget(self.connect_btn)

        content_layout.addLayout(left_layout, stretch=2)

        # ─── Right: Profile Details ───
        right_group = QGroupBox("รายละเอียด")
        right_layout = QVBoxLayout()

        # Profile Name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("ชื่อ Profile:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("เช่น: Basler, Watashi_IPCam")
        self.name_edit.textChanged.connect(self.on_profile_modified)
        name_layout.addWidget(self.name_edit)
        right_layout.addLayout(name_layout)

        # Camera Type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("ประเภท:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["USB Camera", "RTSP/IP Camera", "GigE Vision"])
        self.type_combo.currentTextChanged.connect(self.on_type_changed)
        type_layout.addWidget(self.type_combo)
        right_layout.addLayout(type_layout)

        # ─ USB Camera Settings ─
        self.usb_group = QGroupBox("การตั้งค่า USB Camera")
        usb_layout = QVBoxLayout()
        usb_source_layout = QHBoxLayout()
        usb_source_layout.addWidget(QLabel("Camera Index:"))
        self.usb_index_spin = QSpinBox()
        self.usb_index_spin.setMinimum(0)
        self.usb_index_spin.setMaximum(10)
        self.usb_index_spin.setValue(0)
        self.usb_index_spin.valueChanged.connect(self.on_profile_modified)
        usb_source_layout.addWidget(self.usb_index_spin)

        self.usb_scan_btn = QPushButton("Scan")
        self.usb_scan_btn.setToolTip("สแกนหากล้อง USB ที่เชื่อมต่ออยู่")
        self.usb_scan_btn.setFixedWidth(60)
        self.usb_scan_btn.clicked.connect(self.on_scan_usb_cameras)
        usb_source_layout.addWidget(self.usb_scan_btn)

        usb_layout.addLayout(usb_source_layout)

        self.usb_scan_result = QLabel("")
        self.usb_scan_result.setWordWrap(True)
        self.usb_scan_result.setStyleSheet("color: #888; font-size: 10px;")
        usb_layout.addWidget(self.usb_scan_result)

        self.usb_group.setLayout(usb_layout)
        right_layout.addWidget(self.usb_group)

        # ─ RTSP Camera Settings ─
        self.rtsp_group = QGroupBox("การตั้งค่า RTSP/IP Camera")
        rtsp_layout = QVBoxLayout()
        rtsp_layout.addWidget(QLabel("RTSP URL:"))
        self.rtsp_url_edit = QLineEdit()
        self.rtsp_url_edit.setPlaceholderText("rtsp://username:password@192.168.1.100:554/stream")
        self.rtsp_url_edit.textChanged.connect(self.on_profile_modified)
        rtsp_layout.addWidget(self.rtsp_url_edit)

        help_label = QLabel(
            "ตัวอย่าง:\n"
            "  rtsp://admin:12345@192.168.1.100:554/stream1\n"
            "  rtsp://192.168.1.100/live\n"
            "  http://192.168.1.100:8080/video")
        help_label.setStyleSheet("color: #888; font-size: 10px;")
        rtsp_layout.addWidget(help_label)

        self.rtsp_group.setLayout(rtsp_layout)
        right_layout.addWidget(self.rtsp_group)

        # ─ GigE Vision Settings ─
        self.gige_group = QGroupBox("การตั้งค่า GigE Vision")
        gige_layout = QVBoxLayout()

        # GenTL Producer
        gentl_layout = QVBoxLayout()
        gentl_layout.addWidget(QLabel("GenTL Producer (.cti):"))
        gentl_input_layout = QHBoxLayout()
        self.gige_gentl_edit = QLineEdit()
        self.gige_gentl_edit.setPlaceholderText("/opt/pylon/lib/gentlproducer/gtl/ProducerGEV.cti")
        self.gige_gentl_edit.textChanged.connect(self.on_profile_modified)
        gentl_input_layout.addWidget(self.gige_gentl_edit)

        self.gige_browse_btn = QPushButton("เลือกไฟล์...")
        self.gige_browse_btn.clicked.connect(self.browse_gentl)
        gentl_input_layout.addWidget(self.gige_browse_btn)
        gentl_layout.addLayout(gentl_input_layout)
        gige_layout.addLayout(gentl_layout)

        # Camera ID
        camera_id_layout = QHBoxLayout()
        camera_id_layout.addWidget(QLabel("Camera ID:"))
        self.gige_camera_id_edit = QLineEdit()
        self.gige_camera_id_edit.setPlaceholderText("0 (index), serial number, or IP")
        self.gige_camera_id_edit.textChanged.connect(self.on_profile_modified)
        camera_id_layout.addWidget(self.gige_camera_id_edit)
        gige_layout.addLayout(camera_id_layout)

        gige_help = QLabel("ต้องติดตั้ง Camera SDK (Basler Pylon, Vimba, ฯลฯ) ก่อนใช้งาน")
        gige_help.setStyleSheet("color: #888; font-size: 10px;")
        gige_layout.addWidget(gige_help)

        self.gige_group.setLayout(gige_layout)
        right_layout.addWidget(self.gige_group)

        # ─ Resolution ─
        res_group = QGroupBox("ความละเอียด")
        res_layout = QHBoxLayout()

        res_layout.addWidget(QLabel("Width:"))
        self.width_spin = QSpinBox()
        self.width_spin.setMinimum(320)
        self.width_spin.setMaximum(7680)
        self.width_spin.setSingleStep(160)
        self.width_spin.setValue(1280)
        self.width_spin.valueChanged.connect(self.on_profile_modified)
        res_layout.addWidget(self.width_spin)

        res_layout.addWidget(QLabel("Height:"))
        self.height_spin = QSpinBox()
        self.height_spin.setMinimum(240)
        self.height_spin.setMaximum(4320)
        self.height_spin.setSingleStep(120)
        self.height_spin.setValue(720)
        self.height_spin.valueChanged.connect(self.on_profile_modified)
        res_layout.addWidget(self.height_spin)

        res_layout.addWidget(QLabel("FPS:"))
        self.fps_spin = QSpinBox()
        self.fps_spin.setMinimum(1)
        self.fps_spin.setMaximum(120)
        self.fps_spin.setValue(30)
        self.fps_spin.valueChanged.connect(self.on_profile_modified)
        res_layout.addWidget(self.fps_spin)

        res_group.setLayout(res_layout)
        right_layout.addWidget(res_group)

        # ─ Advanced Parameters ─
        adv_group = QGroupBox("พารามิเตอร์ขั้นสูง (Optional)")
        adv_layout = QHBoxLayout()

        adv_layout.addWidget(QLabel("Exposure (us):"))
        self.exposure_spin = QSpinBox()
        self.exposure_spin.setMinimum(0)
        self.exposure_spin.setMaximum(100000)
        self.exposure_spin.setValue(0)
        self.exposure_spin.setSpecialValueText("Auto")
        self.exposure_spin.valueChanged.connect(self.on_profile_modified)
        adv_layout.addWidget(self.exposure_spin)

        adv_layout.addWidget(QLabel("Gain:"))
        self.gain_spin = QSpinBox()
        self.gain_spin.setMinimum(0)
        self.gain_spin.setMaximum(100)
        self.gain_spin.setValue(0)
        self.gain_spin.setSpecialValueText("Auto")
        self.gain_spin.valueChanged.connect(self.on_profile_modified)
        adv_layout.addWidget(self.gain_spin)

        adv_group.setLayout(adv_layout)
        right_layout.addWidget(adv_group)

        # Save Profile button
        self.save_profile_btn = QPushButton("บันทึก Profile นี้")
        self.save_profile_btn.clicked.connect(self.on_save_profile)
        self.save_profile_btn.setEnabled(False)
        right_layout.addWidget(self.save_profile_btn)

        right_layout.addStretch()
        right_group.setLayout(right_layout)
        content_layout.addWidget(right_group, stretch=3)

        layout.addLayout(content_layout)

        # Close button
        button_box = QHBoxLayout()
        button_box.addStretch()
        close_btn = QPushButton("ปิด")
        close_btn.clicked.connect(self.accept)
        button_box.addWidget(close_btn)
        layout.addLayout(button_box)

        self.setLayout(layout)

        # Update visibility
        self.on_type_changed(self.type_combo.currentText())

    def browse_gentl(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "เลือก GenTL Producer File", "",
            "GenTL Producer (*.cti);;All Files (*)")
        if file_path:
            self.gige_gentl_edit.setText(file_path)

    # ─── Profile List ───

    def load_profiles(self):
        self.profile_list.clear()
        profiles = self.profiles_data.get("profiles", {})
        active = self.profiles_data.get("active_profile")

        for name, data in profiles.items():
            display = f"* {name}" if name == active else name
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, {"name": name, **data})
            self.profile_list.addItem(item)

    def on_profile_selected(self, item):
        self.delete_btn.setEnabled(True)
        self.set_default_btn.setEnabled(True)
        self.connect_btn.setEnabled(True)

        data = item.data(Qt.ItemDataRole.UserRole)
        name = data.get("name", "")
        self.name_edit.setText(name)

        # Type
        cam_type = data.get("type", "usb")
        type_map = {
            "usb": "USB Camera",
            "rtsp": "RTSP/IP Camera",
            "ip": "RTSP/IP Camera",
            "gige": "GigE Vision"
        }
        self.type_combo.setCurrentText(type_map.get(cam_type, "USB Camera"))

        # Type-specific fields
        if cam_type == "usb":
            self.usb_index_spin.setValue(int(data.get("source", 0)))
        elif cam_type in ["rtsp", "ip"]:
            self.rtsp_url_edit.setText(str(data.get("source", "")))
        elif cam_type == "gige":
            source = data.get("source", {})
            if isinstance(source, dict):
                self.gige_gentl_edit.setText(source.get("gentl_path", ""))
                self.gige_camera_id_edit.setText(str(source.get("camera_id", 0)))
            else:
                self.gige_gentl_edit.setText(str(source))
                self.gige_camera_id_edit.setText("0")

        # Resolution
        self.width_spin.setValue(data.get("width", 1280))
        self.height_spin.setValue(data.get("height", 720))
        self.fps_spin.setValue(data.get("fps", 30))

        # Advanced
        self.exposure_spin.setValue(data.get("exposure", 0))
        self.gain_spin.setValue(data.get("gain", 0))

        self.save_profile_btn.setEnabled(False)

    def on_scan_usb_cameras(self):
        """Scan for available USB cameras"""
        self.usb_scan_result.setText("Scanning...")
        try:
            from camera_manager import CameraManager
            cameras = CameraManager.list_available_cameras()
            if cameras:
                lines = []
                for cam in cameras:
                    lines.append(f"  index {cam['index']}: {cam['name']}")
                self.usb_scan_result.setText(
                    f"พบกล้อง {len(cameras)} ตัว:\n" + "\n".join(lines))
            else:
                self.usb_scan_result.setText("ไม่พบกล้อง USB")
        except Exception as e:
            self.usb_scan_result.setText(f"Scan error: {e}")

    def on_type_changed(self, camera_type):
        self.usb_group.setVisible(camera_type == "USB Camera")
        self.rtsp_group.setVisible(camera_type == "RTSP/IP Camera")
        self.gige_group.setVisible(camera_type == "GigE Vision")
        self.on_profile_modified()

    def on_profile_modified(self):
        self.save_profile_btn.setEnabled(True)

    # ─── Actions ───

    def on_add_profile(self):
        self.name_edit.clear()
        self.type_combo.setCurrentIndex(0)
        self.usb_index_spin.setValue(0)
        self.rtsp_url_edit.clear()
        self.gige_gentl_edit.clear()
        self.gige_camera_id_edit.setText("0")
        self.width_spin.setValue(1280)
        self.height_spin.setValue(720)
        self.fps_spin.setValue(30)
        self.exposure_spin.setValue(0)
        self.gain_spin.setValue(0)
        self.name_edit.setFocus()
        self.save_profile_btn.setEnabled(True)

    def on_save_profile(self):
        profile_name = self.name_edit.text().strip()
        if not profile_name:
            QMessageBox.warning(self, "คำเตือน", "กรุณาใส่ชื่อ Profile")
            return

        camera_type_map = {
            "USB Camera": "usb",
            "RTSP/IP Camera": "rtsp",
            "GigE Vision": "gige"
        }
        camera_type = camera_type_map[self.type_combo.currentText()]

        # Validate and get source
        if camera_type == "usb":
            source = self.usb_index_spin.value()
        elif camera_type == "rtsp":
            source = self.rtsp_url_edit.text().strip()
            if not source:
                QMessageBox.warning(self, "คำเตือน", "กรุณาใส่ RTSP URL")
                return
        elif camera_type == "gige":
            gentl_path = self.gige_gentl_edit.text().strip()
            camera_id_str = self.gige_camera_id_edit.text().strip() or "0"

            if not gentl_path:
                QMessageBox.warning(self, "คำเตือน", "กรุณาเลือก GenTL Producer file (.cti)")
                return

            try:
                camera_id = int(camera_id_str)
            except ValueError:
                camera_id = camera_id_str

            source = {
                "gentl_path": gentl_path,
                "camera_id": camera_id
            }

        profile_data = {
            "type": camera_type,
            "source": source,
            "width": self.width_spin.value(),
            "height": self.height_spin.value(),
            "fps": self.fps_spin.value()
        }

        if self.exposure_spin.value() > 0:
            profile_data["exposure"] = self.exposure_spin.value()
        if self.gain_spin.value() > 0:
            profile_data["gain"] = self.gain_spin.value()

        self.profiles_data.setdefault("profiles", {})[profile_name] = profile_data
        save_profiles(self.profiles_data)

        self.load_profiles()
        self.modified = True
        self.save_profile_btn.setEnabled(False)

        QMessageBox.information(self, "สำเร็จ", f"บันทึก Profile '{profile_name}' เรียบร้อยแล้ว")

    def on_delete_profile(self):
        item = self.profile_list.currentItem()
        if not item:
            return

        data = item.data(Qt.ItemDataRole.UserRole)
        profile_name = data.get("name", "")

        reply = QMessageBox.question(
            self, "ยืนยันการลบ",
            f"ต้องการลบ Profile '{profile_name}' หรือไม่?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            profiles = self.profiles_data.get("profiles", {})
            profiles.pop(profile_name, None)

            if self.profiles_data.get("active_profile") == profile_name:
                self.profiles_data["active_profile"] = None

            save_profiles(self.profiles_data)
            self.load_profiles()
            self.modified = True

    def on_set_default(self):
        item = self.profile_list.currentItem()
        if not item:
            return

        data = item.data(Qt.ItemDataRole.UserRole)
        profile_name = data.get("name", "")

        self.profiles_data["active_profile"] = profile_name
        save_profiles(self.profiles_data)
        self.load_profiles()
        self.modified = True

        QMessageBox.information(self, "สำเร็จ", f"ตั้ง '{profile_name}' เป็น Profile เริ่มต้นแล้ว")

    def on_connect_profile(self):
        item = self.profile_list.currentItem()
        if not item:
            return

        data = item.data(Qt.ItemDataRole.UserRole)
        profile_name = data.get("name", "")

        self.selected_profile = {
            "name": profile_name,
            "type": data.get("type", "usb"),
            "source": data.get("source", 0),
            "width": data.get("width", 1280),
            "height": data.get("height", 720),
            "fps": data.get("fps", 30),
            "exposure": data.get("exposure", 0),
            "gain": data.get("gain", 0)
        }

        self.accept()


class CameraSettingsWidget(QWidget):
    """Widget ย่อสำหรับแสดงใน Tab — กดเพื่อเปิด Camera Profiles Dialog"""

    camera_config_changed = Signal()
    connect_requested = Signal(dict)  # emit profile data เมื่อกด เชื่อมต่อ

    def __init__(self):
        super().__init__()
        self.init_ui()
        self.refresh_profiles()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Camera Profiles")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        desc = QLabel("จัดการ Camera Profiles — USB, RTSP/IP, GigE Vision\n"
                       "กด 'จัดการ Camera Profiles' เพื่อเพิ่ม/แก้ไข/ลบ")
        desc.setStyleSheet("color: #6c757d;")
        layout.addWidget(desc)

        # Toolbar
        toolbar = QHBoxLayout()

        self.manage_btn = QPushButton("จัดการ Camera Profiles")
        self.manage_btn.setStyleSheet(
            "QPushButton { background-color: #007bff; color: white; padding: 10px 20px; "
            "font-weight: bold; border-radius: 4px; font-size: 14px; }"
            "QPushButton:hover { background-color: #0056b3; }")
        self.manage_btn.clicked.connect(self.open_profiles_dialog)
        toolbar.addWidget(self.manage_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Profile info table
        self.info_group = QGroupBox("Profiles ที่บันทึกไว้")
        info_layout = QVBoxLayout()
        self.profile_list_widget = QListWidget()
        self.profile_list_widget.setStyleSheet("""
            QListWidget { border: 1px solid #dee2e6; border-radius: 4px; font-size: 13px; }
            QListWidget::item { padding: 8px; }
            QListWidget::item:selected { background-color: #007bff; color: white; }
            QListWidget::item:alternate { background-color: #f8f9fa; }
        """)
        self.profile_list_widget.setAlternatingRowColors(True)
        info_layout.addWidget(self.profile_list_widget)
        self.info_group.setLayout(info_layout)
        layout.addWidget(self.info_group, 1)

        # Info
        info_label = QLabel(
            "USB: เชื่อมต่อผ่าน device index (0, 1, 2...)\n"
            "RTSP: เชื่อมต่อผ่าน URL rtsp://[user:pass@]ip:port/path\n"
            "GigE: เชื่อมต่อผ่าน GenTL Producer + Camera SDK (Basler Pylon, Vimba)")
        info_label.setStyleSheet("color: #495057; font-size: 12px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

    def refresh_profiles(self):
        self.profile_list_widget.clear()
        data = load_profiles()
        profiles = data.get("profiles", {})
        active = data.get("active_profile")

        if not profiles:
            self.profile_list_widget.addItem("(ยังไม่มี Profile — กดปุ่มด้านบนเพื่อเพิ่ม)")
            return

        for name, pdata in profiles.items():
            cam_type = pdata.get("type", "usb").upper()
            source = pdata.get("source", "")
            if isinstance(source, dict):
                display_src = source.get("gentl_path", "")
            else:
                display_src = str(source)

            w = pdata.get("width", 1280)
            h = pdata.get("height", 720)
            fps = pdata.get("fps", 30)

            star = "* " if name == active else "  "
            text = f"{star}{name}  [{cam_type}]  {display_src}  ({w}x{h} @ {fps}fps)"
            self.profile_list_widget.addItem(text)

    def open_profiles_dialog(self):
        dialog = CameraProfilesDialog(self)
        result = dialog.exec()

        if dialog.modified:
            self.refresh_profiles()
            self.camera_config_changed.emit()

        if dialog.selected_profile:
            self.connect_requested.emit(dialog.selected_profile)

    def get_active_profile(self):
        """Return active (default) profile data หรือ None"""
        data = load_profiles()
        active_name = data.get("active_profile")
        if active_name:
            profiles = data.get("profiles", {})
            profile = profiles.get(active_name)
            if profile:
                return {"name": active_name, **profile}
        return None

    def get_all_profiles(self):
        """Return dict ของ profiles ทั้งหมด"""
        data = load_profiles()
        return data.get("profiles", {})
