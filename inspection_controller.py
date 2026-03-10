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
from anomaly_engine import AnomalyEngine


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
        self.anomaly = AnomalyEngine()

        self.current_mode: str = "capture"      # "capture", "realtime", "anomaly"
        self.current_product_id: Optional[int] = None
        self.current_product_name: str = ""
        self.expected_parts: List[Dict] = []    # loaded from component DB
        self.expected_class_names: Set[str] = set()

        # Per-camera product support (cam0, cam1)
        self._camera_products: Dict[int, dict] = {}  # {camera_id: {"id", "name", "parts", "class_names"}}

        self.is_streaming: bool = False
        self.inspect_fps: int = 30              # ความถี่ในการ detect (Realtime mode)
        self.save_pass_images: bool = False
        self.save_fail_images: bool = True

        # FPS tracking
        self._frame_count = 0
        self._fps_start_time = time.time()
        self._current_fps = 0.0

        # Frame skip สำหรับ Realtime mode
        self._frame_skip_counter = 0
        self._last_result: Optional[dict] = None

        # Cached detection results for smooth overlay (per camera)
        self._cached_detections: Dict[int, List[dict]] = {}
        self._cached_missing_parts: Dict[int, Optional[List[dict]]] = {}

        # Background detection worker
        self._detection_worker: Optional[DetectionWorker] = None
        self._detecting: bool = False  # True = detection is in progress

        # Multi-camera state
        self._streaming_cameras: set = set()  # camera_ids currently streaming

    # ─── Product / Expected Parts ───

    def set_product(self, product_id: int, camera_id: int = None):
        """โหลด expected parts จาก component_definition DB

        Args:
            product_id: ID ของ product
            camera_id: ถ้าระบุ จะ set เฉพาะกล้องนั้น (per-camera mode)
                       ถ้าไม่ระบุ จะ set แบบ global (ทุกกล้องใช้ product เดียวกัน)
        """
        product = self.components.get_product(product_id)
        if product:
            name = product["name"]
            parts = self.components.get_product_components(product_id)
            class_names = {p["name"] for p in parts}
            print(f"Product set: {name} "
                  f"({len(parts)} expected parts: "
                  f"{', '.join(class_names)})"
                  f"{f' [camera {camera_id}]' if camera_id is not None else ''}")
        else:
            name = ""
            parts = []
            class_names = set()

        if camera_id is not None:
            # Per-camera mode
            self._camera_products[camera_id] = {
                "id": product_id, "name": name,
                "parts": parts, "class_names": class_names
            }
        else:
            # Global mode (backward compat)
            self._camera_products.clear()

        # Always update global state (used as default/fallback)
        self.current_product_id = product_id
        self.current_product_name = name
        self.expected_parts = parts
        self.expected_class_names = class_names

    def clear_product(self, camera_id: int = None):
        """ล้าง product selection"""
        if camera_id is not None:
            self._camera_products.pop(camera_id, None)
        else:
            self._camera_products.clear()
            self.current_product_id = None
            self.current_product_name = ""
            self.expected_parts = []
            self.expected_class_names = set()

    def _get_product_for_camera(self, camera_id: int) -> tuple:
        """คืน (product_name, expected_parts, expected_class_names) สำหรับกล้องที่ระบุ"""
        if camera_id in self._camera_products:
            cp = self._camera_products[camera_id]
            return cp["name"], cp["parts"], cp["class_names"]
        # Fallback to global
        return self.current_product_name, self.expected_parts, self.expected_class_names

    def get_expected_class_names(self, camera_id: int = None) -> Set[str]:
        if camera_id is not None and camera_id in self._camera_products:
            return self._camera_products[camera_id]["class_names"].copy()
        return self.expected_class_names.copy()

    # ─── Mode Control ───

    def set_mode(self, mode: str):
        """เปลี่ยนโหมด: "capture", "realtime", "anomaly" """
        if mode not in ("capture", "realtime", "anomaly"):
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
        self._cached_detections[camera_id] = []
        self._cached_missing_parts[camera_id] = None
        self._streaming_cameras.add(camera_id)

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
        self._streaming_cameras.discard(camera_id)
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
        self._cached_detections.pop(camera_id, None)
        self._cached_missing_parts.pop(camera_id, None)
        self.status_changed.emit("ready")
        print("Realtime stopped")

    def start_realtime_cam2(self, camera_id: int = 1):
        """เริ่ม stream + detect สำหรับกล้องตัวที่ 2 (Multi mode)"""
        if not self.camera.is_opened(camera_id):
            self.error_occurred.emit(f"Camera {camera_id} not opened")
            return

        self._cached_detections[camera_id] = []
        self._cached_missing_parts[camera_id] = None
        self._streaming_cameras.add(camera_id)

        # Start camera 2 stream (ใช้ detection worker ร่วมกับ cam 0)
        stream_fps = 30
        self.camera.start_stream(camera_id, stream_fps)
        print(f"Realtime cam2 started: camera={camera_id}")

    def stop_realtime_cam2(self, camera_id: int = 1):
        """หยุด stream กล้องตัวที่ 2"""
        self._streaming_cameras.discard(camera_id)
        self.camera.stop_stream(camera_id)
        self._cached_detections.pop(camera_id, None)
        self._cached_missing_parts.pop(camera_id, None)
        print(f"Realtime cam2 stopped: camera={camera_id}")

    def _on_realtime_frame(self, camera_id: int, frame: np.ndarray):
        """เรียกทุกเฟรมจากกล้อง — แสดง preview ทุกเฟรม + overlay cached detection"""
        if not self.is_streaming:
            return

        # Filter: only process frames from cameras we're streaming
        if camera_id not in self._streaming_cameras:
            return

        # ═══ แสดง live preview ทุกเฟรม พร้อม overlay cached detection (per camera) ═══
        cam_dets = self._cached_detections.get(camera_id, [])
        cam_missing = self._cached_missing_parts.get(camera_id)
        if cam_dets or cam_missing:
            display_frame = self.detector.draw_detections(
                frame.copy(), cam_dets, cam_missing)
        else:
            display_frame = frame
        self.frame_display.emit(camera_id, display_frame)

        # ═══ FPS calculation (นับทุกเฟรมที่แสดง) ═══
        self._frame_count += 1
        elapsed = time.time() - self._fps_start_time
        if elapsed >= 1.0:
            self._current_fps = self._frame_count / elapsed
            self.fps_updated.emit(self._current_fps)
            self._frame_count = 0
            self._fps_start_time = time.time()

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

    def _on_detection_done(self, camera_id: int, frame: np.ndarray,
                            detection: dict, _unused):
        """เรียกเมื่อ background detection เสร็จ — cache ผลไว้ overlay บนเฟรมถัดไป"""
        if not self.is_streaming:
            return

        self._detecting = False

        result = self._compare_with_expected(detection, camera_id, frame)

        # ═══ Cache detection results per camera สำหรับ overlay บนเฟรมถัดไป ═══
        self._cached_detections[camera_id] = detection.get("detections", [])
        self._cached_missing_parts[camera_id] = result.get("missing_parts_detail")

        # Annotate frame for result/history
        annotated = self.detector.draw_detections(
            frame.copy(),
            self._cached_detections.get(camera_id, []),
            self._cached_missing_parts.get(camera_id)
        )
        result["annotated_image"] = annotated

        # Emit result (ไม่ emit frame_display ที่นี่ — _on_realtime_frame จะ overlay ให้แล้ว)
        self.inspection_result.emit(result)
        self._last_result = result

        # Save FAIL images only (Realtime mode)
        if result["status"] == "FAIL" and self.save_fail_images:
            self._save_to_history(result, annotated)

    # ─── Comparison Logic ───

    def _compare_with_expected(self, detection_result: dict,
                                camera_id: int,
                                frame: np.ndarray) -> dict:
        """เปรียบเทียบ detection กับ expected parts (per-camera aware)"""
        product_name, expected_parts, _ = self._get_product_for_camera(camera_id)

        detected_classes = {}
        for det in detection_result["detections"]:
            name = det["class_name"]
            if name not in detected_classes or det["confidence"] > detected_classes[name]["confidence"]:
                detected_classes[name] = det

        found_parts = []
        missing_parts = []
        missing_parts_detail = []

        if expected_parts:
            # มี expected parts — เปรียบเทียบ
            for expected in expected_parts:
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

            total_expected = len(expected_parts)
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
            "product_name": product_name,
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

    # ─── Anomaly Mode ───

    def trigger_anomaly(self, camera_id: int = 0) -> Optional[dict]:
        """Anomaly Mode: ถ่ายภาพ → YOLO crop (optional) → PatchCore → แสดง heatmap"""
        if not self.anomaly.is_trained:
            self.error_occurred.emit("Anomaly model not trained")
            return None

        self.status_changed.emit("inspecting")

        # 1. Capture frame
        frame = self.camera.capture_frame(camera_id)
        if frame is None:
            self.error_occurred.emit("Failed to capture frame")
            self.status_changed.emit("ready")
            return None

        # 2. YOLO crop + Anomaly detect (hybrid) or whole image
        use_crop = self.anomaly.use_yolo_crop and self.detector.is_model_loaded()

        if self.anomaly.use_yolo_crop and not self.detector.is_model_loaded():
            print("WARNING: YOLO Crop enabled but YOLO model NOT loaded → fallback to standalone")
            self.error_occurred.emit(
                "YOLO Crop enabled but YOLO model not loaded — using whole image mode")

        if use_crop:
            # YOLO detect first → crop → anomaly on each crop
            detection = self.detector.detect(frame)
            det_count = len(detection["detections"])
            print(f"Anomaly YOLO Hybrid: detected {det_count} objects")

            if det_count > 0:
                anomaly_result = self.anomaly.predict_on_crops(
                    frame, detection["detections"])
                annotated = self.anomaly.annotate_crops_result(frame, anomaly_result)
            else:
                print("WARNING: YOLO detected 0 objects → fallback to standalone")
                anomaly_result = self.anomaly.predict(frame)
                annotated = self.anomaly.annotate_result(frame, anomaly_result)
        else:
            # Anomaly on whole image (no YOLO)
            print("Anomaly Standalone: checking whole image")
            anomaly_result = self.anomaly.predict(frame)
            annotated = self.anomaly.annotate_result(frame, anomaly_result)

        # 3. Build result
        is_anomaly = anomaly_result.get("is_anomaly", False)
        score = anomaly_result.get("anomaly_score", 0)

        result = {
            "status": "FAIL" if is_anomaly else "PASS",
            "reason": f"Anomaly score: {score:.2f} (threshold: {self.anomaly.threshold:.1f})",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "camera_id": camera_id,
            "product_name": self.current_product_name or "Anomaly Check",
            "mode": "anomaly",
            "found_count": 0,
            "total_expected": 0,
            "missing_parts": [],
            "inference_time_ms": anomaly_result.get("inference_time_ms", 0),
            "detection_count": 0,
            "all_detections": [],
            "anomaly_score": score,
            "annotated_image": annotated,
            "original_image": frame,
        }

        # 4. Display
        self.frame_display.emit(camera_id, annotated)

        # 5. Save to history
        self._save_to_history(result, annotated)

        # 6. Emit result
        self.inspection_result.emit(result)
        self.status_changed.emit("ready")

        return result

    def trigger_anomaly_from_file(self, file_path: str) -> Optional[dict]:
        """Anomaly Mode: โหลดภาพจากไฟล์ → PatchCore"""
        if not self.anomaly.is_trained:
            self.error_occurred.emit("Anomaly model not trained")
            return None

        self.status_changed.emit("inspecting")

        frame = self.camera.load_image_file(file_path)
        if frame is None:
            self.error_occurred.emit(f"Failed to load image: {file_path}")
            self.status_changed.emit("ready")
            return None

        use_crop = self.anomaly.use_yolo_crop and self.detector.is_model_loaded()

        if self.anomaly.use_yolo_crop and not self.detector.is_model_loaded():
            print("WARNING: YOLO Crop enabled but YOLO model NOT loaded → fallback to standalone")

        if use_crop:
            detection = self.detector.detect(frame)
            det_count = len(detection["detections"])
            print(f"Anomaly from file — YOLO Hybrid: detected {det_count} objects")

            if det_count > 0:
                anomaly_result = self.anomaly.predict_on_crops(
                    frame, detection["detections"])
                annotated = self.anomaly.annotate_crops_result(frame, anomaly_result)
            else:
                anomaly_result = self.anomaly.predict(frame)
                annotated = self.anomaly.annotate_result(frame, anomaly_result)
        else:
            print("Anomaly from file — Standalone: checking whole image")
            anomaly_result = self.anomaly.predict(frame)
            annotated = self.anomaly.annotate_result(frame, anomaly_result)

        is_anomaly = anomaly_result.get("is_anomaly", False)
        score = anomaly_result.get("anomaly_score", 0)

        result = {
            "status": "FAIL" if is_anomaly else "PASS",
            "reason": f"Anomaly score: {score:.2f} (threshold: {self.anomaly.threshold:.1f})",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "camera_id": -1,
            "product_name": self.current_product_name or "Anomaly Check",
            "mode": "anomaly",
            "found_count": 0,
            "total_expected": 0,
            "missing_parts": [],
            "inference_time_ms": anomaly_result.get("inference_time_ms", 0),
            "detection_count": 0,
            "all_detections": [],
            "anomaly_score": score,
            "annotated_image": annotated,
            "original_image": frame,
        }

        self.frame_display.emit(0, annotated)
        self._save_to_history(result, annotated)
        self.inspection_result.emit(result)
        self.status_changed.emit("ready")

        return result

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
