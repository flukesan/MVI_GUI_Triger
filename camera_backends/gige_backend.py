"""
GigE Vision Camera Backend — รองรับ Industrial GigE Cameras
Backend for GigE Vision cameras using Harvesters (GenICam)
ต้องติดตั้ง: pip install harvesters genicam
ต้องมี Camera SDK เช่น Basler Pylon, Vimba ติดตั้งบนเครื่อง
"""
import threading
import time
from typing import Optional, Dict, Any
import numpy as np
from .base_backend import BaseCameraBackend

try:
    from harvesters.core import Harvester
    HARVESTERS_AVAILABLE = True
except ImportError:
    HARVESTERS_AVAILABLE = False


class GigEBackend(BaseCameraBackend):
    """Camera backend สำหรับ GigE Vision cameras (Harvesters/GenICam)"""

    def __init__(self):
        super().__init__()

        if not HARVESTERS_AVAILABLE:
            raise RuntimeError(
                "Harvesters library is not installed. "
                "Install with: pip install harvesters genicam")

        self.harvester: Optional[Harvester] = None
        self.image_acquirer = None
        self.is_running = False
        self.current_frame: Optional[np.ndarray] = None
        self.frame_lock = threading.Lock()
        self.capture_thread: Optional[threading.Thread] = None

        self.frame_count = 0
        self.fps = 0
        self.last_fps_time = time.time()
        self.fps_frame_count = 0

    def connect(self, source: Any, width: int = 1280, height: int = 720,
                fps: int = 30, **kwargs) -> bool:
        """
        เชื่อมต่อกล้อง GigE Vision

        Args:
            source: dict {'gentl_path': '/path/to/producer.cti', 'camera_id': 0}
                    หรือ str (GenTL producer path)
            width: Frame width
            height: Frame height
            fps: Target FPS
            **kwargs: exposure_time, gain
        """
        try:
            self.disconnect()

            gentl_path = None
            camera_id = 0

            if isinstance(source, dict):
                gentl_path = source.get('gentl_path')
                camera_id = source.get('camera_id', 0)
            elif isinstance(source, str):
                gentl_path = source
                camera_id = kwargs.get('camera_id', 0)

            if gentl_path is None:
                gentl_path = kwargs.get('gentl_path')

            if gentl_path is None:
                print("ต้องระบุ GenTL producer path (.cti file)")
                return False

            print(f"กำลังเชื่อมต่อกล้อง GigE Vision...")
            print(f"  GenTL Producer: {gentl_path}")
            print(f"  Camera ID: {camera_id}")

            self.harvester = Harvester()
            self.harvester.add_file(gentl_path)
            self.harvester.update()

            time.sleep(0.5)

            if len(self.harvester.device_info_list) == 0:
                print("  รอให้ device discovery เสร็จ...")
                time.sleep(1.0)
                self.harvester.update()

            if len(self.harvester.device_info_list) == 0:
                print("ไม่พบกล้อง GigE Vision")
                return False

            print(f"พบกล้อง {len(self.harvester.device_info_list)} ตัว:")
            for idx, device_info in enumerate(self.harvester.device_info_list):
                print(f"  [{idx}] {device_info}")

            # Create image acquirer
            if isinstance(camera_id, int):
                if camera_id >= len(self.harvester.device_info_list):
                    print(f"Camera index {camera_id} ไม่ถูกต้อง")
                    return False
                self.image_acquirer = self.harvester.create(camera_id)
            else:
                camera_id_str = str(camera_id)
                matched_index = None
                for idx, dev in enumerate(self.harvester.device_info_list):
                    if (str(getattr(dev, 'serial_number', '')) == camera_id_str or
                        str(getattr(dev, 'user_defined_name', '')) == camera_id_str or
                        str(getattr(dev, 'display_name', '')) == camera_id_str or
                        str(getattr(dev, 'id_', '')) == camera_id_str):
                        matched_index = idx
                        break

                if matched_index is None:
                    print(f"ไม่พบกล้องที่ตรงกับ '{camera_id_str}'")
                    return False

                self.image_acquirer = self.harvester.create(matched_index)

            # Configure camera parameters
            try:
                try:
                    node_map = self.image_acquirer.remote_device.node_map
                    if hasattr(node_map, 'PixelFormat'):
                        available_formats = []
                        try:
                            if hasattr(node_map.PixelFormat, 'symbolics'):
                                available_formats = node_map.PixelFormat.symbolics
                        except Exception:
                            pass

                        preferred_formats = ['RGB8', 'BGR8', 'RGB8Packed', 'BGR8Packed']
                        for fmt in preferred_formats:
                            if fmt in available_formats:
                                node_map.PixelFormat.value = fmt
                                print(f"  Pixel Format: {fmt}")
                                break
                except Exception:
                    pass

                if self.image_acquirer.remote_device.node_map.Width:
                    max_width = self.image_acquirer.remote_device.node_map.Width.max
                    self.image_acquirer.remote_device.node_map.Width.value = min(width, max_width)

                if self.image_acquirer.remote_device.node_map.Height:
                    max_height = self.image_acquirer.remote_device.node_map.Height.max
                    self.image_acquirer.remote_device.node_map.Height.value = min(height, max_height)

                try:
                    if hasattr(self.image_acquirer.remote_device.node_map, 'AcquisitionFrameRate'):
                        self.image_acquirer.remote_device.node_map.AcquisitionFrameRateEnable.value = True
                        self.image_acquirer.remote_device.node_map.AcquisitionFrameRate.value = fps
                except Exception:
                    pass

                if 'exposure_time' in kwargs and kwargs['exposure_time'] > 0:
                    try:
                        self.image_acquirer.remote_device.node_map.ExposureTime.value = kwargs['exposure_time']
                    except Exception:
                        pass

                if 'gain' in kwargs and kwargs['gain'] > 0:
                    try:
                        self.image_acquirer.remote_device.node_map.Gain.value = kwargs['gain']
                    except Exception:
                        pass

            except Exception as e:
                print(f"บางการตั้งค่าไม่สามารถใช้งานได้: {e}")

            actual_width = self.image_acquirer.remote_device.node_map.Width.value
            actual_height = self.image_acquirer.remote_device.node_map.Height.value

            device_info = self.harvester.device_info_list[camera_id if isinstance(camera_id, int) else 0]

            self.camera_info = {
                'backend': 'GigE Vision',
                'source': str(camera_id),
                'vendor': getattr(device_info, 'vendor', 'Unknown'),
                'model': getattr(device_info, 'model', 'Unknown'),
                'serial_number': getattr(device_info, 'serial_number', 'Unknown'),
                'width': actual_width,
                'height': actual_height,
                'pixel_format': self.image_acquirer.remote_device.node_map.PixelFormat.value
            }

            print(f"เชื่อมต่อกล้องสำเร็จ (GigE Vision)")
            print(f"  Model: {self.camera_info['vendor']} {self.camera_info['model']}")
            print(f"  Resolution: {actual_width}x{actual_height}")

            self.image_acquirer.start()

            self.is_running = True
            self.is_connected_flag = True
            self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.capture_thread.start()

            return True

        except Exception as e:
            print(f"Error connecting GigE camera: {e}")
            import traceback
            traceback.print_exc()
            return False

    def disconnect(self) -> None:
        self.is_running = False
        self.is_connected_flag = False

        if self.capture_thread is not None:
            self.capture_thread.join(timeout=2.0)
            self.capture_thread = None

        if self.image_acquirer is not None:
            try:
                self.image_acquirer.stop()
                self.image_acquirer.destroy()
            except Exception:
                pass
            self.image_acquirer = None

        if self.harvester is not None:
            try:
                self.harvester.reset()
            except Exception:
                pass
            self.harvester = None

        self.current_frame = None

    def _capture_loop(self) -> None:
        import cv2

        while self.is_running and self.image_acquirer is not None:
            try:
                with self.image_acquirer.fetch(timeout=1.0) as buffer:
                    component = buffer.payload.components[0]
                    pixel_format = self.image_acquirer.remote_device.node_map.PixelFormat.value

                    if 'Bayer' in pixel_format:
                        frame = component.data.reshape(component.height, component.width)
                        if 'RG' in pixel_format:
                            frame = cv2.cvtColor(frame, cv2.COLOR_BayerRG2BGR)
                        elif 'GB' in pixel_format:
                            frame = cv2.cvtColor(frame, cv2.COLOR_BayerGB2BGR)
                        elif 'GR' in pixel_format:
                            frame = cv2.cvtColor(frame, cv2.COLOR_BayerGR2BGR)
                        elif 'BG' in pixel_format:
                            frame = cv2.cvtColor(frame, cv2.COLOR_BayerBG2BGR)
                        else:
                            frame = cv2.cvtColor(frame, cv2.COLOR_BayerRG2BGR)
                    else:
                        frame = component.data.reshape(component.height, component.width, -1)
                        if len(frame.shape) == 2:
                            frame = np.stack([frame] * 3, axis=-1)
                        elif frame.shape[2] == 1:
                            frame = np.repeat(frame, 3, axis=2)
                        elif frame.shape[2] == 3:
                            frame = frame[:, :, ::-1]
                        elif frame.shape[2] == 4:
                            frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)

                    if frame.dtype != np.uint8:
                        frame = (frame / frame.max() * 255).astype(np.uint8)

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

            except Exception as e:
                if self.is_running:
                    print(f"Timeout or error fetching frame: {e}")
                time.sleep(0.01)

    def get_frame(self) -> Optional[np.ndarray]:
        with self.frame_lock:
            if self.current_frame is not None:
                return self.current_frame.copy()
            return None

    def is_connected(self) -> bool:
        return self.image_acquirer is not None and self.is_running

    def get_info(self) -> Dict[str, Any]:
        return {
            **self.camera_info,
            'connected': self.is_connected(),
            'frame_count': self.frame_count,
            'current_fps': round(self.fps, 1)
        }

    def __del__(self):
        self.disconnect()
