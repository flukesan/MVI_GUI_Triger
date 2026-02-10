# Dual Mode Inspection System

ระบบตรวจสอบชิ้นงานอัตโนมัติด้วย AI (YOLOv8) แบบ Local — ไม่ต้องพึ่งเซิร์ฟเวอร์ภายนอก
รองรับทั้งโหมด **Capture** (ถ่ายทีละภาพ) และ **Realtime** (ตรวจสอบต่อเนื่องจากวิดีโอสด)

## คุณสมบัติ

- **Dual Mode** — สลับระหว่าง Capture Mode และ Realtime Mode
- **Local YOLO Detection** — รันโมเดล YOLOv8 บนเครื่อง รองรับ GPU (NVIDIA RTX4000) และ CPU
- **Camera Support** — รองรับ USB Camera, RTSP Stream, และโหลดไฟล์ภาพ
- **Missing Parts Detection** — ตรวจจับชิ้นส่วนที่ขาดหายโดยเทียบกับ Component Definition
- **Annotation** — แสดงกรอบสีเขียว (พบ) และกรอบสีแดง (ขาดหาย) บนภาพ
- **Inspection History** — บันทึกผลตรวจสอบพร้อมภาพลง SQLite
- **Dual Camera View** — แสดงผลกล้อง 2 ตัวพร้อมกัน รองรับ Zoom และ Fullscreen

## โครงสร้างโปรแกรม

```
MVI_GUI_Triger/
├── main.py                        # GUI Application หลัก (PyQt6/PySide6)
├── camera_manager.py              # จัดการกล้อง USB/RTSP + Stream
├── detection_engine.py            # YOLOv8 Inference Engine (GPU/CPU)
├── inspection_controller.py       # ตัวควบคุมการตรวจสอบ (Capture + Realtime)
├── component_definition.py        # จัดการข้อมูลชิ้นส่วนที่คาดหวัง
├── component_definition_widget.py # GUI สำหรับกำหนด Component + ROI
├── history_manager.py             # บันทึก/ดึงผลตรวจสอบจาก SQLite
├── history_widget.py              # GUI แสดงประวัติการตรวจสอบ
├── config.json                    # ไฟล์ Configuration
├── requirements.txt               # Python dependencies (PyQt6)
└── requirements-pyside6.txt       # Python dependencies (PySide6)
```

## ข้อกำหนดของระบบ

| รายการ | ขั้นต่ำ | แนะนำ |
|--------|---------|-------|
| Python | 3.8+ | 3.10+ |
| OS | Windows 10 / Ubuntu 20.04 | Windows 11 / Ubuntu 22.04 |
| RAM | 8 GB | 16 GB |
| GPU | - (ใช้ CPU ได้) | NVIDIA RTX4000 หรือสูงกว่า |
| CUDA | - | 11.8+ (สำหรับ GPU) |
| กล้อง | USB Webcam | Industrial USB/RTSP Camera |

## การติดตั้ง

### 1. Clone Repository

```bash
git clone -b claude/missing-parts-identification-LMMfh https://github.com/flukesan/MVI_GUI_Triger.git
cd MVI_GUI_Triger
```

### 2. สร้าง Virtual Environment (แนะนำ)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate
```

### 3. ติดตั้ง Dependencies

**ใช้ PyQt6 (ค่าเริ่มต้น):**
```bash
pip install -r requirements.txt
```

**หรือใช้ PySide6 (ถ้า PyQt6 มีปัญหา):**
```bash
pip install -r requirements-pyside6.txt
```

### 4. ติดตั้ง OpenCV

```bash
pip install opencv-python
```

### 5. ติดตั้ง Ultralytics (YOLOv8)

```bash
pip install ultralytics
```

### 6. ติดตั้ง CUDA สำหรับ GPU (ถ้ามี NVIDIA GPU)

```bash
# ติดตั้ง PyTorch พร้อม CUDA 11.8
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

> หรือเลือกเวอร์ชัน CUDA ที่ตรงกับเครื่องได้ที่ https://pytorch.org/get-started/locally/

### 7. ตรวจสอบว่า GPU พร้อมใช้งาน

```bash
python -c "import torch; print('CUDA:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')"
```

