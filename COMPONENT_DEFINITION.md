# 🎯 Component Definition + MVI Integration

## Overview

ระบบ **Component Definition** ช่วยให้ MVI สามารถระบุได้ว่า**ตำแหน่งไหนของวัตถุหายไป** เมื่อผลตรวจสอบเป็น FAIL

### ปัญหาเดิม
```
MVI บอกว่า: "พบ 2 objects → FAIL"
❌ แต่ไม่บอกว่าตำแหน่งไหนหาย
```

### Solution ใหม่
```
MVI + Component Definition บอกว่า:
"พบ 2/3 objects → FAIL"
✅ พบ: pig (left), monk (center)
❌ หายไป: peacock (right) ← บอกเจาะจง!
```

---

## 🎯 Features

### 1. Component Definition Manager
- กำหนด expected components (ตำแหน่งที่ควรมี)
- Manage products และ components
- Save/Load configurations
- Database integration

### 2. MVI Component Integration
- รับ detection results จาก MVI
- Match detected objects กับ expected positions
- ระบุตำแหน่งที่หายได้เจาะจง
- Visual report พร้อม highlights

### 3. Database Schema
- `products`: ชิ้นงานแต่ละประเภท
- `component_definitions`: กำหนด components ที่ต้องมี
- `component_results`: บันทึกผลการตรวจแต่ละ component

---

## 📋 System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    MVI System Flow                      │
└─────────────────────────────────────────────────────────┘

                         ┌──────────────┐
                         │   Camera     │
                         │  📷 Capture  │
                         └──────┬───────┘
                                │ Image
                                ↓
                    ┌───────────────────────┐
                    │  MVI Detection        │
                    │  (YOLOv8, etc.)       │
                    └───────────┬───────────┘
                                │ Detections
                                │ [
                                │   {class: "pig", conf: 0.94, bbox: {...}},
                                │   {class: "monk", conf: 0.98, bbox: {...}}
                                │ ]
                                ↓
                    ┌───────────────────────────────┐
                    │  Component Definition Loader  │
                    │  📋 Load Expected Layout      │
                    └───────────┬───────────────────┘
                                │ Expected:
                                │ - pig (left)
                                │ - monk (center)
                                │ - peacock (right)
                                ↓
                    ┌───────────────────────────────┐
                    │  MVI Component Integration    │
                    │  🔍 Match & Analyze           │
                    └───────────┬───────────────────┘
                                │ Results:
                                │ - Found: pig, monk
                                │ - Missing: peacock (right)
                                ↓
              ┌─────────────────┴─────────────────┐
              │                                   │
              ↓                                   ↓
    ┌─────────────────┐                ┌─────────────────┐
    │    Database     │                │  Visualization  │
    │  💾 Save Result │                │  🖼️ Annotate   │
    └─────────────────┘                └─────────────────┘
              │                                   │
              │                                   ↓
              │                        ┌─────────────────┐
              │                        │   GUI Display   │
              │                        │  📊 Show Result │
              │                        └─────────────────┘
              │                                   │
              └─────────────────┬─────────────────┘
                                ↓
                    ┌───────────────────────┐
                    │   AI Analysis         │
                    │  🧠 Intelligent Engine│
                    └───────────────────────┘
```

---

## 🚀 Quick Start

### Installation

ไม่ต้องติดตั้ง dependencies เพิ่มเติม (ใช้ OpenCV ที่มีอยู่แล้ว)

```bash
# ตรวจสอบว่ามีไฟล์ครบหรือไม่
ls component_definition.py
ls mvi_component_integration.py
ls test_component_definition.py
```

### Basic Usage

#### 1. สร้าง Product และ Components

```python
from component_definition import ComponentDefinitionManager

# Initialize
manager = ComponentDefinitionManager()

# สร้าง Product
product_id = manager.create_product(
    name="Buddha_Set_3pcs",
    description="Set of 3 Buddha statues",
    pass_threshold=1.0  # ต้องพบครบ 100%
)

# เพิ่ม Component Definition
manager.add_component_definition(
    product_id=product_id,
    component_name="pig",
    component_type="object",
    roi={"x": 180, "y": 180, "width": 180, "height": 270},
    position_label="left",
    tolerance=50,  # ยอมรับตำแหน่งเยื้อมได้ 50 pixels
    min_confidence=0.8,
    is_critical=True
)

# เพิ่ม components อื่นๆ...
```

#### 2. ตรวจสอบด้วย MVI Detection Results

```python
from mvi_component_integration import MVIComponentIntegration
import cv2

# Initialize
integration = MVIComponentIntegration(manager)

