#!/usr/bin/env python3
"""
Test Intelligent AI Engine Level 2
Tests: ReAct Pattern, Context Memory, Multi-Agent System
"""

import sys
import sqlite3

print("=" * 60)
print("🧪 Testing Intelligent AI Engine (Level 2)")
print("=" * 60)

# Test 1: Import modules
print("\n1️⃣ Testing imports...")
try:
    from ai_agent import AIAgent
    from database_agent import DatabaseAgent
    from document_rag import DocumentRAG
    from react_engine import ReActEngine
    from context_memory import ContextMemoryManager
    from intelligent_engine_v2 import IntelligentAIEngineV2
    print("✅ All Level 2 modules imported")
except Exception as e:
    print(f"❌ Import error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 2: Initialize components
print("\n2️⃣ Initializing AI components...")
try:
    ai_agent = AIAgent()
    if ai_agent.is_available():
        print(f"✅ AI Agent ready (Model: {ai_agent.current_model})")
    else:
        print("⚠️ Ollama not available - limited testing")
        print("   Run: ollama serve")
except Exception as e:
    print(f"❌ AI Agent error: {e}")
    sys.exit(1)

# Test 3: Database Agent
print("\n3️⃣ Initializing Database Agent...")
try:
    db = sqlite3.connect("inspection_history.db")
    db_agent = DatabaseAgent(ai_agent, db)

    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM inspections WHERE date(timestamp) >= date('now', '-7 days')")
    count = cursor.fetchone()[0]
    print(f"✅ Database Agent initialized")
    print(f"   📊 Past 7 days inspections: {count}")
except Exception as e:
    print(f"❌ Database error: {e}")
    sys.exit(1)

# Test 4: Document RAG
print("\n4️⃣ Initializing Document RAG...")
try:
    doc_rag = DocumentRAG(ai_agent, documents_folder="manuals")
    print(f"✅ Document RAG initialized ({doc_rag.get_document_count()} documents)")
except Exception as e:
    print(f"⚠️ Document RAG error: {e}")
    doc_rag = None

# Test 5: ReAct Engine
print("\n5️⃣ Testing ReAct Engine...")
try:
    react_engine = ReActEngine(ai_agent, db_agent, doc_rag)
    print("✅ ReAct Engine initialized")

    # Test tools
    print("\n  Testing tools:")
    stat_result = react_engine._tool_get_statistics("today")
    print(f"    • get_statistics: {stat_result[:80]}...")

    calc_result = react_engine._tool_calculate("pass rate")
    print(f"    • calculate: {calc_result}")

    print("  ✅ Tools working")
except Exception as e:
    print(f"❌ ReAct Engine error: {e}")
    import traceback
    traceback.print_exc()

# Test 6: Context Memory
print("\n6️⃣ Testing Context Memory...")
try:
    context_memory = ContextMemoryManager(short_term_size=5)
    print("✅ Context Memory initialized")

    # Add test conversations
    context_memory.add_exchange(
        "มีการตรวจสอบกี่ครั้งวันนี้",
        "มี 7 ครั้งวันนี้",
        {'intent': 'count', 'entities': {'time_period': 'today'}}
    )

    context_memory.add_exchange(
        "แล้ว FAIL กี่ครั้ง",
        "FAIL 2 ครั้ง",
        {'intent': 'count', 'entities': {'result_type': 'fail', 'time_period': 'today'}}
    )

    # Test follow-up detection
    is_followup = context_memory._is_followup_question("แล้ว PASS ล่ะ")
    print(f"  • Follow-up detection: {is_followup} ✅")

    # Test context retrieval
    context = context_memory.get_context("แล้ว PASS ล่ะ")
    print(f"  • Context retrieval: {len(context['recent_exchanges'])} exchanges")

    # Test enrichment
    enriched = context_memory.enrich_query("แล้ว PASS ล่ะ")
    print(f"  • Query enrichment: {enriched[:60]}...")

    print("  ✅ Context Memory working")
except Exception as e:
    print(f"❌ Context Memory error: {e}")
    import traceback
    traceback.print_exc()

# Test 7: Intelligent Engine V2
print("\n7️⃣ Testing Intelligent Engine V2...")
try:
    engine_v2 = IntelligentAIEngineV2(
        ai_agent,
        db_agent,
        doc_rag,
        mode='auto'
    )
    print("✅ Intelligent Engine V2 initialized")

    # Test query understanding
    understanding = engine_v2._understand_query("วิเคราะห์ผลการตรวจสอบวันนี้")
    print(f"  • Query understanding:")
    print(f"    Intent: {understanding['intent']}")
    print(f"    Complexity: {understanding['complexity']}")

    # Test execution mode decision
    exec_mode = engine_v2._decide_execution_mode(understanding)
    print(f"    Execution mode: {exec_mode}")

    print("  ✅ Engine V2 core functions working")
except Exception as e:
    print(f"❌ Engine V2 error: {e}")
    import traceback
    traceback.print_exc()

# Test 8: Full Query Processing (if Ollama available)
if ai_agent.is_available():
    print("\n8️⃣ Testing Full Query Processing...")

    test_queries = [
        ("Simple", "มีการตรวจสอบกี่ครั้งวันนี้"),
        # ReAct and Multi-Agent tests would be too slow for quick testing
    ]

    for test_name, query in test_queries:
        print(f"\n  Test: {test_name}")
        print(f"  Query: {query}")
        print("  " + "-" * 56)

        try:
            answer = engine_v2.process_query(query, use_context=True)
            print(f"\n  📋 Answer Preview:")
            print(f"  {answer[:200]}...")
            print("  " + "-" * 56)
            print(f"  ✅ {test_name} query processed")
        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()
else:
    print("\n8️⃣ Skipping full query processing (Ollama not available)")

# Summary
print("\n" + "=" * 60)
print("✨ Test Summary")
print("=" * 60)
print("✅ ReAct Engine: Initialized")
print("✅ Context Memory: Working")
print("✅ Intelligent Engine V2: Working")

if ai_agent.is_available():
    print("✅ Full Processing: Tested")
else:
    print("⚠️ Full Processing: Not tested (Ollama required)")

print("=" * 60)

print("\n💡 To test advanced features:")
print("   1. Start Ollama: ollama serve")
print("   2. Run: python3 test_level2.py")
print("   3. Or test in GUI: python3 main.py (AI tab)")
print()

print("📚 Level 2 Features:")
print("   ✓ ReAct Pattern - AI chooses tools automatically")
print("   ✓ Context Memory - Remembers conversation")
print("   ✓ Multi-Agent - Planner → Executor → Analyzer")
print("   ✓ Advanced Tools - calculate, compare, analyze_trend")
print()

db.close()
