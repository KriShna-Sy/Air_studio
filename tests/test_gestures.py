"""
Unit tests for GestureRecognizer and finger geometric logic.
Verifies DRAW, MOVE_CURSOR, STOP, IDLE poses and hysteresis stability.
"""

import unittest
from vision.gesture_recognizer import GestureRecognizer, GestureType


def create_synthetic_hand(
    index_ext=True,
    middle_ext=False,
    ring_ext=False,
    pinky_ext=False,
    thumb_ext=False,
):
    """
    Constructs 21 synthetic 3D landmarks for a hand.
    Wrist is at (0.5, 0.8, 0.0), Middle MCP is at (0.5, 0.5, 0.0) -> palm size = 0.3.
    """
    landmarks = [(0.5, 0.8, 0.0)] * 21  # Default fill

    # Wrist (0)
    landmarks[0] = (0.5, 0.8, 0.0)
    # Middle MCP (9) -> defines palm_size = 0.3
    landmarks[9] = (0.5, 0.5, 0.0)

    # Thumb: 1, 2, 3, 4
    landmarks[1] = (0.45, 0.75, 0.0)
    landmarks[2] = (0.40, 0.70, 0.0)
    if thumb_ext:
        landmarks[3] = (0.35, 0.65, 0.0)
        landmarks[4] = (0.25, 0.60, 0.0)  # Extended out
    else:
        landmarks[3] = (0.42, 0.68, 0.0)
        landmarks[4] = (0.45, 0.65, 0.0)  # Curled inward

    # Index: 5 (MCP), 6 (PIP), 7 (DIP), 8 (TIP)
    landmarks[5] = (0.45, 0.52, 0.0)
    if index_ext:
        landmarks[6] = (0.45, 0.40, 0.0)
        landmarks[7] = (0.45, 0.30, 0.0)
        landmarks[8] = (0.45, 0.20, 0.0)  # Extended straight up
    else:
        landmarks[6] = (0.45, 0.45, 0.0)
        landmarks[7] = (0.46, 0.50, 0.0)
        landmarks[8] = (0.47, 0.55, 0.0)  # Curled down into palm

    # Middle: 9 (MCP), 10 (PIP), 11 (DIP), 12 (TIP)
    if middle_ext:
        landmarks[10] = (0.50, 0.38, 0.0)
        landmarks[11] = (0.50, 0.28, 0.0)
        landmarks[12] = (0.50, 0.18, 0.0)
    else:
        landmarks[10] = (0.50, 0.44, 0.0)
        landmarks[11] = (0.50, 0.49, 0.0)
        landmarks[12] = (0.50, 0.54, 0.0)

    # Ring: 13 (MCP), 14 (PIP), 15 (DIP), 16 (TIP)
    landmarks[13] = (0.55, 0.52, 0.0)
    if ring_ext:
        landmarks[14] = (0.55, 0.40, 0.0)
        landmarks[15] = (0.55, 0.30, 0.0)
        landmarks[16] = (0.55, 0.20, 0.0)
    else:
        landmarks[14] = (0.55, 0.45, 0.0)
        landmarks[15] = (0.55, 0.50, 0.0)
        landmarks[16] = (0.55, 0.55, 0.0)

    # Pinky: 17 (MCP), 18 (PIP), 19 (DIP), 20 (TIP)
    landmarks[17] = (0.60, 0.55, 0.0)
    if pinky_ext:
        landmarks[18] = (0.60, 0.44, 0.0)
        landmarks[19] = (0.60, 0.35, 0.0)
        landmarks[20] = (0.60, 0.25, 0.0)
    else:
        landmarks[18] = (0.60, 0.48, 0.0)
        landmarks[19] = (0.60, 0.53, 0.0)
        landmarks[20] = (0.60, 0.58, 0.0)

    return landmarks


class TestGestureRecognizer(unittest.TestCase):
    def setUp(self):
        self.recognizer = GestureRecognizer(enter_draw_frames=2, exit_draw_frames=1)

    def test_draw_gesture_raw(self):
        # Index extended, others folded
        lm = create_synthetic_hand(index_ext=True, middle_ext=False, ring_ext=False, pinky_ext=False, thumb_ext=False)
        gesture = self.recognizer.classify_raw(lm)
        self.assertEqual(gesture, GestureType.DRAW)

    def test_move_cursor_gesture_raw(self):
        # All fingers extended (open palm)
        lm = create_synthetic_hand(index_ext=True, middle_ext=True, ring_ext=True, pinky_ext=True, thumb_ext=True)
        gesture = self.recognizer.classify_raw(lm)
        self.assertEqual(gesture, GestureType.MOVE_CURSOR)

    def test_stop_gesture_raw(self):
        # All fingers folded (fist)
        lm = create_synthetic_hand(index_ext=False, middle_ext=False, ring_ext=False, pinky_ext=False, thumb_ext=False)
        gesture = self.recognizer.classify_raw(lm)
        self.assertEqual(gesture, GestureType.STOP)

    def test_idle_or_uncertain_gesture_raw(self):
        # Index + Middle extended (peace / V sign) -> must be IDLE, never DRAW
        lm = create_synthetic_hand(index_ext=True, middle_ext=True, ring_ext=False, pinky_ext=False, thumb_ext=False)
        gesture = self.recognizer.classify_raw(lm)
        self.assertEqual(gesture, GestureType.IDLE)

    def test_empty_landmarks_return_idle(self):
        self.assertEqual(self.recognizer.classify_raw(None), GestureType.IDLE)
        self.assertEqual(self.recognizer.classify_raw([]), GestureType.IDLE)

    def test_hysteresis_enter_draw(self):
        # Requires 2 consecutive frames of DRAW to enter DRAW
        lm_draw = create_synthetic_hand(index_ext=True, middle_ext=False, ring_ext=False, pinky_ext=False)
        
        # Frame 1: candidate enters, but not yet active
        gesture, is_drawing = self.recognizer.update(lm_draw)
        self.assertFalse(is_drawing)

        # Frame 2: confirmed
        gesture, is_drawing = self.recognizer.update(lm_draw)
        self.assertEqual(gesture, GestureType.DRAW)
        self.assertTrue(is_drawing)

    def test_instant_exit_from_draw(self):
        lm_draw = create_synthetic_hand(index_ext=True, middle_ext=False, ring_ext=False, pinky_ext=False)
        lm_palm = create_synthetic_hand(index_ext=True, middle_ext=True, ring_ext=True, pinky_ext=True, thumb_ext=True)

        # Establish DRAW
        self.recognizer.update(lm_draw)
        self.recognizer.update(lm_draw)
        self.assertEqual(self.recognizer.current_gesture, GestureType.DRAW)

        # Transition to palm: must immediately cut off drawing in 1 frame
        gesture, is_drawing = self.recognizer.update(lm_palm)
        self.assertFalse(is_drawing, "Drawing must cut off immediately without trailing ink!")


if __name__ == "__main__":
    unittest.main()
