# DUAL MODE INSPECTION SYSTEM — Architecture Plan

## Overview

ปรับโครงสร้างจาก MVI GUI Trigger เป็นระบบตรวจสอบ Missing Parts แบบ Standalone
ตัด MVI + MQTT ออก → ใช้ Local Camera + Local YOLOv8 แทน
รองรับ 2 โหมด: **Capture Mode** (ถ่ายทีละภาพ) และ **Realtime Mode** (วิเคราะห์ต่อเนื่อง)

---

## File Structure — เดิม vs ใหม่

```
เดิม (MVI)                          ใหม่ (DUAL MODE)
─────────────────────────           ─────────────────────────────────
main.py                      →     main.py (ปรับใหญ่)
mqtt_client.py                →     ลบ (ไม่ใช้แล้ว)
mvi_component_integration.py  →     ลบ (แทนที่ด้วย detection_engine.py)
component_definition.py       →     คงไว้ (ใช้จัดการ product/expected parts)
component_definition_widget.py →    คงไว้ (ใช้จัดการ component definitions)
history_manager.py            →     คงไว้ (ปรับเล็กน้อย)
history_widget.py             →     คงไว้ (ปรับเล็กน้อย)
config.json                   →     config.json (ปรับโครงสร้าง)
─                             →     camera_manager.py (ใหม่)
─                             →     detection_engine.py (ใหม่)
─                             →     inspection_controller.py (ใหม่)
```

---

## New Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         main.py (GUI Layer)                         │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │   Live Tab    │  │  History Tab  │  │  Component Definition Tab │  │
│  │              │  │              │  │                          │  │
│  │ ┌──────────┐ │  │ history_     │  │ component_definition_   │  │
│  │ │ Camera 1 │ │  │ widget.py    │  │ widget.py               │  │
│  │ │ Preview  │ │  │              │  │                          │  │
│  │ └──────────┘ │  └──────────────┘  └──────────────────────────┘  │
│  │ ┌──────────┐ │                                                   │
│  │ │ Camera 2 │ │                                                   │
│  │ │ Preview  │ │                                                   │
│  │ └──────────┘ │                                                   │
│  │              │                                                   │
│  │ [Mode: ○ Capture  ○ Realtime]                                   │
│  │ [TRIGGER] / [START/STOP]                                        │
│  │ [Status: PASS/FAIL]                                             │
│  └──────────────┘                                                   │
└────────┬──────────────────────────────────────────────┬─────────────┘
         │ Qt Signals                                   │
         ▼                                              ▼
┌─────────────────────────┐              ┌──────────────────────────┐
│ inspection_controller.py │              │  component_definition.py  │
│                         │              │  (คงเดิม)                 │
│ - orchestrate flow      │◄────────────►│  - product DB             │
│ - mode management       │  query       │  - expected parts DB      │
│ - result comparison     │  expected    │  - import/export          │
│ - PASS/FAIL logic       │  parts      └──────────────────────────┘
│                         │
└────────┬────────────────┘
         │ uses
    ┌────┴────┐
    ▼         ▼
┌────────────────┐   ┌──────────────────┐
│camera_manager.py│   │detection_engine.py│
│                │   │                  │
│- open/close   │   │- load YOLO model │
│- capture frame│   │- detect objects  │
│- stream frames│   │- draw annotations│
│- multi-camera │   │- parse results   │
└────────────────┘   └──────────────────┘

         │                    │
         ▼                    ▼
