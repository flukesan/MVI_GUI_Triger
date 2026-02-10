"""
Dual Mode Inspection System
Local YOLOv8 + Camera GUI — ไม่พึ่ง MVI / MQTT
รองรับ Capture Mode และ Realtime Mode
GPU: RTX4000
"""
import sys
import json
import os
from pathlib import Path

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QComboBox, QLabel, QLineEdit, QDialog, QDialogButtonBox,
        QMessageBox, QGroupBox, QGridLayout, QStatusBar, QScrollArea, QTabWidget,
        QRadioButton, QSlider, QFileDialog, QSplitter
    )
    from PyQt6.QtCore import Qt, QTimer, QSize
    from PyQt6.QtGui import QFont, QColor, QPixmap, QPainter, QPen, QImage
    print("Using PyQt6")
except ImportError:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QComboBox, QLabel, QLineEdit, QDialog, QDialogButtonBox,
        QMessageBox, QGroupBox, QGridLayout, QStatusBar, QScrollArea, QTabWidget,
        QRadioButton, QSlider, QFileDialog, QSplitter
    )
    from PySide6.QtCore import Qt, QTimer, QSize
    from PySide6.QtGui import QFont, QColor, QPixmap, QPainter, QPen, QImage
    print("Using PySide6")

import cv2
import numpy as np

from camera_manager import CameraManager
from detection_engine import DetectionEngine
from inspection_controller import InspectionController
from component_definition import ComponentDefinitionManager
from history_manager import HistoryManager
from history_widget import HistoryWidget
from camera_settings_widget import CameraSettingsWidget

try:
    from component_definition_widget import ComponentDefinitionWidget
    COMPONENT_DEF_AVAILABLE = True
except ImportError as e:
    print(f"Component Definition not available: {e}")
    COMPONENT_DEF_AVAILABLE = False


def numpy_to_qpixmap(frame: np.ndarray) -> QPixmap:
    """Convert numpy BGR frame to QPixmap"""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    bytes_per_line = ch * w
    qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg)


