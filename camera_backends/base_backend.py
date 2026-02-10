"""
Base Camera Backend — Abstract base class สำหรับ camera backends
Abstract interface for different camera types
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import numpy as np


class BaseCameraBackend(ABC):
    """Abstract base class สำหรับ camera backend ทุกประเภท"""

    def __init__(self):
        self.is_connected_flag = False
        self.camera_info = {}

    @abstractmethod
    def connect(self, source: Any, width: int = 1280, height: int = 720,
                fps: int = 30, **kwargs) -> bool:
        """เชื่อมต่อกล้อง"""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """ตัดการเชื่อมต่อกล้อง"""
        pass

    @abstractmethod
    def get_frame(self) -> Optional[np.ndarray]:
        """ดึงภาพล่าสุดจากกล้อง"""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """ตรวจสอบว่ากล้องเชื่อมต่ออยู่หรือไม่"""
        pass

    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """ดึงข้อมูลกล้อง"""
        pass

    def capture_image(self, save_path: Optional[str] = None) -> Optional[np.ndarray]:
        """จับภาพนิ่ง"""
        import cv2
        frame = self.get_frame()
        if frame is not None and save_path:
            cv2.imwrite(save_path, frame)
        return frame
