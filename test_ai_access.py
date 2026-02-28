#!/usr/bin/env python3
"""
Test script to verify AI can access database and documents
"""

import sys
import os

print("=" * 60)
print("🧪 Testing AI Access to Database and Documents")
print("=" * 60)

# Test 1: Check if AI modules exist
print("\n1️⃣ Checking AI modules...")
try:
    from ai_agent import AIAgent
    print("✅ ai_agent.py found")
except ImportError as e:
    print(f"❌ ai_agent.py not found: {e}")
    sys.exit(1)

try:
    from document_rag import DocumentRAG
    print("✅ document_rag.py found")
except ImportError as e:
    print(f"❌ document_rag.py not found: {e}")
    sys.exit(1)

try:
    from database_agent import DatabaseAgent
    print("✅ database_agent.py found")
except ImportError as e:
    print(f"❌ database_agent.py not found: {e}")
    sys.exit(1)

# Test 2: Initialize AI Agent
print("\n2️⃣ Initializing AI Agent...")
ai_agent = AIAgent()

if ai_agent.is_available():
    print(f"✅ Ollama connected")
    print(f"   Current model: {ai_agent.current_model}")
    print(f"   Available models: {len(ai_agent.available_models)}")
else:
    print("⚠️  Ollama not available (AI features will be limited)")
    print("   Install: curl -fsSL https://ollama.com/install.sh | sh")
    print("   Start: ollama serve")
    print("   Pull model: ollama pull llama3.2")

# Test 3: Check Document RAG
print("\n3️⃣ Checking Document RAG...")
doc_rag = DocumentRAG(ai_agent, documents_folder="manuals")
doc_count = doc_rag.get_document_count()
print(f"✅ Document RAG initialized")
print(f"   Documents found: {doc_count} files")

if doc_count > 0:
    print("\n   📄 Documents:")
    for filename, doc_data in list(doc_rag.documents.items())[:5]:
        size_kb = doc_data['size'] / 1024
        print(f"      • {filename} ({size_kb:.1f} KB)")
else:
    print("   ℹ️  No documents found in manuals/ folder")
    print("      Add PDF/TXT/MD files to manuals/ to enable document search")

# Test 4: Check Database Access
print("\n4️⃣ Checking Database Access...")
try:
    from history_manager import HistoryManager
    history_manager = HistoryManager()
    print("✅ History manager initialized")

    import sqlite3
    db_connection = sqlite3.connect(history_manager.db_path)
    db_agent = DatabaseAgent(ai_agent, db_connection)
    print("✅ Database agent initialized")

    # Get database schema
    schema = db_agent.get_database_schema()
    print(f"   Database schema:")
    for line in schema.split('\n')[:10]:
        if line.strip():
            print(f"      {line}")

    # Get statistics
    try:
        stats = db_agent.get_statistics("today")
        print(f"\n   📊 Today's statistics:")
        print(f"      Total: {stats['total']}")
        print(f"      Pass: {stats['pass']}")
        print(f"      Fail: {stats['fail']}")
        print(f"      Pass rate: {stats['pass_rate']:.1f}%")
    except Exception as e:
        print(f"   ⚠️  Could not get statistics: {e}")

except Exception as e:
    print(f"❌ Database access failed: {e}")
    import traceback
    traceback.print_exc()

# Test 5: Test AI Query (if Ollama available)
if ai_agent.is_available():
    print("\n5️⃣ Testing AI Query...")
    try:
        response = ai_agent.chat("สวัสดี ตอบสั้นๆ ภายใน 1 บรรทัด")
        print(f"✅ AI response: {response[:100]}...")
    except Exception as e:
        print(f"⚠️  AI query failed: {e}")
else:
    print("\n5️⃣ Skipping AI query test (Ollama not available)")

# Summary
print("\n" + "=" * 60)
print("📝 Summary")
print("=" * 60)
print(f"✅ AI Modules: OK")
print(f"{'✅' if ai_agent.is_available() else '⚠️ '} Ollama: {'Connected' if ai_agent.is_available() else 'Not available'}")
print(f"✅ Document RAG: {doc_count} documents")
print(f"✅ Database Access: OK")
print("=" * 60)

if not ai_agent.is_available():
    print("\n💡 To enable full AI features:")
    print("   1. Install Ollama: curl -fsSL https://ollama.com/install.sh | sh")
    print("   2. Start Ollama: ollama serve")
    print("   3. Pull model: ollama pull llama3.2")

if doc_count == 0:
    print("\n💡 To enable document search:")
    print("   1. Add PDF/TXT/MD files to manuals/ folder")
    print("   2. Restart the application")

print("\n✨ Test complete!")