# โหลดภาพ
image = cv2.imread("captured_image.jpg")

# MVI detection results (จาก YOLO/MVI)
mvi_detections = [
    {
        "class": "pig",
        "confidence": 0.94,
        "bbox": {"x": 178, "y": 180, "width": 182, "height": 268}
    },
    {
        "class": "monk",
        "confidence": 0.98,
        "bbox": {"x": 342, "y": 180, "width": 176, "height": 288}
    }
    # peacock หายไป!
]

# ประมวลผล
result = integration.process_mvi_result(
    image=image,
    mvi_detections=mvi_detections,
    product_id=product_id,
    verbose=True
)

# ดูผลลัพธ์
print(f"Status: {result['status']}")  # FAIL
print(f"Found: {result['found']}/{result['total']}")  # 2/3
print(f"Missing: {result['missing_components']}")  # ['peacock']
print(f"Missing Positions: {result['missing_positions']}")  # ['peacock (right)']

# บันทึกภาพที่มี annotations
cv2.imwrite("result_annotated.jpg", result['annotated_image'])
```

---

## 📊 Database Schema

### Products Table
```sql
CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    golden_template_path TEXT,
    pass_threshold REAL DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Component Definitions Table
```sql
CREATE TABLE component_definitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    component_name TEXT NOT NULL,
    component_type TEXT NOT NULL,
    position_label TEXT,
    roi_x INTEGER NOT NULL,
    roi_y INTEGER NOT NULL,
    roi_width INTEGER NOT NULL,
    roi_height INTEGER NOT NULL,
    tolerance INTEGER DEFAULT 50,
    min_confidence REAL DEFAULT 0.8,
    is_critical BOOLEAN DEFAULT 1,
    expected_features TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);
```

### Component Results Table
```sql
CREATE TABLE component_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_id INTEGER NOT NULL,
    component_def_id INTEGER,
    component_name TEXT NOT NULL,
    found BOOLEAN NOT NULL,
    confidence REAL DEFAULT 0.0,
    expected_bbox TEXT,
    detected_bbox TEXT,
    notes TEXT,
    FOREIGN KEY (inspection_id) REFERENCES inspections(id) ON DELETE CASCADE,
    FOREIGN KEY (component_def_id) REFERENCES component_definitions(id) ON DELETE SET NULL
);
```

---

## 🧪 Testing

### Run Test Suite

```bash
python3 test_component_definition.py
```

**Expected Output:**
```
============================================================
🚀 Component Definition + MVI Integration Test Suite
============================================================

🧪 Testing Component Definition Manager
============================================================
1️⃣ Testing product creation...
✓ Created product: Test_Buddha_Set (ID: 1)
✅ Product created: ID 1

2️⃣ Testing component addition...
✓ Added component: pig (ID: 1)
✓ Added component: monk (ID: 2)
✓ Added component: peacock (ID: 3)
✅ Added 3 components

3️⃣ Testing component retrieval...
✅ Retrieved 3 components
   • pig (left) - ROI: {'x': 100, 'y': 150, 'width': 150, 'height': 200}
   • monk (center) - ROI: {'x': 300, 'y': 150, 'width': 150, 'height': 200}
   • peacock (right) - ROI: {'x': 500, 'y': 100, 'width': 200, 'height': 300}

🧪 Testing MVI Component Integration
============================================================
1️⃣ Testing FAIL case (missing peacock)...
  ✅ pig (left): FOUND (confidence: 0.94)
  ✅ monk (center): FOUND (confidence: 0.98)
  ❌ peacock (right): MISSING

✅ FAIL case test passed
   Status: FAIL
   Reason: Missing critical components: peacock
   Found: 2/3
   Missing: ['peacock']
   💾 Saved: test_result_fail.jpg

2️⃣ Testing PASS case (all components found)...
  ✅ pig (left): FOUND (confidence: 0.90)
  ✅ monk (center): FOUND (confidence: 0.96)
  ✅ peacock (right): FOUND (confidence: 0.99)

✅ PASS case test passed
   Status: PASS
   Found: 3/3

✅ All Tests Passed!
```

---

## 📚 API Reference

### ComponentDefinitionManager

#### Product Management

```python
# Create product
product_id = manager.create_product(
    name: str,
    description: str = "",
    golden_template_path: str = "",
    pass_threshold: float = 1.0
) -> int

# Get product
product = manager.get_product(product_id: int) -> Optional[Dict]
product = manager.get_product_by_name(name: str) -> Optional[Dict]

# List all products
products = manager.list_products() -> List[Dict]

# Update product
manager.update_product(product_id: int, **kwargs)

# Delete product
manager.delete_product(product_id: int)
```

