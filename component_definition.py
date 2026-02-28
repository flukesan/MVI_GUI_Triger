"""
Component Definition Manager
จัดการ Component Definitions สำหรับ MVI Inspection

Features:
- กำหนด expected components (ตำแหน่งที่ควรมี)
- Save/Load configurations
- Manage products and their components
- Database integration
"""

import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Any, Optional
import os


class ComponentDefinitionManager:
    """จัดการ Component Definitions"""

    def __init__(self, db_path='inspections.db'):
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """สร้างตารางถ้ายังไม่มี"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create products table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                golden_template_path TEXT,
                pass_threshold REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create component_definitions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS component_definitions (
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
            )
        """)

        # Create component_results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS component_results (
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
            )
        """)

        # Create index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_component_results_inspection
            ON component_results(inspection_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_component_definitions_product
            ON component_definitions(product_id)
        """)

        conn.commit()
        conn.close()

        print("✓ Component Definition database initialized")

    # ==================== Product Management ====================

    def create_product(self, name: str, description: str = "",
                       golden_template_path: str = "",
                       pass_threshold: float = 1.0) -> int:
        """
        สร้าง Product ใหม่

        Args:
            name: ชื่อ product (ต้องไม่ซ้ำ)
            description: คำอธิบาย
            golden_template_path: path ของภาพ golden template
            pass_threshold: เปอร์เซ็นต์ที่ต้องพบเพื่อ PASS (0.0-1.0)

        Returns:
            product_id
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO products (name, description, golden_template_path, pass_threshold)
                VALUES (?, ?, ?, ?)
            """, (name, description, golden_template_path, pass_threshold))

            product_id = cursor.lastrowid
            conn.commit()

            print(f"✓ Created product: {name} (ID: {product_id})")
            return product_id

        except sqlite3.IntegrityError:
            print(f"✗ Product '{name}' already exists")
            # Get existing product ID
            cursor.execute("SELECT id FROM products WHERE name = ?", (name,))
            result = cursor.fetchone()
            return result[0] if result else None

        finally:
            conn.close()

    def get_product(self, product_id: int) -> Optional[Dict]:
        """ดึงข้อมูล Product"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, name, description, golden_template_path,
                   pass_threshold, created_at, updated_at
            FROM products
            WHERE id = ?
        """, (product_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'id': row[0],
                'name': row[1],
                'description': row[2],
                'golden_template_path': row[3],
                'pass_threshold': row[4],
                'created_at': row[5],
                'updated_at': row[6]
            }
        return None

    def get_product_by_name(self, name: str) -> Optional[Dict]:
        """ดึงข้อมูล Product จากชื่อ"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, name, description, golden_template_path,
                   pass_threshold, created_at, updated_at
            FROM products
            WHERE name = ?
        """, (name,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'id': row[0],
                'name': row[1],
                'description': row[2],
                'golden_template_path': row[3],
                'pass_threshold': row[4],
                'created_at': row[5],
                'updated_at': row[6]
            }
        return None

    def list_products(self) -> List[Dict]:
        """ดึงรายการ Products ทั้งหมด"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT p.id, p.name, p.description, p.golden_template_path,
                   p.pass_threshold, p.created_at,
                   COUNT(cd.id) as component_count
            FROM products p
            LEFT JOIN component_definitions cd ON p.id = cd.product_id
            GROUP BY p.id
            ORDER BY p.name
        """)

        rows = cursor.fetchall()
        conn.close()

        products = []
        for row in rows:
            products.append({
                'id': row[0],
                'name': row[1],
                'description': row[2],
                'golden_template_path': row[3],
                'pass_threshold': row[4],
                'created_at': row[5],
                'component_count': row[6]
            })

        return products

    def update_product(self, product_id: int, **kwargs):
        """อัพเดทข้อมูล Product"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        allowed_fields = ['name', 'description', 'golden_template_path', 'pass_threshold']
        updates = []
        values = []

        for field, value in kwargs.items():
            if field in allowed_fields:
                updates.append(f"{field} = ?")
                values.append(value)

        if updates:
            updates.append("updated_at = ?")
            values.append(datetime.now())
            values.append(product_id)

            sql = f"UPDATE products SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(sql, values)
            conn.commit()

            print(f"✓ Updated product ID {product_id}")

        conn.close()

    def delete_product(self, product_id: int):
        """ลบ Product (และ components ทั้งหมด)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        conn.close()

        print(f"✓ Deleted product ID {product_id}")

    # ==================== Component Definition Management ====================

    def add_component_definition(self,
                                  product_id: int,
                                  component_name: str,
                                  component_type: str,
                                  roi: Dict[str, int],
                                  position_label: str = "",
                                  tolerance: int = 50,
                                  min_confidence: float = 0.8,
                                  is_critical: bool = True,
                                  expected_features: Dict = None) -> int:
        """
        เพิ่ม Component Definition

        Args:
            product_id: ID ของ product
            component_name: ชื่อ component (เช่น "pig", "monk", "peacock")
            component_type: ประเภท ("object", "circle", "rectangle", "custom")
            roi: {"x": int, "y": int, "width": int, "height": int}
            position_label: ป้ายตำแหน่ง (เช่น "left", "center", "right")
            tolerance: ระยะห่างที่ยอมรับได้ (pixels)
            min_confidence: confidence ต่ำสุดที่ยอมรับ (0.0-1.0)
            is_critical: เป็น critical component หรือไม่
            expected_features: features เพิ่มเติม (dict)

        Returns:
            component_id
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        features_json = json.dumps(expected_features) if expected_features else "{}"

        cursor.execute("""
            INSERT INTO component_definitions
            (product_id, component_name, component_type, position_label,
             roi_x, roi_y, roi_width, roi_height, tolerance,
             min_confidence, is_critical, expected_features)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            product_id, component_name, component_type, position_label,
            roi['x'], roi['y'], roi['width'], roi['height'], tolerance,
            min_confidence, is_critical, features_json
        ))

        component_id = cursor.lastrowid
        conn.commit()
        conn.close()

        print(f"✓ Added component: {component_name} (ID: {component_id})")
        return component_id

    def get_product_components(self, product_id: int) -> List[Dict]:
        """ดึง Components ทั้งหมดของ Product"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, component_name, component_type, position_label,
                   roi_x, roi_y, roi_width, roi_height, tolerance,
                   min_confidence, is_critical, expected_features
            FROM component_definitions
            WHERE product_id = ?
            ORDER BY id
        """, (product_id,))

        rows = cursor.fetchall()
        conn.close()

        components = []
        for row in rows:
            components.append({
                'id': row[0],
                'name': row[1],
                'type': row[2],
                'position': row[3],
                'roi': {
                    'x': row[4],
                    'y': row[5],
                    'width': row[6],
                    'height': row[7]
                },
                'tolerance': row[8],
                'min_confidence': row[9],
                'critical': bool(row[10]),
                'expected_features': json.loads(row[11]) if row[11] else {}
            })

        return components

    def update_component_definition(self, component_id: int, **kwargs):
        """อัพเดท Component Definition"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        allowed_fields = [
            'component_name', 'component_type', 'position_label',
            'roi_x', 'roi_y', 'roi_width', 'roi_height', 'tolerance',
            'min_confidence', 'is_critical', 'expected_features'
        ]

        updates = []
        values = []

        for field, value in kwargs.items():
            if field in allowed_fields:
                if field == 'expected_features' and isinstance(value, dict):
                    value = json.dumps(value)
                updates.append(f"{field} = ?")
                values.append(value)

        if updates:
            values.append(component_id)
            sql = f"UPDATE component_definitions SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(sql, values)
            conn.commit()

            print(f"✓ Updated component ID {component_id}")

        conn.close()

    def delete_component_definition(self, component_id: int):
        """ลบ Component Definition"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM component_definitions WHERE id = ?", (component_id,))
        conn.commit()
        conn.close()

        print(f"✓ Deleted component ID {component_id}")

    # ==================== Component Results Management ====================

    def save_component_results(self,
                               inspection_id: int,
                               component_results: List[Dict]):
        """
        บันทึกผลการตรวจแต่ละ Component

        Args:
            inspection_id: ID ของ inspection
            component_results: [
                {
                    "component_def_id": int,
                    "name": str,
                    "found": bool,
                    "confidence": float,
                    "expected_bbox": dict,
                    "detected_bbox": dict or None,
                    "notes": str
                },
                ...
            ]
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for result in component_results:
            expected_bbox_json = json.dumps(result.get('expected_bbox', {}))
            detected_bbox_json = json.dumps(result.get('detected_bbox')) if result.get('detected_bbox') else None

            cursor.execute("""
                INSERT INTO component_results
                (inspection_id, component_def_id, component_name,
                 found, confidence, expected_bbox, detected_bbox, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                inspection_id,
                result.get('component_def_id'),
                result['name'],
                result['found'],
                result.get('confidence', 0.0),
                expected_bbox_json,
                detected_bbox_json,
                result.get('notes', '')
            ))

        conn.commit()
        conn.close()

        print(f"✓ Saved {len(component_results)} component results for inspection {inspection_id}")

    def get_component_results(self, inspection_id: int) -> List[Dict]:
        """ดึงผลการตรวจ Components ของ inspection"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, component_def_id, component_name, found, confidence,
                   expected_bbox, detected_bbox, notes
            FROM component_results
            WHERE inspection_id = ?
            ORDER BY id
        """, (inspection_id,))

        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            results.append({
                'id': row[0],
                'component_def_id': row[1],
                'name': row[2],
                'found': bool(row[3]),
                'confidence': row[4],
                'expected_bbox': json.loads(row[5]) if row[5] else {},
                'detected_bbox': json.loads(row[6]) if row[6] else None,
                'notes': row[7]
            })

        return results

    # ==================== Configuration Import/Export ====================

    def export_product_config(self, product_id: int, filepath: str):
        """Export product configuration เป็น JSON"""
        product = self.get_product(product_id)
        if not product:
            print(f"✗ Product ID {product_id} not found")
            return

        components = self.get_product_components(product_id)

        config = {
            'product': product,
            'components': components,
            'version': '1.0',
            'exported_at': datetime.now().isoformat()
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        print(f"✓ Exported config to {filepath}")

    def import_product_config(self, filepath: str) -> int:
        """Import product configuration จาก JSON"""
        if not os.path.exists(filepath):
            print(f"✗ File not found: {filepath}")
            return None

        with open(filepath, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # Create product
        product_data = config['product']
        product_id = self.create_product(
            name=product_data['name'],
            description=product_data.get('description', ''),
            golden_template_path=product_data.get('golden_template_path', ''),
            pass_threshold=product_data.get('pass_threshold', 1.0)
        )

        # Add components
        for comp in config['components']:
            self.add_component_definition(
                product_id=product_id,
                component_name=comp['name'],
                component_type=comp['type'],
                roi=comp['roi'],
                position_label=comp.get('position', ''),
                tolerance=comp.get('tolerance', 50),
                min_confidence=comp.get('min_confidence', 0.8),
                is_critical=comp.get('critical', True),
                expected_features=comp.get('expected_features', {})
            )

        print(f"✓ Imported config from {filepath}")
        return product_id

    # ==================== Statistics ====================

    def get_component_statistics(self, component_def_id: int, days: int = 7) -> Dict:
        """สถิติของ component"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN found = 1 THEN 1 ELSE 0 END) as found_count,
                AVG(CASE WHEN found = 1 THEN confidence ELSE 0 END) as avg_confidence
            FROM component_results
            WHERE component_def_id = ?
            AND inspection_id IN (
                SELECT id FROM inspections
                WHERE timestamp >= datetime('now', '-' || ? || ' days')
            )
        """, (component_def_id, days))

        row = cursor.fetchone()
        conn.close()

        if row:
            total = row[0]
            found = row[1]
            return {
                'total_inspections': total,
                'found_count': found,
                'missing_count': total - found,
                'found_rate': (found / total * 100) if total > 0 else 0,
                'avg_confidence': row[2] or 0.0
            }

        return {
            'total_inspections': 0,
            'found_count': 0,
            'missing_count': 0,
            'found_rate': 0.0,
            'avg_confidence': 0.0
        }


# Example usage
if __name__ == "__main__":
    print("Component Definition Manager")
    print("=" * 60)

    manager = ComponentDefinitionManager()

    # Example: Create product
    product_id = manager.create_product(
        name="Buddha_Set_3pcs",
        description="Set of 3 Buddha statues: pig, monk, peacock",
        pass_threshold=1.0
    )

    # Example: Add components
    manager.add_component_definition(
        product_id=product_id,
        component_name="pig",
        component_type="object",
        roi={"x": 180, "y": 180, "width": 180, "height": 270},
        position_label="left",
        tolerance=50,
        min_confidence=0.8,
        is_critical=True
    )

    manager.add_component_definition(
        product_id=product_id,
        component_name="monk",
        component_type="object",
        roi={"x": 340, "y": 180, "width": 180, "height": 290},
        position_label="center",
        tolerance=50,
        min_confidence=0.8,
        is_critical=True
    )

    manager.add_component_definition(
        product_id=product_id,
        component_name="peacock",
        component_type="object",
        roi={"x": 480, "y": 80, "width": 320, "height": 440},
        position_label="right",
        tolerance=50,
        min_confidence=0.8,
        is_critical=True
    )

    # List products
    print("\nProducts:")
    products = manager.list_products()
    for p in products:
        print(f"  • {p['name']} ({p['component_count']} components)")

    # List components
    print(f"\nComponents for {products[0]['name']}:")
    components = manager.get_product_components(product_id)
    for c in components:
        print(f"  • {c['name']} ({c['position']}) - ROI: {c['roi']}")

    print("\n✅ Component Definition Manager ready!")
