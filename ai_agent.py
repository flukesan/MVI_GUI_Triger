"""
AI Agent Module for MVI Inspection System
Supports multiple Ollama models with model selection
"""

import requests
import json
from datetime import datetime


class AIAgent:
    """AI Agent with model selection and chat capabilities"""

    def __init__(self, ollama_url="http://localhost:11434"):
        self.ollama_url = ollama_url
        self.current_model = "llama3.2"
        self.available_models = []
        self.conversation_history = []
        self.max_history = 10  # Keep last 10 exchanges

        # Try to connect and get available models
        self.refresh_available_models()

    def refresh_available_models(self):
        """Get list of installed models from Ollama"""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.available_models = [
                    {
                        "name": model["name"],
                        "size": model.get("size", 0),
                        "modified": model.get("modified_at", ""),
                        "family": self.get_model_family(model["name"])
                    }
                    for model in data.get("models", [])
                ]
                print(f"✓ พบ {len(self.available_models)} AI models")

                # Set first available model as current if not set
                if self.available_models and self.current_model not in [m["name"] for m in self.available_models]:
                    self.current_model = self.available_models[0]["name"]
                    print(f"✓ ตั้งค่า default model: {self.current_model}")

                return True
            else:
                print(f"⚠️ ไม่สามารถเชื่อมต่อ Ollama (status: {response.status_code})")
                return False
        except requests.exceptions.ConnectionError:
            print("⚠️ Ollama server ไม่ทำงาน - กรุณาเริ่ม Ollama ก่อน (ollama serve)")
            return False
        except Exception as e:
            print(f"❌ Error connecting to Ollama: {e}")
            return False

    def get_model_family(self, model_name):
        """Determine model family (text/vision/code)"""
        model_lower = model_name.lower()
        if "llava" in model_lower or "vision" in model_lower:
            return "vision"
        elif "code" in model_lower:
            return "code"
        else:
            return "text"

    def set_model(self, model_name):
        """Switch to different model"""
        if any(m["name"] == model_name for m in self.available_models):
            self.current_model = model_name
            print(f"✓ เปลี่ยนเป็น model: {model_name}")
            # Clear conversation history when switching models
            self.conversation_history = []
            return True
        else:
            print(f"❌ Model {model_name} ไม่พบในระบบ")
            return False

    def get_model_info(self, model_name=None):
        """Get detailed info about a model"""
        if model_name is None:
            model_name = self.current_model

        try:
            response = requests.post(
                f"{self.ollama_url}/api/show",
                json={"name": model_name},
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
            else:
                return None
        except:
            return None

    def chat(self, user_message, context=None, system_prompt=None):
        """Chat with AI model"""
        if not self.available_models:
            return "❌ ไม่พบ AI models - กรุณาติดตั้ง Ollama และ pull models ก่อน"

        # Default system prompt for MVI context
        if system_prompt is None:
            system_prompt = """คุณเป็น AI Assistant สำหรับระบบ MVI (Maximo Visual Inspection).
คุณช่วยวิเคราะห์ผลการตรวจสอบ, แนะนำแก้ปัญหา, สรุปข้อมูล, และตอบคำถามเกี่ยวกับระบบ.
ตอบเป็นภาษาไทยที่เข้าใจง่าย กระชับ และตรงประเด็น.
ถ้าไม่แน่ใจ ให้บอกว่าไม่แน่ใจ อย่าสร้างข้อมูลเท็จ."""

        # Build messages
        messages = [
            {"role": "system", "content": system_prompt}
        ]

        # Add context if provided
        if context:
            context_str = json.dumps(context, ensure_ascii=False, indent=2)
            messages.append({
                "role": "system",
                "content": f"ข้อมูลเพิ่มเติม:\n{context_str}"
            })

        # Add conversation history (limit to max_history)
        messages.extend(self.conversation_history[-self.max_history:])

        # Add user message
        messages.append({"role": "user", "content": user_message})

        # Call Ollama API
        try:
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.current_model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 512
                    }
                },
                timeout=60  # 60 second timeout
            )

            if response.status_code == 200:
                ai_response = response.json()["message"]["content"]

                # Save to history
                self.conversation_history.append({"role": "user", "content": user_message})
                self.conversation_history.append({"role": "assistant", "content": ai_response})

                return ai_response
            else:
                return f"❌ Error: HTTP {response.status_code}"

        except requests.exceptions.Timeout:
            return "⏱️ Timeout - AI ใช้เวลานานเกินไป กรุณาลองใหม่"
        except requests.exceptions.ConnectionError:
            return "❌ ไม่สามารถเชื่อมต่อ Ollama server - กรุณาเริ่ม Ollama ก่อน"
        except Exception as e:
            return f"❌ เกิดข้อผิดพลาด: {str(e)}"

    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
        print("🗑️ ล้างประวัติการสนทนาแล้ว")

    def analyze_defect_pattern(self, history_data):
        """วิเคราะห์ pattern ของ defects จาก history"""
        if not history_data:
            return "ไม่มีข้อมูลให้วิเคราะห์"

        prompt = f"""วิเคราะห์ข้อมูลการตรวจสอบต่อไปนี้ และสรุป:
1. จำนวนครั้งที่ Pass/Fail
2. Defect ที่พบบ่อยที่สุด (ถ้ามี)
3. Pattern หรือแนวโน้มที่น่าสังเกต
4. ข้อเสนอแนะ

ข้อมูล (รูปแบบ: device_id, result, count):
{json.dumps(history_data, ensure_ascii=False, indent=2)}

โปรดวิเคราะห์และให้คำแนะนำ:"""

        return self.chat(prompt)

    def suggest_troubleshooting(self, error_description):
        """แนะนำวิธีแก้ปัญหา"""
        prompt = f"""ช่วยวิเคราะห์ปัญหาและแนะนำวิธีแก้ไข:

ปัญหา: {error_description}

โปรดให้:
1. สาเหตุที่เป็นไปได้
2. ขั้นตอนแก้ปัญหาทีละขั้น
3. วิธีป้องกันไม่ให้เกิดซ้ำ"""

        return self.chat(prompt)

    def generate_summary_report(self, data, report_type="daily"):
        """สร้างรายงานสรุป"""
        prompt = f"""สร้างรายงานสรุป{report_type}จากข้อมูลต่อไปนี้:

{json.dumps(data, ensure_ascii=False, indent=2)}

โปรดสรุปในรูปแบบ:
- สถิติรวม (Pass/Fail)
- จุดเด่น/ข้อสังเกต
- ข้อเสนอแนะ

ใช้ emoji และจัดรูปแบบให้อ่านง่าย:"""

        return self.chat(prompt)

    def is_available(self):
        """Check if Ollama is available"""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False


# Example usage
if __name__ == "__main__":
    # Test AI Agent
    agent = AIAgent()

    if agent.is_available():
        print("\n=== Testing AI Agent ===\n")

        # Test chat
        response = agent.chat("สวัสดี ช่วยแนะนำตัวหน่อย")
        print(f"AI: {response}\n")

        # Test defect analysis
        test_data = [
            ("Watashi_cam", "fail", 15),
            ("Watashi_cam", "pass", 5),
            ("Basler_GigE", "fail", 8),
            ("Basler_GigE", "pass", 12)
        ]
        analysis = agent.analyze_defect_pattern(test_data)
        print(f"Analysis: {analysis}\n")
    else:
        print("❌ Ollama not available. Please start Ollama server.")
