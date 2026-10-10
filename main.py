#!/usr/bin/env python3
"""
AirDraw Studio — Gesture-Controlled Drawing Workspace and Desktop Overlay.
Application entry point.
"""

import sys
import os
import signal
import argparse

# Ensure PyQt5 plugin path is prioritized over OpenCV bundled plugins
import PyQt5
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.join(os.path.dirname(PyQt5.__file__), "Qt5", "plugins")

# Ensure local package imports work cleanly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont

from config import APP_NAME, APP_VERSION, DEFAULT_MODEL_PATH, DEFAULT_CAMERA_INDEX
from ui.main_window import MainWindow


def parse_args():
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} v{APP_VERSION} — Gesture-Controlled Drawing Workspace & Desktop Overlay"
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=DEFAULT_CAMERA_INDEX,
        help=f"Initial camera index (default: {DEFAULT_CAMERA_INDEX})",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL_PATH,
        help=f"Path to MediaPipe hand_landmarker.task model (default: {DEFAULT_MODEL_PATH})",
    )
    parser.add_argument(
        "--overlay",
        action="store_true",
        help="Start directly in Desktop Drawing Overlay mode",
    )
    parser.add_argument(
        "--test-headless",
        action="store_true",
        help="Run self-diagnostic initialization test and exit",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Handle Ctrl+C cleanly in terminal
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Configure High-DPI attributes before creating QApplication
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.join(os.path.dirname(PyQt5.__file__), "Qt5", "plugins")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setFont(QFont("Segoe UI", 9))

    # Self-diagnostic test mode for headless verification
    if args.test_headless:
        print(f"[AirDraw Studio] Running self-diagnostic verification...")
        from drawing.document import Document
        from vision.gesture_recognizer import GestureRecognizer
        from vision.filter import OneEuroFilter
        doc = Document()
        doc.start_stroke("pen", "#2563EB", 6.0, 0.5, 0.5)
        doc.add_point_to_active(0.6, 0.6)
        doc.finish_stroke()
        assert len(doc.strokes) == 1, "Stroke test failed"
        print("[AirDraw Studio] Self-diagnostic test passed successfully!")
        return 0

    window = MainWindow(camera_index=args.camera, model_path=args.model)

    if args.overlay:
        window.switch_to_overlay_mode()
    else:
        window.show()

    # Allow Python to process Unix signals periodically
    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(500)

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
