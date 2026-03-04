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
        QRadioButton, QSlider, QFileDialog, QSplitter, QCheckBox
    )
    from PyQt6.QtCore import Qt, QTimer, QSize
    from PyQt6.QtGui import QFont, QColor, QPixmap, QPainter, QPen, QImage
    print("Using PyQt6")
except ImportError:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QComboBox, QLabel, QLineEdit, QDialog, QDialogButtonBox,
        QMessageBox, QGroupBox, QGridLayout, QStatusBar, QScrollArea, QTabWidget,
        QRadioButton, QSlider, QFileDialog, QSplitter, QCheckBox
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
from anomaly_engine import AnomalyEngine

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
        if self.anomaly_radio.isChecked():
            mode = "anomaly"
        product_id = self.product_combo.currentData()
        camera_mode = self.camera_mode_combo.currentData() or "single"
        self.config["ui_state"] = {
            "last_product_id": product_id,
            "cam1_zoom": self.cam1_zoom,
            "cam2_zoom": self.cam2_zoom,
            "camera_mode": camera_mode
        }
        self.config["inspection"]["mode"] = mode
        self.save_config()

    def load_ui_state(self):
        ui = self.config.get("ui_state", {})
        mode = self.config.get("inspection", {}).get("mode", "capture")
        if mode == "realtime":
            self.realtime_radio.setChecked(True)
        elif mode == "anomaly":
            self.anomaly_radio.setChecked(True)
        else:
            self.capture_radio.setChecked(True)

        # Restore camera mode (Single/Multi)
        camera_mode = ui.get("camera_mode", "single")
        idx = self.camera_mode_combo.findData(camera_mode)
        if idx >= 0:
            self.camera_mode_combo.setCurrentIndex(idx)

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

        # Populate camera profile combos now that widget is ready
        self._populate_camera_combos()

        # Anomaly Training Tab
        self.anomaly_tab = self._create_anomaly_tab()
        self.tabs.addTab(self.anomaly_tab, "Anomaly Training")

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
        cam_layout = QGridLayout()

        # Cam 1 profile combo
        cam_layout.addWidget(QLabel("Cam 1:"), 0, 0)
        self.cam1_profile_combo = QComboBox()
        cam_layout.addWidget(self.cam1_profile_combo, 0, 1)

        # Cam 2 profile combo
        cam_layout.addWidget(QLabel("Cam 2:"), 1, 0)
        self.cam2_profile_combo = QComboBox()
        cam_layout.addWidget(self.cam2_profile_combo, 1, 1)

        # Manage profiles button
        self.open_profiles_btn = QPushButton("Camera Profiles...")
        self.open_profiles_btn.setStyleSheet(
            "QPushButton { background-color: #007bff; color: white; padding: 6px; }"
            "QPushButton:hover { background-color: #0056b3; }")
        self.open_profiles_btn.clicked.connect(self.on_open_camera_profiles)
        cam_layout.addWidget(self.open_profiles_btn, 2, 0, 1, 2)

        # Connect / Disconnect
        cam_btn_layout = QHBoxLayout()
        self.connect_cam_btn = QPushButton("Connect")
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
        cam_layout.addLayout(cam_btn_layout, 3, 0, 1, 2)

        self.cam_status_label = QLabel("Disconnected")
        self.cam_status_label.setStyleSheet(
            "QLabel { background-color: #dc3545; color: white; padding: 5px; "
            "border-radius: 3px; font-weight: bold; }")
        cam_layout.addWidget(self.cam_status_label, 4, 0, 1, 2)

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

        model_btn_row = QHBoxLayout()
        self.load_model_btn = QPushButton("Load Model")
        self.load_model_btn.setStyleSheet(
            "QPushButton { background-color: #007bff; color: white; padding: 6px; font-weight: bold; }"
            "QPushButton:hover { background-color: #0056b3; }")
        self.load_model_btn.clicked.connect(self.on_load_model)
        model_btn_row.addWidget(self.load_model_btn)

        self.gpu_info_btn = QPushButton("GPU Info")
        self.gpu_info_btn.setStyleSheet(
            "QPushButton { background-color: #6f42c1; color: white; padding: 6px; }"
            "QPushButton:hover { background-color: #5a32a3; }")
        self.gpu_info_btn.clicked.connect(self.on_show_gpu_info)
        model_btn_row.addWidget(self.gpu_info_btn)
        model_layout.addLayout(model_btn_row, 3, 0, 1, 2)

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
        self.anomaly_radio = QRadioButton("Anomaly")
        self.capture_radio.setChecked(True)
        self.capture_radio.toggled.connect(self.on_mode_changed)
        self.realtime_radio.toggled.connect(self.on_mode_changed)
        self.anomaly_radio.toggled.connect(self.on_mode_changed)
        mode_row.addWidget(self.capture_radio)
        mode_row.addWidget(self.realtime_radio)
        mode_row.addWidget(self.anomaly_radio)
        insp_layout.addLayout(mode_row)

        # Camera Mode (Single / Multi)
        cam_mode_row = QHBoxLayout()
        cam_mode_row.addWidget(QLabel("Camera:"))
        self.camera_mode_combo = QComboBox()
        self.camera_mode_combo.addItem("Single (Cam 1)", "single")
        self.camera_mode_combo.addItem("Multi (Cam 1+2)", "multi")
        self.camera_mode_combo.currentIndexChanged.connect(self.on_camera_mode_changed)
        cam_mode_row.addWidget(self.camera_mode_combo, 1)
        insp_layout.addLayout(cam_mode_row)

        # Detect FPS slider (Realtime mode) — wrapped in widget for show/hide
        self.detect_fps_widget = QWidget()
        detect_fps_row = QHBoxLayout(self.detect_fps_widget)
        detect_fps_row.setContentsMargins(0, 0, 0, 0)
        detect_fps_row.addWidget(QLabel("Detect FPS:"))
        self.detect_fps_slider = QSlider(Qt.Orientation.Horizontal)
        self.detect_fps_slider.setRange(1, 30)
        self.detect_fps_slider.setValue(30)
        self.detect_fps_slider.valueChanged.connect(self.on_detect_fps_changed)
        detect_fps_row.addWidget(self.detect_fps_slider)
        self.detect_fps_label = QLabel("30")
        self.detect_fps_label.setMinimumWidth(25)
        detect_fps_row.addWidget(self.detect_fps_label)
        insp_layout.addWidget(self.detect_fps_widget)

        # Anomaly threshold slider (Anomaly mode) — wrapped in widget
        self.anomaly_threshold_widget = QWidget()
        anomaly_thr_row = QHBoxLayout(self.anomaly_threshold_widget)
        anomaly_thr_row.setContentsMargins(0, 0, 0, 0)
        anomaly_thr_row.addWidget(QLabel("Threshold:"))
        self.anomaly_threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.anomaly_threshold_slider.setRange(5, 100)
        self.anomaly_threshold_slider.setValue(25)
        self.anomaly_threshold_slider.valueChanged.connect(self.on_anomaly_threshold_changed)
        anomaly_thr_row.addWidget(self.anomaly_threshold_slider)
        self.anomaly_threshold_label = QLabel("2.5")
        self.anomaly_threshold_label.setMinimumWidth(30)
        anomaly_thr_row.addWidget(self.anomaly_threshold_label)
        insp_layout.addWidget(self.anomaly_threshold_widget)

        # Anomaly status
        self.anomaly_status_label = QLabel("Anomaly: Not trained")
        self.anomaly_status_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        self.anomaly_status_label.setWordWrap(True)
        insp_layout.addWidget(self.anomaly_status_label)

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

        # Initial widget visibility (Capture mode is default)
        self.detect_fps_widget.setVisible(False)
        self.anomaly_threshold_widget.setVisible(False)
        self.anomaly_status_label.setVisible(False)

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
    #  ANOMALY TRAINING TAB
    # ═══════════════════════════════════════════

    def _create_anomaly_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        title = QLabel("Anomaly Detection — PatchCore Training")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        desc = QLabel(
            "เทรนด้วยภาพ 'ปกติ' (สมบูรณ์) 10-30 ภาพ\n"
            "ระบบจะเรียนรู้ว่า 'ปกติ' หน้าตาเป็นอย่างไร\n"
            "เมื่อตรวจสอบ จะแสดง heatmap บริเวณที่ผิดปกติ (Missing / Defect)")
        desc.setStyleSheet("color: #6c757d; font-size: 13px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        content = QHBoxLayout()

        # ─── Left: Training Controls ───
        left_group = QGroupBox("Training")
        left_layout = QVBoxLayout()

        # YOLO Crop option
        self.anomaly_yolo_crop_cb = QCheckBox("Use YOLO Crop (ทนตำแหน่งขยับ)")
        self.anomaly_yolo_crop_cb.setChecked(True)
        self.anomaly_yolo_crop_cb.setToolTip(
            "YOLO detect ก่อน → crop ชิ้นงาน → PatchCore ตรวจ anomaly บน crop\n"
            "ช่วยให้ไม่ไวต่อตำแหน่งที่เปลี่ยน\n"
            "พร้อม Per-class model: แยก bank ตาม YOLO class อัตโนมัติ")
        self.anomaly_yolo_crop_cb.stateChanged.connect(self.on_anomaly_yolo_crop_changed)
        left_layout.addWidget(self.anomaly_yolo_crop_cb)

        # Training Augmentation option
        self.anomaly_augmentation_cb = QCheckBox("Training Augmentation (ทนแสงเปลี่ยน)")
        self.anomaly_augmentation_cb.setChecked(True)
        self.anomaly_augmentation_cb.setToolTip(
            "เพิ่มภาพ augmented (ปรับแสง ±10%) ตอนเทรน\n"
            "ช่วยให้ทนต่อแสงเปลี่ยนในไลน์ผลิต")
        self.anomaly_augmentation_cb.stateChanged.connect(self.on_anomaly_augmentation_changed)
        left_layout.addWidget(self.anomaly_augmentation_cb)

        # Step 1: Capture normal images
        step1 = QLabel("Step 1: เก็บภาพ 'ปกติ'")
        step1.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        left_layout.addWidget(step1)

        cap_row = QHBoxLayout()
        self.anomaly_capture_btn = QPushButton("Capture")
        self.anomaly_capture_btn.setStyleSheet(
            "QPushButton { background-color: #28a745; color: white; padding: 8px; }"
            "QPushButton:hover { background-color: #218838; }")
        self.anomaly_capture_btn.clicked.connect(self.on_anomaly_capture_normal)
        cap_row.addWidget(self.anomaly_capture_btn)

        self.anomaly_load_folder_btn = QPushButton("Load from Folder")
        self.anomaly_load_folder_btn.clicked.connect(self.on_anomaly_load_folder)
        cap_row.addWidget(self.anomaly_load_folder_btn)
        left_layout.addLayout(cap_row)

        self.anomaly_train_count_label = QLabel("Normal images: 0")
        self.anomaly_train_count_label.setStyleSheet("font-weight: bold; color: #007bff;")
        left_layout.addWidget(self.anomaly_train_count_label)

        self.anomaly_clear_btn = QPushButton("Clear Training Images")
        self.anomaly_clear_btn.clicked.connect(self.on_anomaly_clear)
        left_layout.addWidget(self.anomaly_clear_btn)

        # Step 2: Train
        step2 = QLabel("Step 2: Train Model")
        step2.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        left_layout.addWidget(step2)

        self.anomaly_train_btn = QPushButton("Train PatchCore")
        self.anomaly_train_btn.setStyleSheet(
            "QPushButton { background-color: #007bff; color: white; padding: 10px; "
            "font-weight: bold; font-size: 14px; }"
            "QPushButton:hover { background-color: #0056b3; }")
        self.anomaly_train_btn.clicked.connect(self.on_anomaly_train)
        left_layout.addWidget(self.anomaly_train_btn)

        self.anomaly_train_status = QLabel("Not trained")
        self.anomaly_train_status.setWordWrap(True)
        self.anomaly_train_status.setStyleSheet("color: #6c757d;")
        left_layout.addWidget(self.anomaly_train_status)

        # Step 3: Save/Load
        step3 = QLabel("Step 3: Save / Load Model")
        step3.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        left_layout.addWidget(step3)

        save_row = QHBoxLayout()
        self.anomaly_save_btn = QPushButton("Save Model")
        self.anomaly_save_btn.clicked.connect(self.on_anomaly_save)
        save_row.addWidget(self.anomaly_save_btn)

        self.anomaly_load_btn = QPushButton("Load Model")
        self.anomaly_load_btn.clicked.connect(self.on_anomaly_load)
        save_row.addWidget(self.anomaly_load_btn)
        left_layout.addLayout(save_row)

        # Step 4: Validate Model
        step4 = QLabel("Step 4: Validate Model")
        step4.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        left_layout.addWidget(step4)

        validate_row = QHBoxLayout()
        self.anomaly_validate_good_btn = QPushButton("Test Good")
        self.anomaly_validate_good_btn.setStyleSheet(
            "QPushButton { background-color: #28a745; color: white; padding: 6px; }"
            "QPushButton:hover { background-color: #218838; }")
        self.anomaly_validate_good_btn.setToolTip("ทดสอบด้วยภาพปกติ (ไม่ควรตรวจพบ anomaly)")
        self.anomaly_validate_good_btn.clicked.connect(self.on_anomaly_validate_good)
        validate_row.addWidget(self.anomaly_validate_good_btn)

        self.anomaly_validate_bad_btn = QPushButton("Test Bad")
        self.anomaly_validate_bad_btn.setStyleSheet(
            "QPushButton { background-color: #dc3545; color: white; padding: 6px; }"
            "QPushButton:hover { background-color: #c82333; }")
        self.anomaly_validate_bad_btn.setToolTip("ทดสอบด้วยภาพผิดปกติ (ควรตรวจพบ anomaly)")
        self.anomaly_validate_bad_btn.clicked.connect(self.on_anomaly_validate_bad)
        validate_row.addWidget(self.anomaly_validate_bad_btn)
        left_layout.addLayout(validate_row)

        self.anomaly_validate_result = QLabel("")
        self.anomaly_validate_result.setWordWrap(True)
        self.anomaly_validate_result.setStyleSheet(
            "color: #495057; font-size: 11px; background-color: #f8f9fa; "
            "padding: 4px; border-radius: 3px;")
        left_layout.addWidget(self.anomaly_validate_result)

        left_layout.addStretch()
        left_group.setLayout(left_layout)
        content.addWidget(left_group)

        # ─── Right: Camera Preview ───
        right_group = QGroupBox("Camera Preview")
        right_layout = QVBoxLayout()

        # Preview controls
        preview_row = QHBoxLayout()
        self.anomaly_preview_btn = QPushButton("Start Preview")
        self.anomaly_preview_btn.setStyleSheet(
            "QPushButton { background-color: #17a2b8; color: white; padding: 8px; "
            "font-weight: bold; }"
            "QPushButton:hover { background-color: #138496; }")
        self.anomaly_preview_btn.clicked.connect(self.on_anomaly_preview_toggle)
        preview_row.addWidget(self.anomaly_preview_btn)
        right_layout.addLayout(preview_row)

        # Preview image
        self.anomaly_preview_label = QLabel("Camera not started\nClick 'Start Preview' to begin")
        self.anomaly_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.anomaly_preview_label.setMinimumSize(480, 360)
        self.anomaly_preview_label.setStyleSheet(
            "QLabel { background-color: #1a1a2e; color: #6c757d; "
            "border: 2px solid #333; border-radius: 5px; font-size: 14px; }")
        right_layout.addWidget(self.anomaly_preview_label, 1)

        # Tips
        tips = QLabel(
            "Tips: ใช้ภาพปกติ 10-30 ภาพ | ถ่ายจากมุมเดียวกัน แสงคล้ายกัน | "
            "ปรับ Threshold ตาม sensitivity ที่ต้องการ")
        tips.setStyleSheet("color: #6c757d; font-size: 11px;")
        tips.setWordWrap(True)
        right_layout.addWidget(tips)

        right_group.setLayout(right_layout)
        content.addWidget(right_group, 1)  # stretch=1 ให้ preview กินพื้นที่มากกว่า

        layout.addLayout(content)

        # Preview state
        self._anomaly_preview_active = False
        self._anomaly_latest_frame = None

        return widget

    # ═══════════════════════════════════════════
    #  ANOMALY HANDLERS
    # ═══════════════════════════════════════════

    def _ensure_anomaly_initialized(self):
        """Initialize anomaly engine if not done"""
        anomaly = self.inspection_controller.anomaly
        if not anomaly.is_initialized():
            device = self.detection_engine.device if self.detection_engine.device else "auto"
            anomaly.initialize(device)
            anomaly.training_progress.connect(self._on_anomaly_progress)
        return anomaly

    def _on_anomaly_progress(self, msg):
        self.anomaly_train_status.setText(msg)
        self.anomaly_status_label.setText(f"Anomaly: {msg}")
        self.status_bar.showMessage(f"Anomaly: {msg}")

    def on_anomaly_yolo_crop_changed(self, state):
        anomaly = self._ensure_anomaly_initialized()
        anomaly.set_yolo_crop(bool(state))

    def on_anomaly_augmentation_changed(self, state):
        anomaly = self._ensure_anomaly_initialized()
        anomaly.set_augmentation(bool(state))

    # ─── Validation ───

    def on_anomaly_validate_good(self):
        """Validate model with known-good (normal) images"""
        self._anomaly_validate(is_good=True)

    def on_anomaly_validate_bad(self):
        """Validate model with known-bad (anomaly) images"""
        self._anomaly_validate(is_good=False)

    def _anomaly_validate(self, is_good: bool):
        anomaly = self._ensure_anomaly_initialized()
        if not anomaly.is_trained:
            QMessageBox.warning(self, "Warning",
                "Please train the model first.")
            return

        label = "Normal (Good)" if is_good else "Abnormal (Bad)"
        files, _ = QFileDialog.getOpenFileNames(
            self, f"Select {label} Images", "",
            "Images (*.jpg *.jpeg *.png *.bmp *.webp *.tiff *.tif);;All Files (*)")
        if not files:
            return

        self.anomaly_validate_result.setText("Validating...")
        QApplication.processEvents()

        images = []
        for f in files:
            img = cv2.imread(f)
            if img is not None:
                images.append(img)

        if not images:
            self.anomaly_validate_result.setText("No valid images loaded")
            return

        if is_good:
            result = anomaly.validate(normal_images=images)
        else:
            result = anomaly.validate(abnormal_images=images)

        lines = []
        if is_good:
            total = result["normal_total"]
            correct = result["normal_correct"]
            scores = result["normal_scores"]
            lines.append(f"Good: {correct}/{total} classified as NORMAL")
            if total > 0:
                fp_rate = (total - correct) / total * 100
                lines.append(f"False Positive Rate: {fp_rate:.1f}%")
            if scores:
                lines.append(f"Score: min={min(scores):.2f} max={max(scores):.2f} "
                             f"avg={sum(scores)/len(scores):.2f}")
        else:
            total = result["abnormal_total"]
            correct = result["abnormal_correct"]
            scores = result["abnormal_scores"]
            lines.append(f"Bad: {correct}/{total} classified as ANOMALY")
            if total > 0:
                fn_rate = (total - correct) / total * 100
                lines.append(f"False Negative Rate: {fn_rate:.1f}%")
            if scores:
                lines.append(f"Score: min={min(scores):.2f} max={max(scores):.2f} "
                             f"avg={sum(scores)/len(scores):.2f}")

        self.anomaly_validate_result.setText("\n".join(lines))

    # ─── Camera Preview for Anomaly Training ───

    def on_anomaly_preview_toggle(self):
        """Start/Stop camera preview ใน Anomaly Training tab"""
        if self._anomaly_preview_active:
            self._anomaly_preview_stop()
        else:
            self._anomaly_preview_start()

    def _anomaly_preview_start(self):
        """Start camera stream for anomaly preview"""
        if not self.camera_manager.is_opened(0):
            QMessageBox.warning(self, "Error",
                "Camera not connected.\nPlease open camera in Camera Settings first.")
            return

        # Stop realtime if running (avoid conflicts)
        if self._realtime_running:
            self.on_start_stop_realtime()

        self._anomaly_preview_active = True
        self._anomaly_latest_frame = None
        self.anomaly_preview_btn.setText("Stop Preview")
        self.anomaly_preview_btn.setStyleSheet(
            "QPushButton { background-color: #dc3545; color: white; padding: 8px; "
            "font-weight: bold; }"
            "QPushButton:hover { background-color: #c82333; }")

        # Connect camera frames to our preview handler
        self.camera_manager.frame_captured.connect(self._on_anomaly_preview_frame)
        self.camera_manager.start_stream(0, 30)
        self.status_bar.showMessage("Anomaly Training: Camera preview started")

    def _anomaly_preview_stop(self):
        """Stop camera preview"""
        self._anomaly_preview_active = False

        try:
            self.camera_manager.frame_captured.disconnect(self._on_anomaly_preview_frame)
        except (TypeError, RuntimeError):
            pass

        self.camera_manager.stop_stream(0)

        self.anomaly_preview_btn.setText("Start Preview")
        self.anomaly_preview_btn.setStyleSheet(
            "QPushButton { background-color: #17a2b8; color: white; padding: 8px; "
            "font-weight: bold; }"
            "QPushButton:hover { background-color: #138496; }")
        self.status_bar.showMessage("Anomaly Training: Camera preview stopped")

    def _on_anomaly_preview_frame(self, camera_id: int, frame):
        """Display camera frame in anomaly preview label"""
        if not self._anomaly_preview_active or camera_id != 0:
            return

        self._anomaly_latest_frame = frame.copy()

        # Convert and display in preview label
        pixmap = numpy_to_qpixmap(frame)
        label_size = self.anomaly_preview_label.size()
        scaled = pixmap.scaled(label_size, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        self.anomaly_preview_label.setPixmap(scaled)

    def on_anomaly_capture_normal(self):
        """Capture ภาพปกติจากกล้อง"""
        anomaly = self._ensure_anomaly_initialized()

        # Use latest preview frame if preview is active, otherwise single capture
        if self._anomaly_preview_active and self._anomaly_latest_frame is not None:
            frame = self._anomaly_latest_frame.copy()
        else:
            frame = self.camera_manager.capture_frame(0)

        if frame is None:
            QMessageBox.warning(self, "Error",
                "Cannot capture from camera.\n"
                "Please click 'Start Preview' first or connect camera.")
            return

        # If YOLO crop enabled and model loaded, crop first + per-class tracking
        if anomaly.use_yolo_crop and self.detection_engine.is_model_loaded():
            detection = self.detection_engine.detect(frame)
            for det in detection["detections"]:
                bbox = det["bbox"]
                pad = anomaly.crop_padding
                h, w = frame.shape[:2]
                x1 = max(0, bbox["x"] - pad)
                y1 = max(0, bbox["y"] - pad)
                x2 = min(w, bbox["x"] + bbox["w"] + pad)
                y2 = min(h, bbox["y"] + bbox["h"] + pad)
                crop = frame[y1:y2, x1:x2]
                if crop.size > 0:
                    cls_name = det.get("class_name", "")
                    count = anomaly.add_normal_image(crop, class_name=cls_name)
                    self.anomaly_train_count_label.setText(f"Normal images: {count}")
            if not detection["detections"]:
                QMessageBox.warning(self, "Warning",
                    "YOLO did not detect any objects.\n"
                    "Try without YOLO crop or load YOLO model first.")
        else:
            count = anomaly.add_normal_image(frame)
            self.anomaly_train_count_label.setText(f"Normal images: {count}")

        # Flash preview border green to indicate capture
        self.anomaly_preview_label.setStyleSheet(
            "QLabel { background-color: #1a1a2e; color: #6c757d; "
            "border: 3px solid #28a745; border-radius: 5px; }")
        QTimer.singleShot(300, lambda: self.anomaly_preview_label.setStyleSheet(
            "QLabel { background-color: #1a1a2e; color: #6c757d; "
            "border: 2px solid #333; border-radius: 5px; }"))

        self.status_bar.showMessage(
            f"Captured normal image (total: {anomaly.get_training_count()})")

    def on_anomaly_load_folder(self):
        """Load ภาพปกติจาก folder หรือเลือกไฟล์ภาพ"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Normal Images",
            "",
            "Images (*.jpg *.jpeg *.png *.bmp *.webp *.tiff *.tif);;All Files (*)")
        if not files:
            return

        anomaly = self._ensure_anomaly_initialized()
        use_crop = anomaly.use_yolo_crop and self.detection_engine.is_model_loaded()
        count = 0
        crop_count = 0

        for file_path in files:
            image = cv2.imread(file_path)
            if image is None:
                continue

            if use_crop:
                # YOLO crop ก่อน → เทรน PatchCore บน crop (เหมือนตอน inference)
                detection = self.detection_engine.detect(image)
                for det in detection["detections"]:
                    bbox = det["bbox"]
                    pad = anomaly.crop_padding
                    h, w = image.shape[:2]
                    x1 = max(0, bbox["x"] - pad)
                    y1 = max(0, bbox["y"] - pad)
                    x2 = min(w, bbox["x"] + bbox["w"] + pad)
                    y2 = min(h, bbox["y"] + bbox["h"] + pad)
                    crop = image[y1:y2, x1:x2]
                    if crop.size > 0:
                        cls_name = det.get("class_name", "")
                        anomaly.add_normal_image(crop, class_name=cls_name)
                        crop_count += 1
            else:
                anomaly.add_normal_image(image)

            count += 1

        self.anomaly_train_count_label.setText(
            f"Normal images: {anomaly.get_training_count()}")
        if use_crop:
            self.status_bar.showMessage(
                f"Loaded {count} images → {crop_count} YOLO crops added")
        else:
            self.status_bar.showMessage(f"Loaded {count} images")

    def on_anomaly_clear(self):
        anomaly = self._ensure_anomaly_initialized()
        anomaly.reset_training()
        self.anomaly_train_count_label.setText("Normal images: 0")
        self.anomaly_train_status.setText("Not trained")
        self.anomaly_status_label.setText("Anomaly: Not trained")
        self.anomaly_validate_result.setText("")

    def on_anomaly_train(self):
        """Train PatchCore model"""
        anomaly = self._ensure_anomaly_initialized()
        if anomaly.get_training_count() == 0:
            QMessageBox.warning(self, "Warning",
                "No normal images added.\nPlease capture or load normal images first.")
            return

        self.anomaly_train_status.setText("Training...")
        self.anomaly_train_btn.setEnabled(False)
        QApplication.processEvents()

        success = anomaly.train()
        self.anomaly_train_btn.setEnabled(True)

        if success:
            # Update threshold slider to match auto-calibrated value
            thr_int = int(anomaly.threshold * 10)
            self.anomaly_threshold_slider.setValue(thr_int)
            self.anomaly_threshold_label.setText(f"{anomaly.threshold:.1f}")
            self.anomaly_status_label.setText(
                f"Anomaly: Trained OK | Threshold: {anomaly.threshold:.1f}")

    def on_anomaly_save(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Anomaly Model", "anomaly_model.pkl",
            "Pickle Files (*.pkl);;All Files (*)")
        if path:
            anomaly = self._ensure_anomaly_initialized()
            anomaly.save_model(path)

    def on_anomaly_load(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Anomaly Model", "",
            "Pickle Files (*.pkl);;All Files (*)")
        if path:
            anomaly = self._ensure_anomaly_initialized()
            if anomaly.load_model(path):
                self.anomaly_train_count_label.setText(
                    f"Normal images: {anomaly.get_training_count()}")
                # Sync UI with loaded model settings
                thr_int = int(anomaly.threshold * 10)
                self.anomaly_threshold_slider.setValue(thr_int)
                self.anomaly_threshold_label.setText(f"{anomaly.threshold:.1f}")
                self.anomaly_augmentation_cb.setChecked(anomaly.use_augmentation)
                self.anomaly_yolo_crop_cb.setChecked(anomaly.use_yolo_crop)
                # Show per-class info
                per_cls = anomaly.get_per_class_info()
                if per_cls:
                    cls_str = ", ".join(f"{k}" for k in per_cls)
                    self.anomaly_status_label.setText(
                        f"Anomaly: Model loaded | Per-class: [{cls_str}]")
                else:
                    self.anomaly_status_label.setText("Anomaly: Model loaded")

    def on_anomaly_threshold_changed(self, value):
        thr = value / 10.0
        self.anomaly_threshold_label.setText(f"{thr:.1f}")
        self.inspection_controller.anomaly.set_threshold(thr)

    # ═══════════════════════════════════════════
    #  CAMERA HANDLERS
    # ═══════════════════════════════════════════

    def _populate_camera_combos(self):
        """Populate Cam 1 / Cam 2 combo boxes from camera_profiles.json"""
        profiles = self.camera_settings_widget.get_all_profiles()

        for combo in [self.cam1_profile_combo, self.cam2_profile_combo]:
            current_text = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("-- None --")
            for name in profiles.keys():
                combo.addItem(name)
            # Restore previous selection if possible
            idx = combo.findText(current_text)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            combo.blockSignals(False)

    def on_camera_config_changed(self):
        """เมื่อ Camera Settings เปลี่ยน — refresh UI"""
        self._populate_camera_combos()
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
        self._populate_camera_combos()
        # Switch back to Live tab
        self.tabs.setCurrentIndex(0)

    def _get_profile_by_name(self, profile_name: str):
        """Get profile data dict by name from camera_profiles.json"""
        profiles = self.camera_settings_widget.get_all_profiles()
        profile_data = profiles.get(profile_name)
        if profile_data:
            return {"name": profile_name, **profile_data}
        return None

    def on_connect_camera(self):
        """Connect cameras using Cam 1 / Cam 2 combo selections"""
        cam1_name = self.cam1_profile_combo.currentText()
        cam2_name = self.cam2_profile_combo.currentText()

        has_cam1 = cam1_name and cam1_name != "-- None --"
        has_cam2 = cam2_name and cam2_name != "-- None --"

        if not has_cam1 and not has_cam2:
            QMessageBox.information(
                self, "No Profile Selected",
                "Please select a camera profile for Cam 1 or Cam 2.\n"
                "Use 'Camera Profiles...' to add profiles.")
            return

        # Check for same source conflict
        if has_cam1 and has_cam2:
            profile1 = self._get_profile_by_name(cam1_name)
            profile2 = self._get_profile_by_name(cam2_name)
            if (profile1 and profile2
                    and profile1.get("source") == profile2.get("source")
                    and profile1.get("type") == profile2.get("type")):
                QMessageBox.warning(self, "Source Conflict",
                    f"Cam 1 and Cam 2 ใช้ source เดียวกัน "
                    f"({profile1.get('type')} : {profile1.get('source')})\n"
                    f"กรุณาเลือก camera source ที่ต่างกัน\n\n"
                    f"Tip: ไปที่ 'Camera Profiles...' เพื่อสร้าง profile "
                    f"สำหรับกล้องตัวที่ 2 (source index ต่างกัน)")
                return

        errors = []
        connected = False

        if has_cam1:
            profile = self._get_profile_by_name(cam1_name)
            if profile:
                self.status_bar.showMessage(f"Connecting Cam 1: {cam1_name}...")
                QApplication.processEvents()
                if self.camera_manager.connect_from_profile(0, profile):
                    connected = True
                    print(f"Cam 1 connected: {cam1_name} (source={profile.get('source')})")
                else:
                    errors.append(f"Cam 1: {cam1_name} (source={profile.get('source')})")

        # Delay between camera connections to avoid USB bus contention
        if has_cam1 and has_cam2:
            import time
            time.sleep(0.5)
            QApplication.processEvents()

        if has_cam2:
            profile = self._get_profile_by_name(cam2_name)
            if profile:
                self.status_bar.showMessage(f"Connecting Cam 2: {cam2_name}...")
                QApplication.processEvents()
                if self.camera_manager.connect_from_profile(1, profile):
                    connected = True
                    print(f"Cam 2 connected: {cam2_name} (source={profile.get('source')})")
                else:
                    errors.append(f"Cam 2: {cam2_name} (source={profile.get('source')})")

        if errors:
            error_msg = "เชื่อมต่อไม่สำเร็จ:\n" + "\n".join(errors)
            error_msg += "\n\nสาเหตุที่เป็นไปได้:\n"
            error_msg += "• กล้องถูกใช้งานโดยโปรแกรมอื่น\n"
            error_msg += "• Source index ไม่ตรงกับกล้องจริง\n"
            error_msg += "• Linux: /dev/video0 กับ /dev/video1 อาจเป็นกล้องตัวเดียวกัน\n"
            error_msg += "\nลองตรวจสอบ: Camera Profiles... → ตั้ง source ให้ตรง"
            if connected:
                self.status_bar.showMessage(
                    f"Connected partially — {', '.join(errors)} failed")
            QMessageBox.warning(self, "Connection Error", error_msg)
        elif not connected:
            self.status_bar.showMessage("Failed to connect cameras")

    def on_disconnect_camera(self):
        if self._realtime_running:
            self.on_start_stop_realtime()  # Stop realtime first
        self.camera_manager.close_all()

    def on_camera_opened(self, camera_id):
        # Build status text showing all connected cameras
        connected_ids = list(self.camera_manager.cameras.keys())
        cam_names = [f"Cam {cid+1}" for cid in connected_ids]
        self.cam_status_label.setText(f"Connected: {', '.join(cam_names)}")
        self.cam_status_label.setStyleSheet(
            "QLabel { background-color: #28a745; color: white; padding: 5px; "
            "border-radius: 3px; font-weight: bold; }")
        self.connect_cam_btn.setEnabled(False)
        self.disconnect_cam_btn.setEnabled(True)
        self.trigger_btn.setEnabled(True)
        self.status_bar.showMessage(f"Camera {camera_id} (Cam {camera_id+1}) connected")

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

    def on_show_gpu_info(self):
        """แสดงข้อมูล GPU / CUDA — เช็คว่าใช้ GPU จริงหรือไม่"""
        gpu_info = DetectionEngine.get_gpu_info()

        lines = []
        lines.append(f"PyTorch: {gpu_info.get('torch_version', 'N/A')}")
        lines.append(f"CUDA: {gpu_info.get('cuda_version', 'N/A')}")

        if gpu_info.get("gpu_available"):
            lines.append(f"GPU: {gpu_info.get('gpu_name', 'Unknown')}")
            total = gpu_info.get("gpu_memory_total_mb", 0)
            used = gpu_info.get("gpu_memory_used_mb", 0)
            free = gpu_info.get("gpu_memory_free_mb", 0)
            lines.append(f"VRAM Total: {total} MB")
            lines.append(f"VRAM Used: {used} MB")
            lines.append(f"VRAM Free: {free} MB")
        else:
            lines.append("GPU: Not available (using CPU)")

        # Current engine device
        if self.detection_engine.is_model_loaded():
            dev = self.detection_engine.device
            if dev in ("0", "cuda"):
                lines.append(f"\nModel running on: GPU ({dev})")
            else:
                lines.append(f"\nModel running on: {dev.upper()}")
        else:
            lines.append("\nModel not loaded")

        if gpu_info.get("error"):
            lines.append(f"\nError: {gpu_info['error']}")

        QMessageBox.information(self, "GPU Information", "\n".join(lines))

    # ═══════════════════════════════════════════
    #  MODE & PRODUCT HANDLERS
    # ═══════════════════════════════════════════

    def on_detect_fps_changed(self, value):
        self.detect_fps_label.setText(str(value))
        self.inspection_controller.set_inspect_fps(value)

    def on_mode_changed(self):
        is_capture = self.capture_radio.isChecked()
        is_realtime = self.realtime_radio.isChecked()
        is_anomaly = self.anomaly_radio.isChecked()

        # Capture/Anomaly → show TRIGGER + Load File
        self.trigger_btn.setVisible(is_capture or is_anomaly)
        self.load_file_btn.setVisible(is_capture or is_anomaly)

        # Realtime → show START/STOP + FPS
        self.start_stop_btn.setVisible(is_realtime)
        self.fps_label.setVisible(is_realtime)
        self.detect_fps_widget.setVisible(is_realtime)

        # Anomaly → show threshold + status
        self.anomaly_threshold_widget.setVisible(is_anomaly)
        self.anomaly_status_label.setVisible(is_anomaly)

        if is_capture:
            self.inspection_controller.set_mode("capture")
        elif is_realtime:
            self.inspection_controller.set_mode("realtime")
        elif is_anomaly:
            self.inspection_controller.set_mode("anomaly")

        self.save_ui_state()

    def on_camera_mode_changed(self):
        cam_mode = self.camera_mode_combo.currentData()
        print(f"Camera mode: {cam_mode}")
        self.save_ui_state()

    def is_multi_camera(self) -> bool:
        """ตรวจสอบว่าเลือกโหมด Multi camera หรือไม่"""
        return self.camera_mode_combo.currentData() == "multi"

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
        is_anomaly = self.anomaly_radio.isChecked()

        if is_anomaly:
            # Anomaly mode
            if not self.inspection_controller.anomaly.is_trained:
                QMessageBox.warning(self, "Warning",
                    "Anomaly model not trained.\n"
                    "Go to 'Anomaly Training' tab to train first.")
                return
        else:
            # Capture mode (YOLO)
            if not self.detection_engine.is_model_loaded():
                QMessageBox.warning(self, "Warning", "Please load a YOLO model first")
                return

        self.trigger_btn.setText("Inspecting...")
        self.trigger_btn.setEnabled(False)
        QApplication.processEvents()

        # Cam 1 (always)
        if is_anomaly:
            self.inspection_controller.trigger_anomaly(0)
        else:
            self.inspection_controller.trigger_capture(0)

        # Cam 2 (Multi mode only)
        if self.is_multi_camera() and self.camera_manager.is_opened(1):
            if is_anomaly:
                self.inspection_controller.trigger_anomaly(1)
            else:
                self.inspection_controller.trigger_capture(1)

        self.trigger_btn.setText("TRIGGER")
        self.trigger_btn.setEnabled(True)

    def on_load_image_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp);;All Files (*)")
        if not file_path:
            return

        is_anomaly = self.anomaly_radio.isChecked()

        if is_anomaly:
            if not self.inspection_controller.anomaly.is_trained:
                QMessageBox.warning(self, "Warning", "Anomaly model not trained.")
                return
        else:
            if not self.detection_engine.is_model_loaded():
                QMessageBox.warning(self, "Warning", "Please load a YOLO model first")
                return

        self.trigger_btn.setText("Inspecting...")
        self.trigger_btn.setEnabled(False)
        QApplication.processEvents()

        if is_anomaly:
            self.inspection_controller.trigger_anomaly_from_file(file_path)
        else:
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

            multi = self.is_multi_camera()
            if multi and not self.camera_manager.is_opened(1):
                QMessageBox.warning(self, "Warning",
                    "Multi mode: Camera 2 not connected.\n"
                    "กรุณาเชื่อมต่อกล้องตัวที่ 2 หรือเปลี่ยนเป็น Single mode")
                return

            # Stop anomaly preview if running (avoid conflicts)
            if self._anomaly_preview_active:
                self._anomaly_preview_stop()

            self._realtime_running = True
            self.start_stop_btn.setText("STOP")
            self.start_stop_btn.setStyleSheet(
                "QPushButton { background-color: #dc3545; color: white; border-radius: 5px; }"
                "QPushButton:hover { background-color: #c82333; }")
            self.trigger_btn.setEnabled(False)

            self.inspection_controller.start_realtime(0)

            # Multi mode: start camera 2 stream too
            if multi:
                self.inspection_controller.start_realtime_cam2(1)
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

            # Multi mode: stop camera 2 stream too
            if self.is_multi_camera():
                self.inspection_controller.stop_realtime_cam2(1)

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
        if self._anomaly_preview_active:
            self._anomaly_preview_stop()
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
