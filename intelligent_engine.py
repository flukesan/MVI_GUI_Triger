"""
Intelligent AI Engine with Reasoning (Level 1)
Provides:
- Query Understanding (เข้าใจคำถามลึกขึ้น)
- Chain-of-Thought Reasoning (คิดทีละขั้นตอน)
- Evidence-based Answers (ตอบด้วยหลักฐาน)
- Causal Analysis (หาสาเหตุปัญหา)
"""

import json
from datetime import datetime


class IntelligentAIEngine:
    """AI Engine ที่ชาญฉลาดและให้เหตุผล"""

    def __init__(self, ai_agent, db_agent, doc_rag=None):
        self.ai_agent = ai_agent
        self.db_agent = db_agent
        self.doc_rag = doc_rag
        self.conversation_history = []

        print("✓ Intelligent AI Engine initialized")
        print("  → Query Understanding: enabled")
        print("  → Chain-of-Thought: enabled")
        print("  → Evidence-based reasoning: enabled")

    def process_query(self, query):
        """ประมวลผลคำถามอย่างชาญฉลาด"""

        print(f"\n{'='*60}")
        print(f"🤔 Processing: {query}")
        print(f"{'='*60}")

        # Step 1: Understand query intent
        understanding = self._understand_query(query)
        print(f"🔍 Intent detected: {understanding['intent']}")
        print(f"📊 Complexity: {understanding['complexity']}")

        # Step 2: Gather evidence
        print(f"📚 Gathering evidence...")
        evidence = self._gather_evidence(query, understanding)

        # Step 3: Reason and answer
        print(f"🧠 Reasoning...")
        answer = self._reason_and_answer(query, understanding, evidence)

        # Step 4: Store history
        self.conversation_history.append({
            'query': query,
            'understanding': understanding,
            'answer': answer,
            'timestamp': datetime.now().isoformat()
        })

        print(f"✅ Answer generated\n")

        return answer

    def _understand_query(self, query):
        """เข้าใจคำถามและระบุ intent"""

        # Intent detection with Thai + English keywords
        intent_keywords = {
            'troubleshoot': [
                'ทำไม', 'why', 'สาเหตุ', 'cause', 'ปัญหา', 'problem',
                'เกิดอะไร', 'what happened', 'แก้ไข', 'fix', 'wrong'
            ],
            'analyze': [
                'วิเคราะห์', 'analyze', 'แนวโน้ม', 'trend', 'เปรียบเทียบ', 'compare',
                'ประเมิน', 'evaluate', 'สถานการณ์', 'situation'
            ],
            'count': [
                'กี่', 'how many', 'จำนวน', 'count', 'มี.*ครั้ง', 'มี.*รายการ'
            ],
            'detail': [
                'รายละเอียด', 'detail', 'แสดง', 'show', 'list', 'ทั้งหมด', 'all'
            ],
            'latest': [
                'ล่าสุด', 'latest', 'recent', 'เมื่อกี้', 'just now', 'อันล่าสุด'
            ],
            'summary': [
                'สรุป', 'summary', 'overview', 'ภาพรวม', 'ทั้งหมด', 'วันนี้'
            ]
        }

        # Detect intent
        detected_intent = 'general'
        max_matches = 0

        query_lower = query.lower()
        for intent, keywords in intent_keywords.items():
            matches = sum(1 for kw in keywords if kw in query_lower)
            if matches > max_matches:
                max_matches = matches
                detected_intent = intent

        # Detect complexity
        complexity = 'simple'
        if detected_intent in ['troubleshoot', 'analyze']:
            complexity = 'complex'
        elif detected_intent in ['summary']:
            complexity = 'medium'

        # Extract entities (basic)
        entities = {
            'time_period': 'today' if any(kw in query_lower for kw in ['วันนี้', 'today']) else None,
            'result_type': 'fail' if any(kw in query_lower for kw in ['fail', 'ng', 'ไม่ผ่าน']) else
                          'pass' if any(kw in query_lower for kw in ['pass', 'ok', 'ผ่าน']) else None,
            'device': self._extract_device(query)
        }

        return {
            'intent': detected_intent,
            'complexity': complexity,
            'entities': entities,
            'requires_reasoning': complexity in ['medium', 'complex'],
            'original_query': query
        }

    def _extract_device(self, query):
        """Extract device name from query"""
        common_devices = ['Basler_GigE', 'Watashi_cam', 'Camera_03']

        for device in common_devices:
            if device.lower() in query.lower() or device.replace('_', ' ').lower() in query.lower():
                return device

        return None

    def _gather_evidence(self, query, understanding):
        """รวบรวมหลักฐานจากแหล่งต่างๆ"""

        evidence = {
            'database_results': None,
            'statistics': None,
            'documents': None,
            'metadata': {}
        }

        if not self.db_agent:
            return evidence

        try:
            intent = understanding['intent']
            entities = understanding['entities']

            # Gather based on intent
            if intent == 'troubleshoot':
                # สำหรับการแก้ปัญหา: ต้องการ fail data + context
                evidence['fail_analysis'] = self._get_fail_analysis(entities)
                evidence['recent_context'] = self.db_agent.get_recent_inspections(20, period="today")
                evidence['statistics'] = self.db_agent.get_statistics("today")

            elif intent == 'analyze' or intent == 'summary':
                # สำหรับการวิเคราะห์: สถิติ + รายละเอียด
                evidence['statistics'] = self.db_agent.get_statistics("today")
                evidence['details'] = self.db_agent.get_recent_inspections(15, period="today")

            elif intent == 'detail' or intent == 'latest':
                # สำหรับดูรายละเอียด
                evidence['inspections'] = self.db_agent.get_recent_inspections(10, period="today")

            elif intent == 'count':
                # สำหรับนับจำนวน
                evidence['statistics'] = self.db_agent.get_statistics("today")

            else:
                # General query
                evidence['inspections'] = self.db_agent.get_recent_inspections(10)

            # Document search for troubleshooting
            if intent == 'troubleshoot' and self.doc_rag and self.doc_rag.get_document_count() > 0:
                try:
                    evidence['documents'] = self.doc_rag.search(query, top_k=3)
                except:
                    pass

        except Exception as e:
            print(f"⚠️ Error gathering evidence: {e}")
            evidence['error'] = str(e)

        return evidence

    def _get_fail_analysis(self, entities):
        """วิเคราะห์ FAIL อย่างละเอียด"""

        try:
            cursor = self.db_agent.db.cursor()

            # Build WHERE clause based on entities
            conditions = ["date(timestamp) = date('now')", "result = 'fail'"]

            if entities.get('device'):
                conditions.append(f"device_id = '{entities['device']}'")

            where_clause = " AND ".join(conditions)

            # Query for fail analysis
            cursor.execute(f"""
                SELECT
                    device_id,
                    station,
                    COUNT(*) as fail_count,
                    MIN(timestamp) as first_fail,
                    MAX(timestamp) as last_fail,
                    GROUP_CONCAT(timestamp, '|||') as all_timestamps
                FROM inspections
                WHERE {where_clause}
                GROUP BY device_id, station
                ORDER BY fail_count DESC
            """)

            columns = ['device_id', 'station', 'fail_count', 'first_fail', 'last_fail', 'all_timestamps']
            results = []
            for row in cursor.fetchall():
                record = dict(zip(columns, row))
                # Parse timestamps
                if record['all_timestamps']:
                    record['timestamps'] = record['all_timestamps'].split('|||')
                    del record['all_timestamps']
                results.append(record)

            return results

        except Exception as e:
            print(f"⚠️ Error in fail analysis: {e}")
            return []

    def _reason_and_answer(self, query, understanding, evidence):
        """ให้เหตุผลและตอบคำถาม"""

        if not understanding['requires_reasoning']:
            # Simple answer - format data directly
            return self._format_simple_answer(query, understanding, evidence)

        # Complex reasoning based on intent
        if understanding['intent'] == 'troubleshoot':
            return self._troubleshoot_reasoning(query, evidence)

        elif understanding['intent'] == 'analyze' or understanding['intent'] == 'summary':
            return self._analytical_reasoning(query, evidence)

        else:
            # Fallback to simple answer
            return self._format_simple_answer(query, understanding, evidence)

    def _format_simple_answer(self, query, understanding, evidence):
        """จัดรูปแบบคำตอบแบบง่าย"""

        intent = understanding['intent']

        if intent == 'count':
            stats = evidence.get('statistics', {})
            if stats:
                total = stats.get('total', 0)
                pass_count = stats.get('pass', 0)
                fail_count = stats.get('fail', 0)

                return f"""📊 **จำนวนการตรวจสอบวันนี้**

• ทั้งหมด: **{total} รายการ**
  ├─ ✅ PASS: {pass_count} รายการ
  └─ ❌ FAIL: {fail_count} รายการ

📈 Pass rate: **{stats.get('pass_rate', 0):.1f}%**"""

        elif intent == 'detail' or intent == 'latest':
            inspections = evidence.get('inspections', [])
            if inspections:
                result_lines = []
                for idx, insp in enumerate(inspections[:10], 1):
                    icon = "✅" if insp['result'] == 'pass' else "❌"
                    time_str = self._format_timestamp(insp['timestamp'])
                    result_lines.append(
                        f"{idx}. {icon} [{time_str}] {insp['device_id']} @ {insp['station']} → {insp['result'].upper()}"
                    )

                return f"""📋 **รายละเอียดการตรวจสอบ** ({len(inspections)} รายการ)\n\n""" + "\n".join(result_lines)

        # Fallback: use AI to explain
        prompt = f"""คำถาม: {query}

ข้อมูล:
{json.dumps(evidence, ensure_ascii=False, indent=2, default=str)}

โปรดตอบคำถามจากข้อมูลที่ให้มา (ใช้ emoji และจัดรูปแบบให้อ่านง่าย):"""

        return self.ai_agent.chat(prompt)

    def _troubleshoot_reasoning(self, query, evidence):
        """วิเคราะห์หาสาเหตุปัญหาแบบมีเหตุผล"""

        prompt = f"""คุณเป็นผู้เชี่ยวชาญด้าน Machine Vision Inspection กำลังช่วยวิเคราะห์ปัญหา

คำถาม: {query}

ข้อมูล FAIL ที่พบ:
{json.dumps(evidence.get('fail_analysis', []), ensure_ascii=False, indent=2, default=str)}

สถิติวันนี้:
{json.dumps(evidence.get('statistics', {}), ensure_ascii=False, indent=2)}

การตรวจสอบล่าสุด (10 รายการ):
{json.dumps(evidence.get('recent_context', [])[:10], ensure_ascii=False, indent=2, default=str)}

โปรดวิเคราะห์หาสาเหตุอย่างมีเหตุผล ทีละขั้นตอน:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 **ขั้นที่ 1: วิเคราะห์ข้อมูล FAIL**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[ดูข้อมูล: เครื่องไหน FAIL บ่อย? สถานีไหน? กี่ครั้ง? เวลาไหนบ้าง?]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧩 **ขั้นที่ 2: หา Pattern (รูปแบบ)**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[มี pattern หรือไม่?]
• FAIL จากเครื่องเดียว หรือหลายเครื่อง?
• FAIL ที่สถานีเดียว หรือหลายสถานี?
• FAIL ติดต่อกัน หรือห่างๆ?
• เครื่องอื่นๆ ผ่านหรือไม่?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 **ขั้นที่ 3: สรุปสาเหตุที่เป็นไปได้**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[จากการวิเคราะห์ข้างต้น สรุปสาเหตุที่เป็นไปได้:]
• สาเหตุที่ 1: [อธิบาย] - เพราะ [เหตุผลจากข้อมูล]
• สาเหตุที่ 2: [อธิบาย] - เพราะ [เหตุผลจากข้อมูล]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 **ขั้นที่ 4: ข้อเสนอแนะ**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. ควรตรวจสอบ: [อะไร?]
2. ควรทดสอบ: [อะไร?]
3. ถ้าเป็น [สาเหตุ X] ให้: [ทำอย่างไร?]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**สำคัญ:** ให้เหตุผลจากข้อมูลจริงเท่านั้น ห้ามสมมติหรือแต่งข้อมูล

วิเคราะห์:"""

        return self.ai_agent.chat(prompt)

    def _analytical_reasoning(self, query, evidence):
        """วิเคราะห์เชิงลึกแบบมีเหตุผล"""

        prompt = f"""คุณเป็นผู้เชี่ยวชาญด้าน Machine Vision Inspection กำลังวิเคราะห์ผลการตรวจสอบ

คำถาม: {query}

สถิติวันนี้:
{json.dumps(evidence.get('statistics', {}), ensure_ascii=False, indent=2)}

รายละเอียดการตรวจสอบ:
{json.dumps(evidence.get('details', []), ensure_ascii=False, indent=2, default=str)}

โปรดวิเคราะห์อย่างมีเหตุผล:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 **สรุปภาพรวม**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• จำนวนการตรวจสอบทั้งหมด: [X รายการ]
• ผลลัพธ์: PASS [X] รายการ, FAIL [X] รายการ
• Pass rate: [X%] ([เปรียบเทียบกับมาตรฐาน 95%])
• ช่วงเวลา: [เวลาแรก - เวลาสุดท้าย]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 **รายละเอียดที่สำคัญ**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[แสดงรายละเอียด 5-10 รายการล่าสุด พร้อมเวลาและ device]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 **การวิเคราะห์และข้อสังเกต**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[วิเคราะห์:]
• เครื่องไหนตรวจมากที่สุด? PASS/FAIL อัตราส่วนเท่าไหร่?
• สถานีไหนมีปัญหา?
• มี pattern อะไรน่าสังเกต?
• แนวโน้มดีขึ้น/แย่ลง/คงที่?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💭 **ประเมินสถานการณ์**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
สถานะ: [🟢 ดี / 🟡 ปานกลาง / 🔴 ต้องปรับปรุง]

เหตุผล: [อธิบายจากข้อมูล]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ **ข้อเสนอแนะ**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. [คำแนะนำที่ 1]
2. [คำแนะนำที่ 2]
3. [คำแนะนำที่ 3]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**สำคัญ:** วิเคราะห์จากข้อมูลจริงเท่านั้น แสดงเวลาและ device ให้ชัดเจน

วิเคราะห์:"""

        return self.ai_agent.chat(prompt)

    def _format_timestamp(self, timestamp):
        """Format timestamp to readable format"""
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return dt.strftime("%H:%M:%S")
        except:
            return timestamp[:8] if len(timestamp) > 8 else timestamp

    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []


# Example usage
if __name__ == "__main__":
    print("Intelligent AI Engine - Level 1")
    print("Features:")
    print("  ✓ Query Understanding")
    print("  ✓ Chain-of-Thought Reasoning")
    print("  ✓ Evidence-based Answers")
    print("  ✓ Causal Analysis")
