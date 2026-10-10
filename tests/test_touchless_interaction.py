"""
Test Touchless UI Interaction (Dwell Click, Pinch Click, and Magnetic Snapping) in AirDraw Studio.
Verifies that air cursor hovering over transparent FloatingGlassToolbar buttons,
color swatches, brush thickness, and actions triggers selections with zero mouse dependency.
"""

import sys
import os
import time
import unittest
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QPoint

import PyQt5
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.join(os.path.dirname(PyQt5.__file__), "Qt5", "plugins")

from ui.main_window import MainWindow
from drawing.stroke import ToolType


class TestTouchlessInteraction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.window = MainWindow(camera_index=-1)
        # Disconnect live camera thread to isolate synthetic test events
        try:
            self.window.camera_thread.tracking_updated.disconnect(self.window._on_tracking_updated)
        except Exception:
            pass
        self.window.resize(1280, 800)
        self.window.show()
        for _ in range(5):
            self.app.processEvents()
            time.sleep(0.02)

    def tearDown(self):
        self.window.close()
        self.app.processEvents()

    def test_toolbar_hover_inhibits_ink(self):
        """Moving the index finger over the floating toolbar must not draw strokes."""
        tb_center = self.window.floating_toolbar.rect().center()
        win_pos = self.window.mapFromGlobal(self.window.floating_toolbar.mapToGlobal(tb_center))

        norm_x = win_pos.x() / max(1, self.window.width())
        norm_y = win_pos.y() / max(1, self.window.height())

        # Simulate DRAW gesture over the toolbar
        self.window._on_tracking_updated(
            gesture="DRAW",
            nx=norm_x,
            ny=norm_y,
            is_drawing=True,
            hand_detected=True,
            is_pinched=False,
        )
        self.app.processEvents()

        # Must NOT start an ink stroke because cursor is over toolbar UI
        self.assertFalse(self.window._is_air_drawing_active)
        self.assertEqual(len(self.window.document.strokes), 0)

    def test_magnetic_snap_and_dwell_click(self):
        """Resting the finger near Eraser button (even 20px off) magnetically snaps and triggers click."""
        eraser_btn = self.window.floating_toolbar.eraser_btn
        self.assertFalse(eraser_btn.isChecked())

        # Find position of eraser button + 15px offset
        btn_center = eraser_btn.rect().center()
        btn_win_pos = self.window.mapFromGlobal(eraser_btn.mapToGlobal(btn_center))
        offset_pos = btn_win_pos + QPoint(15, 10)  # slightly off center
        norm_x = offset_pos.x() / max(1, self.window.width())
        norm_y = offset_pos.y() / max(1, self.window.height())

        # 1. Start hovering near eraser button with MOVE_CURSOR gesture
        self.window._on_tracking_updated(
            gesture="MOVE_CURSOR",
            nx=norm_x,
            ny=norm_y,
            is_drawing=False,
            hand_detected=True,
            is_pinched=False,
        )
        self.app.processEvents()
        self.assertEqual(self.window._dwell_target, eraser_btn)
        self.assertFalse(self.window._dwell_triggered)

        # 2. Wait longer than DWELL_CLICK_TIME (0.50s)
        time.sleep(0.55)

        # 3. Next frame event at the same position triggers dwell click ("BOOM!")
        self.window._on_tracking_updated(
            gesture="MOVE_CURSOR",
            nx=norm_x,
            ny=norm_y,
            is_drawing=False,
            hand_detected=True,
            is_pinched=False,
        )
        self.app.processEvents()

        # Button should now be clicked and active tool changed to ERASER
        self.assertTrue(self.window._dwell_triggered)
        self.assertTrue(eraser_btn.isChecked())
        self.assertEqual(self.window.active_tool, ToolType.ERASER)

    def test_pinch_click_immediate_trigger(self):
        """Pinching over Pen button immediately triggers click without waiting for dwell."""
        pen_btn = self.window.floating_toolbar.pen_btn
        self.window.active_tool = ToolType.ERASER
        pen_btn.setChecked(False)

        btn_center = pen_btn.rect().center()
        btn_win_pos = self.window.mapFromGlobal(pen_btn.mapToGlobal(btn_center))
        norm_x = btn_win_pos.x() / max(1, self.window.width())
        norm_y = btn_win_pos.y() / max(1, self.window.height())

        # Send event with is_pinched=True
        self.window._on_tracking_updated(
            gesture="MOVE_CURSOR",
            nx=norm_x,
            ny=norm_y,
            is_drawing=False,
            hand_detected=True,
            is_pinched=True,
        )
        self.app.processEvents()

        self.assertTrue(self.window._pinch_triggered)
        self.assertTrue(pen_btn.isChecked())
        self.assertEqual(self.window.active_tool, ToolType.PEN)

    def test_touchless_color_selection(self):
        """Pinching or dwelling over a color swatch selects that color."""
        # Swatch 1 is Red (#DC2626)
        red_swatch = self.window.floating_toolbar._color_swatches[1]
        self.assertFalse(red_swatch.isChecked())

        btn_center = red_swatch.rect().center()
        btn_win_pos = self.window.mapFromGlobal(red_swatch.mapToGlobal(btn_center))
        norm_x = btn_win_pos.x() / max(1, self.window.width())
        norm_y = btn_win_pos.y() / max(1, self.window.height())

        # Pinch click over red swatch
        self.window._on_tracking_updated(
            gesture="MOVE_CURSOR",
            nx=norm_x,
            ny=norm_y,
            is_drawing=False,
            hand_detected=True,
            is_pinched=True,
        )
        self.app.processEvents()

        self.assertEqual(self.window.active_color, red_swatch.hex_color)
        self.assertTrue(red_swatch.isChecked())

    def test_touchless_clear_canvas_two_step(self):
        """Two-step touchless clear canvas does not open modal dialog and clears strokes."""
        # Add a stroke
        self.window.document.start_stroke(ToolType.PEN, "#2563EB", 6.0, 0.4, 0.4)
        self.window.document.add_point_to_active(0.5, 0.5)
        self.window.document.finish_stroke()
        self.assertEqual(len(self.window.document.strokes), 1)

        clear_btn = self.window.floating_toolbar.clear_btn
        btn_center = clear_btn.rect().center()
        btn_win_pos = self.window.mapFromGlobal(clear_btn.mapToGlobal(btn_center))
        norm_x = btn_win_pos.x() / max(1, self.window.width())
        norm_y = btn_win_pos.y() / max(1, self.window.height())

        # Step 1: Pinch click over Clear button -> enters confirm pending state
        self.window._on_tracking_updated("MOVE_CURSOR", norm_x, norm_y, False, True, is_pinched=True)
        self.app.processEvents()
        self.assertTrue(self.window.floating_toolbar._clear_confirm_pending)
        self.assertEqual(len(self.window.document.strokes), 1)  # not cleared yet

        # Reset pinch state
        self.window._on_tracking_updated("MOVE_CURSOR", norm_x, norm_y, False, True, is_pinched=False)
        self.app.processEvents()
        time.sleep(0.25)  # past cooldown

        # Step 2: Pinch click again -> executes clear
        self.window._on_tracking_updated("MOVE_CURSOR", norm_x, norm_y, False, True, is_pinched=True)
        self.app.processEvents()

        self.assertFalse(self.window.floating_toolbar._clear_confirm_pending)
        self.assertEqual(len(self.window.document.strokes), 0)  # canvas successfully cleared!


if __name__ == "__main__":
    unittest.main()
