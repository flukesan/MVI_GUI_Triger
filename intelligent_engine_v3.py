"""
Intelligent AI Engine V3 (Level 3)
รวม: Level 1 + Level 2 + Level 3

Level 3 New Features:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 Vector Search: Semantic search (ไม่ใช่แค่ keyword)
🪞 Self-Reflection: AI ตรวจสอบคำตอบตัวเอง
🧠 Long-term Memory: จำ insights ระยะยาว
"""

import json
from datetime import datetime
from typing import Dict, List, Any, Optional

# Import Level 2 components
from intelligent_engine_v2 import IntelligentAIEngineV2

# Import Level 3 components
try:
    from vector_search import VectorSearchEngine
    VECTOR_SEARCH_AVAILABLE = True
except ImportError:
    print("⚠️ Vector Search not available (sentence-transformers required)")
    VECTOR_SEARCH_AVAILABLE = False

from self_reflection import SelfReflectionSystem
from longterm_memory import LongTermMemoryManager


class IntelligentAIEngineV3:
    """AI Engine Level 3 with Vector Search, Self-Reflection, and Long-term Memory"""

    def __init__(self, ai_agent, db_agent, doc_rag=None, mode='auto', enable_vector_search=True):
        """
        Args:
            ai_agent: AIAgent instance
            db_agent: DatabaseAgent instance
            doc_rag: DocumentRAG instance
            mode: 'auto' (default), 'react', 'multi-agent', 'simple'
            enable_vector_search: Enable vector search (requires sentence-transformers)
        """
        self.ai_agent = ai_agent
        self.db_agent = db_agent
        self.doc_rag = doc_rag
        self.mode = mode

        # Initialize Level 2 engine
        self.v2_engine = IntelligentAIEngineV2(ai_agent, db_agent, doc_rag, mode=mode)

        # Initialize Level 3 components
        if enable_vector_search and VECTOR_SEARCH_AVAILABLE:
            try:
                self.vector_search = VectorSearchEngine(use_gpu=False)
                print("✓ Vector Search enabled")
            except Exception as e:
                print(f"⚠️ Vector Search initialization failed: {e}")
                self.vector_search = None
        else:
            self.vector_search = None

        self.self_reflection = SelfReflectionSystem(ai_agent)
        self.longterm_memory = LongTermMemoryManager(ai_agent, max_memories=100)

        # Conversation tracking for daily summaries
        self.daily_conversations = []

        print("✓ Intelligent AI Engine V3 initialized (Level 3)")
        print(f"  → Mode: {mode}")
        print(f"  → Level 1: Query Understanding + Chain-of-Thought")
        print(f"  → Level 2: ReAct + Context Memory + Multi-Agent")
        print(f"  → Level 3: Vector Search + Self-Reflection + Long-term Memory")

    def process_query(self, query: str, use_context=True, use_reflection=True, use_vector_search=False):
        """
        Process query with full Level 3 capabilities

        Args:
            query: User question
            use_context: Use context memory (Level 2)
            use_reflection: Use self-reflection (Level 3)
            use_vector_search: Use vector search (Level 3)

        Returns:
            answer: Final answer (potentially self-corrected)
        """

        print(f"\n{'='*60}")
        print(f"🧠 Intelligent Engine V3 Processing")
        print(f"{'='*60}")
        print(f"Query: {query}")
        print(f"Context: {use_context}, Reflection: {use_reflection}, Vector: {use_vector_search}")

        # Step 1: Check for relevant long-term memories
        if self.longterm_memory.insights:
            print(f"📚 Checking long-term memory...")
            memories = self.longterm_memory.get_relevant_memories(query, top_k=3)
            if memories['insights']:
                print(f"   Found {len(memories['insights'])} relevant insights")
            if memories['patterns']:
                print(f"   Found {len(memories['patterns'])} relevant patterns")

        # Step 2: Enhanced search with vector search
        if use_vector_search and self.vector_search and self.vector_search.inspection_index is not None:
            print(f"🔍 Using Vector Search...")
            vector_results = self.vector_search.search_inspections(query, top_k=5, threshold=0.4)
            if vector_results:
                print(f"   Found {len(vector_results)} semantically similar results")
                # TODO: Inject vector results into evidence

        # Step 3: Process query using Level 2 engine
        print(f"⚙️ Processing with Level 2 engine...")
        answer = self.v2_engine.process_query(query, use_context=use_context)

        # Step 4: Self-reflection (if enabled)
        if use_reflection:
            print(f"🪞 Self-Reflection...")

            # Gather evidence that was used
            evidence = self._gather_evidence_snapshot(query)

            # Reflect on answer
            reflection = self.self_reflection.reflect_on_answer(
                question=query,
                answer=answer,
                evidence=evidence,
                verbose=False
            )

            print(f"   Quality score: {reflection['overall_score']:.2f}")
            print(f"   Passed: {reflection['passed']}")

            # If quality is low, get corrected answer
            if not reflection['passed'] and reflection['overall_score'] < 0.7:
                print(f"   ⚠️ Low quality detected, generating corrected answer...")
                corrected_answer, new_reflection = self.self_reflection.get_corrected_answer(
                    query, answer, evidence
                )
                print(f"   Corrected score: {new_reflection['overall_score']:.2f}")
                print(f"   Improvement: +{new_reflection.get('improvement', 0):.2f}")
                answer = corrected_answer

        # Step 5: Store conversation for long-term memory
        understanding = self.v2_engine._understand_query(query)
        self.daily_conversations.append({
            'timestamp': datetime.now().isoformat(),
            'user': query,
            'ai': answer,
            'metadata': understanding
        })

        # Auto-summarize daily (if > 20 conversations)
        if len(self.daily_conversations) >= 20:
            print(f"📝 Auto-summarizing conversations...")
            self._auto_summarize_daily()

        print(f"✅ Answer generated (Level 3)")
        print(f"{'='*60}\n")

        return answer

    def _gather_evidence_snapshot(self, query: str) -> Dict[str, Any]:
        """Gather current evidence for reflection"""

        evidence = {}

        # Get stats if available
        if self.db_agent:
            try:
                evidence['statistics'] = self.db_agent.get_statistics('today')
                evidence['recent_inspections'] = self.db_agent.get_recent_inspections(5)
            except:
                pass

        # Get relevant long-term memories
        if self.longterm_memory.insights:
            memories = self.longterm_memory.get_relevant_memories(query, top_k=3)
            evidence['relevant_memories'] = memories

        return evidence

    def _auto_summarize_daily(self):
        """Auto-summarize daily conversations"""

        if not self.daily_conversations:
            return

        self.longterm_memory.add_conversation_summary(
            self.daily_conversations,
            period='daily'
        )

        # Clear daily conversations
        self.daily_conversations = []

    def index_inspections_for_vector_search(self, inspections: List[Dict]):
        """
        Index inspections for vector search

        Args:
            inspections: List of inspection records
        """
        if not self.vector_search:
            print("⚠️ Vector search not available")
            return

        try:
            self.vector_search.index_inspections(inspections)
            print(f"✅ Indexed {len(inspections)} inspections for vector search")
        except Exception as e:
            print(f"❌ Error indexing inspections: {e}")

    def index_documents_for_vector_search(self, documents: List[Dict]):
        """Index documents for vector search"""
        if not self.vector_search:
            print("⚠️ Vector search not available")
            return

        try:
            self.vector_search.index_documents(documents)
            print(f"✅ Indexed {len(documents)} documents for vector search")
        except Exception as e:
            print(f"❌ Error indexing documents: {e}")

    def semantic_search_inspections(self, query: str, top_k: int = 10) -> List[Dict]:
        """
        Perform semantic search on inspections

        Args:
            query: Natural language query
            top_k: Number of results

        Returns:
            List of semantically similar inspections
        """
        if not self.vector_search:
            print("⚠️ Vector search not available")
            return []

        return self.vector_search.search_inspections(query, top_k=top_k)

    def get_insights_summary(self) -> Dict[str, Any]:
        """Get summary of learned insights"""
        return {
            'long_term_memory': self.longterm_memory.get_statistics(),
            'reflection_stats': self.self_reflection.get_reflection_summary(),
            'vector_search': self.vector_search.get_statistics() if self.vector_search else None,
            'daily_conversations_pending': len(self.daily_conversations)
        }

    def consolidate_knowledge(self) -> Dict[str, Any]:
        """Consolidate all knowledge and insights"""
        return self.longterm_memory.consolidate_knowledge()

    def save_memories(self, filepath: str):
        """Save all memories to file"""
        self.longterm_memory.save_to_file(filepath)

        # Also save vector index if available
        if self.vector_search and self.vector_search.inspection_index is not None:
            vector_filepath = filepath.replace('.json', '_vectors.pkl')
            self.vector_search.save_index(vector_filepath)
            print(f"✅ Vector index saved to {vector_filepath}")

    def load_memories(self, filepath: str):
        """Load memories from file"""
        import os

        self.longterm_memory.load_from_file(filepath)

        # Load vector index if available
        vector_filepath = filepath.replace('.json', '_vectors.pkl')
        if os.path.exists(vector_filepath) and self.vector_search:
            self.vector_search.load_index(vector_filepath)

    def clear_context(self):
        """Clear context memory (Level 2)"""
        self.v2_engine.clear_context()

    def clear_all_memories(self):
        """Clear all memories (context + long-term)"""
        self.v2_engine.clear_context()
        self.longterm_memory.clear()
        self.self_reflection.clear_history()
        self.daily_conversations = []
        print("✓ All memories cleared")

    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics"""
        return {
            'engine_version': 3,
            'mode': self.mode,
            'level_2': self.v2_engine.get_statistics(),
            'level_3': {
                'vector_search_enabled': self.vector_search is not None,
                'long_term_memory': self.longterm_memory.get_statistics(),
                'reflection_history': self.self_reflection.get_reflection_summary(),
                'daily_conversations': len(self.daily_conversations)
            }
        }


# Example usage
if __name__ == "__main__":
    print("Intelligent AI Engine V3 (Level 3)")
    print("=" * 60)
    print("\nAll Features:")
    print("  ✅ Level 1: Query Understanding + Chain-of-Thought")
    print("  ✅ Level 2: ReAct Pattern + Context Memory + Multi-Agent")
    print("  ✅ Level 3: Vector Search + Self-Reflection + Long-term Memory")
    print("\nExecution Modes:")
    print("  • auto        - Automatic selection (default)")
    print("  • simple      - Level 1 (fast)")
    print("  • react       - ReAct Pattern (multi-step)")
    print("  • multi-agent - Multi-Agent System (deep analysis)")
    print("=" * 60)
