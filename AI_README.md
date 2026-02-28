# 🤖 AI Features Documentation

## Overview

MVI GUI ตอนนี้มี AI Assistant ที่ขับเคลื่อนโดย **Ollama** (Offline AI) ช่วย:
- วิเคราะห์ผลการตรวจสอบ
- ค้นหาข้อมูลจากคู่มือ/เอกสาร
- Query ฐานข้อมูล inspection history
- แนะนำแก้ปัญหา

## ✨ Features

### 1. **AI Chat Assistant**
- สนทนาภาษาไทย/อังกฤษ
- วิเคราะห์ผลการตรวจสอบ
- แนะนำแก้ปัญหา
- สรุปรายงาน

### 2. **Model Selector**
- เลือก AI model ได้ตามต้องการ
- รองรับ text models (llama3.2, mistral)
- รองรับ vision models (llava) สำหรับวิเคราะห์ภาพ

### 3. **Document RAG (Retrieval-Augmented Generation)**
- ค้นหาข้อมูลจาก PDF/TXT/MD files
- Auto-scan folder `manuals/`
- ตอบคำถามโดยอ้างอิงเอกสาร
- แสดงแหล่งอ้างอิง

### 4. **Database Query Agent**
- Query ฐานข้อมูล inspection ด้วยภาษาปกติ
- AI สร้าง SQL อัตโนมัติ
- วิเคราะห์และสรุปผลลัพธ์

## 🚀 Installation

### 1. Install Ollama

**Linux/Mac:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Windows:**
Download from [https://ollama.com](https://ollama.com)

### 2. Start Ollama Server

```bash
ollama serve
```

### 3. Pull AI Models

```bash
# Text model (แนะนำ - เบา เร็ว)
ollama pull llama3.2

# Text model (แม่นยำกว่า)
ollama pull mistral

# Vision model (วิเคราะห์ภาพ)
ollama pull llava
```

### 4. Install Python Dependencies

```bash
pip install -r requirements-ai.txt
```

## 📖 Usage

### Basic Chat

```
คุณ: สวัสดี ช่วยแนะนำตัวหน่อย
AI: สวัสดีครับ! ผมเป็น AI Assistant สำหรับระบบ MVI...
```

### Analyze Inspection Results

```
คุณ: วิเคราะห์ผลการตรวจสอบวันนี้
AI: 📊 สรุปผลการตรวจสอบวันนี้
- Total: 150 inspections
- Pass: 85 (56.7%)
- Fail: 65 (43.3%)
...
```

### Query Database

```
คุณ: มี FAIL กี่ครั้งในวันนี้?
AI: 🔍 ค้นหาข้อมูล...
📊 ผลลัพธ์: พบ FAIL ทั้งหมด 65 ครั้งในวันนี้
...
```

### Search Documents

```
คุณ: วิธีตั้งค่า detection threshold ใน MVI Edge
AI: 🔍 กำลังค้นหาในเอกสาร...
📄 จากคู่มือ MVI_Edge_Manual.pdf:
...
```

## 🎯 Quick Actions

- **📊 วิเคราะห์วันนี้** - วิเคราะห์ผลการตรวจสอบวันนี้
- **🔍 Top Defects** - แสดง defects/devices ที่มีปัญหา
- **📚 เอกสาร** - รายการเอกสารที่โหลดไว้
- **🗑️ Clear** - ล้างประวัติการสนทนา

## 📚 Adding Documents

1. วาง PDF/TXT/MD files ใน folder `manuals/`
2. AI จะ auto-scan และโหลดเอกสารทั้งหมด
3. ถามคำถามที่เกี่ยวข้องกับเอกสาร

**Example:**
```
manuals/
├── MVI_Edge_Manual.pdf
├── Troubleshooting.pdf
└── Camera_Setup_Guide.pdf
```

## 🔧 Configuration

### Model Selection

เลือก model ตามความต้องการ:

| Model | Size | Speed | Accuracy | Use Case |
|-------|------|-------|----------|----------|
| llama3.2:3b | 2GB | ⚡⚡⚡ | ⭐⭐⭐ | General chat, fast |
| mistral:7b | 4GB | ⚡⚡ | ⭐⭐⭐⭐ | Better analysis |
| llava:7b | 4.5GB | ⚡⚡ | ⭐⭐⭐⭐ | Image analysis |

### System Requirements

- **RAM:** 8GB+ (16GB recommended)
- **Disk:** 5-10GB for models
- **CPU:** Modern multi-core (GPU optional)

## ⚠️ Troubleshooting

### Problem: "Ollama Not Available"

**Solution:**
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# If not, start it
ollama serve
```

### Problem: "No models found"

**Solution:**
```bash
ollama list  # Check installed models
ollama pull llama3.2  # Pull a model
```

### Problem: Slow responses

**Solutions:**
- ใช้ model ที่เบากว่า (llama3.2:3b)
- ตรวจสอบ RAM usage
- ปิดโปรแกรมอื่นที่ใช้ RAM มาก

## 🎓 Example Prompts

### Analysis
- "วิเคราะห์ fail rate 7 วันที่ผ่านมา"
- "Camera ไหนมีปัญหามากที่สุด?"
- "แสดง top 5 defects"

### Troubleshooting
- "MQTT connection ขาดบ่อย แก้ไขอย่างไร?"
- "ภาพไม่แสดง ควรเช็คอะไร?"
- "Timeout error เกิดจากอะไร?"

### Documentation
- "วิธีติดตั้ง MVI Edge"
- "ขั้นตอนการ setup camera"
- "API สำหรับ trigger inspection"

## 📝 Notes

- AI ทำงาน **offline** ทั้งหมด - ไม่ส่งข้อมูลออกนอก
- Model ยิ่งใหญ่ = ช้าแต่แม่นกว่า
- Document RAG ทำงานได้ดีกับเอกสารที่มี structure ชัดเจน
- Database queries อาจต้อง retry ถ้า SQL ไม่ถูกต้อง

## 🔮 Future Features

- [ ] Vision analysis integration (วิเคราะห์ภาพจาก inspection)
- [ ] Auto-alert based on AI analysis
- [ ] Report generation
- [ ] Multi-language support
- [ ] Vector database for better document search

## 📄 License

Same as main project
