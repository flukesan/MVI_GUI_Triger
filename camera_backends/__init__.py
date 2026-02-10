"""
Camera Backends — รองรับกล้องหลายประเภท
Support for multiple camera types (USB/RTSP/GigE Vision)
"""
from .base_backend import BaseCameraBackend
from .opencv_backend import OpenCVBackend
from .gige_backend import GigEBackend

__all__ = [
    'BaseCameraBackend',
    'OpenCVBackend',
    'GigEBackend'
]
