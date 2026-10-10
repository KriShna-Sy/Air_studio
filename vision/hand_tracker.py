"""
HandTracker module for AirDraw Studio.
Wraps MediaPipe Tasks Vision HandLandmarker (VIDEO mode), manages monotonic timestamps,
extracts index fingertip coordinates, and draws the hand skeleton overlay.
"""

import os
import sys
import time
from typing import Optional, List, Tuple, Any
import cv2
import PyQt5
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.join(os.path.dirname(PyQt5.__file__), "Qt5", "plugins")
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.vision import HandLandmarksConnections

from config import (
    DEFAULT_MODEL_PATH,
    ALTERNATIVE_MODEL_PATHS,
    MIN_DETECTION_CONFIDENCE,
    MIN_TRACKING_CONFIDENCE,
    MIN_PRESENCE_CONFIDENCE,
    NUM_HANDS,
)


class HandTracker:
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = self._resolve_model_path(model_path)
        self.landmarker: Optional[vision.HandLandmarker] = None
        self._last_timestamp_ms: int = 0
        self._init_landmarker()

    @staticmethod
    def _resolve_model_path(custom_path: Optional[str]) -> str:
        candidates = []
        if custom_path:
            candidates.append(os.path.expanduser(custom_path))
        candidates.append(DEFAULT_MODEL_PATH)
        for p in ALTERNATIVE_MODEL_PATHS:
            candidates.append(str(p))

        for c in candidates:
            if os.path.exists(c) and os.path.getsize(c) > 1000:
                return c

        searched = ", ".join(candidates)
        raise FileNotFoundError(
            f"MediaPipe Hand Landmarker model not found. Searched: [{searched}].\n"
            f"Please ensure 'hand_landmarker.task' exists at '~/mediapipe_models/hand_landmarker.task'."
        )

    def _init_landmarker(self) -> None:
        base_options = mp_python.BaseOptions(model_asset_path=self.model_path)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_hands=NUM_HANDS,
            min_hand_detection_confidence=MIN_DETECTION_CONFIDENCE,
            min_hand_presence_confidence=MIN_PRESENCE_CONFIDENCE,
            min_tracking_confidence=MIN_TRACKING_CONFIDENCE,
        )
        self.landmarker = vision.HandLandmarker.create_from_options(options)
        self._last_timestamp_ms = 0

    def process_frame(
        self,
        bgr_frame: np.ndarray,
        timestamp_ms: Optional[int] = None,
    ) -> Tuple[Optional[List[Any]], Optional[Tuple[float, float]]]:
        """
        Runs MediaPipe inference on BGR frame.
        Returns:
            (landmarks_list, (index_tip_raw_x, index_tip_raw_y))
            where raw_x, raw_y are in camera normalized space [0.0, 1.0].
        """
        if self.landmarker is None:
            return None, None

        # Convert to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        # Monotonically increasing timestamp requirement
        if timestamp_ms is None:
            curr_ms = int(time.time() * 1000)
        else:
            curr_ms = timestamp_ms

        if curr_ms <= self._last_timestamp_ms:
            curr_ms = self._last_timestamp_ms + 1
        self._last_timestamp_ms = curr_ms

        try:
            result = self.landmarker.detect_for_video(mp_image, curr_ms)
        except Exception as e:
            return None, None

        if result and result.hand_landmarks and len(result.hand_landmarks) > 0:
            first_hand = result.hand_landmarks[0]
            # Landmark 8 is INDEX_FINGER_TIP
            if len(first_hand) > 8:
                tip = first_hand[8]
                return first_hand, (float(tip.x), float(tip.y))
            return first_hand, None

        return None, None

    def draw_hand_overlay(
        self,
        frame: np.ndarray,
        landmarks: Optional[List[Any]],
        gesture: str = "IDLE",
        mirror: bool = True,
    ) -> np.ndarray:
        """
        Draws the hand skeleton and landmarks onto the frame.
        If mirror=True, the frame is horizontally flipped first so user sees a natural mirror.
        """
        out_frame = cv2.flip(frame, 1) if mirror else frame.copy()
        if not landmarks or len(landmarks) < 21:
            return out_frame

        h, w = out_frame.shape[:2]
        pts = []
        for lm in landmarks:
            # If mirrored, x coordinate is flipped
            norm_x = (1.0 - lm.x) if mirror else lm.x
            px = int(np.clip(norm_x * w, 0, w - 1))
            py = int(np.clip(lm.y * h, 0, h - 1))
            pts.append((px, py))

        # Color schemes based on current gesture
        if gesture == "DRAW":
            bone_color = (60, 220, 60)      # Bright green
            joint_color = (20, 180, 20)
        elif gesture == "MOVE_CURSOR":
            bone_color = (235, 140, 40)     # Blue (BGR: B=235, G=140, R=40)
            joint_color = (200, 100, 20)
        elif gesture == "STOP":
            bone_color = (40, 40, 230)      # Red (BGR)
            joint_color = (30, 30, 180)
        else:
            bone_color = (180, 180, 180)    # Light slate
            joint_color = (140, 140, 140)

        # Draw bone connections
        connections = getattr(HandLandmarksConnections, "HAND_CONNECTIONS", [])
        for conn in connections:
            start_idx = conn.start
            end_idx = conn.end
            if start_idx < len(pts) and end_idx < len(pts):
                cv2.line(out_frame, pts[start_idx], pts[end_idx], bone_color, 2, cv2.LINE_AA)

        # Draw joints
        for idx, (px, py) in enumerate(pts):
            if idx == 8:
                # Highlight index fingertip with glowing double ring
                cv2.circle(out_frame, (px, py), 12, (255, 255, 255), 2, cv2.LINE_AA)
                cv2.circle(out_frame, (px, py), 8, (0, 255, 255), -1, cv2.LINE_AA)
            else:
                cv2.circle(out_frame, (px, py), 4, joint_color, -1, cv2.LINE_AA)
                cv2.circle(out_frame, (px, py), 4, (255, 255, 255), 1, cv2.LINE_AA)

        return out_frame

    def close(self) -> None:
        """Releases the MediaPipe Landmarker."""
        if self.landmarker is not None:
            try:
                self.landmarker.close()
            except Exception:
                pass
            self.landmarker = None
