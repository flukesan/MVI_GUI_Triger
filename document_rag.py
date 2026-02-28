"""
Document RAG (Retrieval-Augmented Generation) System
Automatically loads and searches PDF, TXT, MD documents
"""

import os
from pathlib import Path
import json


class DocumentRAG:
    """RAG system for searching and querying documents"""

    def __init__(self, ai_agent, documents_folder="manuals"):
        self.ai_agent = ai_agent
        self.documents_folder = documents_folder
        self.documents = {}  # {filename: {text, metadata}}
        self.index = {}  # Simple keyword index

        # Create folder if not exists
        if not os.path.exists(self.documents_folder):
            os.makedirs(self.documents_folder)
            print(f"✓ สร้าง folder: {self.documents_folder}")

        # Auto-load documents on init
        self.load_all_documents()

    def load_all_documents(self):
        """Auto-scan and load all documents from folder"""
        print(f"🔍 กำลังค้นหาเอกสารใน {self.documents_folder}...")

        supported_extensions = ['.pdf', '.txt', '.md']
        found_files = []

        # Walk through all subdirectories
        for root, dirs, files in os.walk(self.documents_folder):
            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()

                if ext in supported_extensions:
                    found_files.append(file_path)

        print(f"📁 พบไฟล์ {len(found_files)} ไฟล์")

        # Load each document
        for file_path in found_files:
            try:
                self.load_document(file_path)
            except Exception as e:
                print(f"⚠️ ไม่สามารถโหลด {file_path}: {e}")

        print(f"✓ โหลดเอกสารสำเร็จ {len(self.documents)} ไฟล์")

        if len(self.documents) > 0:
            self.build_index()

    def load_document(self, file_path):
        """Load a single document"""
        ext = os.path.splitext(file_path)[1].lower()
        filename = os.path.basename(file_path)

        if ext == '.pdf':
            text = self.extract_pdf(file_path)
        elif ext in ['.txt', '.md']:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
        else:
            return

        # Store document
        self.documents[filename] = {
            "text": text,
            "path": file_path,
            "size": os.path.getsize(file_path),
            "modified": os.path.getmtime(file_path),
            "type": ext[1:]  # Remove dot
        }

        print(f"  ✓ {filename} ({len(text)} chars)")

    def extract_pdf(self, pdf_path):
        """Extract text from PDF"""
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(pdf_path)
            full_text = ""

            for page_num in range(len(doc)):
                page = doc[page_num]
                full_text += f"\n--- หน้า {page_num + 1} ---\n"
                full_text += page.get_text()

            return full_text

        except ImportError:
            print("⚠️ PyMuPDF ไม่ได้ติดตั้ง - ข้าม PDF files")
            print("   ติดตั้งด้วย: pip install PyMuPDF")
            return ""
        except Exception as e:
            print(f"⚠️ Error reading PDF: {e}")
            return ""

    def build_index(self):
        """Build simple keyword index"""
        self.index = {}

        for filename, doc_data in self.documents.items():
            text = doc_data["text"].lower()
            # Split into words (simple tokenization)
            words = set(text.split())

            for word in words:
                # Index words longer than 3 chars
                if len(word) > 3:
                    if word not in self.index:
                        self.index[word] = []
                    self.index[word].append(filename)

        print(f"✓ สร้าง index {len(self.index)} keywords")

    def search_documents(self, query, max_results=3):
        """Search for relevant documents"""
        query_words = query.lower().split()
        doc_scores = {}

        # Score documents by keyword matches
        for word in query_words:
            if word in self.index:
                for filename in self.index[word]:
                    doc_scores[filename] = doc_scores.get(filename, 0) + 1

        # Sort by score
        ranked_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)

        # Get top results
        results = []
        for filename, score in ranked_docs[:max_results]:
            # Extract relevant excerpt
            text = self.documents[filename]["text"]
            excerpt = self.extract_relevant_excerpt(text, query_words)

            results.append({
                "filename": filename,
                "score": score,
                "excerpt": excerpt,
                "path": self.documents[filename]["path"]
            })

        return results

    def extract_relevant_excerpt(self, text, query_words, context_chars=500):
        """Extract relevant text excerpt around query words"""
        text_lower = text.lower()

        # Find first occurrence of any query word
        best_pos = -1
        for word in query_words:
            pos = text_lower.find(word.lower())
            if pos != -1 and (best_pos == -1 or pos < best_pos):
                best_pos = pos

        if best_pos == -1:
            # No match found, return beginning
            return text[:context_chars] + "..."

        # Extract context around the word
        start = max(0, best_pos - context_chars // 2)
        end = min(len(text), best_pos + context_chars // 2)

        excerpt = text[start:end]

        if start > 0:
            excerpt = "..." + excerpt
        if end < len(text):
            excerpt = excerpt + "..."

        return excerpt

    def ask_with_rag(self, question):
        """Ask question with RAG (Retrieval-Augmented Generation)"""
        if not self.documents:
            return "ไม่มีเอกสารในระบบ - กรุณาเพิ่มเอกสารใน folder 'manuals'"

        # 1. Search for relevant documents
        results = self.search_documents(question)

        if not results:
            return "ไม่พบเอกสารที่เกี่ยวข้องกับคำถาม"

        # 2. Build context from search results
        context = "เอกสารที่เกี่ยวข้อง:\n\n"

        for i, result in enumerate(results, 1):
            context += f"📄 [{i}] {result['filename']}:\n"
            context += f"{result['excerpt']}\n\n"

        # 3. Ask AI with context
        prompt = f"""คำถาม: {question}

{context}

โปรดตอบคำถามโดยอ้างอิงจากเอกสารที่ให้มา:
- ถ้าพบคำตอบ ให้ตอบพร้อมอ้างอิงชื่อไฟล์
- ถ้าไม่พบ ให้บอกว่าไม่มีข้อมูลในเอกสาร"""

        answer = self.ai_agent.chat(prompt)

        # 4. Add source references
        sources = "\n\n📚 แหล่งอ้างอิง:\n"
        for result in results:
            sources += f"  • {result['filename']} (score: {result['score']})\n"

        return answer + sources

    def list_documents(self):
        """List all loaded documents"""
        if not self.documents:
            return "ไม่มีเอกสารในระบบ"

        doc_list = f"📚 เอกสารในระบบ ({len(self.documents)} ไฟล์):\n\n"

        for filename, doc_data in sorted(self.documents.items()):
            size_kb = doc_data["size"] / 1024
            doc_type = doc_data["type"].upper()
            doc_list += f"• {filename} ({doc_type}, {size_kb:.1f} KB)\n"

        return doc_list

    def refresh_documents(self):
        """Reload all documents"""
        self.documents = {}
        self.index = {}
        self.load_all_documents()

    def get_document_count(self):
        """Get number of loaded documents"""
        return len(self.documents)


# Example usage
if __name__ == "__main__":
    from ai_agent import AIAgent

    # Test Document RAG
    agent = AIAgent()
    doc_rag = DocumentRAG(agent, documents_folder="manuals")

    print("\n=== Testing Document RAG ===\n")

    # List documents
    print(doc_rag.list_documents())

    # Test search
    if doc_rag.get_document_count() > 0:
        results = doc_rag.search_documents("MVI Edge")
        print(f"\nSearch results for 'MVI Edge':")
        for result in results:
            print(f"  • {result['filename']} (score: {result['score']})")

        # Test RAG query
        if agent.is_available():
            answer = doc_rag.ask_with_rag("อธิบายวิธีตั้งค่า MVI Edge")
            print(f"\nRAG Answer:\n{answer}")
    else:
        print("\n⚠️ ไม่มีเอกสาร - วาง PDF/TXT files ใน folder 'manuals'")
