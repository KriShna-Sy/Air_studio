"""
MainWindow coordinator for AirDraw Studio.
Integrates full-screen canvas with live CPU blurred background,
a floating translucent glass toolbar, top-level cursor overlay with
magnetic proximity snapping, dwell progress ring, instant pinch click,
"BOOM" click shockwave ripples, and non-modal toast notifications.
"""

import os
import math
import time
from typing import Optional
from PyQt5.QtCore import Qt, QSize, QPoint
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QMessageBox,
    QFileDialog,
    QShortcut,
    QApplication,
    QPushButton,
)
from PyQt5.QtGui import QKeySequence

from config import (
    APP_NAME,
    APP_SUBTITLE,
    DEFAULT_PEN_COLOR,
    DEFAULT_PEN_THICKNESS,
    DEFAULT_ERASER_RADIUS,
    DEFAULT_CAMERA_INDEX,
    DWELL_CLICK_TIME,
    PINCH_CLICK_THRESHOLD,
    MAGNETIC_SNAP_RADIUS,
    HOVER_CLICK_HYSTERESIS,
)
from drawing.document import Document
from drawing.canvas import CanvasWidget
from drawing.stroke import ToolType
from vision.camera_thread import CameraThread
from .floating_toolbar import FloatingGlassToolbar
from .cursor_overlay import CursorOverlay
from .camera_panel import CameraPanel
from .overlay_window import DesktopOverlayWindow


