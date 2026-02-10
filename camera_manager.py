"""
Camera Manager for Dual Mode Inspection System
จัดการกล้อง USB, IP Camera (RTSP), และ Image File
รองรับทั้ง Capture Mode และ Realtime Mode
"""
import time
import cv2
import numpy as np
from typing import Optional, Dict, List, Union

try:
    from PyQt6.QtCore import QObject, QThread, pyqtSignal as Signal
except ImportError:
    from PySide6.QtCore import QObject, QThread, Signal


class CameraStreamWorker(QThread):
    """Worker thread สำหรับดึงเฟรมจากกล้องแบบต่อเนื่อง (Realtime Mode)"""
    frame_ready = Signal(int, object)  # (camera_id, numpy frame)

    def __init__(self, camera_id: int, capture: cv2.VideoCapture, target_fps: int = 30):
        super().__init__()
        self.camera_id = camera_id
        self.capture = capture
        self.target_fps = target_fps
        self.running = False

    def run(self):
        self.running = True
        interval = 1.0 / max(self.target_fps, 1)
        while self.running:
            if self.capture and self.capture.isOpened():
                ret, frame = self.capture.read()
                if ret:
                    self.frame_ready.emit(self.camera_id, frame)
                else:
                    time.sleep(0.01)
            else:
                time.sleep(0.1)
            time.sleep(interval)

    def stop(self):
        self.running = False
        self.wait(3000)


class CameraManager(QObject):
    """จัดการกล้อง — รองรับ USB, RTSP, Image File"""

    # Signals
    frame_captured = Signal(int, object)    # (camera_id, numpy frame)
    camera_opened = Signal(int)             # camera_id
    camera_closed = Signal(int)             # camera_id
    camera_error = Signal(int, str)         # (camera_id, error_msg)

    def __init__(self):
        super().__init__()
        self.cameras: Dict[int, dict] = {}
        self.stream_workers: Dict[int, CameraStreamWorker] = {}

    # ─── Camera Lifecycle ───

    def open_camera(self, camera_id: int, source: Union[int, str]) -> bool:
        """
        เปิดกล้อง
        source: int (USB index: 0,1,2) หรือ str ("rtsp://..." สำหรับ IP Camera)
        """
        try:
            # ปิดกล้องเก่าถ้ามี
            if camera_id in self.cameras:
                self.close_camera(camera_id)

            cap = cv2.VideoCapture(source)
            if not cap.isOpened():
                self.camera_error.emit(camera_id, f"Cannot open camera: {source}")
                return False

            self.cameras[camera_id] = {
                "cap": cap,
                "source": source,
                "is_open": True
            }

            self.camera_opened.emit(camera_id)
            print(f"Camera {camera_id} opened: {source}")
            return True

        except Exception as e:
            self.camera_error.emit(camera_id, str(e))
            return False

    def close_camera(self, camera_id: int):
        """ปิดกล้อง"""
        self.stop_stream(camera_id)

        if camera_id in self.cameras:
            cam = self.cameras[camera_id]
            if cam["cap"]:
                cam["cap"].release()
            del self.cameras[camera_id]
            self.camera_closed.emit(camera_id)
            print(f"Camera {camera_id} closed")

    def close_all(self):
        """ปิดกล้องทั้งหมด"""
        for cam_id in list(self.cameras.keys()):
            self.close_camera(cam_id)

    def is_opened(self, camera_id: int) -> bool:
        """ตรวจสอบว่ากล้องเปิดอยู่หรือไม่"""
        if camera_id in self.cameras:
            return self.cameras[camera_id]["cap"].isOpened()
        return False

    # ─── Capture Mode (ถ่ายทีละภาพ) ───

    def capture_frame(self, camera_id: int) -> Optional[np.ndarray]:
        """ถ่ายภาพ 1 เฟรม"""
        if camera_id not in self.cameras:
            self.camera_error.emit(camera_id, "Camera not opened")
            return None

        cap = self.cameras[camera_id]["cap"]
        if not cap.isOpened():
            self.camera_error.emit(camera_id, "Camera not available")
            return None

        ret, frame = cap.read()
        if ret:
            self.frame_captured.emit(camera_id, frame)
            return frame
        else:
            self.camera_error.emit(camera_id, "Failed to capture frame")
            return None

    # ─── Realtime Mode (stream ต่อเนื่อง) ───

    def start_stream(self, camera_id: int, fps: int = 30):
        """เริ่ม stream ต่อเนื่อง"""
        if camera_id not in self.cameras:
            self.camera_error.emit(camera_id, "Camera not opened")
            return

        self.stop_stream(camera_id)

        cap = self.cameras[camera_id]["cap"]
        worker = CameraStreamWorker(camera_id, cap, fps)
        worker.frame_ready.connect(self._on_stream_frame)
        self.stream_workers[camera_id] = worker
        worker.start()
        print(f"Camera {camera_id} stream started at {fps} FPS")

    def stop_stream(self, camera_id: int):
        """หยุด stream"""
        if camera_id in self.stream_workers:
            worker = self.stream_workers[camera_id]
            worker.stop()
            del self.stream_workers[camera_id]
            print(f"Camera {camera_id} stream stopped")

    def is_streaming(self, camera_id: int) -> bool:
        """ตรวจสอบว่ากำลัง stream อยู่หรือไม่"""
        return camera_id in self.stream_workers and self.stream_workers[camera_id].running

    def _on_stream_frame(self, camera_id: int, frame: np.ndarray):
        """Forward frame จาก worker ไปยัง signal"""
        self.frame_captured.emit(camera_id, frame)

    # ─── Image File (สำหรับ testing/demo) ───

    def load_image_file(self, file_path: str) -> Optional[np.ndarray]:
        """โหลดภาพจากไฟล์"""
        frame = cv2.imread(file_path)
        if frame is not None:
            return frame
        return None

    # ─── Utilities ───

    def set_resolution(self, camera_id: int, width: int, height: int):
        """ตั้งความละเอียด"""
        if camera_id in self.cameras:
            cap = self.cameras[camera_id]["cap"]
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    def get_camera_info(self, camera_id: int) -> Optional[dict]:
        """ข้อมูลกล้อง"""
        if camera_id not in self.cameras:
            return None

        cap = self.cameras[camera_id]["cap"]
        return {
            "source": self.cameras[camera_id]["source"],
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "fps": cap.get(cv2.CAP_PROP_FPS),
            "is_streaming": self.is_streaming(camera_id)
        }

    @staticmethod
    def list_available_cameras(max_check: int = 5) -> List[int]:
        """สแกนหากล้อง USB ที่เชื่อมต่ออยู่"""
        available = []
        for i in range(max_check):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available.append(i)
                cap.release()
        return available