#### Component Definition Management

```python
# Add component definition
comp_id = manager.add_component_definition(
    product_id: int,
    component_name: str,
    component_type: str,
    roi: Dict[str, int],
    position_label: str = "",
    tolerance: int = 50,
    min_confidence: float = 0.8,
    is_critical: bool = True,
    expected_features: Dict = None
) -> int

# Get product components
components = manager.get_product_components(product_id: int) -> List[Dict]

# Update component definition
manager.update_component_definition(component_id: int, **kwargs)

# Delete component definition
manager.delete_component_definition(component_id: int)
```

#### Component Results Management

```python
# Save component results
manager.save_component_results(
    inspection_id: int,
    component_results: List[Dict]
)

# Get component results
results = manager.get_component_results(inspection_id: int) -> List[Dict]

# Get statistics
stats = manager.get_component_statistics(
    component_def_id: int,
    days: int = 7
) -> Dict
```

#### Configuration Import/Export

```python
# Export config
manager.export_product_config(product_id: int, filepath: str)

# Import config
product_id = manager.import_product_config(filepath: str) -> int
```

### MVIComponentIntegration

```python
# Process MVI result
result = integration.process_mvi_result(
    image: np.ndarray,
    mvi_detections: List[Dict],
    product_id: int,
    verbose: bool = False
) -> Dict

# Returns:
{
    "status": "PASS" or "FAIL",
    "reason": str,
    "found": int,
    "total": int,
    "found_percentage": float,
    "missing_components": [str],
    "missing_positions": [str],
    "component_results": [Dict],
    "annotated_image": numpy array
}
```

---

## 🎨 Visualization

### Annotation Colors

```python
✅ FOUND    = Green box   (0, 255, 0)
❌ MISSING  = Red box     (0, 0, 255)

Label format:
  ✓ component_name (confidence)    # Found
  ✗ component_name MISSING         # Missing
```

### Example Output

**FAIL Case (peacock missing):**
```
┌────────────────────────────────────────┐
│                                        │
│  ✅ pig (0.94)     ✅ monk (0.98)     │
│  [Green Box]       [Green Box]        │
│  [LEFT]            [CENTER]           │
│                                        │
│                    ❌ peacock MISSING │
│                    [Red Box]          │
│                    [RIGHT]            │
│                                        │
└────────────────────────────────────────┘

Result: FAIL
Missing: peacock (right)
```

**PASS Case (all found):**
```
┌────────────────────────────────────────┐
│                                        │
│  ✅ pig (0.90)     ✅ monk (0.96)     │
│  [Green Box]       [Green Box]        │
│  [LEFT]            [CENTER]           │
│                                        │
│                    ✅ peacock (0.99)  │
│                    [Green Box]        │
│                    [RIGHT]            │
│                                        │
└────────────────────────────────────────┘

Result: PASS
Found: 3/3
```

---

## 🔧 Matching Algorithm

### How Matching Works

```python
For each expected component:
  1. Find all detected objects with same class name
  2. Calculate center distance between expected and detected
  3. If distance < tolerance:
     → Match found
  4. Else:
     → Missing

Tolerance default: 50 pixels
```

### Example

```python
Expected: pig at (100, 150)
Detected: pig at (105, 155)

Center distance = sqrt((105-100)² + (155-150)²)
                = sqrt(25 + 25)
                = 7.07 pixels

7.07 < 50 (tolerance)
→ ✅ Match!
```

---

## 💡 Use Cases

### Use Case 1: PCB Inspection

```python
# กำหนด components ที่ต้องมีบน PCB
- IC1_TopLeft
- IC2_TopRight
- IC3_BottomLeft
- IC4_BottomRight
- Capacitor_C1
- Resistor_R1

# ตรวจสอบ
→ พบครบ 6/6: PASS
→ ขาด IC3: FAIL - Missing IC3_BottomLeft
```

### Use Case 2: Assembly Line

```python
# กำหนด parts ที่ต้องติดตั้ง
- Screw_1 (front-left)
- Screw_2 (front-right)
- Screw_3 (back-left)
- Screw_4 (back-right)
- Connector (center)

# ตรวจสอบ
→ ขาด Screw_3: FAIL - Missing Screw_3 (back-left)
→ Operator รู้ทันทีว่าต้องติด screw ตำแหน่งไหน
```

### Use Case 3: Quality Control

```python
# กำหนด labels ที่ต้องมี
- Label_Front (product name)
- Label_Back (barcode)
- Label_Side (serial number)

# ตรวจสอบ
→ ขาด Label_Back: FAIL - Missing Label_Back (barcode)
→ แจ้งเตือนทันทีว่า barcode ไม่มี
```

