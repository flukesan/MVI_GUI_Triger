"""
Inspection Controller for Dual Mode Inspection System
ควบคุม flow การตรวจสอบทั้ง Capture Mode และ Realtime Mode
เชื่อม Camera + Detection + Component Definition + History
"""
import math
import time
import threading
from datetime import datetime
from typing import Optional, Dict, List, Set

import cv2
import numpy as np

try:
    from PyQt6.QtCore import QObject, QTimer, QThread, pyqtSignal as Signal
except ImportError:
    from PySide6.QtCore import QObject, QTimer, QThread, Signal

from camera_manager import CameraManager
from detection_engine import DetectionEngine
from component_definition import ComponentDefinitionManager
from history_manager import HistoryManager


class DetectionWorker(QThread):
    """Background thread for YOLO detection — ไม่บล็อก GUI thread"""
    detection_done = Signal(int, object, dict, object)  # (camera_id, frame, detection_result, expected_parts)

    def __init__(self, detector: DetectionEngine):
        super().__init__()
        self.detector = detector
        self._lock = threading.Lock()
        self._pending_frame = None
        self._pending_camera_id = None
        self._running = True
        self._has_work = threading.Event()

    def submit_frame(self, camera_id: int, frame: np.ndarray):
        """Submit frame for detection (drops old frame if detection is still running)"""
        with self._lock:
            self._pending_frame = frame
            self._pending_camera_id = camera_id
        self._has_work.set()

    def run(self):
        while self._running:
            # Wait for work
            self._has_work.wait(timeout=0.1)
            if not self._running:
                break
            self._has_work.clear()

            # Grab latest frame
            with self._lock:
                frame = self._pending_frame
                camera_id = self._pending_camera_id
                self._pending_frame = None

            if frame is None:
                continue

            # Run detection (off the GUI thread)
            detection = self.detector.detect(frame)
            self.detection_done.emit(camera_id, frame, detection, None)

    def stop(self):
        self._running = False
        self._has_work.set()
        self.wait(3000)