┌─────────────────────────────────────┐
│         history_manager.py           │
│         (ปรับเล็กน้อย)                │
│                                     │
│ - save inspection + image           │
│ - query history                     │
│ - export CSV                        │
└─────────────────────────────────────┘
```

---

## Step-by-Step Implementation Plan

### Step 1: camera_manager.py (สร้างใหม่)

จัดการกล้องทั้ง USB Camera, IP Camera (RTSP), และ image file

```python
class CameraManager(QObject):
    """จัดการกล้อง — รองรับหลายแหล่งภาพ"""

    # Signals
    frame_captured = Signal(int, np.ndarray)    # (camera_id, frame)
    camera_opened = Signal(int)                  # camera_id
    camera_closed = Signal(int)                  # camera_id
    camera_error = Signal(int, str)              # (camera_id, error_msg)

    def __init__(self):
        self.cameras: Dict[int, dict] = {}
        # {0: {"cap": cv2.VideoCapture, "source": 0, "is_open": True}, ...}

    # --- Camera Lifecycle ---
    def open_camera(self, camera_id: int, source: Union[int, str]) -> bool
        """เปิดกล้อง — source: 0,1 (USB) หรือ "rtsp://..." (IP Camera)"""

    def close_camera(self, camera_id: int)
        """ปิดกล้อง"""

    def close_all(self)
        """ปิดกล้องทั้งหมด"""

    # --- Capture Mode ---
    def capture_frame(self, camera_id: int) -> Optional[np.ndarray]
        """ถ่ายภาพ 1 เฟรม (สำหรับ Capture Mode)"""

    # --- Realtime Mode ---
    def start_stream(self, camera_id: int, fps: int = 30)
        """เริ่ม stream ต่อเนื่อง — emit frame_captured signal ทุกเฟรม"""
        # ใช้ QThread + QTimer ดึงเฟรมตาม fps
        # emit self.frame_captured.emit(camera_id, frame)

    def stop_stream(self, camera_id: int)
        """หยุด stream"""

    # --- Image File (สำหรับ testing/demo) ---
    def load_image_file(self, file_path: str) -> Optional[np.ndarray]
        """โหลดภาพจากไฟล์ (ใช้ทดสอบโดยไม่ต้องมีกล้อง)"""

    # --- Utilities ---
    def get_camera_info(self, camera_id: int) -> dict
        """ข้อมูลกล้อง: resolution, fps, source"""

    def list_available_cameras(self) -> List[int]
        """สแกนหากล้อง USB ที่เชื่อมต่ออยู่"""

    def set_resolution(self, camera_id: int, width: int, height: int)
        """ตั้งความละเอียด"""
```

**Camera Stream Worker (QThread):**

```python
class CameraStreamWorker(QThread):
    """Worker thread สำหรับดึงเฟรมจากกล้อง"""
    frame_ready = Signal(int, np.ndarray)  # (camera_id, frame)

    def __init__(self, camera_id, capture, target_fps=30):
        self.camera_id = camera_id
        self.capture = capture           # cv2.VideoCapture instance
        self.target_fps = target_fps
        self.running = False

    def run(self):
        self.running = True
        interval = 1.0 / self.target_fps
        while self.running:
            ret, frame = self.capture.read()
            if ret:
                self.frame_ready.emit(self.camera_id, frame)
            time.sleep(interval)

    def stop(self):
        self.running = False
        self.wait(2000)
```

---

### Step 2: detection_engine.py (สร้างใหม่)

แทนที่ MVI — run YOLOv8 ในเครื่อง

```python
class DetectionEngine(QObject):
    """YOLO Detection Engine — run locally"""

    # Signals
    detection_complete = Signal(dict)   # ผล detection
    model_loaded = Signal(str)          # model name
    model_error = Signal(str)           # error message

    def __init__(self):
        self.model = None
        self.model_path: str = ""
        self.device: str = "auto"       # "cpu", "cuda", "auto"
        self.confidence: float = 0.5
        self.iou_threshold: float = 0.45

    # --- Model Management ---
    def load_model(self, model_path: str, device: str = "auto") -> bool
        """โหลด YOLO model (.pt หรือ .onnx)"""
        # self.model = YOLO(model_path)
        # detect device: CUDA if available, else CPU

    def unload_model(self)
        """ปล่อย model จาก memory"""

    def is_model_loaded(self) -> bool

    def get_model_info(self) -> dict
        """ข้อมูล model: class names, input size, device"""

    def get_class_names(self) -> List[str]
        """รายชื่อ class ที่ model detect ได้"""

    # --- Detection ---
    def detect(self, frame: np.ndarray) -> dict
        """ตรวจจับวัตถุใน 1 เฟรม"""
        # Returns:
        # {
        #     "detections": [
        #         {
        #             "class_name": "pig",
        #             "confidence": 0.94,
        #             "bbox": {"x": 178, "y": 180, "w": 182, "h": 268},
        #             "center": (269, 314)
        #         }, ...
        #     ],
        #     "inference_time_ms": 15.2,
        #     "frame_size": (1280, 720)
        # }

    def detect_and_annotate(self, frame: np.ndarray) -> Tuple[dict, np.ndarray]
        """detect + วาด bounding box บนภาพ"""

    # --- Annotation ---
    def draw_detections(self, frame: np.ndarray, detections: List[dict],
                        missing: List[str] = None) -> np.ndarray
        """วาด bounding box — เขียว=เจอ, แดง=หาย"""

    # --- Settings ---
    def set_confidence(self, conf: float)
    def set_iou_threshold(self, iou: float)
    def set_device(self, device: str)
