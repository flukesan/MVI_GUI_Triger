"""
OpenCV Camera Backend — รองรับ USB/RTSP/IP Camera
Backend for USB, RTSP, and IP cameras using OpenCV
"""
import cv2
import threading
import time
from typing import Optional, Dict, Any
import numpy as np
from .base_backend import BaseCameraBackend


class OpenCVBackend(BaseCameraBackend):
    """Camera backend ที่ใช้ OpenCV VideoCapture (USB/RTSP/IP)"""

    def __init__(self):
        super().__init__()
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_running = False
        self.current_frame: Optional[np.ndarray] = None
        self.frame_lock = threading.Lock()
        self.capture_thread: Optional[threading.Thread] = None
        self.source = None

        # Statistics
        self.frame_count = 0
        self.fps = 0
        self.last_fps_time = time.time()
        self.fps_frame_count = 0

    def connect(self, source: Any, width: int = 1280, height: int = 720,
                fps: int = 30, **kwargs) -> bool:
        """
        เชื่อมต่อกล้อง OpenCV

        Args:
            source: Camera source (0, 1, ... for USB or RTSP URL)
            width: Frame width
            height: Frame height
            fps: Target FPS
            **kwargs: exposure, gain, buffer_size
        """
        try:
            self.disconnect()

            print(f"กำลังเชื่อมต่อกล้อง (OpenCV): {source}")
            self.cap = cv2.VideoCapture(source)

            if not self.cap.isOpened():
                print(f"ไม่สามารถเชื่อมต่อกล้อง: {source}")
                return False

            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.cap.set(cv2.CAP_PROP_FPS, fps)

            if 'exposure' in kwargs and kwargs['exposure'] > 0:
                self.cap.set(cv2.CAP_PROP_EXPOSURE, kwargs['exposure'])
            if 'gain' in kwargs and kwargs['gain'] > 0:
                self.cap.set(cv2.CAP_PROP_GAIN, kwargs['gain'])
            if 'buffer_size' in kwargs:
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, kwargs['buffer_size'])

            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = int(self.cap.get(cv2.CAP_PROP_FPS))

            self.source = source
            self.camera_info = {
                'backend': 'OpenCV',
                'source': source,
                'width': actual_width,
                'height': actual_height,
                'fps': actual_fps
            }

            print(f"เชื่อมต่อกล้องสำเร็จ (OpenCV): {actual_width}x{actual_height} @ {actual_fps}fps")

            self.is_running = True
            self.is_connected_flag = True
            self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.capture_thread.start()

            return True

        except Exception as e:
            print(f"Error connecting camera (OpenCV): {e}")
            return False

    def disconnect(self) -> None:
        self.is_running = False
        self.is_connected_flag = False

        if self.capture_thread is not None:
            self.capture_thread.join(timeout=2.0)
            self.capture_thread = None

        if self.cap is not None:
            self.cap.release()
            self.cap = None

        self.current_frame = None

    def _capture_loop(self) -> None:
        while self.is_running and self.cap is not None:
            try:
                ret, frame = self.cap.read()
                if ret:
                    with self.frame_lock:
                        self.current_frame = frame.copy()
                        self.frame_count += 1

                    self.fps_frame_count += 1
                    current_time = time.time()
                    elapsed = current_time - self.last_fps_time
                    if elapsed >= 1.0:
                        self.fps = self.fps_frame_count / elapsed
                        self.fps_frame_count = 0
                        self.last_fps_time = current_time
                else:
                    time.sleep(0.1)
            except Exception as e:
                print(f"Error in capture loop: {e}")
                time.sleep(0.1)

    def get_frame(self) -> Optional[np.ndarray]:
        with self.frame_lock:
            if self.current_frame is not None:
                return self.current_frame.copy()
            return None

    def is_connected(self) -> bool:
        return self.cap is not None and self.cap.isOpened() and self.is_running

    def get_info(self) -> Dict[str, Any]:
        return {
            **self.camera_info,
            'connected': self.is_connected(),
            'frame_count': self.frame_count,
            'current_fps': round(self.fps, 1)
        }

    def __del__(self):
        self.disconnect()
