"""
Detection Engine for Dual Mode Inspection System
Local YOLOv8 inference engine — รองรับ GPU (RTX4000) และ CPU
ตัด MVI dependency ออกทั้งหมด — run detection ในเครื่อง
"""
import time
import cv2
import numpy as np
from typing import List, Dict, Optional, Tuple

try:
    from PyQt6.QtCore import QObject, pyqtSignal as Signal
except ImportError:
    from PySide6.QtCore import QObject, Signal


class DetectionEngine(QObject):
    """YOLO Detection Engine — run locally บน GPU/CPU"""

    # Signals
    model_loaded = Signal(str)      # model info string
    model_error = Signal(str)       # error message

    def __init__(self):
        super().__init__()
        self.model = None
        self.model_path: str = ""
        self.device: str = "auto"       # "cpu", "cuda", "0", "auto"
        self.confidence: float = 0.5
        self.iou_threshold: float = 0.45
        self._class_names: List[str] = []

    # ─── Model Management ───

    def load_model(self, model_path: str, device: str = "auto") -> bool:
        """
        โหลด YOLO model (.pt หรือ .onnx)
        device: "auto" (ใช้ GPU ถ้ามี), "cpu", "cuda", "0"
        """
        try:
            from ultralytics import YOLO

            self.model = YOLO(model_path)
            self.model_path = model_path

            # Determine device
            if device == "auto":
                try:
                    import torch
                    if torch.cuda.is_available():
                        self.device = "0"   # GPU index 0
                        gpu_name = torch.cuda.get_device_name(0)
                        print(f"GPU detected: {gpu_name}")
                    else:
                        self.device = "cpu"
                        print("No GPU detected, using CPU")
                except ImportError:
                    self.device = "cpu"
                    print("PyTorch not available, using CPU")
            else:
                self.device = device

            # Get class names
            if hasattr(self.model, 'names'):
                self._class_names = list(self.model.names.values())

            info = self.get_model_info_str()
            self.model_loaded.emit(info)
            print(f"Model loaded: {info}")
            return True

        except ImportError:
            err = "ultralytics not installed. Run: pip install ultralytics"
            self.model_error.emit(err)
            print(f"Error: {err}")
            return False
        except Exception as e:
            err = f"Failed to load model: {e}"
            self.model_error.emit(err)
            print(f"Error: {err}")
            return False

    def unload_model(self):
        """ปล่อย model จาก memory"""
        self.model = None
        self._class_names = []
        self.model_path = ""
        print("Model unloaded")

    def is_model_loaded(self) -> bool:
        return self.model is not None

    def get_class_names(self) -> List[str]:
        """รายชื่อ class ที่ model detect ได้"""
        return self._class_names.copy()

    def get_model_info(self) -> dict:
        """ข้อมูล model"""
        if not self.model:
            return {}
        return {
            "path": self.model_path,
            "device": self.device,
            "class_names": self._class_names,
            "num_classes": len(self._class_names),
            "confidence": self.confidence,
            "iou_threshold": self.iou_threshold
        }

    def get_model_info_str(self) -> str:
        """ข้อมูล model เป็น string สำหรับแสดงใน GUI"""
        if not self.model:
            return "No model loaded"
        device_str = f"GPU:{self.device}" if self.device != "cpu" else "CPU"
        return f"{self.model_path} | {len(self._class_names)} classes | {device_str}"

    # ─── Detection ───

    def detect(self, frame: np.ndarray) -> dict:
        """
        ตรวจจับวัตถุใน 1 เฟรม

        Returns:
            {
                "detections": [
                    {
                        "class_name": "pig",
                        "confidence": 0.94,
                        "bbox": {"x": 178, "y": 180, "w": 182, "h": 268},
                        "center": (269, 314)
                    }, ...
                ],
                "inference_time_ms": 15.2,
                "frame_size": (1280, 720)
            }
        """
        if not self.model:
            return {"detections": [], "inference_time_ms": 0, "frame_size": (0, 0)}

        start_time = time.time()

        results = self.model(
            frame,
            conf=self.confidence,
            iou=self.iou_threshold,
            device=self.device,
            verbose=False
        )[0]

        inference_ms = (time.time() - start_time) * 1000

        detections = []
        for box in results.boxes:
            cls_id = int(box.cls)
            cls_name = results.names[cls_id]
            conf = float(box.conf)
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            w = x2 - x1
            h = y2 - y1
            cx = x1 + w // 2
            cy = y1 + h // 2

            detections.append({
                "class_name": cls_name,
                "confidence": conf,
                "bbox": {"x": x1, "y": y1, "w": w, "h": h},
                "center": (cx, cy)
            })

        h_frame, w_frame = frame.shape[:2]
        return {
            "detections": detections,
            "inference_time_ms": round(inference_ms, 1),
            "frame_size": (w_frame, h_frame)
        }

    def detect_and_annotate(self, frame: np.ndarray,
                            missing_parts: List[dict] = None) -> Tuple[dict, np.ndarray]:
        """detect + วาด bounding box บนภาพ"""
        result = self.detect(frame)
        annotated = self.draw_detections(
            frame.copy(), result["detections"], missing_parts
        )
        return result, annotated

    # ─── Annotation Drawing ───

    def draw_detections(self, frame: np.ndarray,
                        detections: List[dict],
                        missing_parts: List[dict] = None) -> np.ndarray:
        """
        วาด bounding box บนภาพ
        - เขียว = detected (found)
        - แดง = missing parts (จาก expected list)
        """
        annotated = frame.copy()

        # วาด detections ที่เจอ (เขียว)
        for det in detections:
            bbox = det["bbox"]
            x, y, w, h = bbox["x"], bbox["y"], bbox["w"], bbox["h"]
            conf = det["confidence"]
            name = det["class_name"]

            color = (0, 200, 0)  # Green (BGR)
            cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)

            label = f"{name} {conf:.2f}"
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            label_y = max(y - 10, label_size[1] + 5)

            # Label background
            cv2.rectangle(
                annotated,
                (x, label_y - label_size[1] - 5),
                (x + label_size[0] + 5, label_y + 5),
                color, -1
            )
            cv2.putText(
                annotated, label, (x + 2, label_y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
            )

        # วาด missing parts (แดง)
        if missing_parts:
            for part in missing_parts:
                roi = part.get("expected_bbox") or part.get("roi")
                if not roi:
                    continue

                x = roi.get("x", 0)
                y = roi.get("y", 0)
                w = roi.get("w", roi.get("width", 100))
                h = roi.get("h", roi.get("height", 100))

                color = (0, 0, 220)  # Red (BGR)
                cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 3)

                # Crosshatch pattern สำหรับ missing
                cv2.line(annotated, (x, y), (x + w, y + h), color, 1)
                cv2.line(annotated, (x + w, y), (x, y + h), color, 1)

                name = part.get("name", "MISSING")
                position = part.get("position", "")
                label = f"MISSING: {name}"
                if position:
                    label += f" ({position})"

                label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                label_y = max(y - 10, label_size[1] + 5)

                cv2.rectangle(
                    annotated,
                    (x, label_y - label_size[1] - 5),
                    (x + label_size[0] + 5, label_y + 5),
                    color, -1
                )
                cv2.putText(
                    annotated, label, (x + 2, label_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
                )

        return annotated

    # ─── Settings ───

    def set_confidence(self, conf: float):
        self.confidence = max(0.0, min(1.0, conf))

    def set_iou_threshold(self, iou: float):
        self.iou_threshold = max(0.0, min(1.0, iou))

    def set_device(self, device: str):
        self.device = device

    @staticmethod
    def get_gpu_info() -> dict:
        """ตรวจสอบ GPU status และข้อมูลรายละเอียด"""
        info = {
            "gpu_available": False,
            "gpu_name": "",
            "cuda_version": "",
            "torch_version": "",
            "gpu_memory_total_mb": 0,
            "gpu_memory_used_mb": 0,
            "gpu_memory_free_mb": 0,
        }
        try:
            import torch
            info["torch_version"] = torch.__version__
            info["cuda_version"] = torch.version.cuda or ""
            info["gpu_available"] = torch.cuda.is_available()

            if info["gpu_available"]:
                info["gpu_name"] = torch.cuda.get_device_name(0)
                mem_total = torch.cuda.get_device_properties(0).total_mem
                mem_alloc = torch.cuda.memory_allocated(0)
                mem_reserved = torch.cuda.memory_reserved(0)
                info["gpu_memory_total_mb"] = round(mem_total / 1024**2)
                info["gpu_memory_used_mb"] = round(mem_alloc / 1024**2)
                info["gpu_memory_free_mb"] = round((mem_total - mem_reserved) / 1024**2)
        except ImportError:
            info["torch_version"] = "not installed"
        except Exception as e:
            info["error"] = str(e)

        return info
