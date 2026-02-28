"""
Database Query Agent
Allows AI to query database using natural language
"""

import sqlite3
import json
from datetime import datetime, timedelta


class DatabaseAgent:
    """AI Agent with database access"""

    def __init__(self, ai_agent, db_connection):
        self.ai_agent = ai_agent
        self.db = db_connection

    def get_database_schema(self):
        """Get database structure"""
        cursor = self.db.cursor()

        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()

        schema = "Database Tables:\n\n"

        for table in tables:
            table_name = table[0]
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()

            schema += f"Table: {table_name}\n"
            schema += "Columns:\n"
            for col in columns:
                col_name = col[1]
                col_type = col[2]
                schema += f"  - {col_name} ({col_type})\n"
            schema += "\n"

        return schema

    def _get_sample_data(self, limit=3):
        """Get sample data from database for AI context"""
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT id, timestamp, device_id, result, station
                FROM inspections
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))

            columns = ['id', 'timestamp', 'device_id', 'result', 'station']
            samples = []
            for row in cursor.fetchall():
                samples.append(dict(zip(columns, row)))

            if samples:
                return json.dumps(samples, ensure_ascii=False, indent=2)
            else:
                return "No data in database yet"
        except:
            return "No sample data available"

    def query_database_nl(self, natural_language_query):
        """Convert natural language → SQL → Execute → Return results"""

        # 1. Get database schema
        schema = self.get_database_schema()

        # 2. Get sample data
        sample_data = self._get_sample_data()

        # 3. Ask AI to generate SQL
        prompt = f"""คุณเป็น SQL Expert. แปลงคำถามต่อไปนี้เป็น SQLite query:

คำถาม: {natural_language_query}

Database Schema:
{schema}

ตัวอย่างข้อมูล:
{sample_data}

กฎสำคัญ:
- ใช้ SQLite syntax
- **ต้อง SELECT columns ที่เกี่ยวข้อง ไม่ใช่แค่ COUNT(*)**
- เมื่อถามเกี่ยวกับรายละเอียด ต้อง SELECT: id, timestamp, device_id, result, station
- เรียงลำดับด้วย ORDER BY timestamp DESC
- ใช้ LIMIT (max 20) เพื่อไม่ให้ข้อมูลเยอะเกิน
- วันที่: ใช้ date(timestamp) = date('now') สำหรับวันนี้
- ตอบเฉพาะ SQL query เท่านั้น ห้ามอธิบาย
- ห้ามใส่ ```sql หรือ markdown

ตัวอย่าง:
คำถาม: "มีการตรวจสอบกี่ครั้งวันนี้"
SQL: SELECT COUNT(*) FROM inspections WHERE date(timestamp) = date('now')

คำถาม: "แสดงรายละเอียดการตรวจสอบวันนี้"
SQL: SELECT id, timestamp, device_id, result, station FROM inspections WHERE date(timestamp) = date('now') ORDER BY timestamp DESC LIMIT 10

คำถาม: "อันแรก" หรือ "ล่าสุด"
SQL: SELECT id, timestamp, device_id, result, station FROM inspections ORDER BY timestamp DESC LIMIT 1

SQL query:"""

        sql_query = self.ai_agent.chat(prompt)

        # Clean SQL (remove any markdown formatting)
        sql_query = sql_query.replace("```sql", "").replace("```", "").strip()
        # Remove any explanatory text (keep only SQL)
        lines = sql_query.split("\n")
        sql_lines = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("--"):
                # Check if line looks like SQL
                sql_keywords = ["SELECT", "INSERT", "UPDATE", "DELETE", "FROM", "WHERE", "GROUP", "ORDER", "LIMIT"]
                if any(keyword in line.upper() for keyword in sql_keywords):
                    sql_lines.append(line)
        sql_query = " ".join(sql_lines)

        print(f"🔍 Generated SQL: {sql_query}")

        # 3. Execute SQL
        try:
            cursor = self.db.cursor()
            cursor.execute(sql_query)
            results = cursor.fetchall()

            # Get column names
            column_names = [description[0] for description in cursor.description] if cursor.description else []

            # Format results
            if not results:
                return "ไม่พบข้อมูล"

            # 4. Ask AI to explain results
            results_formatted = []
            for row in results:
                row_dict = dict(zip(column_names, row))
                results_formatted.append(row_dict)

            explain_prompt = f"""คำถาม: {natural_language_query}

ผลลัพธ์จาก database:
{json.dumps(results_formatted, ensure_ascii=False, indent=2)}

โปรดสรุปผลลัพธ์ในรูปแบบที่เข้าใจง่าย และใส่ emoji:"""

            explanation = self.ai_agent.chat(explain_prompt)

            # Add SQL query reference
            explanation += f"\n\n🔍 SQL Query ที่ใช้:\n```sql\n{sql_query}\n```"

            return explanation

        except sqlite3.Error as e:
            error_msg = f"❌ SQL Error: {str(e)}\n\n🔍 SQL ที่สร้าง:\n{sql_query}"

            # Ask AI to fix the SQL
            fix_prompt = f"""SQL query นี้มี error:

Query: {sql_query}
Error: {str(e)}

Database Schema:
{schema}

โปรดแก้ไข SQL query และอธิบายว่าผิดตรงไหน:"""

            suggestion = self.ai_agent.chat(fix_prompt)
            return error_msg + f"\n\n💡 คำแนะนำ:\n{suggestion}"

    def get_statistics(self, period="today"):
        """Get statistics for a period"""
        cursor = self.db.cursor()

        if period == "today":
            date_filter = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN result = 'pass' THEN 1 ELSE 0 END) as pass_count,
                    SUM(CASE WHEN result = 'fail' THEN 1 ELSE 0 END) as fail_count
                FROM inspections
                WHERE date(timestamp) = ?
            """, (date_filter,))
        elif period == "week":
            week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN result = 'pass' THEN 1 ELSE 0 END) as pass_count,
                    SUM(CASE WHEN result = 'fail' THEN 1 ELSE 0 END) as fail_count
                FROM inspections
                WHERE date(timestamp) >= ?
            """, (week_ago,))
        else:
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN result = 'pass' THEN 1 ELSE 0 END) as pass_count,
                    SUM(CASE WHEN result = 'fail' THEN 1 ELSE 0 END) as fail_count
                FROM inspections
            """)

        result = cursor.fetchone()
        return {
            "total": result[0],
            "pass": result[1] or 0,
            "fail": result[2] or 0,
            "pass_rate": (result[1] or 0) / result[0] * 100 if result[0] > 0 else 0
        }

    def get_top_defects(self, limit=5):
        """Get most common defects (placeholder - needs defect tracking)"""
        # This would require parsing Rule Results from inspections
        # For now, return device statistics
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT device_id, result, COUNT(*) as count
            FROM inspections
            WHERE device_id != ''
            GROUP BY device_id, result
            ORDER BY count DESC
            LIMIT ?
        """, (limit,))

        return cursor.fetchall()

    def get_recent_inspections(self, limit=10, period="today"):
        """Get recent inspections with full details"""
        cursor = self.db.cursor()

        if period == "today":
            date_filter = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("""
                SELECT id, timestamp, device_id, image_id, result, station
                FROM inspections
                WHERE date(timestamp) = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (date_filter, limit))
        else:
            cursor.execute("""
                SELECT id, timestamp, device_id, image_id, result, station
                FROM inspections
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))

        columns = ['id', 'timestamp', 'device_id', 'image_id', 'result', 'station']
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))

        return results

    def analyze_with_ai(self, query_type="summary"):
        """Get AI analysis of database data"""
        if query_type == "summary":
            stats = self.get_statistics("today")
            recent = self.get_recent_inspections(limit=10, period="today")

            prompt = f"""วิเคราะห์สถิติการตรวจสอบวันนี้:

สถิติรวม:
{json.dumps(stats, ensure_ascii=False, indent=2)}

รายละเอียดการตรวจสอบล่าสุด ({len(recent)} รายการ):
{json.dumps(recent, ensure_ascii=False, indent=2)}

โปรดให้:
1. สรุปภาพรวม (จำนวน pass/fail, pass rate)
2. รายละเอียดการตรวจสอบแต่ละครั้ง (เวลา, device, ผล)
3. ประเมินสถานการณ์ (ดี/ปานกลาง/ต้องปรับปรุง)
4. ข้อเสนอแนะ

ใช้ emoji และจัดรูปแบบให้อ่านง่าย แสดงเวลาและ device ให้ชัดเจน:"""

            return self.ai_agent.chat(prompt)

        elif query_type == "devices":
            top_devices = self.get_top_defects(10)
            prompt = f"""วิเคราะห์ข้อมูล devices และผลการตรวจสอบ:

{json.dumps(top_devices, ensure_ascii=False, indent=2)}

รูปแบบข้อมูล: (device_id, result, count)

โปรดวิเคราะห์:
1. Device ไหนมีปัญหามากที่สุด?
2. มี pattern ที่น่าสังเกตไหม?
3. ข้อเสนอแนะ"""

            return self.ai_agent.chat(prompt)

        return "ไม่รู้จัก query_type นี้"


# Example usage
if __name__ == "__main__":
    import sqlite3
    from ai_agent import AIAgent

    # Test with a database
    db = sqlite3.connect("inspection_history.db")
    agent = AIAgent()
    db_agent = DatabaseAgent(agent, db)

    print("\n=== Testing Database Agent ===\n")

    # Show schema
    print("Database Schema:")
    print(db_agent.get_database_schema())

    # Test natural language query
    if agent.is_available():
        print("\n--- Test Query ---")
        result = db_agent.query_database_nl("มี FAIL กี่ครั้งวันนี้?")
        print(result)

        print("\n--- Statistics ---")
        stats = db_agent.get_statistics("today")
        print(json.dumps(stats, indent=2, ensure_ascii=False))

        print("\n--- AI Analysis ---")
        analysis = db_agent.analyze_with_ai("summary")
        print(analysis)