```

**Detection Result Format:**
```python
{
    "detections": [
        {
            "class_name": "pig",
            "confidence": 0.94,
            "bbox": {"x": 178, "y": 180, "w": 182, "h": 268},
            "center": (269, 314)
        },
        {
            "class_name": "monk",
            "confidence": 0.91,
            "bbox": {"x": 380, "y": 150, "w": 200, "h": 300},
            "center": (480, 300)
        }
    ],
    "inference_time_ms": 15.2,
    "frame_size": (1280, 720),
    "model_name": "best.pt",
    "device": "cuda:0"
}
```

---

### Step 3: inspection_controller.py (สร้างใหม่)

ควบคุม flow ทั้งหมด — เชื่อม Camera + Detection + Component Definition + History

```python
class InspectionController(QObject):
    """ควบคุม flow การตรวจสอบทั้ง Capture และ Realtime mode"""

    # Signals to GUI
    inspection_result = Signal(dict)        # ผลการตรวจสอบ
    frame_display = Signal(int, np.ndarray) # (camera_id, annotated_frame) สำหรับ live preview
    status_changed = Signal(str)            # "ready", "inspecting", "streaming"
    error_occurred = Signal(str)            # error message

    def __init__(self, camera_manager, detection_engine, component_manager, history_manager):
        self.camera = camera_manager
        self.detector = detection_engine
        self.components = component_manager      # ComponentDefinitionManager (เดิม)
        self.history = history_manager            # HistoryManager (เดิม)

        self.current_mode: str = "capture"       # "capture" or "realtime"
        self.current_product_id: Optional[int] = None
        self.expected_parts: Dict = {}           # loaded from component DB
        self.is_streaming: bool = False

    # --- Product/Expected Parts ---
    def set_product(self, product_id: int)
        """โหลด expected parts จาก component_definition DB"""
        # self.expected_parts = self.components.get_product_components(product_id)

    def get_expected_class_names(self) -> set
        """ชื่อ class ที่คาดหวัง"""

    # --- Mode Control ---
    def set_mode(self, mode: str)
        """เปลี่ยนโหมด: "capture" หรือ "realtime" """
        # หยุด stream ถ้ากำลัง run อยู่

    # --- Capture Mode ---
    def trigger_capture(self, camera_id: int = 0) -> dict
        """ถ่ายภาพ → detect → เปรียบเทียบ → บันทึก → คืนผล"""
        # 1. frame = self.camera.capture_frame(camera_id)
        # 2. detection = self.detector.detect(frame)
        # 3. result = self._compare_with_expected(detection)
        # 4. annotated = self.detector.draw_detections(frame, ...)
        # 5. self.history.save_inspection(result, annotated)
        # 6. self.inspection_result.emit(result)

    # --- Realtime Mode ---
    def start_realtime(self, camera_id: int = 0, inspect_fps: int = 10)
        """เริ่ม realtime — stream + detect ทุกเฟรม"""
        # 1. self.camera.start_stream(camera_id)
        # 2. connect camera.frame_captured → self._on_realtime_frame
        # 3. ใช้ frame skip เพื่อควบคุม inspect_fps

    def stop_realtime(self)
        """หยุด realtime"""

    def _on_realtime_frame(self, camera_id: int, frame: np.ndarray)
        """เรียกทุกเฟรมจากกล้อง — detect + แสดงผล"""
        # 1. detection = self.detector.detect(frame)
        # 2. result = self._compare_with_expected(detection)
        # 3. annotated = self.detector.draw_detections(frame, ...)
        # 4. self.frame_display.emit(camera_id, annotated)
        # 5. ถ้า FAIL → self.history.save_inspection(result)
        # 6. self.inspection_result.emit(result)

    # --- Comparison Logic (แทนที่ mvi_component_integration.py) ---
    def _compare_with_expected(self, detection_result: dict) -> dict
        """เปรียบเทียบ detection กับ expected parts"""
        # Returns:
        # {
        #     "status": "PASS" or "FAIL",
        #     "detected_parts": [...],
        #     "missing_parts": [...],
        #     "found_count": 2,
        #     "total_expected": 3,
        #     "timestamp": "...",
        #     "inference_time_ms": 15.2
        # }

    def _match_by_class_and_position(self, detections, expected) -> dict
        """จับคู่ detection กับ expected โดยใช้ class name + ตำแหน่ง"""
