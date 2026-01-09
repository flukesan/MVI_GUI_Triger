# MVI Edge Inspection Trigger GUI

GUI Application สำหรับทริกเกอร์ MVI (Maximo Visual Inspection) Edge Inspection ผ่าน MQTT Protocol

## คุณสมบัติ

- 🔘 **ปุ่ม Trigger** สำหรับกดทริกเกอร์การตรวจสอบ
- 📋 **Dropdown Menu** สำหรับเลือก MQTT Topic ของแต่ละโมเดล
- ➕ **เพิ่ม/ลบ Topic** บริหารจัดการ topics ได้ง่าย
- ✅ **แสดงสถานะแบบใหญ่ชัดเจน**:
  - 🟢 **PASS** (สีเขียว)
  - 🔴 **FAIL** (สีแดง)
- 🔌 **แสดงสถานะการเชื่อมต่อ MQTT** แบบ Real-time

## โครงสร้างโปรแกรม

```
MVI_GUI_Triger/
├── main.py              # GUI Application หลัก
├── mqtt_client.py       # MQTT Client สำหรับจัดการการเชื่อมต่อ
├── config.json          # ไฟล์ Configuration
└── requirements.txt     # Python dependencies
```

## การติดตั้ง

1. Clone repository:
```bash
git clone <repository-url>
cd MVI_GUI_Triger
```

2. ติดตั้ง dependencies:
```bash
pip install -r requirements.txt
```

3. แก้ไขไฟล์ `config.json` ตามการตั้งค่า MQTT Broker ของคุณ:
```json
{
  "mqtt": {
    "broker": "localhost",
    "port": 1883,
    "username": "",
    "password": "",
    "qos": 1
  },
  "topics": [
    "mvi/model1/trigger",
    "mvi/model2/trigger"
  ],
  "subscribe_topic": "mvi/+/result"
}
```

## การใช้งาน

1. เริ่มโปรแกรม:
```bash
python main.py
```

2. รอให้เชื่อมต่อกับ MQTT Broker (สถานะจะเป็น "Connected" สีเขียว)

3. เลือก Topic จาก Dropdown menu

4. กดปุ่ม "TRIGGER MVI INSPECTION"

5. รอผลการตรวจสอบ:
   - ✓ PASS (สีเขียว) = ผ่านการตรวจสอบ
   - ✗ FAIL (สีแดง) = ไม่ผ่านการตรวจสอบ

## การจัดการ Topics

### เพิ่ม Topic ใหม่
1. กดปุ่ม "➕ เพิ่ม"
2. ใส่ชื่อ Topic (เช่น: `mvi/model3/trigger`)
3. กด OK

### ลบ Topic
1. เลือก Topic ที่ต้องการลบจาก Dropdown
2. กดปุ่ม "➖ ลบ"
3. ยืนยันการลบ

## รูปแบบข้อความ MQTT

### Trigger Message (Publish)
```json
{
  "action": "trigger",
  "timestamp": "current_time"
}
```

### Result Message (Subscribe)
```json
{
  "result": "pass"  // หรือ "fail"
}
```

## การตั้งค่า MQTT Broker

### ตัวอย่างการตั้งค่า Mosquitto (localhost)
```bash
# ติดตั้ง Mosquitto
sudo apt-get install mosquitto mosquitto-clients

# เริ่ม service
sudo systemctl start mosquitto
sudo systemctl enable mosquitto
```

### ตัวอย่างการทดสอบด้วย MQTT Client
```bash
# Subscribe ผลลัพธ์
mosquitto_sub -t "mvi/+/result"

# Publish trigger (ทดสอบ)
mosquitto_pub -t "mvi/model1/trigger" -m '{"action":"trigger"}'

# Publish result (ทดสอบ)
mosquitto_pub -t "mvi/model1/result" -m '{"result":"pass"}'
```

## ข้อกำหนดของระบบ

- Python 3.8 หรือสูงกว่า
- PyQt6
- paho-mqtt
- MQTT Broker (เช่น Mosquitto, HiveMQ)

## Troubleshooting

### PyQt6 ImportError: undefined symbol
หากพบข้อผิดพลาด `ImportError: undefined symbol` เมื่อรันโปรแกรม:

**วิธีแก้ไข:**
```bash
# 1. ถอนการติดตั้ง PyQt6 ทั้งหมด
pip uninstall PyQt6 PyQt6-Qt6 PyQt6-sip -y

# 2. อัพเกรด pip
pip install --upgrade pip

# 3. ติดตั้ง PyQt6 ใหม่
pip install PyQt6>=6.7.0 PyQt6-Qt6>=6.7.0

# 4. หรือติดตั้งจาก requirements.txt
pip install -r requirements.txt --force-reinstall
```

**ถ้ายังไม่ได้ผล ลองติดตั้งแบบเฉพาะเจาะจง:**
```bash
pip install PyQt6==6.7.1 PyQt6-Qt6==6.7.1 --force-reinstall
```

### ไม่สามารถเชื่อมต่อ MQTT Broker
- ตรวจสอบว่า MQTT Broker ทำงานอยู่
- ตรวจสอบ `broker` และ `port` ใน `config.json`
- ตรวจสอบ firewall settings

### ไม่ได้รับผลลัพธ์
- ตรวจสอบ `subscribe_topic` ใน `config.json`
- ตรวจสอบว่า MVI Edge ส่งผลลัพธ์มาที่ topic ที่ถูกต้อง
- ดู MQTT Broker logs

## License

สำหรับ MVI Maximo MQTT Trigger
