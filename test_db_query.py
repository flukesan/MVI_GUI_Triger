#!/usr/bin/env python3
"""
Test Database Query without AI (to show SQL execution)
"""

import sqlite3
import json
from datetime import datetime

# Connect to database
db = sqlite3.connect("inspection_history.db")
cursor = db.cursor()

print("=" * 60)
print("🧪 Testing Database Queries (Without AI)")
print("=" * 60)

# Test 1: Show all inspections today with details
print("\n1️⃣ Test: แสดงรายละเอียดการตรวจสอบวันนี้")
print("-" * 60)

date_filter = datetime.now().strftime("%Y-%m-%d")
sql = f"""
SELECT id, timestamp, device_id, result, station
FROM inspections
WHERE date(timestamp) = '{date_filter}'
ORDER BY timestamp DESC
LIMIT 10
"""

print(f"📝 SQL Query:")
print(sql)
print()

cursor.execute(sql)
results = cursor.fetchall()
columns = ['id', 'timestamp', 'device_id', 'result', 'station']

print(f"📊 Results ({len(results)} records):")
print()

for row in results:
    record = dict(zip(columns, row))
    # Format timestamp to be more readable
    timestamp = record['timestamp']
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        time_str = dt.strftime("%H:%M:%S")
    except:
        time_str = timestamp

    result_icon = "✅" if record['result'] == 'pass' else "❌"
    print(f"  {result_icon} [{time_str}] {record['device_id']} → {record['result'].upper()} @ {record['station']}")

print()

# Test 2: FAIL cases today
print("\n2️⃣ Test: FAIL เมื่อไหร่บ้างวันนี้")
print("-" * 60)

sql = f"""
SELECT id, timestamp, device_id, result, station
FROM inspections
WHERE date(timestamp) = '{date_filter}' AND result = 'fail'
ORDER BY timestamp DESC
"""

print(f"📝 SQL Query:")
print(sql)
print()

cursor.execute(sql)
results = cursor.fetchall()

print(f"📊 Results ({len(results)} FAIL records):")
print()

if results:
    for row in results:
        record = dict(zip(columns, row))
        timestamp = record['timestamp']
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            time_str = dt.strftime("%H:%M:%S น.")
        except:
            time_str = timestamp

        print(f"  ❌ FAIL ที่ {time_str} - เครื่อง: {record['device_id']} @ Station: {record['station']}")
else:
    print("  ✅ ไม่มี FAIL วันนี้!")

print()

# Test 3: Latest inspection
print("\n3️⃣ Test: อันล่าสุดตรวจเมื่อไหร่ เครื่องไหน")
print("-" * 60)

sql = """
SELECT id, timestamp, device_id, result, station
FROM inspections
ORDER BY timestamp DESC
LIMIT 1
"""

print(f"📝 SQL Query:")
print(sql)
print()

cursor.execute(sql)
result = cursor.fetchone()

if result:
    record = dict(zip(columns, result))
    timestamp = record['timestamp']
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        time_str = timestamp

    result_icon = "✅" if record['result'] == 'pass' else "❌"

    print(f"📊 Latest Inspection:")
    print(f"  {result_icon} เวลา: {time_str}")
    print(f"  📱 เครื่อง: {record['device_id']}")
    print(f"  🏭 Station: {record['station']}")
    print(f"  📋 ผลลัพธ์: {record['result'].upper()}")

print()
print("=" * 60)
print("✨ Test complete!")
print("=" * 60)
print()
print("💡 This is what Database Agent does:")
print("   1. Converts your question to SQL")
print("   2. Executes SQL on real database")
print("   3. Returns ACTUAL data (not fake/hallucinated)")
print("   4. AI explains the results in Thai")
print()

db.close()
