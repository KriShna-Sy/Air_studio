"""
Vision package for AirDraw Studio.
Provides real-time camera capture, MediaPipe HandLandmarker tracking,
geometric gesture classification, and trajectory smoothing.
"""

from .filter import OneEuroFilter, PointSmoother
from .gesture_recognizer import GestureRecognizer, GestureType
from .hand_tracker import HandTracker
from .camera_thread import CameraThread

__all__ = [
    "OneEuroFilter",
    "PointSmoother",
    "GestureRecognizer",
    "GestureType",
    "HandTracker",
    "CameraThread",
]