```

**Inspection Result Format:**
```python
{
    "status": "FAIL",
    "timestamp": "2026-02-10T14:30:00",
    "camera_id": 0,
    "product_name": "Buddha_Set_3pcs",
    "detected_parts": [
        {"class_name": "pig", "confidence": 0.94, "bbox": {...}, "matched_to": "pig (left)"},
        {"class_name": "monk", "confidence": 0.91, "bbox": {...}, "matched_to": "monk (center)"}
    ],
    "missing_parts": [
        {"name": "peacock", "position": "right", "expected_bbox": {...}, "is_critical": True}
    ],
    "found_count": 2,
    "total_expected": 3,
    "found_percentage": 66.7,
    "inference_time_ms": 15.2,
    "annotated_image": np.ndarray,
    "original_image": np.ndarray
}
```

---

### Step 4: main.py (ปรับปรุงใหญ่)

**สิ่งที่ลบ:**
- MQTT connection panel (broker, port, username, password)
- MQTT topic selection (single/multi topic, add/remove topic)
- mqtt_client import and usage
- on_mqtt_message(), on_mqtt_connected(), on_mqtt_disconnected()
- trigger_inspection() ที่ส่ง MQTT
- subscribe_topic, pending_topics, pending_responses tracking
- Multi-topic response counting logic

**สิ่งที่คงไว้:**
- Tab structure (Live, History, Component Definition)
- Dual camera viewer (cam1, cam2) + zoom + fullscreen
- Status display (PASS/FAIL labels)
- Metadata panel
- History tab (history_widget.py)
- Component Definition tab (component_definition_widget.py)
- FullscreenImageDialog
- config.json load/save (ปรับ schema)

**สิ่งที่เพิ่มใหม่:**

```python
class MVITriggerGUI(QMainWindow):  # เปลี่ยนชื่อเป็น InspectionGUI

    def __init__(self):
        # แทนที่ MQTT ด้วย:
        self.camera_manager = CameraManager()
        self.detection_engine = DetectionEngine()
        self.inspection_controller = InspectionController(...)

    # ─── Live Tab (ปรับใหม่) ───

    def init_live_tab(self):
        """สร้าง Live tab ใหม่"""
        # แทนที่ MQTT connection panel ด้วย:
        # ├─ Camera Settings Panel
        # │   ├─ Camera 1 Source: [dropdown: USB 0, USB 1, RTSP URL, Image File]
        # │   ├─ Camera 2 Source: [dropdown: USB 0, USB 1, RTSP URL, Image File]
        # │   └─ [Connect] [Disconnect] buttons
        # │
        # ├─ Model Settings Panel
        # │   ├─ Model Path: [Browse .pt/.onnx file]
        # │   ├─ Device: [Auto / CPU / CUDA]
        # │   ├─ Confidence: [Slider 0.0 - 1.0]
        # │   └─ Model Status: "Loaded: best.pt (YOLOv8s, 15 classes)"
        # │
        # ├─ Inspection Mode Panel
        # │   ├─ ○ Capture Mode  ○ Realtime Mode
        # │   ├─ Product: [dropdown from component_definition DB]
        # │   ├─ [TRIGGER] button (Capture mode)
        # │   └─ [START/STOP] button (Realtime mode)
        # │
        # ├─ Camera Viewers (คงเดิม — cam1, cam2 + zoom + fullscreen)
        # │
        # └─ Inspection Result Panel
        #     ├─ Status: PASS / FAIL (ใหญ่ + สี)
        #     ├─ Found: 2/3 parts (66.7%)
        #     ├─ Missing: peacock (right)
        #     ├─ Inference Time: 15.2ms
        #     └─ FPS: 30 (Realtime mode only)

    # ─── Camera Control ───

    def on_connect_camera(self):
        """เปิดกล้องตาม source ที่เลือก"""

    def on_disconnect_camera(self):
        """ปิดกล้อง"""

    # ─── Model Control ───

    def on_browse_model(self):
        """เลือกไฟล์ model"""

    def on_load_model(self):
        """โหลด model"""

    def on_confidence_changed(self, value):
        """ปรับ confidence threshold"""

    # ─── Mode Control ───

    def on_mode_changed(self):
        """สลับโหมด Capture / Realtime"""
        # Capture: แสดง TRIGGER button, ซ่อน START/STOP
        # Realtime: ซ่อน TRIGGER, แสดง START/STOP

    def on_product_changed(self, product_id):
        """เปลี่ยน product → โหลด expected parts"""

    # ─── Capture Mode ───

    def on_trigger(self):
        """กด TRIGGER → ถ่ายภาพ → ตรวจสอบ"""
        # self.inspection_controller.trigger_capture(camera_id)

    # ─── Realtime Mode ───

    def on_start_realtime(self):
        """กด START → เริ่ม realtime stream + detection"""

    def on_stop_realtime(self):
        """กด STOP → หยุด realtime"""

    # ─── Display Results (ปรับจากเดิม) ───

    def on_inspection_result(self, result: dict):
        """รับผลจาก InspectionController → แสดงบน GUI"""
        # คล้าย display_image() + update_camera_status() เดิม
        # แต่รับ result dict แทน MQTT payload

    def on_frame_display(self, camera_id: int, frame: np.ndarray):
        """รับเฟรมจาก realtime → แสดง live preview"""
        # แปลง numpy → QPixmap → แสดงบน camera viewer

    def display_result_info(self, result: dict):
        """แสดงข้อมูล: found/missing, inference time, fps"""