ผลลัพธ์ที่ควรได้ (ตัวอย่าง RTX4000):
```
CUDA: True
GPU: NVIDIA RTX A4000
```

## การตั้งค่า

### config.json

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
    "path": "",
    "device": "auto",
    "confidence": 0.5,
    "iou_threshold": 0.45
  },
  "inspection": {
    "mode": "capture",
    "realtime_inspect_fps": 10,
    "save_pass_images": false,
    "save_fail_images": true
  }
}
```

| ค่า | คำอธิบาย |
|-----|---------|
| `camera.sources` | กำหนดกล้อง — `usb` (index), `rtsp` (url), `image` (path) |
| `model.path` | พาธไปยังไฟล์โมเดล YOLO (.pt) |
| `model.device` | `auto` = ใช้ GPU ถ้ามี, `cpu` = บังคับใช้ CPU, `cuda:0` = ระบุ GPU |
| `model.confidence` | ค่า Confidence threshold (0.0 - 1.0) |
| `inspection.mode` | `capture` หรือ `realtime` |
| `inspection.realtime_inspect_fps` | จำนวนเฟรมที่ตรวจสอบต่อวินาทีในโหมด Realtime |

## การใช้งาน

### เริ่มโปรแกรม

```bash
python main.py
```

### ขั้นตอนการใช้งาน

1. **เชื่อมต่อกล้อง** — เลือก Camera Source แล้วกด Connect
2. **โหลดโมเดล YOLO** — Browse ไฟล์ `.pt` แล้วกด Load Model
3. **กำหนด Component Definition** — ไปที่แท็บ Component Definition เพื่อกำหนดชิ้นส่วนที่คาดหวัง
4. **เลือก Product** — เลือกชื่อผลิตภัณฑ์จาก Dropdown
5. **เลือกโหมดตรวจสอบ:**
   - **Capture Mode** — กดปุ่ม TRIGGER หรือ Spacebar เพื่อถ่ายภาพและตรวจสอบ
   - **Realtime Mode** — กดปุ่ม START เพื่อเริ่มตรวจสอบต่อเนื่อง
6. **ดูผลลัพธ์** — PASS (สีเขียว) / FAIL (สีแดง) พร้อมรายการชิ้นส่วนที่ขาดหาย
7. **ดูประวัติ** — ไปที่แท็บ History เพื่อดูผลตรวจสอบย้อนหลัง

### โหลดไฟล์ภาพ (ไม่ต้องใช้กล้อง)

กดปุ่ม **Load Image File** เพื่อเลือกไฟล์ภาพ (.jpg, .png, .bmp) สำหรับทดสอบโดยไม่ต้องต่อกล้อง

## Troubleshooting

### PyQt6 ImportError: undefined symbol

```bash
# ถอนการติดตั้ง PyQt6 แล้วติดตั้งใหม่
pip uninstall PyQt6 PyQt6-Qt6 PyQt6-sip -y
pip install PyQt6 --force-reinstall --no-cache-dir

# หรือเปลี่ยนไปใช้ PySide6 แทน
pip uninstall PyQt6 PyQt6-Qt6 PyQt6-sip -y
pip install -r requirements-pyside6.txt
```

### ตรวจไม่เจอ GPU (CUDA: False)

- ตรวจสอบว่าติดตั้ง NVIDIA Driver แล้ว: `nvidia-smi`
- ตรวจสอบเวอร์ชัน CUDA: `nvcc --version`
- ติดตั้ง PyTorch ใหม่ให้ตรงกับ CUDA version

### กล้องเปิดไม่ได้

- ตรวจสอบว่ากล้องเชื่อมต่ออยู่: `ls /dev/video*` (Linux) หรือ Device Manager (Windows)
- ตรวจสอบ `camera.sources` ใน `config.json` ว่า index ถูกต้อง
- ปิดโปรแกรมอื่นที่ใช้กล้องอยู่

### โมเดลโหลดไม่ได้

- ตรวจสอบพาธไฟล์ `.pt` ว่าถูกต้อง
- ตรวจสอบว่าติดตั้ง `ultralytics` แล้ว: `pip show ultralytics`

## License

Dual Mode Inspection System
