"""
History Manager for Dual Mode Inspection System
Manages SQLite database for storing inspection history
Supports both Capture and Realtime mode results
"""
import sqlite3
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np


class HistoryManager:
    """Manage inspection history with SQLite database"""

    def __init__(self, db_path="inspection_history.db", image_dir="history_images"):
        self.db_path = db_path
        self.image_dir = Path(image_dir)
        self.image_dir.mkdir(exist_ok=True)
        self.init_database()

    def init_database(self):
        """Initialize database and create tables if not exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inspections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                camera_id TEXT,
                product_name TEXT,
                result TEXT,
                mode TEXT,
                found_count INTEGER DEFAULT 0,
                total_expected INTEGER DEFAULT 0,
                missing_parts TEXT,
                inference_time_ms REAL DEFAULT 0,
                image_path TEXT,
                json_data TEXT
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp
            ON inspections(timestamp DESC)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_camera_id
            ON inspections(camera_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_result
            ON inspections(result)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_product_name
            ON inspections(product_name)
        """)

        conn.commit()
        conn.close()
        print("History database initialized")

    def save_inspection(self, data, annotated_frame=None):
        """
        Save inspection result to database

        Args:
            data: dict with inspection results from InspectionController
            annotated_frame: numpy array (BGR) of annotated image, or QPixmap

        Returns:
            int: ID of saved record
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        camera_id = str(data.get("camera_id", ""))
        product_name = data.get("product_name", "")
        result = data.get("result", "unknown").lower()
        mode = data.get("mode", "capture")
        found_count = data.get("found_count", 0)
        total_expected = data.get("total_expected", 0)
        missing_parts = data.get("missing_parts", [])
        inference_time_ms = data.get("inference_time_ms", 0)

        # Save image
        image_path = None
        if annotated_frame is not None:
            ts_str = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            filename = f"{ts_str}_{camera_id}.jpg"
            image_path = str(self.image_dir / filename)

            if isinstance(annotated_frame, np.ndarray):
                cv2.imwrite(image_path, annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            else:
                # QPixmap fallback
                try:
                    annotated_frame.save(image_path, "JPG", 95)
                except Exception:
                    image_path = None

        missing_json = json.dumps(missing_parts, ensure_ascii=False) if missing_parts else "[]"

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO inspections
            (timestamp, camera_id, product_name, result, mode,
             found_count, total_expected, missing_parts,
             inference_time_ms, image_path, json_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp,
            camera_id,
            product_name,
            result,
            mode,
            found_count,
            total_expected,
            missing_json,
            inference_time_ms,
            image_path,
            json.dumps(data, ensure_ascii=False, default=str)
        ))

        record_id = cursor.lastrowid
        conn.commit()
        conn.close()

        print(f"Saved inspection #{record_id}: {product_name} - {result} ({mode})")
        return record_id

    def get_inspections(self, limit=100, offset=0, camera_id=None,
                       product_name=None, result=None, mode=None,
                       date_from=None, date_to=None):
        """Query inspections with filters"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM inspections WHERE 1=1"
        params = []

        if camera_id:
            query += " AND camera_id = ?"
            params.append(camera_id)

        if product_name:
            query += " AND product_name = ?"
            params.append(product_name)

        if result:
            query += " AND result = ?"
            params.append(result)

        if mode:
            query += " AND mode = ?"
            params.append(mode)

        if date_from:
            query += " AND date(timestamp) >= date(?)"
            params.append(date_from)

        if date_to:
            query += " AND date(timestamp) <= date(?)"
            params.append(date_to)

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_inspection_by_id(self, record_id):
        """Get single inspection by ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM inspections WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def get_total_count(self, camera_id=None, product_name=None,
                       result=None, mode=None,
                       date_from=None, date_to=None):
        """Get total count of inspections with filters"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT COUNT(*) FROM inspections WHERE 1=1"
        params = []

        if camera_id:
            query += " AND camera_id = ?"
            params.append(camera_id)

        if product_name:
            query += " AND product_name = ?"
            params.append(product_name)

        if result:
            query += " AND result = ?"
            params.append(result)

        if mode:
            query += " AND mode = ?"
            params.append(mode)

        if date_from:
            query += " AND date(timestamp) >= date(?)"
            params.append(date_from)

        if date_to:
            query += " AND date(timestamp) <= date(?)"
            params.append(date_to)

        cursor.execute(query, params)
        count = cursor.fetchone()[0]
        conn.close()

        return count

    def delete_inspection(self, record_id):
        """Delete inspection and its image"""
        record = self.get_inspection_by_id(record_id)
        if not record:
            return False

        if record["image_path"] and os.path.exists(record["image_path"]):
            try:
                os.remove(record["image_path"])
            except Exception as e:
                print(f"Failed to delete image: {e}")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM inspections WHERE id = ?", (record_id,))
        conn.commit()
        conn.close()

        return True

    def cleanup_old_records(self, days=30):
        """Delete records older than specified days"""
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, image_path FROM inspections
            WHERE date(timestamp) < date(?)
        """, (cutoff_date,))
        old_records = cursor.fetchall()

        for record in old_records:
            if record["image_path"] and os.path.exists(record["image_path"]):
                try:
                    os.remove(record["image_path"])
                except Exception:
                    pass

        cursor.execute("""
            DELETE FROM inspections WHERE date(timestamp) < date(?)
        """, (cutoff_date,))

        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()

        print(f"Cleaned up {deleted_count} records older than {days} days")
        return deleted_count

    def export_to_csv(self, output_path, camera_id=None, product_name=None,
                     result=None, mode=None, date_from=None, date_to=None):
        """Export inspections to CSV file"""
        import csv

        records = self.get_inspections(
            limit=10000,
            camera_id=camera_id,
            product_name=product_name,
            result=result,
            mode=mode,
            date_from=date_from,
            date_to=date_to
        )

        if not records:
            return 0

        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'id', 'timestamp', 'camera_id', 'product_name', 'result',
                'mode', 'found_count', 'total_expected', 'missing_parts',
                'inference_time_ms', 'image_path'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for record in records:
                row = {key: record.get(key, '') for key in fieldnames}
                writer.writerow(row)

        print(f"Exported {len(records)} records to {output_path}")
        return len(records)

    def get_statistics(self):
        """Get statistics about inspections"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM inspections")
        total = cursor.fetchone()[0]

        cursor.execute("""
            SELECT result, COUNT(*) FROM inspections
            GROUP BY result
        """)
        result_counts = dict(cursor.fetchall())

        cursor.execute("""
            SELECT camera_id, COUNT(*) FROM inspections
            WHERE camera_id IS NOT NULL AND camera_id != ''
            GROUP BY camera_id
        """)
        camera_counts = dict(cursor.fetchall())

        cursor.execute("""
            SELECT product_name, COUNT(*) FROM inspections
            WHERE product_name IS NOT NULL AND product_name != ''
            GROUP BY product_name
        """)
        product_counts = dict(cursor.fetchall())

        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("""
            SELECT COUNT(*) FROM inspections
            WHERE date(timestamp) = date(?)
        """, (today,))
        today_count = cursor.fetchone()[0]

        conn.close()

        return {
            "total": total,
            "pass": result_counts.get("pass", 0),
            "fail": result_counts.get("fail", 0),
            "cameras": camera_counts,
            "products": product_counts,
            "today": today_count
        }
