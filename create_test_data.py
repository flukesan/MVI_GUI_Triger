#!/usr/bin/env python3
"""
สร้างข้อมูลทดสอบใน database สำหรับทดสอบ AI
"""

import sqlite3
from datetime import datetime, timedelta
import random

# Connect to database
conn = sqlite3.connect('inspection_history.db')
cursor = conn.cursor()

# Create table if not exists
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

# Clear existing data
cursor.execute("DELETE FROM inspections")

# Sample data
devices = ["Watashi_cam", "Basler_GigE", "Camera_03"]
stations = ["STA_580", "STA_581", "STA_582"]
results = ["pass", "fail"]

print("สร้างข้อมูลทดสอบ...")

# Insert test data (last 7 days)
for days_ago in range(7):
    date = datetime.now() - timedelta(days=days_ago)

    # 5-10 inspections per day
    num_inspections = random.randint(5, 10)

    for i in range(num_inspections):
        timestamp = date.strftime("%Y-%m-%d %H:%M:%S")
        device = random.choice(devices)
        station = random.choice(stations)
        result = random.choices(results, weights=[0.7, 0.3])[0]  # 70% pass, 30% fail
        image_id = f"{int(date.timestamp())}_{i:03d}.jpg"

        cursor.execute("""
            INSERT INTO inspections (timestamp, device_id, image_id, result, station)
            VALUES (?, ?, ?, ?, ?)
        """, (timestamp, device, image_id, result, station))

    print(f"  ✓ Day {days_ago}: {num_inspections} inspections")

conn.commit()

# Show statistics
cursor.execute("SELECT COUNT(*) FROM inspections")
total = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM inspections WHERE result='pass'")
pass_count = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM inspections WHERE result='fail'")
fail_count = cursor.fetchone()[0]

print(f"\n📊 สรุป:")
print(f"  Total: {total}")
print(f"  Pass: {pass_count} ({pass_count/total*100:.1f}%)")
print(f"  Fail: {fail_count} ({fail_count/total*100:.1f}%)")

# Today's data
cursor.execute("""
    SELECT COUNT(*) FROM inspections
    WHERE date(timestamp) = date('now')
""")
today_count = cursor.fetchone()[0]
print(f"\n  Today: {today_count} inspections")

conn.close()

print("\n✅ สร้างข้อมูลทดสอบเสร็จสิ้น!")