---

## 🎯 Best Practices

### 1. Setting Tolerance

```python
# Small components (screws, ICs)
tolerance = 20  # Strict

# Large components (assemblies)
tolerance = 100  # Loose

# Default
tolerance = 50  # Balanced
```

### 2. Confidence Threshold

```python
# High accuracy required
min_confidence = 0.9

# Balanced
min_confidence = 0.8  # Recommended

# Lenient (noisy environment)
min_confidence = 0.7
```

### 3. Critical vs Non-Critical

```python
# Critical: ต้องมีเสมอ (FAIL ถ้าหาย)
is_critical = True

# Non-critical: มีดีไม่มีก็ได้ (PASS แม้หาย)
is_critical = False
```

### 4. Position Labels

```python
# ใช้ position labels ให้ชัดเจน
position_label = "left"      # ดีกว่า "1"
position_label = "top-left"  # ดีกว่า "corner"
position_label = "center"    # ดีกว่า "middle"
```

---

## 🚀 Integration with Main GUI

### Step 1: Import Modules

```python
# In main.py
from component_definition import ComponentDefinitionManager
from mvi_component_integration import MVIComponentIntegration
```

### Step 2: Initialize in __init__

```python
class MVIInspectionGUI(QMainWindow):
    def __init__(self):
        super().__init__()

        # Initialize component management
        self.comp_manager = ComponentDefinitionManager()
        self.mvi_integration = MVIComponentIntegration(self.comp_manager)

        # Current product
        self.current_product_id = None
```

### Step 3: Process MVI Results

```python
def process_mvi_detection(self, image, mvi_detections):
    """Process MVI detection with component definition"""

    if not self.current_product_id:
        # No product selected - skip component checking
        return self._process_normal_inspection(image, mvi_detections)

    # Use component definition
    result = self.mvi_integration.process_mvi_result(
        image=image,
        mvi_detections=mvi_detections,
        product_id=self.current_product_id,
        verbose=False
    )

    # Save to database
    inspection_id = self._save_inspection_result(result)

    # Save component results
    self.comp_manager.save_component_results(
        inspection_id,
        result['component_results']
    )

    # Display result
    self._display_component_result(result)

    return result
```

---

## 📈 Statistics & Analytics

### Component-level Statistics

```python
# สถิติของแต่ละ component
stats = manager.get_component_statistics(
    component_def_id=1,
    days=7
)

print(f"Total inspections: {stats['total_inspections']}")
print(f"Found: {stats['found_count']}")
print(f"Missing: {stats['missing_count']}")
print(f"Found rate: {stats['found_rate']:.1f}%")
print(f"Avg confidence: {stats['avg_confidence']:.2f}")
```

### Missing Frequency Analysis

```sql
-- Component ไหนหายบ่อยที่สุด
SELECT
    component_name,
    COUNT(*) as missing_count
FROM component_results
WHERE found = 0
AND inspection_id IN (
    SELECT id FROM inspections
    WHERE timestamp >= datetime('now', '-7 days')
)
GROUP BY component_name
ORDER BY missing_count DESC;
```

---

## 🐛 Troubleshooting

### Issue 1: Components not matching

```python
# Solution: Increase tolerance
manager.update_component_definition(
    component_id=1,
    tolerance=100  # Increase from 50
)
```

### Issue 2: False negatives (found but marked as missing)

```python
# Solution: Lower confidence threshold
manager.update_component_definition(
    component_id=1,
    min_confidence=0.7  # Decrease from 0.8
)
```

### Issue 3: Wrong component matched

```python
# Solution: Tighten ROI and tolerance
manager.update_component_definition(
    component_id=1,
    tolerance=30,  # Stricter
    roi_x=adjusted_x,
    roi_y=adjusted_y
)
```

---

## 📝 Changelog

### Version 1.0.0 (2026-01-29)
- ✅ Initial release
- ✅ Component Definition Manager
- ✅ MVI Component Integration
- ✅ Database schema
- ✅ Matching algorithm
- ✅ Annotation visualization
- ✅ Test suite
- ✅ Documentation

---

## 🤝 Contributing

หากต้องการปรับปรุงหรือเพิ่มฟีเจอร์:
1. แก้ไขไฟล์ที่เกี่ยวข้อง
2. รัน test suite: `python3 test_component_definition.py`
3. อัพเดท documentation
4. Commit และ push

---

## 📄 License

Part of MVI GUI Trigger project.

---

**Version:** 1.0.0
**Last Updated:** 2026-02-02
**Branch:** claude/dev-ai-lPor0
