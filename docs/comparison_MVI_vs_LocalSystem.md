# เปรียบเทียบ IBM MVI vs Dual Mode Inspection System (Local YOLOv8)

> เอกสารเปรียบเทียบความสามารถระหว่างระบบ IBM Maximo Visual Inspection (MVI)
> กับระบบตรวจสอบ Local ที่พัฒนาขึ้นมาแทนที่ (Dual Mode Inspection System)

---

## 1. ภาพรวมระบบ

| รายการ | IBM MVI | Local System (ของเรา) |
|--------|---------|----------------------|
| **ชื่อเต็ม** | IBM Maximo Visual Inspection (MAS) | Dual Mode Inspection System (YOLOv8 + PatchCore) |
| **ผู้พัฒนา** | IBM | พัฒนาเอง (In-house) |
| **Architecture** | Cloud/Edge + OpenShift Container | Standalone Desktop App (PyQt6) |
| **AI Framework** | IBM proprietary (Tiny YOLO v2, Faster R-CNN) | Ultralytics YOLOv8 + PatchCore (ResNet18) |
| **GPU** | NVIDIA Pascal/Volta/Turing/Ampere (16GB ขั้นต่ำ) | NVIDIA RTX4000 Ada (หรือ GPU ใดๆ ที่รองรับ CUDA) |
| **License** | Enterprise subscription (AppPoints) | Open-source stack (ฟรี) |
| **ภาษา UI** | English เท่านั้น | Thai + English |

---

## 2. เปรียบเทียบความสามารถ

### 2.1 การตรวจจับ (Detection)

| ความสามารถ | IBM MVI | Local System | หมายเหตุ |
|-----------|---------|-------------|---------|
| Object Detection | Tiny YOLO v2, Faster R-CNN | **YOLOv8x** (SOTA 2024) | Local ใช้โมเดลใหม่กว่า แม่นยำกว่า |
| Image Classification | ได้ (pass/fail ทั้งภาพ) | ได้ (ผ่าน YOLO class) | |
| Action Detection (Video) | ได้ (เฉพาะ MVI เต็ม) | ไม่ได้ | MVI มี video-based action detection |
| Instance Segmentation | ได้ (FRCNN+MRCNN) | ไม่ได้ | Local ใช้ bbox เท่านั้น |
| **Anomaly Detection** | จำกัด | **PatchCore + YOLO Hybrid** | Local มี heatmap + ทนตำแหน่งขยับ |
| Custom Model Import | ได้ | **ได้ (YOLOv8 .pt / .onnx)** | Local ยืดหยุ่นกว่า |
| Confidence Threshold | ปรับได้ | **ปรับได้ (slider 0.10-0.95)** | |
| Inference Speed | ขึ้นกับ server | **~15-30ms (GPU)** | Local เร็วกว่า (ไม่ผ่าน network) |
| Realtime Detection | ได้ (ผ่าน MVI Edge) | **ได้ (30 FPS + background thread)** | |

### 2.2 กล้อง (Camera Support)

| ความสามารถ | IBM MVI | Local System | หมายเหตุ |
|-----------|---------|-------------|---------|
| USB Camera | ได้ | **ได้** | |
| RTSP / IP Camera | ได้ | **ได้** | |
| GigE Vision (Basler) | ได้ (MVI Edge) | **ได้ (GenICam/Harvesters)** | |
| Dual Camera | ได้ | **ได้ (Cam 1 + Cam 2)** | |
| Camera Profiles | ผ่าน MVI Edge config | **ได้ (JSON profiles)** | |
| Drone / Vehicle Camera | ได้ (MVI Edge) | ไม่ได้ | MVI รองรับกล้องพิเศษ |
| Mobile Camera (iOS) | ได้ (MVI Mobile app) | ไม่ได้ | |
| Live Preview | ได้ | **ได้ (30 FPS smooth)** | |

### 2.3 การเทรน (Training)

