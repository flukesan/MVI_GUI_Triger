"""
ReAct Pattern Engine (Level 2)
Reasoning + Acting: AI ตัดสินใจเองว่าควรทำอะไรต่อ

Pattern:
  Thought → Action → Observation → Thought → ...
"""

import json
from datetime import datetime, timedelta


class ReActEngine:
    """ReAct Pattern: Reasoning + Acting"""

    def __init__(self, ai_agent, db_agent, doc_rag=None):
        self.ai_agent = ai_agent
        self.db_agent = db_agent
        self.doc_rag = doc_rag

        # Tools available to the agent
        self.tools = {
            'query_database': self._tool_query_database,
            'search_docs': self._tool_search_docs,
            'calculate': self._tool_calculate,
            'compare': self._tool_compare,
            'analyze_trend': self._tool_analyze_trend,
            'get_statistics': self._tool_get_statistics,
            'answer': None  # Special action to finish
        }

        print("✓ ReAct Engine initialized (Level 2)")
        print(f"  → Available tools: {len(self.tools)}")

    def solve(self, question, max_steps=5, verbose=True):
        """
        Solve question using ReAct pattern

        Args:
            question: คำถามที่ต้องการตอบ
            max_steps: จำนวนขั้นตอนสูงสุด
            verbose: แสดงการคิดหรือไม่

        Returns:
            final_answer: คำตอบสุดท้าย
        """

        if verbose:
            print(f"\n{'='*60}")
            print(f"🤔 ReAct Solving: {question}")
            print(f"{'='*60}\n")

        observations = []
        thought_history = []

        for step in range(1, max_steps + 1):
            if verbose:
                print(f"━━━ Step {step}/{max_steps} ━━━")

            # THINK: ให้ AI คิดว่าควรทำอะไรต่อ
            thought = self._think(question, observations, thought_history)

            if verbose:
                print(f"💭 Thought:\n{thought}\n")

            thought_history.append(thought)

            # Parse thought to get action
            action_info = self._parse_action(thought)

            if verbose:
                print(f"🎬 Action: {action_info['action']}")
                if action_info['input']:
                    print(f"📥 Input: {action_info['input']}")

            # ACT: ทำ action ที่เลือก
            if action_info['action'] == 'answer':
                # ถึงขั้นตอนสุดท้าย - สร้างคำตอบ
                final_answer = self._generate_final_answer(
                    question,
                    observations,
                    thought_history
                )

                if verbose:
                    print(f"\n✅ Final Answer Generated\n")
                    print(f"{'='*60}\n")

                return final_answer

            # Execute action
            observation = self._execute_action(action_info)

            if verbose:
                print(f"👁️ Observation:\n{observation}\n")

            observations.append({
                'step': step,
                'action': action_info['action'],
                'input': action_info['input'],
                'observation': observation
            })

        # ถ้าถึง max_steps แล้วยังไม่จบ ให้สร้างคำตอบจากข้อมูลที่มี
        if verbose:
            print(f"⚠️ Reached max steps ({max_steps}), generating answer from gathered evidence\n")

        return self._generate_final_answer(question, observations, thought_history)

    def _think(self, question, observations, thought_history):
        """ให้ AI คิดว่าควรทำอะไรต่อ"""

        # สร้าง context จากสิ่งที่เกิดขึ้นมาแล้ว
        context = self._build_context(observations)

        # Previous thoughts
        previous_thoughts = "\n".join([f"- {t}" for t in thought_history[-3:]]) if thought_history else "ยังไม่มี"

        prompt = f"""คุณเป็น AI ที่ใช้ ReAct Pattern (Reasoning + Acting) เพื่อตอบคำถาม

คำถาม: {question}

ความคิดก่อนหน้า:
{previous_thoughts}

สิ่งที่ทำมาแล้วและสังเกตได้:
{context}

Tools ที่ใช้ได้:
1. query_database - ดึงข้อมูลจาก inspection database (ใช้เมื่อต้องการข้อมูล inspection)
2. search_docs - ค้นหาคู่มือและเอกสาร (ใช้เมื่อต้องการวิธีแก้ปัญหา/คำอธิบาย)
3. get_statistics - ดึงสถิติ (ใช้เมื่อต้องการตัวเลขสรุป)
4. calculate - คำนวณ (pass rate, percentage, average, etc.)
5. compare - เปรียบเทียบข้อมูล (เช่น วันนี้ vs เมื่อวาน)
6. analyze_trend - วิเคราะห์แนวโน้ม (เพิ่มขึ้น/ลดลง)
7. answer - ตอบคำถาม (ใช้เมื่อพร้อมตอบแล้ว)

คิดว่าควรทำอะไรต่อ? ตอบในรูปแบบนี้:

Thought: [อธิบายว่าคิดอะไร ทำไมต้องทำสิ่งนี้]
Action: [ชื่อ tool ที่จะใช้]
Input: [input สำหรับ tool นั้น (ถ้ามี)]

ตัวอย่าง:
Thought: ต้องการทราบจำนวนการตรวจสอบวันนี้เพื่อตอบคำถาม ควรดึงสถิติจาก database
Action: get_statistics
Input: today

หรือ:
Thought: มีข้อมูลครบแล้ว พร้อมตอบคำถาม
Action: answer
Input: none

ตอนนี้คิดอะไร?"""

        thought = self.ai_agent.chat(prompt)
        return thought

    def _parse_action(self, thought):
        """Parse thought เพื่อดึง action และ input"""

        lines = thought.strip().split('\n')

        action_info = {
            'thought': '',
            'action': 'answer',  # default
            'input': None
        }

        for line in lines:
            line = line.strip()

            if line.startswith('Thought:'):
                action_info['thought'] = line.replace('Thought:', '').strip()

            elif line.startswith('Action:'):
                action_name = line.replace('Action:', '').strip().lower()
                # Clean up action name
                for tool_name in self.tools.keys():
                    if tool_name in action_name:
                        action_info['action'] = tool_name
                        break

            elif line.startswith('Input:'):
                input_value = line.replace('Input:', '').strip()
                if input_value and input_value.lower() not in ['none', 'ไม่มี', '-']:
                    action_info['input'] = input_value

        return action_info

    def _execute_action(self, action_info):
        """Execute action และคืนค่า observation"""

        action = action_info['action']
        input_data = action_info['input']

        if action not in self.tools:
            return f"Error: Unknown action '{action}'"

        tool_func = self.tools[action]
        if tool_func is None:
            return f"Error: Action '{action}' has no implementation"

        try:
            result = tool_func(input_data)
            return result
        except Exception as e:
            return f"Error executing {action}: {str(e)}"

    def _build_context(self, observations):
        """สร้าง context string จาก observations"""

        if not observations:
            return "ยังไม่มี (เพิ่งเริ่ม)"

        context_lines = []
        for obs in observations[-3:]:  # เอาแค่ 3 ล่าสุด
            context_lines.append(
                f"Step {obs['step']}: {obs['action']}({obs['input']}) → {obs['observation'][:200]}..."
            )

        return "\n".join(context_lines)

    def _generate_final_answer(self, question, observations, thought_history):
        """สร้างคำตอบสุดท้ายจากข้อมูลที่รวบรวมมา"""

        # รวม observations
        evidence = []
        for obs in observations:
            evidence.append({
                'action': obs['action'],
                'result': obs['observation']
            })

        prompt = f"""คำถาม: {question}

ข้อมูลที่รวบรวมมา:
{json.dumps(evidence, ensure_ascii=False, indent=2)}

กระบวนการคิด:
{chr(10).join(['- ' + t[:150] for t in thought_history])}

โปรดสร้างคำตอบที่:
1. ตอบตรงประเด็น
2. ใช้ข้อมูลที่รวบรวมมาสนับสนุน
3. จัดรูปแบบให้อ่านง่าย (ใช้ emoji, bullet points)
4. แสดงข้อมูลสำคัญ (ตัวเลข, เวลา, device)
5. ให้เหตุผลและข้อเสนอแนะ (ถ้าเหมาะสม)

คำตอบ:"""

        return self.ai_agent.chat(prompt)

    # ==================== TOOLS ====================

    def _tool_query_database(self, query):
        """Tool: Query database"""
        if not self.db_agent:
            return "Error: Database agent not available"

        try:
            result = self.db_agent.query_database_nl(query)
            return str(result)[:500]  # จำกัดความยาว
        except Exception as e:
            return f"Error querying database: {str(e)}"

    def _tool_search_docs(self, query):
        """Tool: Search documents"""
        if not self.doc_rag or self.doc_rag.get_document_count() == 0:
            return "Error: Document RAG not available"

        try:
            results = self.doc_rag.search(query, top_k=3)
            return json.dumps(results, ensure_ascii=False, indent=2)[:500]
        except Exception as e:
            return f"Error searching docs: {str(e)}"

    def _tool_get_statistics(self, period="today"):
        """Tool: Get statistics"""
        if not self.db_agent:
            return "Error: Database agent not available"

        try:
            stats = self.db_agent.get_statistics(period)
            return json.dumps(stats, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"Error getting statistics: {str(e)}"

    def _tool_calculate(self, expression):
        """Tool: Calculate values"""

        # Parse expression to determine what to calculate
        if 'pass rate' in expression.lower() or 'pass_rate' in expression.lower():
            # Calculate pass rate
            if self.db_agent:
                stats = self.db_agent.get_statistics("today")
                total = stats.get('total', 0)
                passed = stats.get('pass', 0)

                if total > 0:
                    pass_rate = (passed / total) * 100
                    return f"Pass rate: {pass_rate:.1f}% ({passed}/{total})"
                else:
                    return "No data to calculate pass rate"

        elif 'average' in expression.lower():
            return "Average calculation: Not implemented yet"

        else:
            # Try to evaluate as Python expression (safely)
            try:
                # Simple math only
                import re
                if re.match(r'^[\d+\-*/(). ]+$', expression):
                    result = eval(expression)
                    return f"Result: {result}"
                else:
                    return f"Cannot calculate: {expression}"
            except:
                return f"Invalid expression: {expression}"

    def _tool_compare(self, comparison):
        """Tool: Compare data"""

        if not self.db_agent:
            return "Error: Database agent not available"

        # Parse comparison request
        if 'today' in comparison.lower() and ('yesterday' in comparison.lower() or 'เมื่อวาน' in comparison.lower()):
            # Compare today vs yesterday
            try:
                today_stats = self.db_agent.get_statistics("today")

                # Get yesterday data
                cursor = self.db_agent.db.cursor()
                yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                cursor.execute("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN result = 'pass' THEN 1 ELSE 0 END) as pass_count,
                        SUM(CASE WHEN result = 'fail' THEN 1 ELSE 0 END) as fail_count
                    FROM inspections
                    WHERE date(timestamp) = ?
                """, (yesterday,))

                row = cursor.fetchone()
                yesterday_stats = {
                    'total': row[0] if row[0] else 0,
                    'pass': row[1] if row[1] else 0,
                    'fail': row[2] if row[2] else 0,
                    'pass_rate': (row[1] / row[0] * 100) if row[0] and row[0] > 0 else 0
                }

                comparison_result = {
                    'today': today_stats,
                    'yesterday': yesterday_stats,
                    'difference': {
                        'total': today_stats['total'] - yesterday_stats['total'],
                        'pass': today_stats['pass'] - yesterday_stats['pass'],
                        'fail': today_stats['fail'] - yesterday_stats['fail'],
                        'pass_rate_change': today_stats['pass_rate'] - yesterday_stats['pass_rate']
                    }
                }

                return json.dumps(comparison_result, ensure_ascii=False, indent=2)

            except Exception as e:
                return f"Error comparing: {str(e)}"

        return "Comparison type not recognized"

    def _tool_analyze_trend(self, period="week"):
        """Tool: Analyze trend"""

        if not self.db_agent:
            return "Error: Database agent not available"

        try:
            # Get data for the past N days
            days = 7 if period == "week" else 30

            cursor = self.db_agent.db.cursor()

            query = """
                SELECT
                    date(timestamp) as day,
                    COUNT(*) as total,
                    SUM(CASE WHEN result = 'pass' THEN 1 ELSE 0 END) as pass_count,
                    SUM(CASE WHEN result = 'fail' THEN 1 ELSE 0 END) as fail_count
                FROM inspections
                WHERE date(timestamp) >= date('now', ?)
                GROUP BY date(timestamp)
                ORDER BY date(timestamp) ASC
            """

            cursor.execute(query, (f'-{days} days',))

            daily_stats = []
            for row in cursor.fetchall():
                daily_stats.append({
                    'date': row[0],
                    'total': row[1],
                    'pass': row[2],
                    'fail': row[3],
                    'pass_rate': (row[2] / row[1] * 100) if row[1] > 0 else 0
                })

            # Analyze trend
            if len(daily_stats) >= 2:
                first_pass_rate = daily_stats[0]['pass_rate']
                last_pass_rate = daily_stats[-1]['pass_rate']
                trend = "improving" if last_pass_rate > first_pass_rate else "declining" if last_pass_rate < first_pass_rate else "stable"
            else:
                trend = "insufficient data"

            return json.dumps({
                'period': period,
                'days_analyzed': len(daily_stats),
                'trend': trend,
                'daily_stats': daily_stats
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            return f"Error analyzing trend: {str(e)}"


# Example usage
if __name__ == "__main__":
    print("ReAct Pattern Engine (Level 2)")
    print("Features:")
    print("  ✓ Reasoning + Acting loop")
    print("  ✓ Tool selection by AI")
    print("  ✓ Multi-step problem solving")
    print("\nTools available:")
    print("  • query_database")
    print("  • search_docs")
    print("  • get_statistics")
    print("  • calculate")
    print("  • compare")
    print("  • analyze_trend")
    print("  • answer")