class InspectionController(QObject):
    """ควบคุม flow การตรวจสอบทั้ง Capture และ Realtime mode"""

    # Signals to GUI
    inspection_result = Signal(dict)        # ผลการตรวจสอบ (ทั้ง Capture และ Realtime)
    frame_display = Signal(int, object)     # (camera_id, annotated numpy frame) สำหรับ live preview
    status_changed = Signal(str)            # "ready", "inspecting", "streaming", "error"
    error_occurred = Signal(str)            # error message
    fps_updated = Signal(float)             # current FPS (Realtime mode)

    def __init__(self,
                 camera_manager: CameraManager,
                 detection_engine: DetectionEngine,
                 component_manager: ComponentDefinitionManager,
                 history_manager: HistoryManager):
        super().__init__()
        self.camera = camera_manager
        self.detector = detection_engine
        self.components = component_manager
        self.history = history_manager

        self.current_mode: str = "capture"      # "capture" or "realtime"
        self.current_product_id: Optional[int] = None
        self.current_product_name: str = ""
        self.expected_parts: List[Dict] = []    # loaded from component DB
        self.expected_class_names: Set[str] = set()

        self.is_streaming: bool = False
        self.inspect_fps: int = 10              # ความถี่ในการ detect (Realtime mode)
        self.save_pass_images: bool = False
        self.save_fail_images: bool = True

        # FPS tracking
        self._frame_count = 0
        self._fps_start_time = time.time()
        self._current_fps = 0.0

        # Frame skip สำหรับ Realtime mode
        self._frame_skip_counter = 0
        self._last_result: Optional[dict] = None

        # Background detection worker
        self._detection_worker: Optional[DetectionWorker] = None
        self._detecting: bool = False  # True = detection is in progress

    # ─── Product / Expected Parts ───

    def set_product(self, product_id: int):
        """โหลด expected parts จาก component_definition DB"""
        self.current_product_id = product_id
        product = self.components.get_product(product_id)
        if product:
            self.current_product_name = product["name"]
            self.expected_parts = self.components.get_product_components(product_id)
            self.expected_class_names = {p["name"] for p in self.expected_parts}
            print(f"Product set: {self.current_product_name} "
                  f"({len(self.expected_parts)} expected parts: "
                  f"{', '.join(self.expected_class_names)})")
        else:
            self.current_product_name = ""
            self.expected_parts = []
            self.expected_class_names = set()

    def get_expected_class_names(self) -> Set[str]:
        return self.expected_class_names.copy()

    # ─── Mode Control ───

    def set_mode(self, mode: str):
        """เปลี่ยนโหมด: "capture" หรือ "realtime" """
        if mode not in ("capture", "realtime"):
            return

        if self.is_streaming:
            self.stop_realtime()

        self.current_mode = mode
        self.status_changed.emit("ready")
        print(f"Mode changed to: {mode}")

    # ─── Capture Mode ───

    def trigger_capture(self, camera_id: int = 0) -> Optional[dict]:
        """กดปุ่ม → ถ่ายภาพ → detect → เปรียบเทียบ → บันทึก → คืนผล"""
        if not self.detector.is_model_loaded():
            self.error_occurred.emit("Model not loaded")
            return None

        self.status_changed.emit("inspecting")

        # 1. Capture frame
        frame = self.camera.capture_frame(camera_id)
        if frame is None:
            self.error_occurred.emit("Failed to capture frame")
            self.status_changed.emit("ready")
            return None

        # 2. Detect
        detection = self.detector.detect(frame)

        # 3. Compare with expected
        result = self._compare_with_expected(detection, camera_id, frame)

        # 4. Annotate image
        annotated = self.detector.draw_detections(
            frame.copy(),
            detection["detections"],
            result.get("missing_parts_detail")
        )
        result["annotated_image"] = annotated
        result["original_image"] = frame

        # 5. Display
        self.frame_display.emit(camera_id, annotated)

        # 6. Save to history (always save in Capture mode)
        self._save_to_history(result, annotated)

        # 7. Emit result
        self.inspection_result.emit(result)
        self.status_changed.emit("ready")
        self._last_result = result

        return result

    def trigger_capture_from_file(self, file_path: str) -> Optional[dict]:
        """โหลดภาพจากไฟล์ → detect → เปรียบเทียบ"""
        if not self.detector.is_model_loaded():
            self.error_occurred.emit("Model not loaded")
            return None

        self.status_changed.emit("inspecting")

        frame = self.camera.load_image_file(file_path)
        if frame is None:
            self.error_occurred.emit(f"Failed to load image: {file_path}")
            self.status_changed.emit("ready")
            return None

        detection = self.detector.detect(frame)
        result = self._compare_with_expected(detection, -1, frame)

        annotated = self.detector.draw_detections(
            frame.copy(),
            detection["detections"],
            result.get("missing_parts_detail")
        )
        result["annotated_image"] = annotated
        result["original_image"] = frame

        self.frame_display.emit(0, annotated)
        self._save_to_history(result, annotated)
        self.inspection_result.emit(result)
        self.status_changed.emit("ready")
        self._last_result = result

        return result

    # ─── Realtime Mode ───

    def start_realtime(self, camera_id: int = 0):
        """เริ่ม realtime — stream + detect (detection ทำงานใน background thread)"""
        if not self.detector.is_model_loaded():
            self.error_occurred.emit("Model not loaded")
            return

        if not self.camera.is_opened(camera_id):
            self.error_occurred.emit(f"Camera {camera_id} not opened")
            return

        self.is_streaming = True
        self._detecting = False
        self._frame_count = 0
        self._fps_start_time = time.time()
        self._frame_skip_counter = 0

        # Create and start detection worker (background thread)
        self._detection_worker = DetectionWorker(self.detector)
        self._detection_worker.detection_done.connect(self._on_detection_done)
        self._detection_worker.start()

        # Connect camera stream to our handler
        self.camera.frame_captured.connect(self._on_realtime_frame)

        # Start camera stream
        stream_fps = 30
        self.camera.start_stream(camera_id, stream_fps)

        self.status_changed.emit("streaming")
        print(f"Realtime started: camera={camera_id}, stream_fps={stream_fps}, "
              f"inspect_fps={self.inspect_fps}, detection=background thread")

    def stop_realtime(self, camera_id: int = 0):
        """หยุด realtime"""
        self.is_streaming = False

        try:
            self.camera.frame_captured.disconnect(self._on_realtime_frame)
        except (TypeError, RuntimeError):
            pass

        # Stop detection worker
        if self._detection_worker:
            self._detection_worker.stop()
            self._detection_worker = None

        self.camera.stop_stream(camera_id)
        self._detecting = False
        self.status_changed.emit("ready")
        print("Realtime stopped")

    def _on_realtime_frame(self, camera_id: int, frame: np.ndarray):
        """เรียกทุกเฟรมจากกล้อง — แสดง preview ทุกเฟรม, detect เฉพาะเฟรมที่เลือก"""
        if not self.is_streaming:
            return

        # ═══ แสดง live preview ทุกเฟรม (ไม่ต้องรอ detection) ═══
        self.frame_display.emit(camera_id, frame)

        # ═══ Frame skip — ส่ง detect เฉพาะเฟรมที่เลือก ═══
        stream_fps = 30
        skip_ratio = max(1, stream_fps // max(self.inspect_fps, 1))
        self._frame_skip_counter += 1

        if self._frame_skip_counter % skip_ratio != 0:
            return

        # Skip ถ้า detection ก่อนหน้ายังทำไม่เสร็จ (drop frame แทน)
        if self._detecting:
            return

        # Submit frame to background detection worker
        if self._detection_worker:
            self._detecting = True
            self._detection_worker.submit_frame(camera_id, frame.copy())

        # FPS calculation
        self._frame_count += 1
        elapsed = time.time() - self._fps_start_time
        if elapsed >= 1.0:
            self._current_fps = self._frame_count / elapsed
            self.fps_updated.emit(self._current_fps)
            self._frame_count = 0
            self._fps_start_time = time.time()

    def _on_detection_done(self, camera_id: int, frame: np.ndarray,
                            detection: dict, _unused):
        """เรียกเมื่อ background detection เสร็จ — annotate + emit result"""
        if not self.is_streaming:
            return

        self._detecting = False

        result = self._compare_with_expected(detection, camera_id, frame)

        annotated = self.detector.draw_detections(
            frame.copy(),
            detection["detections"],
            result.get("missing_parts_detail")
        )
        result["annotated_image"] = annotated

        # แสดงภาพ annotated (ทับ preview)
        self.frame_display.emit(camera_id, annotated)

        # Emit result
        self.inspection_result.emit(result)
        self._last_result = result

        # Save FAIL images only (Realtime mode)
        if result["status"] == "FAIL" and self.save_fail_images:
            self._save_to_history(result, annotated)

    # ─── Comparison Logic ───

    def _compare_with_expected(self, detection_result: dict,
                                camera_id: int,
                                frame: np.ndarray) -> dict:
        """เปรียบเทียบ detection กับ expected parts"""
        detected_classes = {}
        for det in detection_result["detections"]:
            name = det["class_name"]
            if name not in detected_classes or det["confidence"] > detected_classes[name]["confidence"]:
                detected_classes[name] = det

        found_parts = []
        missing_parts = []
        missing_parts_detail = []

        if self.expected_parts:
            # มี expected parts — เปรียบเทียบ
            for expected in self.expected_parts:
                exp_name = expected["name"]
                matched = self._find_best_match(expected, detection_result["detections"])

                if matched:
                    found_parts.append({
                        "name": exp_name,
                        "position": expected.get("position", ""),
                        "confidence": matched["confidence"],
                        "bbox": matched["bbox"],
                        "is_critical": expected.get("critical", True)
                    })
                else:
                    missing_parts.append(exp_name)
                    missing_parts_detail.append({
                        "name": exp_name,
                        "position": expected.get("position", ""),
                        "roi": expected.get("roi"),
                        "expected_bbox": expected.get("roi"),
                        "is_critical": expected.get("critical", True)
                    })

            total_expected = len(self.expected_parts)
            found_count = len(found_parts)

            # Check critical components
            critical_missing = [m for m in missing_parts_detail if m.get("is_critical", True)]
            if critical_missing:
                status = "FAIL"
                reason = f"Missing critical: {', '.join(m['name'] for m in critical_missing)}"
            elif found_count < total_expected:
                status = "FAIL"
                reason = f"Found {found_count}/{total_expected}"
            else:
                status = "PASS"
                reason = f"All {total_expected} parts found"
        else:
            # ไม่มี expected parts — แค่แสดงผล detection
            total_expected = 0
            found_count = len(detection_result["detections"])
            status = "PASS" if found_count > 0 else "UNKNOWN"
            reason = f"Detected {found_count} objects (no expected parts defined)"
            for det in detection_result["detections"]:
                found_parts.append({
                    "name": det["class_name"],
                    "confidence": det["confidence"],
                    "bbox": det["bbox"]
                })

        found_pct = (found_count / total_expected * 100) if total_expected > 0 else 0

        return {
            "status": status,
            "reason": reason,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "camera_id": camera_id,
            "product_name": self.current_product_name,
            "mode": self.current_mode,
            "found_parts": found_parts,
            "missing_parts": missing_parts,
            "missing_parts_detail": missing_parts_detail,
            "found_count": found_count,
            "total_expected": total_expected,
            "found_percentage": round(found_pct, 1),
            "inference_time_ms": detection_result.get("inference_time_ms", 0),
            "detection_count": len(detection_result["detections"]),
            "all_detections": detection_result["detections"]
        }

    def _find_best_match(self, expected: dict, detections: List[dict]) -> Optional[dict]:
        """หา detection ที่ตรงกับ expected part ที่สุด"""
        exp_name = expected["name"]
        tolerance = expected.get("tolerance", 50)
        min_conf = expected.get("min_confidence", 0.5)

        # กรอง class name ที่ตรงกัน
        candidates = [d for d in detections if d["class_name"] == exp_name and d["confidence"] >= min_conf]

        if not candidates:
            return None

        # ถ้ามี ROI ให้เลือกตัวที่ใกล้ที่สุด
        roi = expected.get("roi")
        if roi and roi.get("x") is not None:
            exp_cx = roi["x"] + roi.get("width", 0) // 2
            exp_cy = roi["y"] + roi.get("height", 0) // 2

            best = None
            best_dist = float("inf")
            for c in candidates:
                cx, cy = c["center"]
                dist = math.sqrt((cx - exp_cx) ** 2 + (cy - exp_cy) ** 2)
                if dist < best_dist and dist <= tolerance:
                    best = c
                    best_dist = dist

            return best
        else:
            # ไม่มี ROI — เอาตัวที่ confidence สูงสุด
            return max(candidates, key=lambda d: d["confidence"])

    # ─── History ───

    def _save_to_history(self, result: dict, annotated_frame: np.ndarray):
        """บันทึกผลลัพธ์ลง history database"""
        try:
            data = {
                "camera_id": str(result.get("camera_id", "")),
                "product_name": result.get("product_name", ""),
                "result": result["status"].lower(),
                "mode": result.get("mode", self.current_mode),
                "found_count": result.get("found_count", 0),
                "total_expected": result.get("total_expected", 0),
                "missing_parts": result.get("missing_parts", []),
                "inference_time_ms": result.get("inference_time_ms", 0),
                "reason": result.get("reason", ""),
                "all_detections": result.get("all_detections", [])
            }

            self.history.save_inspection(data, annotated_frame)

        except Exception as e:
            print(f"Failed to save to history: {e}")

    # ─── Settings ───

    def set_inspect_fps(self, fps: int):
        self.inspect_fps = max(1, min(60, fps))

    def set_save_options(self, save_pass: bool, save_fail: bool):
        self.save_pass_images = save_pass
        self.save_fail_images = save_fail
