"""
CameraThread worker for AirDraw Studio.
Dedicated background capture and vision processing loop.
Emits Qt signals for thread-safe GUI synchronization without UI lag.
"""

import time
import os
import sys
import math
from typing import Optional, List
import cv2
import PyQt5
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.join(os.path.dirname(PyQt5.__file__), "Qt5", "plugins")
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker
from PyQt5.QtGui import QImage

from config import (
    DEFAULT_CAMERA_INDEX,
    CAMERA_WIDTH,
    CAMERA_HEIGHT,
    TARGET_FPS,
    MAX_CAMERAS_TO_SCAN,
    ACTIVE_MARGIN_X,
    ACTIVE_MARGIN_Y,
    SMOOTHING_MODE,
    PINCH_CLICK_THRESHOLD,
    DEFAULT_BG_MODE,
    BG_MODE_BLURRED,
)
from .filter import PointSmoother
from .gesture_recognizer import GestureRecognizer, GestureType
from .hand_tracker import HandTracker


class CameraThread(QThread):
    # Signals
    frame_ready = pyqtSignal(QImage)
    background_ready = pyqtSignal(QImage)
    tracking_updated = pyqtSignal(str, float, float, bool, bool, bool)  # (gesture, nx, ny, is_drawing, hand_found, is_pinched)
    fps_updated = pyqtSignal(float)
    status_updated = pyqtSignal(str, bool)  # (message, is_error)
    devices_discovered = pyqtSignal(list)   # list of available camera indices

    def __init__(
        self,
        camera_index: int = DEFAULT_CAMERA_INDEX,
        model_path: Optional[str] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.camera_index = camera_index
        self.model_path = model_path
        self.bg_mode = DEFAULT_BG_MODE

        self._running = False
        self._mutex = QMutex()
        self._requested_camera_index: Optional[int] = None
        self._camera_enabled = True

        # Components
        self.hand_tracker: Optional[HandTracker] = None
        self.gesture_recognizer = GestureRecognizer()
        self.smoother = PointSmoother(
            mode=SMOOTHING_MODE,
            margin_x=ACTIVE_MARGIN_X,
            margin_y=ACTIVE_MARGIN_Y,
            mirror=True,
        )

        # FPS metrics
        self._fps_counter = 0
        self._fps_last_time = time.time()
        self._current_fps = 0.0

    def set_camera_index(self, index: int) -> None:
        """Requests camera switch. Safely handled inside thread run loop."""
        with QMutexLocker(self._mutex):
            self._requested_camera_index = int(index)

    def set_camera_enabled(self, enabled: bool) -> None:
        """Enables or disables camera acquisition without quitting thread."""
        with QMutexLocker(self._mutex):
            self._camera_enabled = enabled

    def set_smoothing_mode(self, mode: str) -> None:
        with QMutexLocker(self._mutex):
            self.smoother.mode = mode

    def set_margin(self, margin_x: float, margin_y: float) -> None:
        with QMutexLocker(self._mutex):
            self.smoother.margin_x = float(margin_x)
            self.smoother.margin_y = float(margin_y)

    def set_bg_mode(self, mode: str) -> None:
        with QMutexLocker(self._mutex):
            self.bg_mode = mode

    def stop(self) -> None:
        """Stops the worker thread safely and waits for exit."""
        with QMutexLocker(self._mutex):
            self._running = False
        self.wait(2000)

    @staticmethod
    def probe_available_cameras(max_to_scan: int = MAX_CAMERAS_TO_SCAN) -> List[int]:
        """Probes /dev/video devices or indices to find functional cameras."""
        available = []
        for idx in range(max_to_scan):
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    available.append(idx)
                cap.release()
        return available

    def refresh_devices_async(self) -> None:
        """Requests thread-safe rescan of cameras inside worker thread."""
        with QMutexLocker(self._mutex):
            self._rescan_requested = True

    def run(self) -> None:
        self._running = True
        self._rescan_requested = False

        # Initialize HandTracker
        try:
            self.hand_tracker = HandTracker(model_path=self.model_path)
            self.status_updated.emit("Hand Tracker initialized", False)
        except Exception as e:
            self.status_updated.emit(f"Vision model error: {str(e)}", True)
            self.hand_tracker = None

        # Probe available devices safely inside thread before opening
        initial_devices = self.probe_available_cameras()
        self.devices_discovered.emit(initial_devices)

        # Select initial camera
        current_idx = self.camera_index
        if initial_devices and current_idx not in initial_devices:
            current_idx = initial_devices[0]
            self.camera_index = current_idx

        cap: Optional[cv2.VideoCapture] = None
        try:
            cap = self._open_camera(current_idx)
        except Exception as e:
            self.status_updated.emit(f"Camera {current_idx} error: {e}", True)

        self._fps_last_time = time.time()
        self._fps_counter = 0

        while self._running:
            # Check rescan request
            with QMutexLocker(self._mutex):
                do_rescan = self._rescan_requested
                self._rescan_requested = False
                req_idx = self._requested_camera_index
                self._requested_camera_index = None
                is_enabled = self._camera_enabled

            if do_rescan:
                if cap is not None:
                    cap.release()
                    cap = None
                devices = self.probe_available_cameras()
                self.devices_discovered.emit(devices)
                if devices and current_idx not in devices:
                    current_idx = devices[0]
                    self.camera_index = current_idx
                cap = self._open_camera(current_idx)

            if req_idx is not None and req_idx != current_idx:
                if cap is not None:
                    cap.release()
                    cap = None
                current_idx = req_idx
                self.camera_index = req_idx
                cap = self._open_camera(current_idx)

            if not is_enabled or cap is None or not cap.isOpened():
                # Sleep briefly if camera is paused or unavailable
                time.sleep(0.05)
                continue

            ret, frame = cap.read()
            if not ret or frame is None:
                self.status_updated.emit(f"Failed to read from camera {current_idx}", True)
                time.sleep(0.05)
                continue

            now = time.time()
            timestamp_ms = int(now * 1000)

            # Process with MediaPipe
            landmarks = None
            raw_tip = None
            if self.hand_tracker is not None:
                landmarks, raw_tip = self.hand_tracker.process_frame(frame, timestamp_ms)

            # Update gesture recognition
            gesture, is_drawing = self.gesture_recognizer.update(landmarks)

            # Coordinates and smoothing
            hand_detected = (landmarks is not None and len(landmarks) >= 21 and raw_tip is not None)
            is_pinched = False
            if hand_detected:
                lm_wrist = landmarks[0]
                lm_mid_mcp = landmarks[9]
                lm_index = landmarks[8]
                lm_thumb = landmarks[4]
                palm_size = math.hypot(lm_wrist.x - lm_mid_mcp.x, lm_wrist.y - lm_mid_mcp.y)
                pinch_dist = math.hypot(lm_thumb.x - lm_index.x, lm_thumb.y - lm_index.y)
                if palm_size > 1e-4:
                    is_pinched = (pinch_dist / palm_size) < PINCH_CLICK_THRESHOLD

            if hand_detected and raw_tip is not None:
                nx, ny = self.smoother.process(raw_tip[0], raw_tip[1], timestamp=now)
            else:
                self.smoother.reset()
                nx, ny = (0.5, 0.5)

            # Emit tracking state with pinch
            self.tracking_updated.emit(gesture.value, nx, ny, is_drawing, hand_detected, is_pinched)

            # Fast CPU background generation for fullscreen canvas
            with QMutexLocker(self._mutex):
                cur_bg_mode = self.bg_mode

            if cur_bg_mode == "blurred":
                flipped = cv2.flip(frame, 1)
                small = cv2.resize(flipped, (240, 180), interpolation=cv2.INTER_LINEAR)
                bg_bgr = cv2.GaussianBlur(small, (7, 7), 0)
            elif cur_bg_mode == "dimmed":
                flipped = cv2.flip(frame, 1)
                small = cv2.resize(flipped, (320, 240), interpolation=cv2.INTER_LINEAR)
                bg_bgr = (small * 0.4).astype(np.uint8)
            elif cur_bg_mode == "clear":
                bg_bgr = cv2.flip(frame, 1)
            else:
                bg_bgr = None

            if bg_bgr is not None:
                bg_h, bg_w, bg_ch = bg_bgr.shape
                bg_rgb = cv2.cvtColor(bg_bgr, cv2.COLOR_BGR2RGB)
                bg_qimg = QImage(bg_rgb.data, bg_w, bg_h, bg_ch * bg_w, QImage.Format_RGB888).copy()
                self.background_ready.emit(bg_qimg)

            # Draw visual feedback overlay on frame for camera preview
            if self.hand_tracker is not None:
                preview_frame = self.hand_tracker.draw_hand_overlay(
                    frame,
                    landmarks,
                    gesture=gesture.value,
                    mirror=True,
                )
            else:
                preview_frame = cv2.flip(frame, 1)

            # Convert BGR frame to Qt QImage
            h, w, ch = preview_frame.shape
            bytes_per_line = ch * w
            rgb_preview = cv2.cvtColor(preview_frame, cv2.COLOR_BGR2RGB)
            q_img = QImage(rgb_preview.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
            self.frame_ready.emit(q_img)

            # FPS calculation
            self._fps_counter += 1
            if (now - self._fps_last_time) >= 1.0:
                self._current_fps = self._fps_counter / (now - self._fps_last_time)
                self.fps_updated.emit(self._current_fps)
                self._fps_counter = 0
                self._fps_last_time = now

            # Throttle to target FPS
            elapsed = time.time() - now
            target_delay = 1.0 / TARGET_FPS
            if elapsed < target_delay:
                time.sleep(target_delay - elapsed)

        # Cleanup on exit
        if cap is not None:
            cap.release()
        if self.hand_tracker is not None:
            self.hand_tracker.close()
        self.status_updated.emit("Camera thread terminated", False)

    def _open_camera(self, index: int) -> Optional[cv2.VideoCapture]:
        """Safely opens camera index with configured resolution."""
        cap = cv2.VideoCapture(index)
        if not cap.isOpened():
            self.status_updated.emit(f"Could not open camera {index}", True)
            return None

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)
        self.status_updated.emit(f"Connected to camera {index}", False)
        return cap