| ความสามารถ | IBM MVI | Local System | หมายเหตุ |
|-----------|---------|-------------|---------|
| No-Code Training UI | **ได้ (drag & drop)** | ไม่มี (ต้องเทรนแยก) | MVI สะดวกกว่าสำหรับ non-technical |
| Auto Labeling | **ได้** | ไม่ได้ | |
| Data Augmentation | **อัตโนมัติ** | ไม่ได้ (ต้องทำเอง) | |
| Transfer Learning | ได้ | ได้ (YOLOv8 fine-tune) | |
| **Anomaly Training** | จำกัด | **ได้ (PatchCore — 10-30 ภาพ)** | Local ง่ายกว่า |
| Train บน GPU | ได้ | ได้ (แยกใช้ Ultralytics CLI) | |
| Model Export | จำกัด format | **.pt, .onnx (มาตรฐาน)** | |

### 2.4 การแจ้งผล (Results & Actions)

| ความสามารถ | IBM MVI | Local System | หมายเหตุ |
|-----------|---------|-------------|---------|
| PASS / FAIL | ได้ | **ได้** | |
| Heatmap Visualization | จำกัด | **ได้ (JET colormap overlay)** | |
| Missing Parts ระบุตำแหน่ง | ผ่าน rules | **ได้ (ROI + tolerance matching)** | |
| Inspection History | ผ่าน Maximo Suite | **ได้ (SQLite + image archive)** | |
| Export CSV | ผ่าน API | **ได้ (built-in)** | |
| SMS/Email Alert | ได้ (Twilio) | ไม่ได้ | |
| PLC Trigger | ได้ (ผ่าน MQTT → PLC) | ไม่ได้ (ต้องพัฒนาเพิ่ม) | |

### 2.5 การเชื่อมต่อ (Integration)

| ความสามารถ | IBM MVI | Local System | หมายเหตุ |
|-----------|---------|-------------|---------|
| **MQTT** | **ได้ (built-in)** | ไม่ได้ (ต้องเพิ่ม) | MVI ส่ง MQTT alert อัตโนมัติ |
| **REST API** | **ได้ (full API)** | ไม่ได้ (ต้องเพิ่ม) | MVI มี API ครบ |
| **DeviceWise (Telit)** | ผ่าน MQTT bridge | ไม่ได้ (ต้องเพิ่ม) | ดูหัวข้อ 5 |
| IBM Maximo Monitor | **ได้ (native)** | ไม่ได้ | |
| IBM Maximo Suite (EAM) | **ได้ (native)** | ไม่ได้ | |
| Database | IBM Cloud / OpenShift | **SQLite (local)** | |
| Multi-site Dashboard | **ได้ (MVI Edge central)** | ไม่ได้ | MVI ดู dashboard หลายโรงงาน |

---

## 3. ข้อดี / ข้อเสีย

### IBM MVI

| ข้อดี | ข้อเสีย |
|------|--------|
| No-code training (ใช้ง่ายสำหรับ non-technical) | **ราคาแพง** ($3,150+/เดือน + infrastructure) |
| Enterprise support จาก IBM | **โมเดลเก่า** (Tiny YOLO v2, Faster R-CNN) ไม่ใช่ SOTA |
| MQTT built-in → เชื่อมต่อ DeviceWise ได้ | ต้องมี **OpenShift** infrastructure |
| Multi-site dashboard | **English only** |
| Mobile app (iOS) | iOS เท่านั้น ไม่มี Android |
| Auto labeling + augmentation | **GPU ต้อง 16GB ขั้นต่ำ** |
| Action Detection (video) | **Bug เยอะ** (v9.0.0 — model stuck, OOM, CPU 450%) |
| Integration กับ Maximo Suite ทั้งระบบ | Learning curve สูง (ตั้งค่ายาก) |
| | **ต้องมี internet** สำหรับ cloud features |
| | ไม่มี PatchCore anomaly detection |

### Local System (ของเรา)

| ข้อดี | ข้อเสีย |
|------|--------|
| **ฟรี** (open-source stack) | ไม่มี MQTT/REST API (ต้องพัฒนาเพิ่ม) |
| **YOLOv8** (SOTA — แม่นยำกว่า YOLO v2 มาก) | ไม่มี no-code training UI |
| **PatchCore Anomaly Detection** + heatmap | ไม่มี multi-site dashboard |
| **Inference เร็ว** (~15-30ms ไม่ผ่าน network) | ต้องดูแลเอง (self-maintained) |
| **Offline ได้ 100%** (ไม่ต้องมี internet) | ไม่มี SMS/email alert |
| **GPU RTX4000 Ada** เพียงพอ (ไม่ต้อง 16GB) | ไม่มี mobile app |
| **Thai UI** | ไม่มี auto labeling |
| ไม่ต้องมี OpenShift / container | ไม่มี action detection (video) |
| **Custom ได้ 100%** (แก้ code เอง) | ต้องมีความรู้ programming |
| ทำงานบนเครื่องเดียว (simple deployment) | ยังไม่เชื่อมต่อ DeviceWise |
| Component Definition + ROI matching | |
| History + CSV export | |

