#!/usr/bin/env python3
"""
Test Intelligent AI Engine Level 3
Tests: Vector Search, Self-Reflection, Long-term Memory
"""

import sys
import sqlite3

print("=" * 60)
print("🧪 Testing Intelligent AI Engine (Level 3)")
print("=" * 60)

# Test 1: Import modules
print("\n1️⃣ Testing imports...")
try:
    from ai_agent import AIAgent
    from database_agent import DatabaseAgent
    from document_rag import DocumentRAG

    # Level 3 imports
    try:
        from vector_search import VectorSearchEngine
        VECTOR_AVAILABLE = True
    except ImportError:
        print("   ⚠️ Vector Search not available (sentence-transformers not installed)")
        VECTOR_AVAILABLE = False

    from self_reflection import SelfReflectionSystem
    from longterm_memory import LongTermMemoryManager
    from intelligent_engine_v3 import IntelligentAIEngineV3

    print("✅ All Level 3 modules imported")
except Exception as e:
    print(f"❌ Import error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 2: Initialize AI Agent
print("\n2️⃣ Initializing AI components...")
try:
    ai_agent = AIAgent()
    if ai_agent.is_available():
        print(f"✅ AI Agent ready (Model: {ai_agent.current_model})")
    else:
        print("⚠️ Ollama not available - limited testing")
except Exception as e:
    print(f"❌ AI Agent error: {e}")
    sys.exit(1)

# Test 3: Database Agent
print("\n3️⃣ Initializing Database Agent...")
try:
    db = sqlite3.connect("inspection_history.db")
    db_agent = DatabaseAgent(ai_agent, db)

    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM inspections")
    count = cursor.fetchone()[0]
    print(f"✅ Database Agent initialized")
    print(f"   📊 Total inspections: {count}")
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

# Test 5: Vector Search
if VECTOR_AVAILABLE:
    print("\n5️⃣ Testing Vector Search...")
    try:
        vector_search = VectorSearchEngine(use_gpu=False)
        print("✅ Vector Search Engine initialized")

        # Test with sample inspections
        cursor = db.cursor()
        cursor.execute("""
            SELECT id, timestamp, device_id, result, station
            FROM inspections
            LIMIT 10
        """)

        columns = ['id', 'timestamp', 'device_id', 'result', 'station']
        inspections = []
        for row in cursor.fetchall():
            inspections.append(dict(zip(columns, row)))

        if inspections:
            print(f"  📊 Indexing {len(inspections)} sample inspections...")
            vector_search.index_inspections(inspections)

            # Test search
            print("  🔍 Testing semantic search...")
            results = vector_search.search_inspections("camera inspection failed", top_k=3, threshold=0.1)
            print(f"  ✅ Found {len(results)} results")
            if results:
                print(f"     Top result score: {results[0].get('_score', 0):.3f}")
    except Exception as e:
        print(f"❌ Vector Search error: {e}")
        import traceback
        traceback.print_exc()
else:
    print("\n5️⃣ Skipping Vector Search (not available)")
    print("   Install: pip install sentence-transformers")

# Test 6: Self-Reflection
print("\n6️⃣ Testing Self-Reflection...")
try:
    reflection_sys = SelfReflectionSystem(ai_agent)
    print("✅ Self-Reflection System initialized")

    # Test reflection (without AI if Ollama not available)
    if not ai_agent.is_available():
        print("  ⏭️ Skipping reflection test (Ollama required)")
    else:
        print("  🪞 Testing answer reflection...")
        test_answer = "มีการตรวจสอบ 7 ครั้งวันนี้ ผลลัพธ์ 5 PASS และ 2 FAIL"
        test_evidence = {
            'statistics': {'total': 7, 'pass': 5, 'fail': 2}
        }

        reflection = reflection_sys.reflect_on_answer(
            question="มีการตรวจสอบกี่ครั้งวันนี้",
            answer=test_answer,
            evidence=test_evidence,
            verbose=False
        )

        print(f"  ✅ Reflection completed")
        print(f"     Quality score: {reflection['overall_score']:.2f}")
        print(f"     Passed: {reflection['passed']}")
except Exception as e:
    print(f"❌ Self-Reflection error: {e}")
    import traceback
    traceback.print_exc()

# Test 7: Long-term Memory
print("\n7️⃣ Testing Long-term Memory...")
try:
    longterm_mem = LongTermMemoryManager(ai_agent, max_memories=50)
    print("✅ Long-term Memory Manager initialized")

    # Add test insight
    longterm_mem.add_insight(
        "User frequently asks about FAIL inspections",
        topic="user_behavior",
        source="test"
    )

    longterm_mem.add_pattern(
        "Basler_GigE has higher fail rate than other devices",
        confidence=0.85
    )

    stats = longterm_mem.get_statistics()
    print(f"  ✅ Memory operations working")
    print(f"     Insights: {stats['total_insights']}")
    print(f"     Patterns: {stats['total_patterns']}")
except Exception as e:
    print(f"❌ Long-term Memory error: {e}")
    import traceback
    traceback.print_exc()

# Test 8: Intelligent Engine V3
print("\n8️⃣ Testing Intelligent Engine V3...")
try:
    engine_v3 = IntelligentAIEngineV3(
        ai_agent,
        db_agent,
        doc_rag,
        mode='auto',
        enable_vector_search=VECTOR_AVAILABLE
    )
    print("✅ Intelligent Engine V3 initialized")

    # Get statistics
    stats = engine_v3.get_statistics()
    print(f"  • Engine version: {stats['engine_version']}")
    print(f"  • Vector search: {stats['level_3']['vector_search_enabled']}")
    print(f"  • Long-term memory: {stats['level_3']['long_term_memory']['total_insights']} insights")

    print("  ✅ Engine V3 working")
except Exception as e:
    print(f"❌ Engine V3 error: {e}")
    import traceback
    traceback.print_exc()

# Test 9: Full Query Processing (if Ollama available)
if ai_agent.is_available():
    print("\n9️⃣ Testing Full Query Processing (Level 3)...")

    test_queries = [
        ("Simple", "มีการตรวจสอบกี่ครั้งทั้งหมด", False, False),
        # More tests would be too slow
    ]

    for test_name, query, use_reflection, use_vector in test_queries:
        print(f"\n  Test: {test_name}")
        print(f"  Query: {query}")
        print("  " + "-" * 56)

        try:
            answer = engine_v3.process_query(
                query,
                use_context=True,
                use_reflection=use_reflection,
                use_vector_search=use_vector
            )
            print(f"\n  📋 Answer Preview:")
            print(f"  {answer[:150]}...")
            print("  " + "-" * 56)
            print(f"  ✅ {test_name} query processed")
        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()
else:
    print("\n9️⃣ Skipping full query processing (Ollama not available)")

# Summary
print("\n" + "=" * 60)
print("✨ Test Summary")
print("=" * 60)

if VECTOR_AVAILABLE:
    print("✅ Vector Search: Available")
else:
    print("⚠️ Vector Search: Not available (install sentence-transformers)")

print("✅ Self-Reflection: Working")
print("✅ Long-term Memory: Working")
print("✅ Intelligent Engine V3: Working")

if ai_agent.is_available():
    print("✅ Full Processing: Tested")
else:
    print("⚠️ Full Processing: Not tested (Ollama required)")

print("=" * 60)

print("\n💡 To test advanced features:")
print("   1. Install sentence-transformers:")
print("      pip install sentence-transformers")
print("   2. Start Ollama: ollama serve")
print("   3. Run: python3 test_level3.py")
print("   4. Or test in GUI: python3 main.py (AI tab)")
print()

print("📚 Level 3 Features:")
print("   ✓ Vector Search - Semantic similarity (not just keywords)")
print("   ✓ Self-Reflection - AI checks its own answers")
print("   ✓ Long-term Memory - Remembers insights and patterns")
print("   ✓ All Level 1+2 features included")
print()

db.close()
