"""
End-to-End Simulation Test for AirDraw Studio.
Simulates a live sequence of hand gestures (MOVE_CURSOR -> DRAW -> STOP -> DRAW -> ERASER -> UNDO),
verifying that strokes are created, never cross-connected across transitions,
and that erasing and undo work accurately.
"""

import sys
import os
import unittest
from PyQt5.QtWidgets import QApplication

import PyQt5
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.join(os.path.dirname(PyQt5.__file__), "Qt5", "plugins")

_app = QApplication.instance() or QApplication(sys.argv)

from drawing.document import Document
from drawing.stroke import ToolType
from vision.gesture_recognizer import GestureRecognizer, GestureType
from tests.test_gestures import create_synthetic_hand


class TestEndToEndGestures(unittest.TestCase):
    def setUp(self):
        self.doc = Document()
        self.recognizer = GestureRecognizer(enter_draw_frames=2, exit_draw_frames=1)

    def test_end_to_end_gesture_drawing_pipeline(self):
        # Tracking state machine
        is_drawing_active = False

        def process_hand(lm, nx, ny, tool=ToolType.PEN):
            nonlocal is_drawing_active
            gesture, is_draw = self.recognizer.update(lm)

            if is_draw:
                if not is_drawing_active:
                    is_drawing_active = True
                    if tool == ToolType.PEN:
                        self.doc.start_stroke(ToolType.PEN, "#2563EB", 6.0, nx, ny)
                    elif tool == ToolType.ERASER:
                        self.doc.erase_at(nx, ny, 0.05)
                else:
                    if tool == ToolType.PEN:
                        self.doc.add_point_to_active(nx, ny)
                    elif tool == ToolType.ERASER:
                        self.doc.erase_at(nx, ny, 0.05)
            else:
                if is_drawing_active:
                    is_drawing_active = False
                    if tool == ToolType.PEN:
                        self.doc.finish_stroke()
            return gesture

        # 1. Open palm (MOVE CURSOR) at (0.2, 0.2)
        lm_palm = create_synthetic_hand(index_ext=True, middle_ext=True, ring_ext=True, pinky_ext=True, thumb_ext=True)
        g1 = process_hand(lm_palm, 0.2, 0.2)
        self.assertEqual(g1, GestureType.MOVE_CURSOR)
        self.assertEqual(len(self.doc.strokes), 0)
        self.assertIsNone(self.doc.active_stroke)

        # 2. Transition to DRAW (Index extended)
        lm_draw = create_synthetic_hand(index_ext=True, middle_ext=False, ring_ext=False, pinky_ext=False)
        # Frame 1: hysteresis check
        process_hand(lm_draw, 0.3, 0.3)
        # Frame 2: confirmed DRAW starts Stroke 1
        g2 = process_hand(lm_draw, 0.3, 0.3)
        self.assertEqual(g2, GestureType.DRAW)
        self.assertIsNotNone(self.doc.active_stroke)

        # Move while drawing
        process_hand(lm_draw, 0.4, 0.4)
        process_hand(lm_draw, 0.5, 0.5)

        # 3. Transition to Fist (STOP)
        lm_fist = create_synthetic_hand(index_ext=False, middle_ext=False, ring_ext=False, pinky_ext=False, thumb_ext=False)
        g3 = process_hand(lm_fist, 0.5, 0.5)
        # Must immediately finalize Stroke 1
        self.assertFalse(is_drawing_active)
        self.assertEqual(len(self.doc.strokes), 1)
        self.assertEqual(self.doc.strokes[0].point_count(), 3)

        # Move fist around -> MUST NOT DRAW
        process_hand(lm_fist, 0.8, 0.8)
        self.assertEqual(len(self.doc.strokes), 1)

        # 4. Start second stroke (Stroke 2) at (0.7, 0.7)
        process_hand(lm_draw, 0.7, 0.7)
        process_hand(lm_draw, 0.7, 0.7)
        process_hand(lm_draw, 0.9, 0.9)
        # Release drawing with palm
        process_hand(lm_palm, 0.9, 0.9)

        # Verify we now have 2 independent strokes, NOT connected!
        self.assertEqual(len(self.doc.strokes), 2)
        first_stroke_pts = [p.to_tuple() for p in self.doc.strokes[0].points]
        second_stroke_pts = [p.to_tuple() for p in self.doc.strokes[1].points]
        
        # Verify first stroke ends at (0.5, 0.5) and second stroke starts at (0.7, 0.7)
        self.assertEqual(first_stroke_pts[-1], (0.5, 0.5))
        self.assertEqual(second_stroke_pts[0], (0.7, 0.7))
        # Ensure no cross-connecting points exist between them
        self.assertNotIn((0.8, 0.8), first_stroke_pts)
        self.assertNotIn((0.5, 0.5), second_stroke_pts)

        # 5. Vector Eraser Test: Erase Stroke 1 at (0.4, 0.4)
        erased_count = self.doc.erase_at(0.4, 0.4, radius=0.08)
        self.assertEqual(erased_count, 1)
        self.assertEqual(len(self.doc.strokes), 1)  # Only Stroke 2 remains

        # 6. Undo Eraser
        self.doc.undo()
        self.assertEqual(len(self.doc.strokes), 2)  # Stroke 1 restored!


if __name__ == "__main__":
    unittest.main()
