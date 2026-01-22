"""
History Manager for MVI Inspection Results
Manages SQLite database for storing inspection history
"""
import sqlite3
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import shutil


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

        # Create inspections table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inspections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                device_id TEXT,
                image_id TEXT,
                result TEXT,
                station TEXT,
                inspection_name TEXT,
                image_path TEXT,
                json_data TEXT,
                rule_results TEXT
            )
        """)

        # Create indexes for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp
            ON inspections(timestamp DESC)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_device_id
            ON inspections(device_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_result
            ON inspections(result)
        """)

        conn.commit()
        conn.close()
        print("✓ History database initialized")

    def save_inspection(self, data, image_pixmap=None):
        """
        Save inspection result to database

        Args:
            data: JSON data from MQTT message
            image_pixmap: QPixmap of the image with bounding boxes

        Returns:
            int: ID of saved record
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        device_id = data.get("Device ID", "")
        image_id = data.get("Image ID", "")
        result = data.get("Overall Result", data.get("result", "unknown")).lower()
        station = data.get("Station", "")
        inspection_name = data.get("Inspection name", "")

        # Save image if provided
        image_path = None
        if image_pixmap and not image_pixmap.isNull():
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{device_id}.jpg"
            image_path = str(self.image_dir / filename)
            image_pixmap.save(image_path, "JPG", quality=95)
            print(f"✓ Saved image: {image_path}")

        # Extract rule results
        rule_results = data.get("Rule Results", [])
        rule_results_json = json.dumps(rule_results) if rule_results else None

        # Save to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO inspections
            (timestamp, device_id, image_id, result, station, inspection_name,
             image_path, json_data, rule_results)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp,
            device_id,
            image_id,
            result,
            station,
            inspection_name,
            image_path,
            json.dumps(data),
            rule_results_json
        ))

        record_id = cursor.lastrowid
        conn.commit()
        conn.close()

        print(f"✓ Saved inspection #{record_id}: {device_id} - {result}")
        return record_id

    def get_inspections(self, limit=100, offset=0, device_id=None,
                       result=None, date_from=None, date_to=None):
        """
        Query inspections with filters

        Args:
            limit: Number of records to return
            offset: Offset for pagination
            device_id: Filter by device ID
            result: Filter by result (pass/fail)
            date_from: Filter from date (YYYY-MM-DD)
            date_to: Filter to date (YYYY-MM-DD)

        Returns:
            list: List of inspection records
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        cursor = conn.cursor()

        query = "SELECT * FROM inspections WHERE 1=1"
        params = []

        if device_id:
            query += " AND device_id = ?"
            params.append(device_id)

        if result:
            query += " AND result = ?"
            params.append(result)

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

        # Convert to list of dicts
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

    def get_total_count(self, device_id=None, result=None,
                       date_from=None, date_to=None):
        """Get total count of inspections with filters"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT COUNT(*) FROM inspections WHERE 1=1"
        params = []

        if device_id:
            query += " AND device_id = ?"
            params.append(device_id)

        if result:
            query += " AND result = ?"
            params.append(result)

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
        # Get record first to delete image
        record = self.get_inspection_by_id(record_id)
        if not record:
            return False

        # Delete image file if exists
        if record["image_path"] and os.path.exists(record["image_path"]):
            try:
                os.remove(record["image_path"])
                print(f"✓ Deleted image: {record['image_path']}")
            except Exception as e:
                print(f"⚠️ Failed to delete image: {e}")

        # Delete from database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM inspections WHERE id = ?", (record_id,))
        conn.commit()
        conn.close()

        print(f"✓ Deleted inspection #{record_id}")
        return True

    def cleanup_old_records(self, days=30):
        """
        Delete records older than specified days

        Args:
            days: Keep records from last N days

        Returns:
            int: Number of deleted records
        """
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        # Get old records to delete their images
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, image_path FROM inspections
            WHERE date(timestamp) < date(?)
        """, (cutoff_date,))
        old_records = cursor.fetchall()

        # Delete images
        deleted_count = 0
        for record in old_records:
            if record["image_path"] and os.path.exists(record["image_path"]):
                try:
                    os.remove(record["image_path"])
                    deleted_count += 1
                except Exception as e:
                    print(f"⚠️ Failed to delete image: {e}")

        # Delete from database
        cursor.execute("""
            DELETE FROM inspections WHERE date(timestamp) < date(?)
        """, (cutoff_date,))

        deleted_db_count = cursor.rowcount
        conn.commit()
        conn.close()

        print(f"✓ Cleaned up {deleted_db_count} records older than {days} days")
        print(f"✓ Deleted {deleted_count} image files")

        return deleted_db_count

    def export_to_csv(self, output_path, device_id=None, result=None,
                     date_from=None, date_to=None):
        """
        Export inspections to CSV file

        Args:
            output_path: Path to save CSV file
            device_id: Filter by device ID
            result: Filter by result
            date_from: Filter from date
            date_to: Filter to date

        Returns:
            int: Number of exported records
        """
        import csv

        records = self.get_inspections(
            limit=10000,  # Export max 10000 records
            device_id=device_id,
            result=result,
            date_from=date_from,
            date_to=date_to
        )

        if not records:
            print("⚠️ No records to export")
            return 0

        # Write to CSV
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'id', 'timestamp', 'device_id', 'image_id', 'result',
                'station', 'inspection_name', 'image_path'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for record in records:
                # Write only selected fields (exclude large JSON)
                row = {key: record.get(key, '') for key in fieldnames}
                writer.writerow(row)

        print(f"✓ Exported {len(records)} records to {output_path}")
        return len(records)

    def get_statistics(self):
        """Get statistics about inspections"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total count
        cursor.execute("SELECT COUNT(*) FROM inspections")
        total = cursor.fetchone()[0]

        # Pass/Fail count
        cursor.execute("""
            SELECT result, COUNT(*) FROM inspections
            GROUP BY result
        """)
        result_counts = dict(cursor.fetchall())

        # Device counts
        cursor.execute("""
            SELECT device_id, COUNT(*) FROM inspections
            GROUP BY device_id
        """)
        device_counts = dict(cursor.fetchall())

        # Today's count
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
            "devices": device_counts,
            "today": today_count
        }
