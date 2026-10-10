"""
GestureRecognizer for AirDraw Studio.
Uses scale-invariant geometric landmark analysis and joint angle metrics
to classify hand poses (DRAW, MOVE_CURSOR, STOP, IDLE) with hysteresis stability.
"""

import math
from enum import Enum
from typing import List, Tuple, Optional, Any


class GestureType(str, Enum):
    DRAW = "DRAW"                # Index finger only extended
    MOVE_CURSOR = "MOVE_CURSOR"  # Open palm (all fingers extended)
    STOP = "STOP"                # Fist (all fingers curled)
    IDLE = "IDLE"                # Indeterminate or no hand


class GestureRecognizer:
    def __init__(
        self,
        enter_draw_frames: int = 2,
        exit_draw_frames: int = 1,
        stop_confirm_frames: int = 2,
    ):
        self.enter_draw_frames = enter_draw_frames
        self.exit_draw_frames = exit_draw_frames
        self.stop_confirm_frames = stop_confirm_frames

        self.current_gesture: GestureType = GestureType.IDLE
        self.raw_gesture: GestureType = GestureType.IDLE

        # Stability counters
        self._candidate_gesture: GestureType = GestureType.IDLE
        self._candidate_count: int = 0
        self._prev_is_drawing: bool = False

    def reset(self) -> None:
        """Resets the state machine when tracking is lost."""
        self.current_gesture = GestureType.IDLE
        self.raw_gesture = GestureType.IDLE
        self._candidate_gesture = GestureType.IDLE
        self._candidate_count = 0
        self._prev_is_drawing = False

    @staticmethod
    def _calc_dist(p1: Tuple[float, float, float], p2: Tuple[float, float, float]) -> float:
        dx = p1[0] - p2[0]
        dy = p1[1] - p2[1]
        dz = p1[2] - p2[2]
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    @staticmethod
    def _calc_cos_angle(
        p_mcp: Tuple[float, float, float],
        p_pip: Tuple[float, float, float],
        p_tip: Tuple[float, float, float],
    ) -> float:
        v1 = (p_pip[0] - p_mcp[0], p_pip[1] - p_mcp[1], p_pip[2] - p_mcp[2])
        v2 = (p_tip[0] - p_pip[0], p_tip[1] - p_pip[1], p_tip[2] - p_pip[2])
        len1 = math.sqrt(v1[0] * v1[0] + v1[1] * v1[1] + v1[2] * v1[2])
        len2 = math.sqrt(v2[0] * v2[0] + v2[1] * v2[1] + v2[2] * v2[2])
        if len1 < 1e-6 or len2 < 1e-6:
            return 1.0
        dot = v1[0] * v2[0] + v1[1] * v2[1] + v1[2] * v2[2]
        return dot / (len1 * len2)

    def _is_finger_extended(
        self,
        lm: List[Tuple[float, float, float]],
        mcp_idx: int,
        pip_idx: int,
        tip_idx: int,
        palm_size: float,
    ) -> Tuple[bool, bool]:
        """Returns (is_extended, is_folded)."""
        wrist = lm[0]
        mcp = lm[mcp_idx]
        pip = lm[pip_idx]
        tip = lm[tip_idx]

        d_wrist_tip = self._calc_dist(wrist, tip)
        d_wrist_pip = self._calc_dist(wrist, pip)
        d_mcp_tip = self._calc_dist(mcp, tip)
        cos_ang = self._calc_cos_angle(mcp, pip, tip)

        extended = (
            (d_wrist_tip > d_wrist_pip * 1.08)
            and (d_mcp_tip > 0.65 * palm_size)
            and (cos_ang > 0.25)
        )
        folded = (
            (d_wrist_tip < d_wrist_pip * 1.05)
            or (d_mcp_tip < 0.55 * palm_size)
            or (cos_ang < -0.1)
        )
        return extended, folded

    def _is_thumb_extended(
        self,
        lm: List[Tuple[float, float, float]],
        palm_size: float,
    ) -> Tuple[bool, bool]:
        wrist = lm[0]
        mcp = lm[2]
        tip = lm[4]
        pinky_mcp = lm[17]

        d_pinky_tip = self._calc_dist(pinky_mcp, tip)
        d_wrist_tip = self._calc_dist(wrist, tip)
        d_wrist_mcp = self._calc_dist(wrist, mcp)

        extended = (d_pinky_tip > 0.82 * palm_size) and (d_wrist_tip > d_wrist_mcp * 1.1)
        folded = (d_pinky_tip < 0.68 * palm_size)
        return extended, folded

    def classify_raw(self, landmarks: Optional[List[Any]]) -> GestureType:
        """
        Classifies instantaneous hand pose from 21 MediaPipe landmarks.
        Accepts list of landmarks with x, y, z attributes or (x, y, z) tuples.
        """
        if not landmarks or len(landmarks) < 21:
            return GestureType.IDLE

        # Convert to uniform float tuples
        lm: List[Tuple[float, float, float]] = []
        for p in landmarks:
            if hasattr(p, "x") and hasattr(p, "y"):
                z = getattr(p, "z", 0.0)
                lm.append((float(p.x), float(p.y), float(z)))
            elif isinstance(p, (list, tuple)) and len(p) >= 2:
                z = float(p[2]) if len(p) >= 3 else 0.0
                lm.append((float(p[0]), float(p[1]), z))
            else:
                return GestureType.IDLE

        # Calculate scale invariant palm size: wrist (0) to middle finger MCP (9)
        palm_size = self._calc_dist(lm[0], lm[9])
        if palm_size < 1e-4:
            return GestureType.IDLE

        # Analyze each finger
        idx_ext, idx_fold = self._is_finger_extended(lm, 5, 6, 8, palm_size)
        mid_ext, mid_fold = self._is_finger_extended(lm, 9, 10, 12, palm_size)
        ring_ext, ring_fold = self._is_finger_extended(lm, 13, 14, 16, palm_size)
        pinky_ext, pinky_fold = self._is_finger_extended(lm, 17, 18, 20, palm_size)
        thumb_ext, thumb_fold = self._is_thumb_extended(lm, palm_size)

        # Rule 1: DRAW (Index extended, others folded)
        if idx_ext and mid_fold and ring_fold and pinky_fold:
            return GestureType.DRAW

        # Rule 2: MOVE CURSOR (Open palm: all fingers extended)
        if idx_ext and mid_ext and ring_ext and pinky_ext and (thumb_ext or not thumb_fold):
            return GestureType.MOVE_CURSOR

        # Rule 3: STOP (Fist: all fingers folded)
        if idx_fold and mid_fold and ring_fold and pinky_fold and thumb_fold:
            return GestureType.STOP

        return GestureType.IDLE

    def update(self, landmarks: Optional[List[Any]]) -> Tuple[GestureType, bool]:
        """
        Processes frame landmarks through the hysteresis stability filter.
        Returns (stabilized_gesture, is_drawing_active).
        Guarantees instant drawing cutoff when leaving DRAW to prevent trailing lines.
        """
        raw = self.classify_raw(landmarks)
        self.raw_gesture = raw

        if landmarks is None or raw == GestureType.IDLE:
            # Immediate exit on tracking loss
            self.current_gesture = GestureType.IDLE
            self._candidate_gesture = GestureType.IDLE
            self._candidate_count = 0
            self._prev_is_drawing = False
            return GestureType.IDLE, False

        # Fast exit from DRAW: If currently DRAW and raw pose ceases to be DRAW,
        # cut off drawing immediately so we never draw connecting tails or fold-fist tails!
        if self.current_gesture == GestureType.DRAW and raw != GestureType.DRAW:
            self.current_gesture = raw
            self._candidate_gesture = raw
            self._candidate_count = 1
            self._prev_is_drawing = False
            return self.current_gesture, False

        # Standard hysteresis check for entering new states
        if raw == self._candidate_gesture:
            self._candidate_count += 1
        else:
            self._candidate_gesture = raw
            self._candidate_count = 1

        required_frames = 1
        if raw == GestureType.DRAW:
            required_frames = self.enter_draw_frames
        elif raw == GestureType.STOP:
            required_frames = self.stop_confirm_frames

        if self._candidate_count >= required_frames:
            self.current_gesture = raw

        is_drawing = (self.current_gesture == GestureType.DRAW)
        self._prev_is_drawing = is_drawing
        return self.current_gesture, is_drawing
