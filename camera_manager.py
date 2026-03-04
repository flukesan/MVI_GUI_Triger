"""
Camera Manager for Dual Mode Inspection System
จัดการกล้อง USB, RTSP/IP Camera, GigE Vision, และ Image File
ใช้ Backend Pattern รองรับทั้ง Capture Mode และ Realtime Mode

Based on yolo_inspection_system camera_manager + camera_backends
"""
import time
import cv2
import numpy as np
from typing import Optional, Dict, List, Union, Any

try:
    from PyQt6.QtCore import QObject, QThread, pyqtSignal as Signal
except ImportError:
    from PySide6.QtCore import QObject, QThread, Signal

from camera_backends import BaseCameraBackend, OpenCVBackend, GigEBackend


class CameraStreamWorker(QThread):
    """Worker thread สำหรับดึงเฟรมจากกล้องแบบต่อเนื่อง (Realtime Mode)"""
    frame_ready = Signal(int, object)  # (camera_id, numpy frame)

    def __init__(self, camera_id: int, backend: BaseCameraBackend, target_fps: int = 30):
        super().__init__()
        self.camera_id = camera_id
        self.backend = backend
        self.target_fps = target_fps
        self.running = False

    def run(self):
        self.running = True
        interval = 1.0 / max(self.target_fps, 1)
        while self.running:
            start = time.time()
            if self.backend and self.backend.is_connected():
                frame = self.backend.get_frame()
                if frame is not None:
                    self.frame_ready.emit(self.camera_id, frame)
                else:
                    time.sleep(0.005)
            else:
                time.sleep(0.1)
                continue
            # Adaptive sleep: subtract elapsed time from interval
            elapsed = time.time() - start
            sleep_time = interval - elapsed
            if sleep_time > 0.001:
                time.sleep(sleep_time)

    def stop(self):
        self.running = False
        self.wait(3000)


