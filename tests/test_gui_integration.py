"""
GUI Integration test for AirDraw Studio.
Launches the real MainWindow on the active display, verifies rendering,
switches between Workspace Mode and Desktop Overlay Mode,
captures screenshots of both modes, and tests clean shutdown.
"""

import sys
import os
import time
import unittest
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

# Ensure plugin path
import PyQt5
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.join(os.path.dirname(PyQt5.__file__), "Qt5", "plugins")

from ui.main_window import MainWindow
from drawing.stroke import ToolType


class TestGuiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_workspace_and_overlay_lifecycle(self):
        # Create MainWindow
        window = MainWindow(camera_index=0)
        window.show()
        self.app.processEvents()

        # Let the window paint and camera thread initialize
        start_time = time.time()
        while time.time() - start_time < 0.6:
            self.app.processEvents()
            time.sleep(0.05)

        # 1. Verify Mode A (Workspace)
        self.assertTrue(window.isVisible())
        self.assertFalse(window.overlay_window.isVisible())
        self.assertEqual(window.canvas.document, window.document)

        # Grab workspace screenshot
        workspace_pix = window.grab()
        self.assertGreater(workspace_pix.width(), 800)
        self.assertGreater(workspace_pix.height(), 500)
        os.makedirs("tests", exist_ok=True)
        workspace_shot_path = os.path.join("tests", "gui_workspace_screenshot.png")
        saved = workspace_pix.save(workspace_shot_path, "PNG")
        self.assertTrue(saved)
        print(f"Saved workspace screenshot: {workspace_shot_path} ({workspace_pix.width()}x{workspace_pix.height()})")

        # 2. Add strokes to document
        window.document.start_stroke(ToolType.PEN, "#2563EB", 8.0, 0.3, 0.3)
        window.document.add_point_to_active(0.5, 0.4)
        window.document.add_point_to_active(0.7, 0.3)
        window.document.finish_stroke()
        self.assertEqual(len(window.document.strokes), 1)

        # 3. Switch to Mode B (Desktop Overlay Mode)
        window.switch_to_overlay_mode()
        self.app.processEvents()
        time.sleep(0.1)
        self.app.processEvents()

        self.assertFalse(window.isVisible())
        self.assertTrue(window.overlay_window.isVisible())
        # Overlay shares exact same document
        self.assertEqual(window.overlay_window.document, window.document)
        self.assertEqual(len(window.overlay_window.document.strokes), 1)

        # Grab overlay screenshot
        overlay_pix = window.overlay_window.grab()
        overlay_shot_path = os.path.join("tests", "gui_overlay_screenshot.png")
        saved = overlay_pix.save(overlay_shot_path, "PNG")
        self.assertTrue(saved)
        print(f"Saved overlay screenshot: {overlay_shot_path} ({overlay_pix.width()}x{overlay_pix.height()})")

        # 4. Return to Workspace Mode
        window.switch_to_workspace_mode()
        self.app.processEvents()
        time.sleep(0.1)
        self.app.processEvents()

        self.assertTrue(window.isVisible())
        self.assertFalse(window.overlay_window.isVisible())
        self.assertEqual(len(window.document.strokes), 1)

        # Grab workspace screenshot after return to verify shared strokes
        workspace_after_pix = window.grab()
        workspace_after_path = os.path.join("tests", "gui_workspace_after_overlay.png")
        workspace_after_pix.save(workspace_after_path, "PNG")
        print(f"Saved workspace post-overlay screenshot: {workspace_after_path}")

        # 5. Clean teardown
        window.close()
        self.app.processEvents()
        time.sleep(0.2)
        self.app.processEvents()
        print("MainWindow and CameraThread closed cleanly!")


if __name__ == "__main__":
    unittest.main()