class MainWindow(QMainWindow):
    def __init__(self, camera_index: int = DEFAULT_CAMERA_INDEX, model_path: Optional[str] = None):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — {APP_SUBTITLE}")
        self.resize(1280, 800)

        # 1. Core Data Model (Single Source of Truth)
        self.document = Document()

        # Active tool state
        self.active_tool: ToolType = ToolType.PEN
        self.active_color: str = DEFAULT_PEN_COLOR
        self.active_thickness: float = DEFAULT_PEN_THICKNESS
        self.active_eraser_radius: float = DEFAULT_ERASER_RADIUS

        # Air gesture stroke state
        self._is_air_drawing_active: bool = False
        self._last_gesture: str = "IDLE"

        # Touchless Hand Interaction State (Magnetism, Dwell & Pinch "BOOM")
        self._dwell_target: Optional[QPushButton] = None
        self._dwell_start_time: float = 0.0
        self._dwell_triggered: bool = False
        self._pinch_triggered: bool = False
        self._last_click_time: float = 0.0

        # 2. UI Components
        # A. Full-screen canvas filling 100% of window
        self.canvas = CanvasWidget(self.document, self)

        # B. Floating translucent glass toolbar
        self.floating_toolbar = FloatingGlassToolbar(self)
        self.ribbon = self.floating_toolbar  # Backwards-compatibility alias

        # C. Camera preview panel (dockable/toggleable)
        self.camera_panel = CameraPanel(self)
        self.camera_panel.hide()  # Background is already live across canvas!

        # D. Desktop Overlay Mode (Mode B)
        self.overlay_window = DesktopOverlayWindow(self.document)

        # E. Top-level cursor overlay: ALWAYS on top of all widgets
        self.cursor_overlay = CursorOverlay(self)

        # 3. Dedicated Camera & Vision Thread
        self.camera_thread = CameraThread(
            camera_index=camera_index,
            model_path=model_path,
            parent=self,
        )

        self._connect_signals()
        self._init_shortcuts()

        # Position elements on screen
        self._layout_components()

        # Start vision capture thread
        self.camera_thread.start()

    def _layout_components(self) -> None:
        """Positions canvas, floating toolbar, and cursor overlay across window."""
        win_w = self.width()
        win_h = self.height()

        # Canvas occupies full window
        self.canvas.setGeometry(0, 0, win_w, win_h)

        # Floating glass toolbar centered at the top
        tb_hint = self.floating_toolbar.sizeHint()
        tb_w = min(win_w - 40, tb_hint.width())
        tb_h = max(46, tb_hint.height())
        tb_x = (win_w - tb_w) // 2
        tb_y = 14
        self.floating_toolbar.setGeometry(tb_x, tb_y, tb_w, tb_h)
        self.floating_toolbar.raise_()

        # Cursor overlay covers full window on top of EVERYTHING
        self.cursor_overlay.setGeometry(0, 0, win_w, win_h)
        self.cursor_overlay.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_components()

    def _connect_signals(self) -> None:
        # Floating Toolbar events
        self.floating_toolbar.tool_changed.connect(self._on_tool_changed)
        self.floating_toolbar.color_changed.connect(self._on_color_changed)
        self.floating_toolbar.thickness_changed.connect(self._on_thickness_changed)
        self.floating_toolbar.undo_requested.connect(self._on_undo)
        self.floating_toolbar.redo_requested.connect(self._on_redo)
        self.floating_toolbar.clear_requested.connect(self._confirm_clear_canvas)
        self.floating_toolbar.save_png_requested.connect(self._quick_save_png)
        self.floating_toolbar.toggle_overlay_mode.connect(self.switch_to_overlay_mode)
        self.floating_toolbar.toggle_fullscreen_requested.connect(self._toggle_fullscreen)
        self.floating_toolbar.close_app_requested.connect(self.close)

        # Camera Panel events
        self.camera_panel.camera_selected.connect(self.camera_thread.set_camera_index)
        self.camera_panel.refresh_requested.connect(self.camera_thread.refresh_devices_async)
        self.camera_panel.toggle_camera.connect(self.camera_thread.set_camera_enabled)

        # Camera Thread signals
        self.camera_thread.frame_ready.connect(self.camera_panel.set_frame)
        self.camera_thread.background_ready.connect(self.canvas.set_background_image)
        self.camera_thread.tracking_updated.connect(self._on_tracking_updated)
        self.camera_thread.fps_updated.connect(self._on_fps_updated)
        self.camera_thread.status_updated.connect(self.camera_panel.set_status_message)
        self.camera_thread.devices_discovered.connect(self._on_devices_discovered)

        # Overlay events
        self.overlay_window.return_to_workspace.connect(self.switch_to_workspace_mode)

    def _init_shortcuts(self) -> None:
        QShortcut(QKeySequence(Qt.Key_F9), self, self.toggle_overlay_mode)
        QShortcut(QKeySequence(Qt.Key_F11), self, self._toggle_fullscreen)
        QShortcut(QKeySequence("Ctrl+Z"), self, self._on_undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, self._on_redo)
        QShortcut(QKeySequence("Ctrl+N"), self, self._new_document)
        QShortcut(QKeySequence("Ctrl+S"), self, self._quick_save_png)
        QShortcut(QKeySequence("Ctrl+E"), self, self._quick_save_png)

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
            self.cursor_overlay.show_toast("Windowed Mode", color_hex="#38BDF8")
        else:
            self.showFullScreen()
            self.cursor_overlay.show_toast("⛶ Fullscreen Active", color_hex="#38BDF8")

    # Tool & Parameter Synchronization
    def _on_tool_changed(self, tool: ToolType) -> None:
        self.active_tool = tool
        self.canvas.set_tool(tool)
        self.overlay_window.set_tool_params(
            self.active_tool, self.active_color, self.active_thickness, self.active_eraser_radius
        )
        tool_name = "Pen" if tool == ToolType.PEN else "Eraser"
        self.cursor_overlay.show_toast(f"✓ Tool: {tool_name}", color_hex="#38BDF8")

    def _on_color_changed(self, hex_color: str) -> None:
        self.active_color = hex_color
        self.canvas.set_color(hex_color)
        self.overlay_window.set_tool_params(
            self.active_tool, self.active_color, self.active_thickness, self.active_eraser_radius
        )
        self.cursor_overlay.show_toast("✓ Color Selected", color_hex=hex_color)

    def _on_thickness_changed(self, thickness: float) -> None:
        self.active_thickness = thickness
        self.canvas.set_thickness(thickness)
        self.overlay_window.set_tool_params(
            self.active_tool, self.active_color, self.active_thickness, self.active_eraser_radius
        )
        self.cursor_overlay.show_toast(f"✓ Brush: {int(thickness)}px", color_hex="#38BDF8")

    def _on_undo(self) -> None:
        self.document.undo()
        self.cursor_overlay.show_toast("↩️ Undo", color_hex="#A855F7")

    def _on_redo(self) -> None:
        self.document.redo()
        self.cursor_overlay.show_toast("↪️ Redo", color_hex="#A855F7")

    # Vision Tracking & Touchless Magnetic "BOOM" Interaction
    def _on_tracking_updated(
        self,
        gesture: str,
        nx: float,
        ny: float,
        is_drawing: bool,
        hand_detected: bool,
        is_pinched: bool = False,
    ) -> None:
        win_w = max(1, self.width())
        win_h = max(1, self.height())
        px = int(nx * win_w)
        py = int(ny * win_h)

        # 1. Update Top-level Cursor Overlay (Always visible on top of all widgets)
        self.cursor_overlay.set_cursor_state(
            px=px,
            py=py,
            gesture=gesture if hand_detected else "IDLE",
            visible=hand_detected,
            active_color=self.active_color,
            is_pinched=is_pinched,
        )

        # 2. Update Gesture Badges
        self.floating_toolbar.set_gesture_status(gesture if hand_detected else "IDLE")

        # Forward tracking to overlay window if open
        if self.overlay_window.isVisible():
            self.overlay_window.update_air_cursor(nx, ny, gesture, is_drawing, hand_detected)

        # If tracking lost: cleanly reset states
        if not hand_detected:
            self.floating_toolbar.set_focused_button(None)
            self._dwell_target = None
            self.cursor_overlay.set_dwell_state(False, 0.0)
            if self._is_air_drawing_active:
                self._is_air_drawing_active = False
                if self.active_tool == ToolType.PEN:
                    self.document.finish_stroke()
            self._last_gesture = "IDLE"
            return

        now = time.time()

        # 3. Magnetic Proximity Snapping for Touchless Navigation
        closest_btn: Optional[QPushButton] = None
        min_dist = float("inf")
        closest_btn_center = QPoint(0, 0)

        for btn in self.floating_toolbar.get_all_clickable_buttons():
            if btn.isVisible():
                btn_center = btn.rect().center()
                btn_win_pos = self.mapFromGlobal(btn.mapToGlobal(btn_center))
                dist = math.hypot(px - btn_win_pos.x(), py - btn_win_pos.y())
                if dist < min_dist:
                    min_dist = dist
                    closest_btn = btn
                    closest_btn_center = btn_win_pos

        is_near_button = (closest_btn is not None and min_dist <= MAGNETIC_SNAP_RADIUS)
        is_over_toolbar_rect = self.floating_toolbar.geometry().contains(px, py)

        if is_near_button:
            # --- Magnetic Focus Locked on Button ---
            self.floating_toolbar.set_focused_button(closest_btn)

            # Inhibit ink drawing when interacting with toolbar
            if self._is_air_drawing_active:
                self._is_air_drawing_active = False
                if self.active_tool == ToolType.PEN:
                    self.document.finish_stroke()

            # Cooldown check
            in_cooldown = (now - self._last_click_time) < HOVER_CLICK_HYSTERESIS

            # A. Instant Pinch-to-Click ("BOOM!")
            if is_pinched and not self._pinch_triggered and not in_cooldown:
                self._pinch_triggered = True
                self._last_click_time = now
                self._trigger_boom_click(closest_btn, closest_btn_center)
                self._dwell_target = None
                self.cursor_overlay.set_dwell_state(False, 0.0)

            elif not is_pinched:
                self._pinch_triggered = False

                # B. Dwell-to-Click ("BOOM!")
                if closest_btn == self._dwell_target:
                    elapsed = now - self._dwell_start_time
                    progress = min(1.0, elapsed / DWELL_CLICK_TIME)
                    self.cursor_overlay.set_dwell_state(True, progress)

                    if progress >= 1.0 and not self._dwell_triggered and not in_cooldown:
                        self._dwell_triggered = True
                        self._last_click_time = now
                        self._trigger_boom_click(closest_btn, closest_btn_center)
                        self.cursor_overlay.set_dwell_state(False, 0.0)
                else:
                    self._dwell_target = closest_btn
                    self._dwell_start_time = now
                    self._dwell_triggered = False
                    self.cursor_overlay.set_dwell_state(True, 0.0)

        else:
            # --- Outside Magnetic Button Snapping ---
            self.floating_toolbar.set_focused_button(None)
            self._dwell_target = None
            self._dwell_triggered = False
            self._pinch_triggered = False
            self.cursor_overlay.set_dwell_state(False, 0.0)

            if is_over_toolbar_rect:
                # Inside toolbar container margin: inhibit drawing
                if self._is_air_drawing_active:
                    self._is_air_drawing_active = False
                    if self.active_tool == ToolType.PEN:
                        self.document.finish_stroke()
            else:
                # --- Free Drawing Canvas Area ---
                if is_drawing:
                    if not self._is_air_drawing_active:
                        self._is_air_drawing_active = True
                        if self.active_tool == ToolType.PEN:
                            self.document.start_stroke(
                                tool=ToolType.PEN,
                                color=self.active_color,
                                thickness=self.active_thickness,
                                x=nx,
                                y=ny,
                            )
                        elif self.active_tool == ToolType.ERASER:
                            norm_r = self.active_eraser_radius / 1920.0
                            self.document.erase_at(nx, ny, norm_r)
                    else:
                        if self.active_tool == ToolType.PEN:
                            self.document.add_point_to_active(nx, ny)
                        elif self.active_tool == ToolType.ERASER:
                            norm_r = self.active_eraser_radius / 1920.0
                            self.document.erase_at(nx, ny, norm_r)
                else:
                    if self._is_air_drawing_active:
                        self._is_air_drawing_active = False
                        if self.active_tool == ToolType.PEN:
                            self.document.finish_stroke()

        self._last_gesture = gesture

    def _trigger_boom_click(self, button: QPushButton, center_pos: QPoint) -> None:
        """Executes touchless selection with audio chime, visual shockwave, and action."""
        # 1. Audio Confirmation
        try:
            QApplication.beep()
        except Exception:
            pass

        # 2. Visual "BOOM" Ripple Shockwave
        self.cursor_overlay.trigger_boom_ripple(center_pos, color_hex="#00F0FF")

        # 3. Execute action
        button.click()

    def _on_fps_updated(self, fps: float) -> None:
        self.camera_panel.set_tracking_telemetry(self._last_gesture, fps)

    def _on_devices_discovered(self, devices: list) -> None:
        self.camera_panel.set_available_devices(devices, self.camera_thread.camera_index)

    # Modes switching: Mode A (Workspace) <-> Mode B (Desktop Overlay)
    def toggle_overlay_mode(self) -> None:
        if self.overlay_window.isVisible():
            self.switch_to_workspace_mode()
        else:
            self.switch_to_overlay_mode()

    def switch_to_overlay_mode(self) -> None:
        """Enters Mode B: Fullscreen transparent desktop overlay."""
        self.overlay_window.set_tool_params(
            self.active_tool, self.active_color, self.active_thickness, self.active_eraser_radius
        )
        self.hide()
        self.overlay_window.showFullScreen()
        self.overlay_window.raise_()
        self.overlay_window.activateWindow()

    def switch_to_workspace_mode(self) -> None:
        """Returns to Mode A: Ribbon/Glass drawing workspace."""
        self.overlay_window.hide()
        self.show()
        self.raise_()
        self.activateWindow()
        self.canvas.update()

    # Touchless Document Operations (100% Zero-Mouse Dialogs)
    def _confirm_clear_canvas(self) -> None:
        self.document.clear()
        self.cursor_overlay.show_toast("✓ Canvas Cleared", color_hex="#F59E0B")

    def _new_document(self) -> None:
        self.document.clear()
        self.cursor_overlay.show_toast("✓ New Document Ready", color_hex="#38BDF8")

    def _quick_save_png(self) -> None:
        """Instant touchless PNG export with zero modal file pickers."""
        pictures_dir = os.path.expanduser("~/Pictures")
        os.makedirs(pictures_dir, exist_ok=True)
        filename = f"AirDraw_{time.strftime('%Y%m%d_%H%M%S')}.png"
        path = os.path.join(pictures_dir, filename)

        success = self.document.export_to_png(path, width=1920, height=1080)
        if success:
            self.cursor_overlay.show_toast(f"✓ Saved: {filename}", color_hex="#10B981")
        else:
            self.cursor_overlay.show_toast("⚠️ Export Failed", color_hex="#EF4444")

    def _export_png(self) -> None:
        self._quick_save_png()

    def closeEvent(self, event) -> None:
        """Ensures safe termination of threads and camera hardware release."""
        self.camera_thread.stop()
        if self.overlay_window is not None:
            self.overlay_window.close()
        event.accept()
