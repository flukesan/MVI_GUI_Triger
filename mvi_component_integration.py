"""
MVI Component Integration
Integration ระหว่าง MVI Detection กับ Component Definition

Features:
- รับ detection results จาก MVI
- Match detected objects กับ expected positions
- ระบุตำแหน่งที่หายได้เจาะจง
- สร้าง annotated images with missing highlights
- บันทึกผลลง database
"""

import cv2
import numpy as np
from typing import List, Dict, Optional, Tuple
import json
from datetime import datetime


class MVIComponentIntegration:
    """Integration ระหว่าง MVI Detection กับ Component Definition"""

    def __init__(self, component_definition_manager):
        """
        Args:
            component_definition_manager: ComponentDefinitionManager instance
        """
        self.comp_manager = component_definition_manager

    def process_mvi_result(self,
                          image: np.ndarray,
                          mvi_detections: List[Dict],
                          product_id: int,
                          verbose: bool = False) -> Dict:
        """
        ประมวลผล MVI detection results + Component Definition

        Args:
            image: ภาพจาก MVI (numpy array)
            mvi_detections: [
                {
                    "class": "pig",
                    "confidence": 0.94,
                    "bbox": {"x": 178, "y": 180, "width": 182, "height": 268}
                },
                {
                    "class": "monk",
                    "confidence": 0.98,
                    "bbox": {"x": 342, "y": 180, "width": 176, "height": 288}
                },
                ...
            ]
            product_id: ID ของ product
            verbose: แสดงข้อความ debug

        Returns:
            Dict {
                "status": "PASS" or "FAIL",
                "reason": str,
                "found": int,
                "total": int,
                "found_percentage": float,
                "missing_components": [str],
                "missing_positions": [str],
                "component_results": [Dict],
                "annotated_image": numpy array
            }
        """

        if verbose:
            print(f"\n{'='*60}")
            print(f"🔍 MVI Component Integration")
            print(f"{'='*60}")

        # 1. โหลด expected components
        expected_components = self.comp_manager.get_product_components(product_id)

        if not expected_components:
            return {
                "status": "ERROR",
                "reason": "No component definitions found for this product",
                "found": 0,
                "total": 0,
                "found_percentage": 0.0,
                "missing_components": [],
                "missing_positions": [],
                "component_results": [],
                "annotated_image": image
            }

        if verbose:
            print(f"Expected components: {len(expected_components)}")
            print(f"MVI detections: {len(mvi_detections)}")

        # 2. Match detected objects กับ expected positions
        matching_results = self._match_components(
            expected_components,
            mvi_detections,
            verbose=verbose
        )

        # 3. วิเคราะห์ผล
        analysis = self._analyze_results(
            matching_results,
            expected_components,
            verbose=verbose
        )

        # 4. สร้าง annotated image
        annotated_image = self._draw_annotations(
            image.copy(),
            matching_results,
            expected_components
        )

        if verbose:
            print(f"\n{'='*60}")
            print(f"Result: {analysis['status']}")
            print(f"Reason: {analysis['reason']}")
            print(f"Found: {analysis['found_count']}/{analysis['total_count']}")
            print(f"{'='*60}\n")

        return {
            "status": analysis["status"],
            "reason": analysis["reason"],
            "found": analysis["found_count"],
            "total": analysis["total_count"],
            "found_percentage": analysis["found_percentage"],
            "missing_components": analysis["missing_components"],
            "missing_positions": analysis["missing_positions"],
            "component_results": matching_results,
            "annotated_image": annotated_image
        }

    def _match_components(self,
                         expected_components: List[Dict],
                         mvi_detections: List[Dict],
                         verbose: bool = False) -> List[Dict]:
        """
        เทียบ expected vs detected

        ⚠️ แก้ไข: เพิ่มการ track detection ที่ match แล้ว
        เพื่อป้องกัน detection ตัวเดียวถูก match กับ expected หลายตัว
        (สำคัญสำหรับ component ชื่อเดียวกันหลายตำแหน่ง เช่น screw ที่ left/center/right)

        Returns:
            List of {
                "component_def_id": int,
                "name": str,
                "position": str,
                "status": "FOUND" or "MISSING",
                "confidence": float,
                "expected_bbox": dict,
                "detected_bbox": dict or None,
                "critical": bool,
                "notes": str
            }
        """

        results = []
        matched_detection_indices = set()  # เก็บ index ของ detection ที่ match แล้ว

        for expected in expected_components:
            # หา detected object ที่ match (ยกเว้นที่ match ไปแล้ว)
            matched, matched_idx = self._find_matching_object(
                expected,
                mvi_detections,
                matched_detection_indices
            )

            if matched:
                # Mark detection นี้ว่า match แล้ว
                matched_detection_indices.add(matched_idx)

                results.append({
                    "component_def_id": expected["id"],
                    "name": expected["name"],
                    "position": expected.get("position", ""),
                    "status": "FOUND",
                    "confidence": matched["confidence"],
                    "expected_bbox": expected["roi"],
                    "detected_bbox": matched["bbox"],
                    "critical": expected["critical"],
                    "notes": f"Detected with confidence {matched['confidence']:.2f}"
                })

                if verbose:
                    print(f"  ✅ {expected['name']} ({expected.get('position', 'N/A')}): "
                          f"FOUND (confidence: {matched['confidence']:.2f})")

            else:
                results.append({
                    "component_def_id": expected["id"],
                    "name": expected["name"],
                    "position": expected.get("position", ""),
                    "status": "MISSING",
                    "confidence": 0.0,
                    "expected_bbox": expected["roi"],
                    "detected_bbox": None,
                    "critical": expected["critical"],
                    "notes": "Not detected in expected region"
                })

                if verbose:
                    print(f"  ❌ {expected['name']} ({expected.get('position', 'N/A')}): "
                          f"MISSING")

        return results

    def _find_matching_object(self,
                             expected: Dict,
                             detections: List[Dict],
                             matched_indices: set = None) -> Tuple[Optional[Dict], Optional[int]]:
        """
        หา detected object ที่ตรงกับ expected

        ⚠️ แก้ไข: เพิ่มการตรวจสอบ matched_indices เพื่อป้องกัน detection ซ้ำ

        Matching criteria (in order of priority):
        1. Class name ต้องตรงกัน (partial match)
        2. IoU > 5% (primary - ยืดหยุ่นกับการวางที่คลาดเคลื่อน)
        3. Center distance < tolerance (fallback)

        Args:
            expected: Expected component definition
            detections: List of MVI detections
            matched_indices: Set of detection indices that are already matched

        Returns:
            Tuple of (matched_detection, matched_index) or (None, None)
        """

        if matched_indices is None:
            matched_indices = set()

        expected_center = self._calculate_center(expected["roi"])
        tolerance = expected.get("tolerance", 50)
        min_iou = 0.05  # ยอมรับถ้ากรอบทับกันอย่างน้อย 5% (ยืดหยุ่นกับการวางคลาดเคลื่อน)

        best_match = None
        best_match_idx = None
        best_score = 0.0  # IoU score หรือ 1/distance

        print(f"\n  🔍 Matching '{expected['name']}' at position '{expected.get('position', 'N/A')}':")
        print(f"     Expected: center={expected_center}, size={expected['roi']['width']}x{expected['roi']['height']}")
        print(f"     Matching: IoU>{min_iou*100:.0f}% OR distance<{tolerance}px")
        print(f"     Already matched detections: {matched_indices}")

        for idx, detection in enumerate(detections):
            # ข้าม detection ที่ match ไปแล้ว
            if idx in matched_indices:
                print(f"\n     Skipping detection[{idx}]: '{detection['class']}' (already matched)")
                continue

            # เช็ค class name (case insensitive + partial match)
            detected_class = detection["class"].lower()
            expected_class = expected["name"].lower()

            print(f"\n     Checking detection[{idx}]: '{detection['class']}' (confidence: {detection['confidence']:.2f})")

            # Check if expected class is contained in detected class or vice versa
            # This handles cases like "Pig Inspection" matching "pig"
            is_match = (expected_class in detected_class or
                       detected_class in expected_class or
                       expected_class == detected_class)

            if not is_match:
                print(f"       ❌ Class mismatch: '{detected_class}' !contains '{expected_class}'")
                continue

            print(f"       ✓ Class match!")

            # Method 1: ลอง IoU ก่อน (primary)
            iou = self._calculate_iou(expected["roi"], detection["bbox"])
            print(f"       📐 IoU: {iou:.3f} ({iou*100:.1f}%)")

            if iou > min_iou:
                # Match by IoU - ยืดหยุ่นมาก เหมาะกับการวางที่คลาดเคลื่อน
                if iou > best_score:
                    best_match = detection
                    best_match_idx = idx
                    best_score = iou
                    print(f"       ✅ MATCH by IoU! (best so far: {iou:.3f})")
                continue

            # Method 2: ลอง center distance (fallback)
            detected_center = self._calculate_center(detection["bbox"])
            distance = self._calculate_distance(expected_center, detected_center)
            print(f"       📏 Center distance: {distance:.1f}px (tolerance: {tolerance}px)")

            if distance <= tolerance:
                # Match by distance
                score = 1.0 / (distance + 1)  # ยิ่งใกล้ยิ่งดี
                if score > best_score:
                    best_match = detection
                    best_match_idx = idx
                    best_score = score
                    print(f"       ✅ MATCH by distance! (best so far: {distance:.1f}px)")

        if best_match:
            print(f"     ✅ Found best match: detection[{best_match_idx}] = {best_match['class']}")
        else:
            print(f"     ❌ No match found (all detections failed IoU and distance check)")

        return best_match, best_match_idx

    def _calculate_center(self, bbox: Dict) -> Tuple[float, float]:
        """คำนวณจุดกึ่งกลาง bbox"""
        cx = bbox["x"] + bbox["width"] / 2
        cy = bbox["y"] + bbox["height"] / 2
        return (cx, cy)

    def _calculate_distance(self, point1: Tuple[float, float],
                           point2: Tuple[float, float]) -> float:
        """คำนวณระยะห่าง Euclidean"""
        return np.sqrt((point1[0] - point2[0])**2 + (point1[1] - point2[1])**2)

    def _calculate_iou(self, bbox1: Dict, bbox2: Dict) -> float:
        """คำนวณ Intersection over Union (IoU)"""
        x1_min = bbox1["x"]
        y1_min = bbox1["y"]
        x1_max = bbox1["x"] + bbox1["width"]
        y1_max = bbox1["y"] + bbox1["height"]

        x2_min = bbox2["x"]
        y2_min = bbox2["y"]
        x2_max = bbox2["x"] + bbox2["width"]
        y2_max = bbox2["y"] + bbox2["height"]

        # Intersection
        x_inter_min = max(x1_min, x2_min)
        y_inter_min = max(y1_min, y2_min)
        x_inter_max = min(x1_max, x2_max)
        y_inter_max = min(y1_max, y2_max)

        if x_inter_max <= x_inter_min or y_inter_max <= y_inter_min:
            return 0.0

        inter_area = (x_inter_max - x_inter_min) * (y_inter_max - y_inter_min)

        # Union
        bbox1_area = bbox1["width"] * bbox1["height"]
        bbox2_area = bbox2["width"] * bbox2["height"]
        union_area = bbox1_area + bbox2_area - inter_area

        return inter_area / union_area if union_area > 0 else 0.0

    def _analyze_results(self,
                        matching_results: List[Dict],
                        expected_components: List[Dict],
                        verbose: bool = False) -> Dict:
        """วิเคราะห์ผลการตรวจสอบ"""

        found_count = sum(1 for r in matching_results if r["status"] == "FOUND")
        total_count = len(expected_components)
        found_percentage = (found_count / total_count * 100) if total_count > 0 else 0

        # รายการที่หาย
        missing_components = [
            r["name"]
            for r in matching_results
            if r["status"] == "MISSING"
        ]

        missing_positions = [
            f"{r['name']} ({r['position']})" if r['position'] else r['name']
            for r in matching_results
            if r["status"] == "MISSING"
        ]

        # Critical components ที่หาย
        missing_critical = [
            r["name"]
            for r in matching_results
            if r["status"] == "MISSING" and r["critical"]
        ]

        # ตัดสิน PASS/FAIL
        if missing_critical:
            status = "FAIL"
            reason = f"Missing critical components: {', '.join(missing_critical)}"
        elif found_count == total_count:
            status = "PASS"
            reason = f"All components found ({found_count}/{total_count})"
        else:
            status = "FAIL"
            reason = f"Found only {found_count}/{total_count} components"

        return {
            "status": status,
            "reason": reason,
            "found_count": found_count,
            "total_count": total_count,
            "found_percentage": found_percentage,
            "missing_components": missing_components,
            "missing_positions": missing_positions
        }

    def _draw_annotations(self,
                         image: np.ndarray,
                         matching_results: List[Dict],
                         expected_components: List[Dict]) -> np.ndarray:
        """
        วาด annotations บนภาพ

        - Green box + ✓ label = FOUND
        - Red box + ✗ MISSING label = MISSING
        """

        for result in matching_results:
            roi = result["expected_bbox"]

            if result["status"] == "FOUND":
                # วาดกรอบเขียว + label
                color = (0, 255, 0)  # Green
                label = f"✓ {result['name']} ({result['confidence']:.2f})"
                thickness = 3
            else:
                # วาดกรอบแดง + MISSING
                color = (0, 0, 255)  # Red
                label = f"✗ {result['name']} MISSING"
                thickness = 4

            # Draw rectangle
            x, y, w, h = roi["x"], roi["y"], roi["width"], roi["height"]
            cv2.rectangle(
                image,
                (x, y),
                (x + w, y + h),
                color,
                thickness
            )

            # Draw filled background for label
            label_size, baseline = cv2.getTextSize(
                label,
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                2
            )

            label_y = y - 10 if y - 10 > label_size[1] else y + h + label_size[1] + 10

            cv2.rectangle(
                image,
                (x, label_y - label_size[1] - 5),
                (x + label_size[0], label_y + baseline),
                color,
                -1
            )

            # Draw label text
            text_color = (255, 255, 255)  # White
            cv2.putText(
                image,
                label,
                (x, label_y - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                text_color,
                2
            )

            # Draw position label if available
            if result.get("position"):
                position_label = f"[{result['position'].upper()}]"
                cv2.putText(
                    image,
                    position_label,
                    (x, y - 35 if y > 50 else y + h + 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    color,
                    2
                )

        return image

    def parse_mvi_detections_from_image(self, image_path: str) -> List[Dict]:
        """
        Parse MVI detections จาก annotated image
        (สำหรับกรณีที่ MVI บันทึกผล detection ลงในภาพ)

        Note: ฟังก์ชันนี้เป็น placeholder
        ในการใช้งานจริง คุณควรได้รับ detection results เป็น JSON/dict โดยตรง
        """
        # TODO: Implement OCR or other method to extract detection from image
        # For now, return empty list
        return []

    def create_comparison_image(self,
                               original_image: np.ndarray,
                               annotated_image: np.ndarray) -> np.ndarray:
        """
        สร้างภาพเปรียบเทียบ Original vs Annotated

        Returns:
            Side-by-side comparison image
        """
        h1, w1 = original_image.shape[:2]
        h2, w2 = annotated_image.shape[:2]

        # Resize ถ้าขนาดไม่เท่ากัน
        if h1 != h2:
            scale = h1 / h2
            w2 = int(w2 * scale)
            annotated_image = cv2.resize(annotated_image, (w2, h1))

        # Add labels
        cv2.putText(
            original_image,
            "Original",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (255, 255, 255),
            2
        )

        cv2.putText(
            annotated_image,
            "Analysis Result",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (255, 255, 255),
            2
        )

        # Concatenate
        comparison = np.hstack([original_image, annotated_image])

        return comparison


# Example usage
if __name__ == "__main__":
    print("MVI Component Integration")
    print("=" * 60)

    from component_definition import ComponentDefinitionManager

    # Initialize
    comp_manager = ComponentDefinitionManager()
    integration = MVIComponentIntegration(comp_manager)

    # Get product
    product = comp_manager.get_product_by_name("Buddha_Set_3pcs")

    if product:
        print(f"\nProduct: {product['name']}")
        print(f"Components: {product.get('component_count', 0)}")

        # Example MVI detections (FAIL case - missing peacock)
        mvi_detections_fail = [
            {
                "class": "pig",
                "confidence": 0.94,
                "bbox": {"x": 178, "y": 180, "width": 182, "height": 268}
            },
            {
                "class": "monk",
                "confidence": 0.98,
                "bbox": {"x": 342, "y": 180, "width": 176, "height": 288}
            }
            # peacock หายไป!
        ]

        # Create dummy image
        dummy_image = np.zeros((600, 800, 3), dtype=np.uint8)
        dummy_image[:] = (100, 100, 100)  # Gray background

        # Process
        result = integration.process_mvi_result(
            image=dummy_image,
            mvi_detections=mvi_detections_fail,
            product_id=product['id'],
            verbose=True
        )

        print(f"\n📊 Result Summary:")
        print(f"  Status: {result['status']}")
        print(f"  Reason: {result['reason']}")
        print(f"  Found: {result['found']}/{result['total']} ({result['found_percentage']:.1f}%)")
        print(f"  Missing: {result['missing_components']}")
        print(f"  Missing Positions: {result['missing_positions']}")

        # Example MVI detections (PASS case - all found)
        print("\n" + "=" * 60)
        print("Testing PASS case...")

        mvi_detections_pass = [
            {
                "class": "pig",
                "confidence": 0.90,
                "bbox": {"x": 190, "y": 185, "width": 175, "height": 265}
            },
            {
                "class": "monk",
                "confidence": 0.96,
                "bbox": {"x": 375, "y": 185, "width": 140, "height": 285}
            },
            {
                "class": "peacock",
                "confidence": 0.99,
                "bbox": {"x": 480, "y": 80, "width": 315, "height": 435}
            }
        ]

        result_pass = integration.process_mvi_result(
            image=dummy_image,
            mvi_detections=mvi_detections_pass,
            product_id=product['id'],
            verbose=True
        )

        print(f"\n📊 Result Summary:")
        print(f"  Status: {result_pass['status']}")
        print(f"  Found: {result_pass['found']}/{result_pass['total']}")

    print("\n✅ MVI Component Integration ready!")
