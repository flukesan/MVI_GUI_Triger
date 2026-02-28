"""
Context Memory Manager (Level 2)
จัดการบริบทการสนทนา รองรับคำถามต่อเนื่อง
"""

import json
from datetime import datetime
from collections import deque


class ContextMemoryManager:
    """จัดการความจำและบริบทการสนทนา"""

    def __init__(self, short_term_size=10, max_context_length=4000):
        """
        Args:
            short_term_size: จำนวนข้อความที่เก็บใน short-term memory
            max_context_length: ความยาวสูงสุดของ context (characters)
        """
        self.short_term_memory = deque(maxlen=short_term_size)
        self.long_term_memory = []
        self.working_memory = {}  # สำหรับข้อมูลชั่วคราวของ session ปัจจุบัน
        self.max_context_length = max_context_length

        print("✓ Context Memory Manager initialized")
        print(f"  → Short-term memory: {short_term_size} messages")
        print(f"  → Max context length: {max_context_length} chars")

    def add_exchange(self, user_message, ai_response, metadata=None):
        """
        เพิ่มการสนทนาลงใน memory

        Args:
            user_message: ข้อความจากผู้ใช้
            ai_response: คำตอบจาก AI
            metadata: ข้อมูลเพิ่มเติม (intent, entities, etc.)
        """
        exchange = {
            'timestamp': datetime.now().isoformat(),
            'user': user_message,
            'ai': ai_response,
            'metadata': metadata or {}
        }

        self.short_term_memory.append(exchange)

        # อัพเดท working memory ด้วย entities ที่พบ
        if metadata and 'entities' in metadata:
            self._update_working_memory(metadata['entities'])

    def get_context(self, current_query=None):
        """
        ดึง context ที่เกี่ยวข้องสำหรับ query ปัจจุบัน

        Args:
            current_query: คำถามปัจจุบัน

        Returns:
            dict: context ที่รวบรวมแล้ว
        """
        context = {
            'recent_exchanges': list(self.short_term_memory)[-5:],  # 5 ล่าสุด
            'working_memory': self.working_memory.copy(),
            'summary': self._get_conversation_summary()
        }

        # ถ้ามี query และเป็นคำถามต่อเนื่อง ให้เพิ่ม reference entities
        if current_query and self._is_followup_question(current_query):
            context['referenced_entities'] = self._extract_referenced_entities()

        return context

    def _is_followup_question(self, query):
        """ตรวจสอบว่าเป็นคำถามต่อเนื่องหรือไม่"""
        followup_indicators = [
            # Thai
            'แล้ว', 'ล่ะ', 'อีก', 'ต่อ', 'เพิ่ม', 'ด้วย',
            'อันนั้น', 'อันนี้', 'มัน', 'ตัวนั้น', 'นั่น', 'นี่',
            'เหมือนกัน', 'เช่นกัน',
            # English
            'also', 'too', 'and', 'what about', 'how about',
            'that', 'this', 'it', 'them', 'those',
            'same', 'similar'
        ]

        query_lower = query.lower()
        return any(indicator in query_lower for indicator in followup_indicators)

    def _extract_referenced_entities(self):
        """ดึง entities จากการสนทนาก่อนหน้า"""
        entities = {
            'devices': set(),
            'stations': set(),
            'time_periods': set(),
            'results': set()
        }

        # ดูจาก working memory
        if 'last_device' in self.working_memory:
            entities['devices'].add(self.working_memory['last_device'])

        if 'last_station' in self.working_memory:
            entities['stations'].add(self.working_memory['last_station'])

        if 'last_time_period' in self.working_memory:
            entities['time_periods'].add(self.working_memory['last_time_period'])

        # ดูจาก recent exchanges
        for exchange in list(self.short_term_memory)[-3:]:
            if 'entities' in exchange['metadata']:
                ents = exchange['metadata']['entities']

                if 'device' in ents and ents['device']:
                    entities['devices'].add(ents['device'])

                if 'station' in ents and ents['station']:
                    entities['stations'].add(ents['station'])

                if 'time_period' in ents and ents['time_period']:
                    entities['time_periods'].add(ents['time_period'])

                if 'result_type' in ents and ents['result_type']:
                    entities['results'].add(ents['result_type'])

        # Convert sets to lists
        return {k: list(v) for k, v in entities.items() if v}

    def _update_working_memory(self, entities):
        """อัพเดท working memory ด้วย entities ใหม่"""

        if 'device' in entities and entities['device']:
            self.working_memory['last_device'] = entities['device']

        if 'station' in entities and entities['station']:
            self.working_memory['last_station'] = entities['station']

        if 'time_period' in entities and entities['time_period']:
            self.working_memory['last_time_period'] = entities['time_period']

        if 'result_type' in entities and entities['result_type']:
            self.working_memory['last_result'] = entities['result_type']

    def _get_conversation_summary(self):
        """สรุปการสนทนา"""
        if not self.short_term_memory:
            return "No conversation yet"

        # สรุปสั้นๆ จำนวนข้อความและหัวข้อ
        num_exchanges = len(self.short_term_memory)

        # ดึง topics จาก metadata
        topics = set()
        for exchange in self.short_term_memory:
            if 'metadata' in exchange and 'intent' in exchange['metadata']:
                topics.add(exchange['metadata']['intent'])

        summary = f"{num_exchanges} exchanges"
        if topics:
            summary += f", topics: {', '.join(topics)}"

        return summary

    def enrich_query(self, current_query):
        """
        เสริมคำถามด้วยบริบทที่เกี่ยวข้อง

        Args:
            current_query: คำถามปัจจุบัน

        Returns:
            enriched_query: คำถามที่เสริมด้วยบริบท
        """
        if not self._is_followup_question(current_query):
            return current_query

        # ดึง entities ที่อ้างถึง
        referenced = self._extract_referenced_entities()

        if not referenced:
            return current_query

        # สร้าง context string
        context_parts = []

        if referenced.get('devices'):
            context_parts.append(f"อุปกรณ์: {', '.join(referenced['devices'])}")

        if referenced.get('stations'):
            context_parts.append(f"สถานี: {', '.join(referenced['stations'])}")

        if referenced.get('time_periods'):
            context_parts.append(f"ช่วงเวลา: {', '.join(referenced['time_periods'])}")

        if referenced.get('results'):
            context_parts.append(f"ผล: {', '.join(referenced['results'])}")

        if context_parts:
            enriched = f"{current_query}\n\n[Context: {', '.join(context_parts)}]"
            return enriched

        return current_query

    def format_context_for_prompt(self, include_details=True):
        """
        จัดรูปแบบ context สำหรับใส่ใน prompt

        Args:
            include_details: แสดงรายละเอียดหรือไม่

        Returns:
            formatted_context: context ในรูปแบบ string
        """
        if not self.short_term_memory and not self.working_memory:
            return "ไม่มีบริบทก่อนหน้า"

        parts = []

        # Recent conversation
        if self.short_term_memory:
            parts.append("**การสนทนาล่าสุด:**")

            for exchange in list(self.short_term_memory)[-3:]:
                time_str = datetime.fromisoformat(exchange['timestamp']).strftime("%H:%M")
                user_msg = exchange['user'][:80]
                parts.append(f"[{time_str}] User: {user_msg}")

                if include_details:
                    ai_msg = exchange['ai'][:80]
                    parts.append(f"[{time_str}] AI: {ai_msg}")

        # Working memory
        if self.working_memory and include_details:
            parts.append("\n**ข้อมูลที่จำไว้:**")

            if 'last_device' in self.working_memory:
                parts.append(f"- อุปกรณ์: {self.working_memory['last_device']}")

            if 'last_station' in self.working_memory:
                parts.append(f"- สถานี: {self.working_memory['last_station']}")

            if 'last_time_period' in self.working_memory:
                parts.append(f"- ช่วงเวลา: {self.working_memory['last_time_period']}")

        result = "\n".join(parts)

        # จำกัดความยาว
        if len(result) > self.max_context_length:
            result = result[:self.max_context_length] + "..."

        return result

    def clear(self):
        """ล้างความจำทั้งหมด"""
        self.short_term_memory.clear()
        self.working_memory.clear()
        print("✓ Memory cleared")

    def get_statistics(self):
        """ดูสถิติการใช้งาน memory"""
        return {
            'short_term_count': len(self.short_term_memory),
            'working_memory_items': len(self.working_memory),
            'long_term_count': len(self.long_term_memory),
            'total_context_size': len(self.format_context_for_prompt())
        }


# Example usage
if __name__ == "__main__":
    print("Context Memory Manager (Level 2)")
    print("Features:")
    print("  ✓ Short-term memory (recent exchanges)")
    print("  ✓ Working memory (current session)")
    print("  ✓ Follow-up question detection")
    print("  ✓ Entity extraction")
    print("  ✓ Context enrichment")
