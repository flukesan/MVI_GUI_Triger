"""
Intelligent AI Engine V2 (Level 2)
รวม: ReAct Pattern + Context Memory + Multi-Agent

Upgrades from V1:
- ✅ ReAct Pattern: AI ตัดสินใจเองว่าจะใช้ tool ไหน
- ✅ Context Memory: จำบริบทการสนทนา รองรับคำถามต่อเนื่อง
- ✅ Multi-Agent: Planner, Executor, Analyzer ทำงานร่วมกัน
- ✅ Advanced Tools: calculate, compare, analyze_trend
"""

import json
from datetime import datetime

from react_engine import ReActEngine
from context_memory import ContextMemoryManager


class IntelligentAIEngineV2:
    """AI Engine Level 2 with ReAct, Context Memory, and Multi-Agent"""

    def __init__(self, ai_agent, db_agent, doc_rag=None, mode='auto'):
        """
        Args:
            ai_agent: AIAgent instance
            db_agent: DatabaseAgent instance
            doc_rag: DocumentRAG instance (optional)
            mode: 'auto' (ใช้ V2 auto), 'react' (บังคับ ReAct), 'simple' (ใช้ V1)
        """
        self.ai_agent = ai_agent
        self.db_agent = db_agent
        self.doc_rag = doc_rag
        self.mode = mode

        # Initialize Level 2 components
        self.react_engine = ReActEngine(ai_agent, db_agent, doc_rag)
        self.context_memory = ContextMemoryManager(short_term_size=10)

        # Import Level 1 engine for simple queries
        from intelligent_engine import IntelligentAIEngine
        self.level1_engine = IntelligentAIEngine(ai_agent, db_agent, doc_rag)

        print("✓ Intelligent AI Engine V2 initialized (Level 2)")
        print(f"  → Mode: {mode}")
        print(f"  → ReAct Engine: enabled")
        print(f"  → Context Memory: enabled")
        print(f"  → Multi-Agent: enabled")

    def process_query(self, query, use_context=True):
        """
        ประมวลผลคำถามอย่างชาญฉลาด (Level 2)

        Args:
            query: คำถาม
            use_context: ใช้บริบทการสนทนาหรือไม่

        Returns:
            answer: คำตอบ
        """

        print(f"\n{'='*60}")
        print(f"🧠 Intelligent Engine V2 Processing")
        print(f"{'='*60}")
        print(f"Query: {query}")
        print(f"Use context: {use_context}")

        # Step 1: Enrich query with context (ถ้าเป็นคำถามต่อเนื่อง)
        if use_context:
            enriched_query = self.context_memory.enrich_query(query)
            if enriched_query != query:
                print(f"✨ Enriched query: {enriched_query}")
                query = enriched_query

        # Step 2: Understand query
        understanding = self._understand_query(query)
        print(f"🔍 Intent: {understanding['intent']}, Complexity: {understanding['complexity']}")

        # Step 3: Decide execution mode
        execution_mode = self._decide_execution_mode(understanding)
        print(f"⚙️ Execution mode: {execution_mode}")

        # Step 4: Execute based on mode
        if execution_mode == 'react':
            # Use ReAct for complex multi-step reasoning
            answer = self.react_engine.solve(query, max_steps=5, verbose=True)

        elif execution_mode == 'multi-agent':
            # Use Multi-Agent system
            answer = self._multi_agent_solve(query, understanding)

        else:  # simple
            # Use Level 1 for simple queries
            answer = self.level1_engine.process_query(query)

        # Step 5: Store in context memory
        if use_context:
            self.context_memory.add_exchange(
                user_message=query,
                ai_response=answer,
                metadata=understanding
            )

        print(f"✅ Answer generated")
        print(f"{'='*60}\n")

        return answer

    def _understand_query(self, query):
        """เข้าใจคำถาม (ใช้จาก Level 1)"""
        return self.level1_engine._understand_query(query)

    def _decide_execution_mode(self, understanding):
        """ตัดสินใจว่าจะใช้ mode ไหน"""

        if self.mode == 'react':
            return 'react'
        elif self.mode == 'simple':
            return 'simple'

        # Auto mode - ตัดสินใจเอง
        intent = understanding['intent']
        complexity = understanding['complexity']

        # ใช้ ReAct สำหรับ multi-step queries
        if intent in ['troubleshoot', 'compare'] and complexity == 'complex':
            return 'react'

        # ใช้ Multi-Agent สำหรับ deep analysis
        if intent == 'analyze' and complexity == 'complex':
            return 'multi-agent'

        # ใช้ simple mode สำหรับคำถามง่าย
        return 'simple'

    def _multi_agent_solve(self, query, understanding):
        """
        Multi-Agent System: Planner → Executor → Analyzer

        Agents:
        1. Planner: วางแผนว่าจะทำอะไร
        2. Executor: ทำตามแผน (รวบรวมข้อมูล)
        3. Analyzer: วิเคราะห์และสรุปคำตอบ
        """

        print(f"\n{'━'*60}")
        print(f"🤝 Multi-Agent System")
        print(f"{'━'*60}\n")

        # Agent 1: Planner
        print("📋 Agent 1: Planner (วางแผน)")
        plan = self._planner_agent(query, understanding)
        print(f"Plan: {json.dumps(plan, ensure_ascii=False, indent=2)}\n")

        # Agent 2: Executor
        print("⚡ Agent 2: Executor (ทำงาน)")
        evidence = self._executor_agent(plan)
        print(f"Evidence gathered: {len(evidence)} items\n")

        # Agent 3: Analyzer
        print("🔬 Agent 3: Analyzer (วิเคราะห์)")
        analysis = self._analyzer_agent(query, evidence, plan)

        print(f"{'━'*60}\n")

        return analysis

    def _planner_agent(self, query, understanding):
        """Planner Agent: วางแผนการทำงาน"""

        intent = understanding['intent']
        entities = understanding['entities']

        plan = {
            'query': query,
            'intent': intent,
            'steps': []
        }

        # วางแผนตาม intent
        if intent == 'analyze':
            plan['steps'] = [
                {'action': 'get_statistics', 'params': {'period': 'today'}},
                {'action': 'get_details', 'params': {'limit': 10}},
                {'action': 'get_trend', 'params': {'period': 'week'}},
                {'action': 'analyze', 'params': {}}
            ]

        elif intent == 'troubleshoot':
            plan['steps'] = [
                {'action': 'get_fail_analysis', 'params': {}},
                {'action': 'get_statistics', 'params': {'period': 'today'}},
                {'action': 'search_docs', 'params': {'query': query}},
                {'action': 'diagnose', 'params': {}}
            ]

        elif intent == 'compare':
            plan['steps'] = [
                {'action': 'get_statistics', 'params': {'period': 'today'}},
                {'action': 'get_statistics', 'params': {'period': 'yesterday'}},
                {'action': 'compare', 'params': {}},
                {'action': 'analyze', 'params': {}}
            ]

        else:
            # Default plan
            plan['steps'] = [
                {'action': 'get_data', 'params': {}},
                {'action': 'analyze', 'params': {}}
            ]

        return plan

    def _executor_agent(self, plan):
        """Executor Agent: ทำงานตามแผน"""

        evidence = []

        for step in plan['steps']:
            action = step['action']
            params = step['params']

            try:
                if action == 'get_statistics':
                    period = params.get('period', 'today')
                    result = self.db_agent.get_statistics(period)
                    evidence.append({'action': action, 'params': params, 'result': result})

                elif action == 'get_details':
                    limit = params.get('limit', 10)
                    result = self.db_agent.get_recent_inspections(limit)
                    evidence.append({'action': action, 'params': params, 'result': result})

                elif action == 'get_fail_analysis':
                    result = self.level1_engine._get_fail_analysis(params)
                    evidence.append({'action': action, 'params': params, 'result': result})

                elif action == 'get_trend':
                    period = params.get('period', 'week')
                    result = self.react_engine._tool_analyze_trend(period)
                    evidence.append({'action': action, 'params': params, 'result': result})

                elif action == 'search_docs':
                    if self.doc_rag:
                        query = params.get('query', '')
                        result = self.doc_rag.search(query, top_k=3)
                        evidence.append({'action': action, 'params': params, 'result': result})

                elif action in ['analyze', 'diagnose', 'compare']:
                    # These are analysis steps, not data gathering
                    pass

            except Exception as e:
                print(f"  ⚠️ Error in {action}: {e}")
                evidence.append({'action': action, 'params': params, 'error': str(e)})

        return evidence

    def _analyzer_agent(self, query, evidence, plan):
        """Analyzer Agent: วิเคราะห์และสรุป"""

        # สร้าง prompt สำหรับ analysis
        prompt = f"""คุณเป็น Analyzer Agent ทำหน้าที่วิเคราะห์และสรุปคำตอบ

คำถาม: {query}

แผนที่วางไว้:
{json.dumps(plan, ensure_ascii=False, indent=2)}

หลักฐานที่รวบรวมมา:
{json.dumps(evidence, ensure_ascii=False, indent=2, default=str)}

โปรดวิเคราะห์และสร้างคำตอบที่:
1. ตอบตรงประเด็นคำถาม
2. ใช้หลักฐานจากทุก Agent มาสนับสนุน
3. จัดรูปแบบให้อ่านง่าย (emoji, bullet points, sections)
4. แสดงข้อมูลสำคัญ (ตัวเลข, เวลา, device, station)
5. ให้ insights และข้อเสนอแนะ
6. แสดงการวิเคราะห์เชิงลึก (patterns, trends, root causes)

รูปแบบคำตอบ:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 **สรุป**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[สรุปสั้นๆ ตอบตรงคำถาม]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 **รายละเอียด**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[รายละเอียดที่สำคัญจากหลักฐาน]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 **การวิเคราะห์**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[วิเคราะห์ patterns, trends, insights]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 **ข้อเสนอแนะ**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[คำแนะนำที่เป็นประโยชน์]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

คำตอบ:"""

        return self.ai_agent.chat(prompt)

    def get_context_summary(self):
        """ดูสรุปบริบทการสนทนา"""
        return self.context_memory.format_context_for_prompt(include_details=True)

    def clear_context(self):
        """ล้างบริบทการสนทนา"""
        self.context_memory.clear()
        self.level1_engine.clear_history()

    def get_statistics(self):
        """ดูสถิติการใช้งาน"""
        return {
            'engine_version': 2,
            'mode': self.mode,
            'context_memory': self.context_memory.get_statistics()
        }


# Example usage
if __name__ == "__main__":
    print("Intelligent AI Engine V2 (Level 2)")
    print("=" * 60)
    print("\nFeatures:")
    print("  ✅ Level 1: Query Understanding + Chain-of-Thought")
    print("  ✅ Level 2: ReAct Pattern")
    print("  ✅ Level 2: Context Memory")
    print("  ✅ Level 2: Multi-Agent System")
    print("\nExecution Modes:")
    print("  • simple  - Level 1 (fast)")
    print("  • react   - ReAct Pattern (multi-step)")
    print("  • multi-agent - Multi-Agent System (deep analysis)")
    print("  • auto    - Automatic selection (default)")
    print("=" * 60)