class CameraManager(QObject):
    """จัดการกล้อง — รองรับ USB, RTSP, GigE Vision, Image File (ใช้ Backend Pattern)"""

    # Camera type constants
    TYPE_USB = "usb"
    TYPE_RTSP = "rtsp"
    TYPE_IP = "ip"
    TYPE_GIGE = "gige"

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

    def open_camera(self, camera_id: int, camera_type: str = TYPE_USB,
                    source: Any = 0, width: int = 1280, height: int = 720,
                    fps: int = 30, **kwargs) -> bool:
        """
        เปิดกล้อง

        Args:
            camera_id: ID ของกล้อง (0, 1, ...)
            camera_type: "usb", "rtsp", "ip", "gige"
            source: USB index / RTSP URL / GigE dict
            width, height, fps: Resolution and FPS
            **kwargs: exposure, gain, exposure_time, gentl_path, camera_id
        """
        try:
            if camera_id in self.cameras:
                self.close_camera(camera_id)

            # Create appropriate backend
            backend = self._create_backend(camera_type)
            if backend is None:
                self.camera_error.emit(camera_id, f"Cannot create backend for type: {camera_type}")
                return False

            success = backend.connect(source, width, height, fps, **kwargs)
            if not success:
                # Ensure full cleanup of backend when connection fails
                try:
                    backend.disconnect()
                except Exception:
                    pass
                self.camera_error.emit(camera_id, f"Cannot connect to camera: {source}")
                return False

            self.cameras[camera_id] = {
                "backend": backend,
                "type": camera_type,
                "source": source,
                "is_open": True
            }

            self.camera_opened.emit(camera_id)
            print(f"Camera {camera_id} opened: {source} (type={camera_type})")
            return True

        except Exception as e:
            self.camera_error.emit(camera_id, str(e))
            print(f"Camera {camera_id} open error: {e}")
            return False

    def _create_backend(self, camera_type: str) -> Optional[BaseCameraBackend]:
        """สร้าง backend ตาม camera type"""
        camera_type = camera_type.lower()

        if camera_type in [self.TYPE_USB, self.TYPE_RTSP, self.TYPE_IP]:
            return OpenCVBackend()
        elif camera_type == self.TYPE_GIGE:
            try:
                return GigEBackend()
            except RuntimeError as e:
                print(f"GigE backend error: {e}")
                return None
        else:
            print(f"Unsupported camera type: {camera_type}")
            return None

    def connect_from_profile(self, camera_id: int, profile: dict) -> bool:
        """
        เชื่อมต่อกล้องจาก Camera Profile dict
        (ใช้ร่วมกับ CameraProfilesDialog)
        """
        cam_type = profile.get("type", "usb")
        source = profile.get("source", 0)
        width = profile.get("width", 1280)
        height = profile.get("height", 720)
        fps = profile.get("fps", 30)

        kwargs = {}
        if profile.get("exposure", 0) > 0:
            kwargs["exposure"] = profile["exposure"]
            kwargs["exposure_time"] = profile["exposure"]  # สำหรับ GigE
        if profile.get("gain", 0) > 0:
            kwargs["gain"] = profile["gain"]

        return self.open_camera(camera_id, cam_type, source, width, height, fps, **kwargs)

    def close_camera(self, camera_id: int):
        """ปิดกล้อง"""
        self.stop_stream(camera_id)

        if camera_id in self.cameras:
            cam = self.cameras[camera_id]
            backend = cam.get("backend")
            if backend:
                backend.disconnect()
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
            backend = self.cameras[camera_id].get("backend")
            return backend is not None and backend.is_connected()
        return False

    # ─── Capture Mode (ถ่ายทีละภาพ) ───

    def capture_frame(self, camera_id: int) -> Optional[np.ndarray]:
        """ถ่ายภาพ 1 เฟรม"""
        if camera_id not in self.cameras:
            self.camera_error.emit(camera_id, "Camera not opened")
            return None

        backend = self.cameras[camera_id].get("backend")
        if backend is None or not backend.is_connected():
            self.camera_error.emit(camera_id, "Camera not available")
            return None

        frame = backend.get_frame()
        if frame is not None:
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

        backend = self.cameras[camera_id].get("backend")
        worker = CameraStreamWorker(camera_id, backend, fps)
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
        """ตั้งความละเอียด (สำหรับ OpenCV backend)"""
        if camera_id in self.cameras:
            backend = self.cameras[camera_id].get("backend")
            if isinstance(backend, OpenCVBackend) and backend.cap:
                backend.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                backend.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    def get_camera_info(self, camera_id: int) -> Optional[dict]:
        """ข้อมูลกล้อง"""
        if camera_id not in self.cameras:
            return None

        backend = self.cameras[camera_id].get("backend")
        if backend:
            info = backend.get_info()
            info['camera_type'] = self.cameras[camera_id].get("type")
            info['is_streaming'] = self.is_streaming(camera_id)
            return info
        return None

    @staticmethod
    def list_available_cameras(max_check: int = 10) -> List[dict]:
        """
        สแกนหากล้อง USB ที่เชื่อมต่ออยู่

        Returns:
            List of dicts: [{"index": 0, "name": "...", "width": ..., "height": ...}, ...]
        """
        import os
        available = []

        # Linux: check /dev/video* devices to find real camera indices
        real_indices = set()
        if os.path.exists("/dev"):
            for dev in sorted(os.listdir("/dev")):
                if dev.startswith("video"):
                    try:
                        idx = int(dev.replace("video", ""))
                        real_indices.add(idx)
                    except ValueError:
                        pass

        # Try both real indices and sequential scan
        indices_to_check = sorted(real_indices | set(range(max_check)))

        for i in indices_to_check:
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                # Read a test frame to verify it's a real camera
                ret, frame = cap.read()
                if ret and frame is not None:
                    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    backend_name = cap.getBackendName() if hasattr(cap, 'getBackendName') else "unknown"
                    available.append({
                        "index": i,
                        "name": f"USB Camera {i} ({w}x{h})",
                        "width": w,
                        "height": h,
                        "backend": backend_name,
                    })
                    print(f"  Found camera: index={i}, {w}x{h}, backend={backend_name}")
                cap.release()

        print(f"Available cameras: {len(available)} found "
              f"(checked indices: {indices_to_check})")
        return available
