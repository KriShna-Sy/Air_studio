"""
UI package for AirDraw Studio.
Contains the Word-style ribbon interface, document canvas,
camera preview panel, desktop overlay, and main window coordinator.
"""

from .camera_panel import CameraPanel
from .ribbon import RibbonBar
from .overlay_window import DesktopOverlayWindow
from .main_window import MainWindow

__all__ = ["CameraPanel", "RibbonBar", "DesktopOverlayWindow", "MainWindow"]
