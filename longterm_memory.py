"""
Long-term Memory Manager (Level 3)
เก็บและจัดการความจำระยะยาว

Features:
- Automatic summarization
- Insight extraction
- Pattern recognition
- Historical knowledge base
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict


class LongTermMemoryManager:
    """Manages long-term memory and insights"""

    def __init__(self, ai_agent, max_memories=100):
        self.ai_agent = ai_agent
        self.max_memories = max_memories

        # Memory storage
        self.insights = []  # Key insights extracted
        self.patterns = []  # Patterns discovered
        self.summaries = {}  # Summaries by time period
        self.knowledge_base = defaultdict(list)  # Topic → facts

        print("✓ Long-term Memory Manager initialized")
        print(f"  → Max memories: {max_memories}")
        print(f"  → Insight extraction: enabled")
        print(f"  → Pattern recognition: enabled")

    def add_conversation_summary(self, conversations: List[Dict], period: str = "daily"):
        """
        Summarize conversations and store insights

        Args:
            conversations: List of conversation exchanges
            period: Time period (daily, weekly, monthly)
        """

        if not conversations:
            return

        print(f"📝 Summarizing {len(conversations)} conversations ({period})...")

        # Create summary
        summary = self._create_summary(conversations, period)

        # Extract insights
        insights = self._extract_insights(conversations)

        # Detect patterns
        patterns = self._detect_patterns(conversations)

        # Store
        timestamp = datetime.now().isoformat()
        self.summaries[timestamp] = {
            'period': period,
            'timestamp': timestamp,
            'summary': summary,
            'conversation_count': len(conversations),
            'insights': insights,
            'patterns': patterns
        }

        # Add to insights list
        for insight in insights:
            self.insights.append({
                'timestamp': timestamp,
                'insight': insight,
                'source': f'{period}_summary'
            })

        # Add to patterns list
        for pattern in patterns:
            self.patterns.append({
                'timestamp': timestamp,
                'pattern': pattern,
                'source': f'{period}_summary'
            })

        # Trim if too many
        self._trim_memories()

        print(f"✅ Summary created:")
        print(f"   Insights: {len(insights)}")
        print(f"   Patterns: {len(patterns)}")

    def _create_summary(self, conversations: List[Dict], period: str) -> str:
        """Create summary of conversations"""

        # Prepare conversation text
        conv_text = []
        for conv in conversations[-20:]:  # Last 20
            user = conv.get('user', '')
            ai = conv.get('ai', '')[:100]
            conv_text.append(f"User: {user}\nAI: {ai}")

        conv_summary = "\n\n".join(conv_text)

        prompt = f"""สรุปการสนทนาใน {period} นี้:

การสนทนา ({len(conversations)} exchanges):
{conv_summary}

โปรดสรุปสั้นๆ (5-10 ประโยค):
1. หัวข้อหลักที่พูดถึง
2. คำถามที่พบบ่อย
3. ประเด็นสำคัญ
4. แนวโน้มที่สังเกต