---

## 4. เปรียบเทียบ Model AI

| รายการ | MVI (Tiny YOLO v2) | Local (YOLOv8x) | ดีกว่า |
|--------|-------------------|-----------------|--------|
| ปีที่ออก | 2017 | 2023 | **Local** |
| mAP (COCO) | ~22% | **~53%** | **Local** (แม่นกว่า 2.4 เท่า) |
| ความเร็ว | ปานกลาง | **เร็วมาก (~15ms)** | **Local** |
| ขนาด Model | เล็ก | ใหญ่กว่า (แต่ GPU รับได้) | เสมอกัน |
| Custom Training | ผ่าน MVI UI | ผ่าน Ultralytics CLI | MVI ง่ายกว่า |
| Anomaly Detection | ไม่มี built-in | **PatchCore + heatmap** | **Local** |

---

## 5. การเชื่อมต่อกับ DeviceWise

### DeviceWise คืออะไร?
DeviceWise (Telit) เป็น IoT Gateway Platform ที่ใช้เชื่อมต่ออุปกรณ์ industrial (PLC, sensor, machine)
กับระบบ cloud/enterprise ผ่าน protocol ต่างๆ (MQTT, OPC-UA, Modbus, REST)

### IBM MVI + DeviceWise

```
┌─────────┐     MQTT      ┌──────────────┐     MQTT/REST     ┌────────────┐
│ MVI Edge │ ──────────── │  DeviceWise   │ ───────────────── │ Cloud/ERP  │
│ (ตรวจสอบ) │   pass/fail  │  (IoT Gateway)│   forward data   │ Dashboard  │
└─────────┘              └──────────────┘                   └────────────┘
                               │
                          OPC-UA/Modbus
                               │
                         ┌───────────┐
                         │ PLC/Machine│
                         │ (หยุดสาย)  │
                         └───────────┘
```

- MVI Edge ส่ง MQTT message เมื่อตรวจเจอ FAIL
- DeviceWise subscribe MQTT topic → forward ไปยัง cloud หรือ trigger PLC
- **ข้อดี**: Built-in ไม่ต้องเขียน code
- **ข้อเสีย**: ต้องจ่ายค่า license ทั้ง MVI + DeviceWise

### Local System + DeviceWise (ปัจจุบัน)

```
┌──────────────┐                    ┌──────────────┐
│ Local System  │   ❌ ยังไม่เชื่อม   │  DeviceWise   │
│ (YOLOv8+GUI) │                    │  (IoT Gateway)│
└──────────────┘                    └──────────────┘
```

**ปัจจุบัน: ยังไม่ได้เชื่อมต่อ** — ระบบทำงาน standalone

### Local System + DeviceWise (สามารถเพิ่มได้)

```
┌──────────────┐     MQTT      ┌──────────────┐     MQTT/REST     ┌────────────┐
│ Local System  │ ──────────── │  DeviceWise   │ ───────────────── │ Cloud/ERP  │
│ (YOLOv8+GUI) │   pass/fail  │  (IoT Gateway)│   forward data   │ Dashboard  │
└──────────────┘   + score     └──────────────┘                   └────────────┘
      │                              │
      │ (direct)                OPC-UA/Modbus
      │                              │
      │                        ┌───────────┐
      └── REST API ──────────  │ PLC/Machine│
           (optional)          │ (หยุดสาย)  │
                               └───────────┘
```

**สิ่งที่ต้องพัฒนาเพิ่ม:**