class InspectionGUI(QMainWindow):
    """Main GUI — Dual Mode Inspection System"""

    def __init__(self):
        super().__init__()
        self.config_file = Path("config.json")
        self.config = self.load_config()

        # Core components
        self.camera_manager = CameraManager()
        self.detection_engine = DetectionEngine()
        self.component_manager = ComponentDefinitionManager()
        self.history_manager = HistoryManager()
        self.inspection_controller = InspectionController(
            self.camera_manager,
            self.detection_engine,
            self.component_manager,
            self.history_manager
        )

        self.init_ui()
        self.load_ui_state()
        self.connect_signals()
        self.apply_config_settings()

    # ═══════════════════════════════════════════
    #  CONFIG
    # ═══════════════════════════════════════════

    def load_config(self):
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Config load error, using defaults: {e}")
            return {
                "camera": {"sources": {"cam1": {"type": "usb", "index": 0}},
                           "resolution": {"width": 1280, "height": 720},
                           "stream_fps": 30},
                "model": {"path": "", "device": "auto", "confidence": 0.5},
                "inspection": {"mode": "capture", "realtime_inspect_fps": 10},
                "ui_state": {}
            }

    def save_config(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Config save error: {e}")

    def save_ui_state(self):
        mode = "capture" if self.capture_radio.isChecked() else "realtime"
        product_id = self.product_combo.currentData()
        self.config["ui_state"] = {
            "last_product_id": product_id,
            "cam1_zoom": self.cam1_zoom,
            "cam2_zoom": self.cam2_zoom
        }
        self.config["inspection"]["mode"] = mode
        self.save_config()

    def load_ui_state(self):
        ui = self.config.get("ui_state", {})
        mode = self.config.get("inspection", {}).get("mode", "capture")
        if mode == "realtime":
            self.realtime_radio.setChecked(True)
        else:
            self.capture_radio.setChecked(True)

        last_product = ui.get("last_product_id")
        if last_product:
            for i in range(self.product_combo.count()):
                if self.product_combo.itemData(i) == last_product:
                    self.product_combo.setCurrentIndex(i)
                    break

    def apply_config_settings(self):
        model_cfg = self.config.get("model", {})
        if model_cfg.get("path"):
            self.model_path_label.setText(os.path.basename(model_cfg["path"]))

        conf = model_cfg.get("confidence", 0.5)
        self.confidence_slider.setValue(int(conf * 100))

    # ═══════════════════════════════════════════
    #  SIGNALS
    # ═══════════════════════════════════════════

    def connect_signals(self):
        # Camera
        self.camera_manager.camera_opened.connect(self.on_camera_opened)
        self.camera_manager.camera_closed.connect(self.on_camera_closed)
        self.camera_manager.camera_error.connect(self.on_camera_error)

        # Detection
        self.detection_engine.model_loaded.connect(self.on_model_loaded)
        self.detection_engine.model_error.connect(self.on_model_error)

        # Inspection Controller
        self.inspection_controller.inspection_result.connect(self.on_inspection_result)
        self.inspection_controller.frame_display.connect(self.on_frame_display)
        self.inspection_controller.status_changed.connect(self.on_status_changed)
        self.inspection_controller.error_occurred.connect(self.on_error)
        self.inspection_controller.fps_updated.connect(self.on_fps_updated)

    # ═══════════════════════════════════════════
    #  UI INIT
    # ═══════════════════════════════════════════

    def init_ui(self):
        self.setWindowTitle("Dual Mode Inspection System (YOLOv8 + RTX4000)")
        self.setMinimumSize(1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #ccc; border-radius: 5px; }
            QTabBar::tab {
                background: #e9ecef; padding: 10px 30px; margin-right: 2px;
                border-top-left-radius: 5px; border-top-right-radius: 5px;
            }
            QTabBar::tab:selected { background: #007bff; color: white; }
        """)

        # Live Tab
        self.live_widget = QWidget()
        self.init_live_tab()
        self.tabs.addTab(self.live_widget, "Live Inspection")

        # History Tab
        self.history_widget = HistoryWidget()
        self.tabs.addTab(self.history_widget, "History")

        # Camera Settings Tab
        self.camera_settings_widget = CameraSettingsWidget()
        self.camera_settings_widget.camera_config_changed.connect(self.on_camera_config_changed)
        self.camera_settings_widget.connect_requested.connect(self.on_connect_from_profile)
        self.tabs.addTab(self.camera_settings_widget, "Camera Settings")

        # Update active profile label now that widget is ready
        self._update_active_profile_label()

        # Component Definition Tab
        if COMPONENT_DEF_AVAILABLE:
            self.component_def_widget = ComponentDefinitionWidget()
            self.tabs.addTab(self.component_def_widget, "Component Definition")

        main_layout.addWidget(self.tabs)

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        self.setStyleSheet("""
            QGroupBox {
                font-size: 13px; font-weight: bold;
                border: 2px solid #ccc; border-radius: 5px;
                margin-top: 10px; padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 10px; padding: 0 5px;
            }
        """)

    def init_live_tab(self):
        live_layout = QHBoxLayout(self.live_widget)

        # ═══ LEFT PANEL (Settings) ═══
        left_panel = QWidget()
        left_panel.setMaximumWidth(320)
        left_panel.setMinimumWidth(280)
        left_layout = QVBoxLayout(left_panel)

        # --- Camera Settings ---
        cam_group = QGroupBox("Camera")
        cam_layout = QVBoxLayout()

        # Active profile display
        self.active_profile_label = QLabel("No profile")
        self.active_profile_label.setStyleSheet("color: #495057; font-size: 11px;")
        cam_layout.addWidget(self.active_profile_label)

        # Open Profiles button
        self.open_profiles_btn = QPushButton("Camera Profiles...")
        self.open_profiles_btn.setStyleSheet(
            "QPushButton { background-color: #007bff; color: white; padding: 6px; }"
            "QPushButton:hover { background-color: #0056b3; }")
        self.open_profiles_btn.clicked.connect(self.on_open_camera_profiles)
        cam_layout.addWidget(self.open_profiles_btn)

        # Connect / Disconnect
        cam_btn_layout = QHBoxLayout()
        self.connect_cam_btn = QPushButton("Connect Default")
        self.connect_cam_btn.setStyleSheet(
            "QPushButton { background-color: #28a745; color: white; padding: 6px; font-weight: bold; }"
            "QPushButton:hover { background-color: #218838; }")
        self.connect_cam_btn.clicked.connect(self.on_connect_camera)
        cam_btn_layout.addWidget(self.connect_cam_btn)

        self.disconnect_cam_btn = QPushButton("Disconnect")
        self.disconnect_cam_btn.setStyleSheet(
            "QPushButton { background-color: #dc3545; color: white; padding: 6px; }"
            "QPushButton:hover { background-color: #c82333; }")
        self.disconnect_cam_btn.clicked.connect(self.on_disconnect_camera)
        self.disconnect_cam_btn.setEnabled(False)
        cam_btn_layout.addWidget(self.disconnect_cam_btn)
        cam_layout.addLayout(cam_btn_layout)

        self.cam_status_label = QLabel("Disconnected")
        self.cam_status_label.setStyleSheet(
            "QLabel { background-color: #dc3545; color: white; padding: 5px; "
            "border-radius: 3px; font-weight: bold; }")
        cam_layout.addWidget(self.cam_status_label)

        cam_group.setLayout(cam_layout)
        left_layout.addWidget(cam_group)

        # --- Model Settings ---
        model_group = QGroupBox("YOLO Model")
        model_layout = QGridLayout()

        model_layout.addWidget(QLabel("Model:"), 0, 0)
        model_row = QHBoxLayout()
        self.model_path_label = QLabel("No model")
        self.model_path_label.setStyleSheet("color: #6c757d;")
        model_row.addWidget(self.model_path_label, 1)
        self.browse_model_btn = QPushButton("Browse")
        self.browse_model_btn.clicked.connect(self.on_browse_model)
        model_row.addWidget(self.browse_model_btn)
        model_layout.addLayout(model_row, 0, 1)

        model_layout.addWidget(QLabel("Device:"), 1, 0)
        self.device_combo = QComboBox()
        self.device_combo.addItems(["auto", "cpu", "0 (GPU)"])
        model_layout.addWidget(self.device_combo, 1, 1)

        model_layout.addWidget(QLabel("Confidence:"), 2, 0)
        conf_row = QHBoxLayout()
        self.confidence_slider = QSlider(Qt.Orientation.Horizontal)
        self.confidence_slider.setRange(10, 95)
        self.confidence_slider.setValue(50)
        self.confidence_slider.valueChanged.connect(self.on_confidence_changed)
        conf_row.addWidget(self.confidence_slider)
        self.conf_label = QLabel("0.50")
        conf_row.addWidget(self.conf_label)
        model_layout.addLayout(conf_row, 2, 1)

        self.load_model_btn = QPushButton("Load Model")
        self.load_model_btn.setStyleSheet(
            "QPushButton { background-color: #007bff; color: white; padding: 6px; font-weight: bold; }"
            "QPushButton:hover { background-color: #0056b3; }")
        self.load_model_btn.clicked.connect(self.on_load_model)
        model_layout.addWidget(self.load_model_btn, 3, 0, 1, 2)

        self.model_status_label = QLabel("No model loaded")
        self.model_status_label.setWordWrap(True)
        self.model_status_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        model_layout.addWidget(self.model_status_label, 4, 0, 1, 2)

        model_group.setLayout(model_layout)
        left_layout.addWidget(model_group)

        # --- Inspection Settings ---
        insp_group = QGroupBox("Inspection")
        insp_layout = QVBoxLayout()

        # Mode
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode:"))
        self.capture_radio = QRadioButton("Capture")
        self.realtime_radio = QRadioButton("Realtime")
        self.capture_radio.setChecked(True)
        self.capture_radio.toggled.connect(self.on_mode_changed)
        mode_row.addWidget(self.capture_radio)
        mode_row.addWidget(self.realtime_radio)
        mode_row.addStretch()
        insp_layout.addLayout(mode_row)

        # Product
        product_row = QHBoxLayout()
        product_row.addWidget(QLabel("Product:"))
        self.product_combo = QComboBox()
        self.product_combo.addItem("-- No Product --", None)
        self.load_product_list()
        self.product_combo.currentIndexChanged.connect(self.on_product_changed)
        product_row.addWidget(self.product_combo, 1)

        self.refresh_products_btn = QPushButton("Refresh")
        self.refresh_products_btn.setMaximumWidth(60)
        self.refresh_products_btn.clicked.connect(self.load_product_list)
        product_row.addWidget(self.refresh_products_btn)
        insp_layout.addLayout(product_row)

        self.expected_label = QLabel("Expected: -")
        self.expected_label.setStyleSheet("color: #495057; font-size: 11px;")
        insp_layout.addWidget(self.expected_label)

        # TRIGGER button (Capture mode)
        self.trigger_btn = QPushButton("TRIGGER")
        self.trigger_btn.setMinimumHeight(50)
        self.trigger_btn.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.trigger_btn.setStyleSheet(
            "QPushButton { background-color: #007bff; color: white; border-radius: 5px; }"
            "QPushButton:hover { background-color: #0056b3; }"
            "QPushButton:pressed { background-color: #004085; }"
            "QPushButton:disabled { background-color: #6c757d; }")
        self.trigger_btn.setToolTip("Space bar to trigger")
        self.trigger_btn.clicked.connect(self.on_trigger)
        self.trigger_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        insp_layout.addWidget(self.trigger_btn)

        # START / STOP button (Realtime mode)
        self.start_stop_btn = QPushButton("START")
        self.start_stop_btn.setMinimumHeight(50)
        self.start_stop_btn.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.start_stop_btn.setStyleSheet(
            "QPushButton { background-color: #28a745; color: white; border-radius: 5px; }"
            "QPushButton:hover { background-color: #218838; }")
        self.start_stop_btn.clicked.connect(self.on_start_stop_realtime)
        self.start_stop_btn.setVisible(False)
        insp_layout.addWidget(self.start_stop_btn)

        # Load from file button
        self.load_file_btn = QPushButton("Load Image File")
        self.load_file_btn.clicked.connect(self.on_load_image_file)
        insp_layout.addWidget(self.load_file_btn)

        insp_group.setLayout(insp_layout)
        left_layout.addWidget(insp_group)

        # --- Result Summary ---
        result_group = QGroupBox("Last Result")
        result_layout = QVBoxLayout()

        self.result_status_label = QLabel("--")
        self.result_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_status_label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        self.result_status_label.setMinimumHeight(50)
        self.result_status_label.setStyleSheet(
            "QLabel { background-color: #e9ecef; color: #6c757d; "
            "border-radius: 8px; padding: 10px; }")
        result_layout.addWidget(self.result_status_label)

        self.result_detail_label = QLabel("No inspection yet")
        self.result_detail_label.setWordWrap(True)
        self.result_detail_label.setStyleSheet("font-size: 11px; color: #495057;")
        result_layout.addWidget(self.result_detail_label)

        self.fps_label = QLabel("")
        self.fps_label.setStyleSheet("color: #007bff; font-weight: bold;")
        result_layout.addWidget(self.fps_label)

        result_group.setLayout(result_layout)
        left_layout.addWidget(result_group)

        left_layout.addStretch()
        live_layout.addWidget(left_panel)

        # ═══ RIGHT PANEL (Camera Viewers) ═══
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        cameras_layout = QHBoxLayout()

        # Camera 1
        cam1_widgets = self.create_camera_viewer("Camera 1", "cam1")
        self.cam1_image_label = cam1_widgets["image_label"]
        self.cam1_image_scroll = cam1_widgets["image_scroll"]
        self.cam1_status_label = cam1_widgets["status_label"]
        self.cam1_info_label = cam1_widgets["info_label"]
        self.cam1_zoom_reset_btn = cam1_widgets["zoom_reset_btn"]
        cameras_layout.addWidget(cam1_widgets["group"])

        # Camera 2
        cam2_widgets = self.create_camera_viewer("Camera 2", "cam2")
        self.cam2_image_label = cam2_widgets["image_label"]
        self.cam2_image_scroll = cam2_widgets["image_scroll"]
        self.cam2_status_label = cam2_widgets["status_label"]
        self.cam2_info_label = cam2_widgets["info_label"]
        self.cam2_zoom_reset_btn = cam2_widgets["zoom_reset_btn"]
        cameras_layout.addWidget(cam2_widgets["group"])

        right_layout.addLayout(cameras_layout)
        live_layout.addWidget(right_panel, 1)

        # Camera state
        self.cam1_pixmap = None
        self.cam1_zoom = 0.25
        self.cam2_pixmap = None
        self.cam2_zoom = 0.25
        self._realtime_running = False

    def create_camera_viewer(self, title, camera_id):
        group = QGroupBox(title)
        layout = QVBoxLayout()

        # Top row: info + zoom controls
        top_row = QHBoxLayout()

        info_label = QLabel("No data")
        info_label.setFont(QFont("Arial", 9))
        info_label.setStyleSheet("color: #495057; padding: 2px;")
        top_row.addWidget(info_label)
        top_row.addStretch()

        zoom_out_btn = QPushButton("-")
        zoom_out_btn.setMaximumWidth(35)
        zoom_out_btn.clicked.connect(lambda: self.camera_zoom_out(camera_id))
        top_row.addWidget(zoom_out_btn)

        zoom_reset_btn = QPushButton("25%")
        zoom_reset_btn.setMaximumWidth(50)
        zoom_reset_btn.clicked.connect(lambda: self.camera_zoom_reset(camera_id))
        top_row.addWidget(zoom_reset_btn)

        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setMaximumWidth(35)
        zoom_in_btn.clicked.connect(lambda: self.camera_zoom_in(camera_id))
        top_row.addWidget(zoom_in_btn)

        fullscreen_btn = QPushButton("Full")
        fullscreen_btn.setMaximumWidth(40)
        fullscreen_btn.clicked.connect(lambda: self.camera_show_fullscreen(camera_id))
        top_row.addWidget(fullscreen_btn)

        layout.addLayout(top_row)

        # Status label (PASS/FAIL)
        status_label = QLabel()
        status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_label.setMinimumHeight(60)
        status_label.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        status_label.setVisible(False)
        layout.addWidget(status_label)

        # Image scroll area
        image_scroll = QScrollArea()
        image_scroll.setWidgetResizable(True)
        image_scroll.setMinimumHeight(350)
        image_scroll.setStyleSheet(
            "QScrollArea { background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 5px; }")

        image_label = QLabel("No image")
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setStyleSheet(
            "QLabel { background-color: #e9ecef; color: #6c757d; "
            "border: 1px solid #dee2e6; border-radius: 5px; padding: 20px; }")
        image_label.setMinimumSize(400, 300)
        image_label.setScaledContents(False)

        image_scroll.setWidget(image_label)
        layout.addWidget(image_scroll, 1)

        group.setLayout(layout)

        return {
            "group": group,
            "image_label": image_label,
            "image_scroll": image_scroll,
            "status_label": status_label,
            "info_label": info_label,
            "zoom_reset_btn": zoom_reset_btn
        }

    def load_product_list(self):
        current_data = self.product_combo.currentData()
        self.product_combo.clear()
        self.product_combo.addItem("-- No Product --", None)

        products = self.component_manager.list_products()
        for p in products:
            self.product_combo.addItem(
                f"{p['name']} ({p['component_count']} parts)", p['id'])

        # Restore selection
        if current_data:
            for i in range(self.product_combo.count()):
                if self.product_combo.itemData(i) == current_data:
                    self.product_combo.setCurrentIndex(i)
                    break

    # ═══════════════════════════════════════════
    #  CAMERA HANDLERS
    # ═══════════════════════════════════════════

    def _update_active_profile_label(self):
        """Update active profile display label"""
        profile = self.camera_settings_widget.get_active_profile()
        if profile:
            name = profile.get("name", "")
            cam_type = profile.get("type", "usb").upper()
            self.active_profile_label.setText(f"Active: {name} [{cam_type}]")
        else:
            self.active_profile_label.setText("No default profile set")

    def on_camera_config_changed(self):
        """เมื่อ Camera Settings เปลี่ยน — refresh UI"""
        self._update_active_profile_label()
        self.status_bar.showMessage("Camera profiles updated")

    def on_open_camera_profiles(self):
        """เปิด Camera Profiles Dialog"""
        self.camera_settings_widget.open_profiles_dialog()

    def on_connect_from_profile(self, profile: dict):
        """เชื่อมต่อกล้องจาก Camera Profile (จากปุ่ม 'เชื่อมต่อด้วย Profile นี้')"""
        self.status_bar.showMessage(f"Connecting: {profile.get('name', '')}...")
        success = self.camera_manager.connect_from_profile(0, profile)
        if not success:
            self.status_bar.showMessage(f"Failed to connect: {profile.get('name', '')}")
        self._update_active_profile_label()
        # Switch back to Live tab
        self.tabs.setCurrentIndex(0)

    def on_connect_camera(self):
        """Connect using active (default) profile"""
        profile = self.camera_settings_widget.get_active_profile()
        if profile:
            self.status_bar.showMessage(f"Connecting: {profile.get('name', '')}...")
            self.camera_manager.connect_from_profile(0, profile)
        else:
            from camera_settings_widget import CameraProfilesDialog
            QMessageBox.information(
                self, "No Profile",
                "No default camera profile set.\n"
                "Please open Camera Profiles to add and set a default profile.")
            self.on_open_camera_profiles()

    def on_disconnect_camera(self):
        if self._realtime_running:
            self.on_start_stop_realtime()  # Stop realtime first
        self.camera_manager.close_all()

    def on_camera_opened(self, camera_id):
        self.cam_status_label.setText(f"Connected (Cam {camera_id})")
        self.cam_status_label.setStyleSheet(
            "QLabel { background-color: #28a745; color: white; padding: 5px; "
            "border-radius: 3px; font-weight: bold; }")
        self.connect_cam_btn.setEnabled(False)
        self.disconnect_cam_btn.setEnabled(True)
        self.trigger_btn.setEnabled(True)
        self.status_bar.showMessage(f"Camera {camera_id} connected")

    def on_camera_closed(self, camera_id):
        if not self.camera_manager.cameras:
            self.cam_status_label.setText("Disconnected")
            self.cam_status_label.setStyleSheet(
                "QLabel { background-color: #dc3545; color: white; padding: 5px; "
                "border-radius: 3px; font-weight: bold; }")
            self.connect_cam_btn.setEnabled(True)
            self.disconnect_cam_btn.setEnabled(False)

    def on_camera_error(self, camera_id, error):
        self.status_bar.showMessage(f"Camera {camera_id} error: {error}")

    # ═══════════════════════════════════════════
    #  MODEL HANDLERS
    # ═══════════════════════════════════════════

    def on_browse_model(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select YOLO Model", "",
            "YOLO Models (*.pt *.onnx);;All Files (*)")
        if file_path:
            self.config["model"]["path"] = file_path
            self.model_path_label.setText(os.path.basename(file_path))
            self.save_config()

    def on_load_model(self):
        model_path = self.config.get("model", {}).get("path", "")
        if not model_path:
            QMessageBox.warning(self, "Warning", "Please select a model file first")
            return

        if not os.path.exists(model_path):
            QMessageBox.warning(self, "Warning", f"Model file not found:\n{model_path}")
            return

        device_text = self.device_combo.currentText()
        if device_text.startswith("0"):
            device = "0"
        elif device_text == "cpu":
            device = "cpu"
        else:
            device = "auto"

        self.model_status_label.setText("Loading model...")
        self.load_model_btn.setEnabled(False)
        QApplication.processEvents()

        success = self.detection_engine.load_model(model_path, device)
        self.load_model_btn.setEnabled(True)

        if not success:
            self.model_status_label.setText("Failed to load model")

    def on_model_loaded(self, info_str):
        self.model_status_label.setText(f"Loaded: {info_str}")
        self.model_status_label.setStyleSheet("color: #28a745; font-size: 11px; font-weight: bold;")
        self.status_bar.showMessage(f"Model loaded: {info_str}")

    def on_model_error(self, error):
        self.model_status_label.setText(f"Error: {error}")
        self.model_status_label.setStyleSheet("color: #dc3545; font-size: 11px;")
        QMessageBox.warning(self, "Model Error", error)

    def on_confidence_changed(self, value):
        conf = value / 100.0
        self.conf_label.setText(f"{conf:.2f}")
        self.detection_engine.set_confidence(conf)
        self.config["model"]["confidence"] = conf

    # ═══════════════════════════════════════════
    #  MODE & PRODUCT HANDLERS
    # ═══════════════════════════════════════════

    def on_mode_changed(self):
        is_capture = self.capture_radio.isChecked()
        self.trigger_btn.setVisible(is_capture)
        self.load_file_btn.setVisible(is_capture)
        self.start_stop_btn.setVisible(not is_capture)
        self.fps_label.setVisible(not is_capture)

        if is_capture:
            self.inspection_controller.set_mode("capture")
        else:
            self.inspection_controller.set_mode("realtime")

        self.save_ui_state()

    def on_product_changed(self, index):
        product_id = self.product_combo.currentData()
        if product_id:
            self.inspection_controller.set_product(product_id)
            expected = self.inspection_controller.get_expected_class_names()
            self.expected_label.setText(f"Expected: {', '.join(expected)}")
        else:
            self.inspection_controller.current_product_id = None
            self.inspection_controller.expected_parts = []
            self.inspection_controller.expected_class_names = set()
            self.expected_label.setText("Expected: -")
        self.save_ui_state()

    # ═══════════════════════════════════════════
    #  CAPTURE MODE
    # ═══════════════════════════════════════════

    def on_trigger(self):
        if not self.detection_engine.is_model_loaded():
            QMessageBox.warning(self, "Warning", "Please load a YOLO model first")
            return

        self.trigger_btn.setText("Inspecting...")
        self.trigger_btn.setEnabled(False)
        QApplication.processEvents()

        self.inspection_controller.trigger_capture(0)

        self.trigger_btn.setText("TRIGGER")
        self.trigger_btn.setEnabled(True)

    def on_load_image_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp);;All Files (*)")
        if not file_path:
            return

        if not self.detection_engine.is_model_loaded():
            QMessageBox.warning(self, "Warning", "Please load a YOLO model first")
            return

        self.trigger_btn.setText("Inspecting...")
        self.trigger_btn.setEnabled(False)
        QApplication.processEvents()

        self.inspection_controller.trigger_capture_from_file(file_path)

        self.trigger_btn.setText("TRIGGER")
        self.trigger_btn.setEnabled(True)

    # ═══════════════════════════════════════════
    #  REALTIME MODE
    # ═══════════════════════════════════════════

    def on_start_stop_realtime(self):
        if not self._realtime_running:
            # START
            if not self.detection_engine.is_model_loaded():
                QMessageBox.warning(self, "Warning", "Please load a YOLO model first")
                return
            if not self.camera_manager.is_opened(0):
                QMessageBox.warning(self, "Warning", "Please connect a camera first")
                return

            self._realtime_running = True
            self.start_stop_btn.setText("STOP")
            self.start_stop_btn.setStyleSheet(
                "QPushButton { background-color: #dc3545; color: white; border-radius: 5px; }"
                "QPushButton:hover { background-color: #c82333; }")
            self.trigger_btn.setEnabled(False)

            self.inspection_controller.start_realtime(0)
        else:
            # STOP
            self._realtime_running = False
            self.start_stop_btn.setText("START")
            self.start_stop_btn.setStyleSheet(
                "QPushButton { background-color: #28a745; color: white; border-radius: 5px; }"
                "QPushButton:hover { background-color: #218838; }")
            self.trigger_btn.setEnabled(True)
            self.fps_label.setText("")

            self.inspection_controller.stop_realtime(0)

    # ═══════════════════════════════════════════
    #  RESULT DISPLAY
    # ═══════════════════════════════════════════

    def on_inspection_result(self, result):
        status = result.get("status", "UNKNOWN")
        found = result.get("found_count", 0)
        total = result.get("total_expected", 0)
        missing = result.get("missing_parts", [])
        inf_time = result.get("inference_time_ms", 0)

        # Update result status
        if status == "PASS":
            self.result_status_label.setText("PASS")
            self.result_status_label.setStyleSheet(
                "QLabel { background-color: #28a745; color: white; "
                "border-radius: 8px; padding: 10px; }")
        elif status == "FAIL":
            self.result_status_label.setText("FAIL")
            self.result_status_label.setStyleSheet(
                "QLabel { background-color: #dc3545; color: white; "
                "border-radius: 8px; padding: 10px; }")
        else:
            self.result_status_label.setText(status)
            self.result_status_label.setStyleSheet(
                "QLabel { background-color: #ffc107; color: #212529; "
                "border-radius: 8px; padding: 10px; }")

        # Detail text
        detail = f"Found: {found}/{total}" if total > 0 else f"Detected: {found}"
        if missing:
            detail += f"\nMissing: {', '.join(missing)}"
        detail += f"\nInference: {inf_time:.1f} ms"
        self.result_detail_label.setText(detail)

        # Update camera status label
        camera_id = result.get("camera_id", 0)
        cam_status = self.cam1_status_label if camera_id == 0 else self.cam2_status_label

        if status == "PASS":
            cam_status.setText("PASS")
            cam_status.setStyleSheet(
                "QLabel { background-color: #28a745; color: white; "
                "border-radius: 8px; padding: 10px; }")
            cam_status.setVisible(True)
        elif status == "FAIL":
            cam_status.setText("FAIL")
            cam_status.setStyleSheet(
                "QLabel { background-color: #dc3545; color: white; "
                "border-radius: 8px; padding: 10px; }")
            cam_status.setVisible(True)

        # Camera info
        info_label = self.cam1_info_label if camera_id == 0 else self.cam2_info_label
        info_label.setText(f"{result.get('product_name', '')} | {inf_time:.0f}ms")

        # Refresh history if visible
        if self.tabs.currentIndex() == 1:
            self.history_widget.load_history()

        self.status_bar.showMessage(
            f"Inspection: {status} | Found {found}/{total} | {inf_time:.1f}ms")

    def on_frame_display(self, camera_id, frame):
        """Display annotated frame from InspectionController"""
        pixmap = numpy_to_qpixmap(frame)

        if camera_id == 0:
            self.cam1_pixmap = pixmap
            self.camera_apply_zoom("cam1")
        else:
            self.cam2_pixmap = pixmap
            self.camera_apply_zoom("cam2")

    def on_status_changed(self, status):
        self.status_bar.showMessage(f"Status: {status}")

    def on_error(self, error):
        self.status_bar.showMessage(f"Error: {error}")

    def on_fps_updated(self, fps):
        self.fps_label.setText(f"FPS: {fps:.1f}")

    # ═══════════════════════════════════════════
    #  ZOOM CONTROLS (kept from original)
    # ═══════════════════════════════════════════

    def camera_apply_zoom(self, camera_id):
        if camera_id == "cam1":
            pixmap, zoom = self.cam1_pixmap, self.cam1_zoom
            image_label, zoom_btn = self.cam1_image_label, self.cam1_zoom_reset_btn
        else:
            pixmap, zoom = self.cam2_pixmap, self.cam2_zoom
            image_label, zoom_btn = self.cam2_image_label, self.cam2_zoom_reset_btn

        if pixmap and not pixmap.isNull():
            new_w = int(pixmap.width() * zoom)
            new_h = int(pixmap.height() * zoom)
            scaled = pixmap.scaled(new_w, new_h,
                                   Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
            image_label.setPixmap(scaled)
            image_label.setStyleSheet(
                "QLabel { background-color: #e9ecef; border: 1px solid #dee2e6; border-radius: 5px; }")
            image_label.resize(scaled.size())
            zoom_btn.setText(f"{int(zoom * 100)}%")

    def camera_zoom_in(self, camera_id):
        if camera_id == "cam1" and self.cam1_pixmap:
            self.cam1_zoom = min(self.cam1_zoom + 0.25, 5.0)
        elif camera_id == "cam2" and self.cam2_pixmap:
            self.cam2_zoom = min(self.cam2_zoom + 0.25, 5.0)
        self.camera_apply_zoom(camera_id)

    def camera_zoom_out(self, camera_id):
        if camera_id == "cam1" and self.cam1_pixmap:
            self.cam1_zoom = max(self.cam1_zoom - 0.25, 0.25)
        elif camera_id == "cam2" and self.cam2_pixmap:
            self.cam2_zoom = max(self.cam2_zoom - 0.25, 0.25)
        self.camera_apply_zoom(camera_id)

    def camera_zoom_reset(self, camera_id):
        if camera_id == "cam1" and self.cam1_pixmap:
            self.cam1_zoom = 0.25
        elif camera_id == "cam2" and self.cam2_pixmap:
            self.cam2_zoom = 0.25
        self.camera_apply_zoom(camera_id)

    def camera_show_fullscreen(self, camera_id):
        pixmap = self.cam1_pixmap if camera_id == "cam1" else self.cam2_pixmap
        if pixmap and not pixmap.isNull():
            dialog = FullscreenImageDialog(pixmap, camera_id, self)
            dialog.exec()

    # ═══════════════════════════════════════════
    #  KEYBOARD & CLOSE
    # ═══════════════════════════════════════════

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space and self.trigger_btn.isVisible():
            self.on_trigger()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        if self._realtime_running:
            self.inspection_controller.stop_realtime(0)
        self.camera_manager.close_all()
        self.save_ui_state()
        event.accept()


class FullscreenImageDialog(QDialog):
    """Fullscreen dialog for displaying image"""

    def __init__(self, pixmap, title, parent=None):
        super().__init__(parent)
        self.pixmap = pixmap
        self.zoom_level = 1.0
        self.dragging = False
        self.last_pos = None

        self.setWindowTitle(f"Full Screen - {title}")
        self.setModal(True)
        self.showMaximized()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.addStretch()

        zoom_out_btn = QPushButton("-")
        zoom_out_btn.setMaximumWidth(40)
        zoom_out_btn.clicked.connect(self.zoom_out)
        toolbar.addWidget(zoom_out_btn)

        self.zoom_label = QPushButton("100%")
        self.zoom_label.setMaximumWidth(60)
        self.zoom_label.clicked.connect(self.zoom_reset)
        toolbar.addWidget(self.zoom_label)

        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setMaximumWidth(40)
        zoom_in_btn.clicked.connect(self.zoom_in)
        toolbar.addWidget(zoom_in_btn)

        close_btn = QPushButton("Close")
        close_btn.setMaximumWidth(60)
        close_btn.clicked.connect(self.close)
        toolbar.addWidget(close_btn)

        layout.addLayout(toolbar)

        # Image
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setStyleSheet("QScrollArea { background-color: #2b2b2b; border: none; }")

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("QLabel { background-color: #2b2b2b; }")
        self.image_label.setScaledContents(False)

        self.scroll_area.setWidget(self.image_label)
        layout.addWidget(self.scroll_area)

        self.apply_zoom()

        self.setStyleSheet("""
            QDialog { background-color: #2b2b2b; }
            QPushButton {
                background-color: #444; color: white; border: none;
                border-radius: 3px; padding: 5px 10px;
            }
            QPushButton:hover { background-color: #555; }
        """)

    def apply_zoom(self):
        if self.pixmap and not self.pixmap.isNull():
            new_w = int(self.pixmap.width() * self.zoom_level)
            new_h = int(self.pixmap.height() * self.zoom_level)
            scaled = self.pixmap.scaled(new_w, new_h,
                                        Qt.AspectRatioMode.KeepAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation)
            self.image_label.setPixmap(scaled)
            self.image_label.resize(scaled.size())
            self.zoom_label.setText(f"{int(self.zoom_level * 100)}%")

    def zoom_in(self):
        self.zoom_level = min(self.zoom_level + 0.25, 10.0)
        self.apply_zoom()

    def zoom_out(self):
        self.zoom_level = max(self.zoom_level - 0.25, 0.1)
        self.apply_zoom()

    def zoom_reset(self):
        self.zoom_level = 1.0
        self.apply_zoom()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        elif event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.zoom_in()
        elif event.key() == Qt.Key.Key_Minus:
            self.zoom_out()
        elif event.key() == Qt.Key.Key_0:
            self.zoom_reset()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.last_pos = event.pos()
            self.scroll_area.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self.dragging and self.last_pos:
            delta = event.pos() - self.last_pos
            self.last_pos = event.pos()
            h_bar = self.scroll_area.horizontalScrollBar()
            v_bar = self.scroll_area.verticalScrollBar()
            h_bar.setValue(h_bar.value() - delta.x())
            v_bar.setValue(v_bar.value() - delta.y())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.scroll_area.viewport().setCursor(Qt.CursorShape.ArrowCursor)


def main():
    app = QApplication(sys.argv)
    window = InspectionGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