```

**Signal-Slot Connections ใหม่:**
```python
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

# Mode
self.capture_radio.toggled.connect(self.on_mode_changed)
self.realtime_radio.toggled.connect(self.on_mode_changed)

# Buttons
self.trigger_btn.clicked.connect(self.on_trigger)
self.start_stop_btn.clicked.connect(self.on_start_stop_realtime)
self.browse_model_btn.clicked.connect(self.on_browse_model)
```

---

### Step 5: config.json (ปรับโครงสร้าง)

```json
{
    "camera": {
        "sources": {
            "cam1": {"type": "usb", "index": 0, "label": "Camera 1"},
            "cam2": {"type": "usb", "index": 1, "label": "Camera 2"}
        },
        "resolution": {"width": 1280, "height": 720},
        "stream_fps": 30
    },
    "model": {
        "path": "models/best.pt",
        "device": "auto",
        "confidence": 0.5,
        "iou_threshold": 0.45
    },
    "inspection": {
        "mode": "capture",
        "realtime_inspect_fps": 10,
        "save_pass_images": false,
        "save_fail_images": true,
        "auto_save_history": true
    },
    "ui_state": {
        "last_product_id": 1,
        "cam1_zoom": 0.25,
        "cam2_zoom": 0.25
    }
}
```

---

### Step 6: history_manager.py (ปรับเล็กน้อย)

**เปลี่ยน:**
- `save_inspection(data)` → รับ result dict จาก InspectionController แทน MQTT payload
- เพิ่มฟิลด์: `inference_time_ms`, `detection_count`, `missing_count`, `mode` (capture/realtime)
- ลบฟิลด์ที่เกี่ยวกับ MVI: `station`, `inspection_name` (ถ้าไม่ต้องการ)

**Table Schema ใหม่:**
```sql
inspections (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    camera_id TEXT,
    product_name TEXT,
    result TEXT,                    -- "pass" / "fail"
    mode TEXT,                     -- "capture" / "realtime"
    found_count INTEGER,
    total_expected INTEGER,
    missing_parts TEXT,            -- JSON array
    inference_time_ms REAL,
    image_path TEXT,
    json_data TEXT                 -- full result JSON
)
```

---

### Step 7: history_widget.py (ปรับเล็กน้อย)

**เปลี่ยน:**
- Table columns: Date, Time, Camera, Product, Result, Found, Missing, Mode, Actions
- Filter: เพิ่ม Product filter, Mode filter
- Detail dialog: แสดง missing parts list, inference time

---

## Implementation Order

```
Phase 1 — Foundation (ไม่กระทบ GUI)
├── 1.1  camera_manager.py         — จัดการกล้อง + stream
├── 1.2  detection_engine.py       — YOLO wrapper
└── 1.3  inspection_controller.py  — orchestration logic

Phase 2 — GUI Rebuild
├── 2.1  main.py                   — ลบ MQTT, เพิ่ม camera/model/mode panels
├── 2.2  config.json               — ปรับโครงสร้างใหม่
└── 2.3  Signal-Slot wiring        — เชื่อม controller ↔ GUI

Phase 3 — Database Update
├── 3.1  history_manager.py        — ปรับ schema + save logic
└── 3.2  history_widget.py         — ปรับ table columns + filters