| Feature | ความยากง่าย | ระยะเวลา | หมายเหตุ |
|---------|-------------|---------|---------|
| MQTT Publisher | ง่าย | 1-2 วัน | ใช้ paho-mqtt library |
| REST API Server | ปานกลาง | 2-3 วัน | ใช้ Flask/FastAPI |
| OPC-UA Client | ปานกลาง | 2-3 วัน | ใช้ opcua library |
| PLC Direct (Modbus) | ง่าย | 1-2 วัน | ใช้ pymodbus library |
| WebSocket Dashboard | ปานกลาง | 3-5 วัน | สำหรับ remote monitoring |

### MQTT Message Format (ที่จะส่งให้ DeviceWise)

```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "camera_id": 0,
  "product_name": "Product_A",
  "result": "FAIL",
  "mode": "anomaly",
  "anomaly_score": 5.96,
  "threshold": 6.5,
  "found_count": 2,
  "total_expected": 3,
  "missing_parts": ["part_C"],
  "inference_time_ms": 76.2
}
```

---

## 6. เปรียบเทียบต้นทุน

| รายการ | IBM MVI | Local System |
|--------|---------|-------------|
| **License Software** | ~$3,150+/เดือน (MAS subscription) | **ฟรี** (open-source) |
| **Infrastructure** | OpenShift cluster + GPU server | **เครื่อง PC 1 ตัว** |
| **GPU** | NVIDIA 16GB+ (~$5,000-10,000) | **RTX4000 Ada 20GB (~$1,200)** |
| **Server** | 64GB RAM, 16+ cores (~$5,000-15,000) | **PC ทั่วไป + GPU** |
| **Camera** | เหมือนกัน | เหมือนกัน |
| **DeviceWise** | ต้องจ่ายแยก | ต้องจ่ายแยก (เท่ากัน) |
| **Maintenance** | IBM support (รวมใน license) | **ดูแลเอง** |
| **ต้นทุนรวม (ปีแรก)** | **~$50,000-100,000+** | **~$3,000-5,000** |
| **ต้นทุนรวม (ปีต่อๆ ไป)** | **~$40,000+/ปี** | **~$0 (ค่า hardware เท่านั้น)** |

---

## 7. สรุป: เลือกระบบไหนเมื่อไหร่?

### เลือก IBM MVI เมื่อ:
- องค์กรใหญ่ มีงบ IT สูง
- ต้องการ multi-site dashboard ข้ามโรงงาน
- ต้องการ no-code training (ผู้ใช้ไม่มีความรู้ programming)
- ต้องการ integration กับ IBM Maximo Suite (EAM/APM) อยู่แล้ว
- ต้องการ mobile inspection (iOS)
- ต้องการ vendor support (IBM)

### เลือก Local System (ของเรา) เมื่อ:
- ต้องการ **ประหยัดต้นทุน** อย่างมาก
- ต้องการ **AI model ที่แม่นยำกว่า** (YOLOv8 >> Tiny YOLO v2)
- ต้องการ **Anomaly Detection** (PatchCore + heatmap)
- เครื่องไม่มี internet (offline 100%)
- ต้องการ **ปรับแต่ง custom** ได้ทุกอย่าง
- มีทีมพัฒนาดูแลได้เอง
- ต้องการ **inference เร็ว** (ไม่ผ่าน network)
- ใช้กับ **โรงงานเดียว** (single-site)

---

## 8. Roadmap — สิ่งที่ Local System สามารถพัฒนาเพิ่มได้

| ลำดับ | Feature | เพื่ออะไร | ความยาก |
|-------|---------|----------|---------|
| 1 | MQTT Publisher | เชื่อม DeviceWise / PLC | ง่าย |
| 2 | REST API | เชื่อม external dashboard | ปานกลาง |
| 3 | Auto-threshold calibration | ลด false positive ของ anomaly | ปานกลาง |
| 4 | Multi-model support | โหลดหลาย YOLO model พร้อมกัน | ง่าย |
| 5 | Web Dashboard | ดูผลจากมือถือ/คอมอื่น | ปานกลาง |
| 6 | OPC-UA Integration | เชื่อม PLC โดยตรง | ปานกลาง |
| 7 | Email/LINE Alert | แจ้งเตือนเมื่อ FAIL | ง่าย |
| 8 | Custom YOLO Training UI | เทรนโมเดลบน GUI | ยาก |

---

*เอกสารนี้สร้างเมื่อ: กุมภาพันธ์ 2026*
*โดย: Dual Mode Inspection System Development Team*