Summary:"""

        try:
            summary = self.ai_agent.chat(prompt)
            return summary
        except:
            return f"Summary of {len(conversations)} conversations in {period}"

    def _extract_insights(self, conversations: List[Dict]) -> List[str]:
        """Extract key insights from conversations"""

        # Analyze conversation topics and user intent
        topics = defaultdict(int)

        for conv in conversations:
            metadata = conv.get('metadata', {})
            intent = metadata.get('intent', 'unknown')
            topics[intent] += 1

        # Create insights
        insights = []

        # Most common intent
        if topics:
            most_common = max(topics.items(), key=lambda x: x[1])
            insights.append(f"Most common query type: {most_common[0]} ({most_common[1]} times)")

        # Entities mentioned
        entities_mentioned = set()
        for conv in conversations:
            metadata = conv.get('metadata', {})
            entities = metadata.get('entities', {})
            for key, value in entities.items():
                if value:
                    entities_mentioned.add(f"{key}:{value}")

        if entities_mentioned:
            insights.append(f"Frequently mentioned: {', '.join(list(entities_mentioned)[:3])}")

        return insights

    def _detect_patterns(self, conversations: List[Dict]) -> List[str]:
        """Detect patterns in conversations"""

        patterns = []

        # Check for follow-up patterns
        followup_count = 0
        for i in range(1, len(conversations)):
            curr = conversations[i].get('user', '').lower()
            if any(indicator in curr for indicator in ['แล้ว', 'ล่ะ', 'อีก', 'ต่อ']):
                followup_count += 1

        if followup_count > len(conversations) * 0.3:
            patterns.append(f"High follow-up rate: {followup_count}/{len(conversations)} conversations")

        # Check for specific device mentions
        device_mentions = defaultdict(int)
        for conv in conversations:
            user_msg = conv.get('user', '').lower()
            for device in ['basler', 'watashi', 'camera']:
                if device in user_msg:
                    device_mentions[device] += 1

        if device_mentions:
            top_device = max(device_mentions.items(), key=lambda x: x[1])
            if top_device[1] >= 3:
                patterns.append(f"Focus on device: {top_device[0]} ({top_device[1]} mentions)")

        return patterns

    def add_insight(self, insight: str, topic: str = "general", source: str = "manual"):
        """
        Add a single insight to memory

        Args:
            insight: The insight text
            topic: Topic category
            source: Where this came from
        """

        self.insights.append({
            'timestamp': datetime.now().isoformat(),
            'insight': insight,
            'topic': topic,
            'source': source
        })

        # Also add to knowledge base
        self.knowledge_base[topic].append(insight)

        self._trim_memories()

    def add_pattern(self, pattern: str, confidence: float = 1.0):
        """Add a discovered pattern"""

        self.patterns.append({
            'timestamp': datetime.now().isoformat(),
            'pattern': pattern,
            'confidence': confidence
        })

        self._trim_memories()

    def get_relevant_memories(self, query: str, top_k: int = 5) -> Dict[str, List]:
        """
        Get relevant memories for a query

        Args:
            query: Current query
            top_k: Number of memories to return

        Returns:
            Dict with insights, patterns, and summaries
        """

        query_lower = query.lower()

        # Find relevant insights
        relevant_insights = []
        for insight_entry in self.insights:
            insight = insight_entry['insight'].lower()
            # Simple relevance: check keyword overlap
            if any(word in insight for word in query_lower.split()):
                relevant_insights.append(insight_entry)

        # Find relevant patterns
        relevant_patterns = []
        for pattern_entry in self.patterns:
            pattern = pattern_entry['pattern'].lower()
            if any(word in pattern for word in query_lower.split()):
                relevant_patterns.append(pattern_entry)

        return {
            'insights': relevant_insights[:top_k],
            'patterns': relevant_patterns[:top_k],
            'recent_summary': self._get_recent_summary()
        }

    def _get_recent_summary(self) -> Optional[Dict]:
        """Get most recent summary"""
        if not self.summaries:
            return None

        # Get latest
        latest_key = max(self.summaries.keys())
        return self.summaries[latest_key]

    def get_knowledge_on_topic(self, topic: str) -> List[str]:
        """Get all knowledge on a specific topic"""
        return self.knowledge_base.get(topic, [])

    def _trim_memories(self):
        """Trim memories if exceeding max"""

        # Trim insights
        if len(self.insights) > self.max_memories:
            # Keep most recent
            self.insights = self.insights[-self.max_memories:]

        # Trim patterns
        if len(self.patterns) > self.max_memories:
            self.patterns = self.patterns[-self.max_memories:]

        # Trim summaries
        if len(self.summaries) > 50:
            # Keep 50 most recent
            sorted_keys = sorted(self.summaries.keys())
            for key in sorted_keys[:-50]:
                del self.summaries[key]

    def consolidate_knowledge(self) -> Dict[str, Any]:
        """
        Consolidate all knowledge into structured format

        Returns:
            Consolidated knowledge dict
        """

        print("🧠 Consolidating knowledge...")

        # Group insights by topic
        insights_by_topic = defaultdict(list)
        for insight_entry in self.insights:
            topic = insight_entry.get('topic', 'general')
            insights_by_topic[topic].append(insight_entry['insight'])

        # Summarize patterns
        pattern_summary = self._summarize_patterns()

        # Create consolidated knowledge
        knowledge = {
            'timestamp': datetime.now().isoformat(),
            'total_insights': len(self.insights),
            'total_patterns': len(self.patterns),
            'insights_by_topic': dict(insights_by_topic),
            'key_patterns': pattern_summary,
            'recent_summaries': list(self.summaries.values())[-5:],
            'knowledge_base': dict(self.knowledge_base)
        }

        print(f"✅ Knowledge consolidated:")
        print(f"   Topics: {len(insights_by_topic)}")
        print(f"   Patterns: {len(pattern_summary)}")

        return knowledge

    def _summarize_patterns(self) -> List[str]:
        """Summarize detected patterns"""

        if not self.patterns:
            return []

        # Group similar patterns
        pattern_texts = [p['pattern'] for p in self.patterns]

        # Use frequency to identify key patterns
        pattern_freq = defaultdict(int)
        for pattern in pattern_texts:
            # Simplified grouping
            pattern_freq[pattern[:50]] += 1

        # Get top patterns
        sorted_patterns = sorted(pattern_freq.items(), key=lambda x: x[1], reverse=True)

        return [f"{pattern} (seen {count}x)" for pattern, count in sorted_patterns[:10]]

    def save_to_file(self, filepath: str):
        """Save long-term memory to file"""

        data = {
            'insights': self.insights,
            'patterns': self.patterns,
            'summaries': self.summaries,
            'knowledge_base': dict(self.knowledge_base),
            'saved_at': datetime.now().isoformat()
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"✅ Long-term memory saved to {filepath}")

    def load_from_file(self, filepath: str):
        """Load long-term memory from file"""

        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.insights = data.get('insights', [])
        self.patterns = data.get('patterns', [])
        self.summaries = data.get('summaries', {})
        self.knowledge_base = defaultdict(list, data.get('knowledge_base', {}))

        print(f"✅ Long-term memory loaded from {filepath}")
        print(f"   Insights: {len(self.insights)}")
        print(f"   Patterns: {len(self.patterns)}")
        print(f"   Summaries: {len(self.summaries)}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get memory statistics"""

        return {
            'total_insights': len(self.insights),
            'total_patterns': len(self.patterns),
            'total_summaries': len(self.summaries),
            'topics_tracked': len(self.knowledge_base),
            'oldest_memory': self.insights[0]['timestamp'] if self.insights else None,
            'newest_memory': self.insights[-1]['timestamp'] if self.insights else None
        }

    def clear(self):
        """Clear all memories"""
        self.insights = []
        self.patterns = []
        self.summaries = {}
        self.knowledge_base = defaultdict(list)
        print("✓ Long-term memory cleared")


# Example usage
if __name__ == "__main__":
    print("Long-term Memory Manager (Level 3)")
    print("=" * 60)
    print("\nFeatures:")
    print("  ✓ Automatic summarization")
    print("  ✓ Insight extraction")
    print("  ✓ Pattern recognition")
    print("  ✓ Knowledge consolidation")
    print("=" * 60)
