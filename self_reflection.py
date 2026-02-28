"""
Self-Reflection System (Level 3)
AI ตรวจสอบและประเมินคำตอบของตัวเอง

Features:
- Answer quality assessment
- Factual accuracy checking
- Hallucination detection
- Self-correction
"""

import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple


class SelfReflectionSystem:
    """AI reflects on and improves its own answers"""

    def __init__(self, ai_agent):
        self.ai_agent = ai_agent
        self.reflection_history = []

        print("✓ Self-Reflection System initialized")
        print("  → Quality assessment: enabled")
        print("  → Factual checking: enabled")
        print("  → Self-correction: enabled")

    def reflect_on_answer(self,
                         question: str,
                         answer: str,
                         evidence: Dict[str, Any],
                         verbose: bool = False) -> Dict[str, Any]:
        """
        Reflect on an answer and assess its quality

        Args:
            question: Original question
            answer: Generated answer
            evidence: Evidence used to generate answer
            verbose: Print reflection process

        Returns:
            reflection: Dict with assessment and improvements
        """

        if verbose:
            print(f"\n{'━'*60}")
            print(f"🔍 Self-Reflection Process")
            print(f"{'━'*60}\n")

        # Step 1: Quality Assessment
        if verbose:
            print("1️⃣ Quality Assessment...")
        quality = self._assess_quality(question, answer, evidence)

        # Step 2: Factual Accuracy Check
        if verbose:
            print("2️⃣ Checking Factual Accuracy...")
        accuracy = self._check_accuracy(answer, evidence)

        # Step 3: Hallucination Detection
        if verbose:
            print("3️⃣ Detecting Hallucinations...")
        hallucination = self._detect_hallucination(answer, evidence)

        # Step 4: Overall Assessment
        if verbose:
            print("4️⃣ Overall Assessment...")

        overall_score = (quality['score'] + accuracy['score'] + (1.0 - hallucination['score'])) / 3.0

        reflection = {
            'timestamp': datetime.now().isoformat(),
            'question': question,
            'answer': answer[:200] + "..." if len(answer) > 200 else answer,
            'quality': quality,
            'accuracy': accuracy,
            'hallucination': hallucination,
            'overall_score': overall_score,
            'passed': overall_score >= 0.7,
            'improvements': []
        }

        # Step 5: Generate Improvements (if needed)
        if overall_score < 0.8:
            if verbose:
                print("5️⃣ Generating Improvements...")
            improvements = self._generate_improvements(question, answer, evidence, reflection)
            reflection['improvements'] = improvements

        # Store reflection
        self.reflection_history.append(reflection)

        if verbose:
            print(f"\n📊 Reflection Score: {overall_score:.2f}")
            print(f"✅ Passed: {reflection['passed']}")
            if reflection['improvements']:
                print(f"💡 Improvements suggested: {len(reflection['improvements'])}")
            print(f"{'━'*60}\n")

        return reflection

    def _assess_quality(self, question: str, answer: str, evidence: Dict) -> Dict[str, Any]:
        """Assess answer quality"""

        prompt = f"""ประเมินคุณภาพของคำตอบนี้ในมาตราส่วน 0-1:

คำถาม: {question}

คำตอบ: {answer}

ประเมินตาม:
1. Relevance: ตอบตรงประเด็นหรือไม่ (0-1)
2. Completeness: ครบถ้วนหรือไม่ (0-1)
3. Clarity: อ่านเข้าใจง่ายหรือไม่ (0-1)
4. Structure: จัดรูปแบบดีหรือไม่ (0-1)

ตอบในรูป JSON:
{{
  "relevance": 0.9,
  "completeness": 0.8,
  "clarity": 0.85,
  "structure": 0.9,
  "overall": 0.86,
  "reasoning": "คำตอบตรงประเด็น แต่ขาดรายละเอียดบางส่วน"
}}

Assessment:"""

        try:
            response = self.ai_agent.chat(prompt)
            # Parse JSON
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                assessment = json.loads(json_match.group())
                return {
                    'score': assessment.get('overall', 0.5),
                    'details': assessment,
                    'reasoning': assessment.get('reasoning', '')
                }
        except:
            pass

        # Fallback: simple heuristic
        return {
            'score': 0.7,
            'details': {},
            'reasoning': 'Unable to assess automatically'
        }

    def _check_accuracy(self, answer: str, evidence: Dict) -> Dict[str, Any]:
        """Check if answer is factually accurate based on evidence"""

        # Extract claims from answer
        claims = self._extract_claims(answer)

        # Check each claim against evidence
        verified_claims = 0
        total_claims = len(claims)

        for claim in claims:
            if self._verify_claim(claim, evidence):
                verified_claims += 1

        accuracy_score = verified_claims / total_claims if total_claims > 0 else 1.0

        return {
            'score': accuracy_score,
            'verified_claims': verified_claims,
            'total_claims': total_claims,
            'details': claims[:3]  # Show first 3 claims
        }

    def _extract_claims(self, answer: str) -> List[str]:
        """Extract factual claims from answer"""

        # Simple extraction: split by periods and filter
        sentences = answer.split('.')
        claims = []

        for sentence in sentences:
            sentence = sentence.strip()
            # Look for sentences with numbers or specific assertions
            if sentence and (any(char.isdigit() for char in sentence) or len(sentence.split()) > 5):
                claims.append(sentence)

        return claims[:10]  # Limit to 10 claims

    def _verify_claim(self, claim: str, evidence: Dict) -> bool:
        """Verify if a claim is supported by evidence"""

        # Convert evidence to text
        evidence_text = json.dumps(evidence, ensure_ascii=False)

        # Check if claim keywords appear in evidence
        claim_words = set(claim.lower().split())
        evidence_words = set(evidence_text.lower().split())

        # Calculate overlap
        overlap = len(claim_words & evidence_words)
        overlap_ratio = overlap / len(claim_words) if claim_words else 0

        # Consider verified if >30% overlap
        return overlap_ratio > 0.3

    def _detect_hallucination(self, answer: str, evidence: Dict) -> Dict[str, Any]:
        """Detect potential hallucinations (made-up facts)"""

        prompt = f"""ตรวจสอบว่าคำตอบนี้มีข้อมูลที่แต่งขึ้นมาเอง (hallucination) หรือไม่:

คำตอบ: {answer}

หลักฐานที่มี:
{json.dumps(evidence, ensure_ascii=False, indent=2, default=str)[:500]}

ตรวจสอบ:
1. มีตัวเลขหรือชื่อที่ไม่มีในหลักฐานหรือไม่?
2. มีรายละเอียดที่เฉพาะเจาะจงเกินไป แต่ไม่มีในหลักฐาน?
3. มีข้อเท็จจริงที่ขัดแย้งกับหลักฐาน?

ตอบใน JSON:
{{
  "has_hallucination": false,
  "confidence": 0.95,
  "suspicious_parts": [],
  "reasoning": "คำตอบอิงจากหลักฐานทั้งหมด"
}}

Analysis:"""

        try:
            response = self.ai_agent.chat(prompt)
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    'score': 1.0 if result.get('has_hallucination', False) else 0.0,
                    'confidence': result.get('confidence', 0.5),
                    'suspicious_parts': result.get('suspicious_parts', []),
                    'reasoning': result.get('reasoning', '')
                }
        except:
            pass

        # Fallback: simple check
        return {
            'score': 0.0,
            'confidence': 0.5,
            'suspicious_parts': [],
            'reasoning': 'Unable to detect automatically'
        }

    def _generate_improvements(self, question: str, answer: str, evidence: Dict, reflection: Dict) -> List[str]:
        """Generate improvement suggestions"""

        issues = []

        # Identify issues
        if reflection['quality']['score'] < 0.7:
            issues.append(f"Quality issues: {reflection['quality']['reasoning']}")

        if reflection['accuracy']['score'] < 0.8:
            issues.append(f"Accuracy issues: Only {reflection['accuracy']['verified_claims']}/{reflection['accuracy']['total_claims']} claims verified")

        if reflection['hallucination']['score'] > 0.3:
            issues.append(f"Possible hallucinations: {', '.join(reflection['hallucination']['suspicious_parts'][:2])}")

        prompt = f"""คำตอบมีปัญหาดังนี้:
{chr(10).join(['- ' + issue for issue in issues])}

คำถาม: {question}
คำตอบปัจจุบัน: {answer[:200]}...
หลักฐาน: {json.dumps(evidence, ensure_ascii=False, default=str)[:300]}...

แนะนำวิธีปรับปรุง 3 ข้อ:

Suggestions:"""

        try:
            response = self.ai_agent.chat(prompt)
            # Extract bullet points
            import re
            suggestions = re.findall(r'[•\-\d]+\.\s*(.+)', response)
            return suggestions[:3]
        except:
            return ["ตรวจสอบความถูกต้องของข้อมูล", "เพิ่มรายละเอียดจากหลักฐาน", "ลดข้อมูลที่ไม่แน่ใจ"]

    def get_corrected_answer(self, question: str, answer: str, evidence: Dict) -> Tuple[str, Dict]:
        """
        Get self-corrected answer

        Args:
            question: Original question
            answer: Original answer
            evidence: Evidence available

        Returns:
            (corrected_answer, reflection)
        """

        # First reflect
        reflection = self.reflect_on_answer(question, answer, evidence, verbose=False)

        # If score is high enough, no need to correct
        if reflection['overall_score'] >= 0.8:
            return answer, reflection

        # Generate corrected answer
        prompt = f"""คำตอบเดิมมีปัญหา (คะแนน: {reflection['overall_score']:.2f}/1.0):

คำถาม: {question}

คำตอบเดิม:
{answer}

ปัญหา:
- Quality: {reflection['quality']['reasoning']}
- Accuracy: {reflection['accuracy']['verified_claims']}/{reflection['accuracy']['total_claims']} claims verified
- Hallucination: {reflection['hallucination']['reasoning']}

หลักฐานที่มี:
{json.dumps(evidence, ensure_ascii=False, indent=2, default=str)}

ข้อเสนอแนะ:
{chr(10).join(['- ' + imp for imp in reflection['improvements']])}

โปรดสร้างคำตอบใหม่ที่:
1. อิงจากหลักฐานเท่านั้น (ไม่แต่งเพิ่ม)
2. ตอบตรงประเด็น ครบถ้วน
3. อ่านง่าย มีโครงสร้างชัดเจน

คำตอบที่ปรับปรุงแล้ว:"""

        corrected_answer = self.ai_agent.chat(prompt)

        # Reflect again
        new_reflection = self.reflect_on_answer(question, corrected_answer, evidence, verbose=False)
        new_reflection['is_corrected'] = True
        new_reflection['original_score'] = reflection['overall_score']
        new_reflection['improvement'] = new_reflection['overall_score'] - reflection['overall_score']

        return corrected_answer, new_reflection

    def get_reflection_summary(self) -> Dict[str, Any]:
        """Get summary of all reflections"""

        if not self.reflection_history:
            return {
                'total_reflections': 0,
                'average_score': 0.0,
                'pass_rate': 0.0
            }

        total = len(self.reflection_history)
        total_score = sum(r['overall_score'] for r in self.reflection_history)
        passed = sum(1 for r in self.reflection_history if r['passed'])

        return {
            'total_reflections': total,
            'average_score': total_score / total,
            'pass_rate': passed / total,
            'recent_scores': [r['overall_score'] for r in self.reflection_history[-5:]]
        }

    def clear_history(self):
        """Clear reflection history"""
        self.reflection_history = []
        print("✓ Reflection history cleared")


# Example usage
if __name__ == "__main__":
    print("Self-Reflection System (Level 3)")
    print("=" * 60)
    print("\nFeatures:")
    print("  ✓ Quality assessment (relevance, completeness, clarity)")
    print("  ✓ Factual accuracy checking")
    print("  ✓ Hallucination detection")
    print("  ✓ Self-correction")
    print("=" * 60)