Phase 4 — Integration & Test
├── 4.1  End-to-end test Capture mode
├── 4.2  End-to-end test Realtime mode
└── 4.3  Test with image files (no camera needed)
```

---

## Dependencies

```
# เดิม
PyQt6>=6.7.0         (คงไว้)
opencv-python         (คงไว้)

# ลบ
paho-mqtt==1.6.1      (ไม่ใช้แล้ว)

# เพิ่ม
ultralytics>=8.0.0    (YOLOv8)
torch>=2.0.0          (PyTorch — required by ultralytics)
numpy                 (มีอยู่แล้วผ่าน opencv)
```

---

## GUI Layout — Live Tab (ใหม่)

```
┌─────────────────────────────────────────────────────────────────┐
│  ┌─── Settings Panel (ซ้าย, แคบ) ──┐  ┌─── Cameras (ขวา) ────┐ │
│  │                                  │  │                      │ │
│  │  ▼ Camera Settings               │  │  ┌────────────────┐  │ │
│  │  Camera 1: [USB:0        ▾]     │  │  │                │  │ │
│  │  Camera 2: [USB:1        ▾]     │  │  │   Camera 1     │  │ │
│  │  [Connect] [Disconnect]         │  │  │   Preview      │  │ │
│  │  Status: ● Connected            │  │  │                │  │ │
│  │                                  │  │  └────────────────┘  │ │
│  │  ▼ Model Settings                │  │  Status: ■ PASS      │ │
│  │  Model: [models/best.pt  📂]    │  │  Found: 3/3 (100%)  │ │
│  │  Device: [Auto ▾]               │  │                      │ │
│  │  Confidence: [====●===] 0.50    │  │  ┌────────────────┐  │ │
│  │  Status: ✓ Loaded (15 classes)  │  │  │                │  │ │
│  │                                  │  │  │   Camera 2     │  │ │
│  │  ▼ Inspection                    │  │  │   Preview      │  │ │
│  │  Mode: ○ Capture ○ Realtime     │  │  │                │  │ │
│  │  Product: [Buddha_3pcs   ▾]     │  │  └────────────────┘  │ │
│  │  Expected: pig, monk, peacock   │  │  Status: ■ FAIL      │ │
│  │                                  │  │  Missing: peacock    │ │
│  │  ┌────────────────────────┐     │  │                      │ │
│  │  │     🔘 TRIGGER          │     │  │  Inference: 15.2ms  │ │
│  │  │   (Space bar)          │     │  │  FPS: — (Capture)   │ │
│  │  └────────────────────────┘     │  │                      │ │
│  │                                  │  │  [🔍+] [🔍-] [↺]   │ │
│  │  ▼ Result                        │  │  [⛶ Fullscreen]     │ │
│  │  Last: FAIL @ 14:30:00          │  │                      │ │
│  │  Missing: peacock (right)        │  │                      │ │
│  │  Inference: 15.2ms              │  │                      │ │
│  └──────────────────────────────────┘  └──────────────────────┘ │
│                                                                 │
│  [Status Bar: Ready | Model: best.pt | Camera 1: Connected]    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Design Decisions

1. **ใช้ Component Definition เดิม** — ไม่จำเป็นต้องกำหนด ROI/ตำแหน่ง
   ถ้าไม่ต้องการตรวจตำแหน่ง ใช้แค่ class name matching ก็ได้
   แต่ถ้าต้องการตรวจตำแหน่งด้วย → ใช้ ROI จาก component_definition DB เดิม

2. **Realtime ใช้ frame skip** — ไม่จำเป็นต้อง detect ทุกเฟรม
   เช่น กล้อง 30 FPS แต่ detect 10 FPS (skip 2 เฟรม)
   เฟรมที่ skip ยังแสดง preview ได้ แค่ไม่ detect

3. **บันทึกเฉพาะ FAIL ใน Realtime** — ประหยัด storage
   ใน Capture mode บันทึกทุกภาพ

4. **รองรับ Image File** — สำหรับ demo/test โดยไม่ต้องมีกล้อง
   เลือก "Image File" ใน camera source → browse ภาพ → ใช้เหมือน capture

5. **ไม่ลบ component_definition_widget.py** — ยังใช้กำหนด expected parts
   เพียงแต่ไม่บังคับกำหนด ROI (ใช้แค่ class name ก็ได้)
