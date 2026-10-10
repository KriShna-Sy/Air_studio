"""
DesktopOverlayWindow for AirDraw Studio (Mode B).
A full-screen, genuinely transparent drawing overlay that allows the user
to draw directly over their desktop applications using hand gestures.
Shares the single Document model with the Drawing Workspace.
"""

from typing import Optional
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal, QSize
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QApplication,
)
from PyQt5.QtGui import (
    QPainter,
    QColor,
    QPen,
    QBrush,
    QFont,
    QImage,
    QKeyEvent,
    QPaintEvent,
)

import math
import time

from config import (
    GESTURE_COLORS,
    GESTURE_LABELS,
    DEFAULT_PEN_COLOR,
    DEFAULT_PEN_THICKNESS,
    DEFAULT_ERASER_RADIUS,
    DWELL_CLICK_TIME,
    MAGNETIC_SNAP_RADIUS,
    HOVER_CLICK_HYSTERESIS,
)
from drawing.document import Document
from drawing.stroke import ToolType


class OverlayMiniHUD(QFrame):
    """Floating, unobtrusive HUD with glassmorphic styling."""
    exit_requested = pyqtSignal()
    undo_requested = pyqtSignal()
    clear_requested = pyqtSignal()
    toggle_clickthrough = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("overlayHUD")
        self._clickthrough_active = False
        self.setStyleSheet("""
            QFrame#overlayHUD {
                background-color: rgba(15, 23, 42, 0.88);
                border: 1px solid rgba(255, 255, 255, 0.22);
                border-radius: 12px;
                padding: 4px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(10)

        # Title & Hotkey Reminder
        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(0)
        hud_title = QLabel("AIRDRAW OVERLAY")
        hud_title.setFont(QFont("Segoe UI", 7, QFont.Bold))
        hud_title.setStyleSheet("color: rgba(255, 255, 255, 0.6); letter-spacing: 0.5px;")
        title_vbox.addWidget(hud_title)

        self.hotkey_hint = QLabel("[Esc] Exit  [F9] Workspace  [T] Click-Thru")
        self.hotkey_hint.setFont(QFont("Segoe UI", 8))
        self.hotkey_hint.setStyleSheet("color: #94A3B8;")
        title_vbox.addWidget(self.hotkey_hint)
        layout.addLayout(title_vbox)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: rgba(255, 255, 255, 0.2);")
        layout.addWidget(sep)

        # Gesture Pill
        self.gesture_pill = QLabel("IDLE")
        self.gesture_pill.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.gesture_pill.setStyleSheet("""
            background-color: #334155;
            color: #FFFFFF;
            border-radius: 6px;
            padding: 4px 10px;
        """)
        layout.addWidget(self.gesture_pill)

        # Tool Pill
        self.tool_pill = QLabel("Pen: 6px")
        self.tool_pill.setFont(QFont("Segoe UI", 9))
        self.tool_pill.setStyleSheet("color: #E2E8F0;")
        layout.addWidget(self.tool_pill)

        # Quick action buttons
        self.undo_btn = QPushButton("Undo")
        self._style_button(self.undo_btn)
        self.undo_btn.clicked.connect(lambda: self.undo_requested.emit())
        layout.addWidget(self.undo_btn)

        self.clear_btn = QPushButton("Clear")
        self._style_button(self.clear_btn)
        self.clear_btn.clicked.connect(lambda: self.clear_requested.emit())
        layout.addWidget(self.clear_btn)

        # Click-Through toggle
        self.clickthrough_btn = QPushButton("Pass Clicks: OFF [T]")
        self.clickthrough_btn.setToolTip("Toggle click-through to apps underneath (Press T)")
        self._style_button(self.clickthrough_btn)
        self.clickthrough_btn.clicked.connect(self._on_clickthrough_clicked)
        layout.addWidget(self.clickthrough_btn)

        # Workspace toggle button
        self.workspace_btn = QPushButton("🖥️ Workspace [F9]")
        self.workspace_btn.setToolTip("Return to Drawing Workspace (Press F9)")
        self._style_button(self.workspace_btn)
        self.workspace_btn.clicked.connect(lambda: self.exit_requested.emit())
        layout.addWidget(self.workspace_btn)

        self.exit_btn = QPushButton("✕ Exit Overlay")
        self.exit_btn.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.exit_btn.setStyleSheet("""
            QPushButton {
                background-color: #DC2626;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background-color: #EF4444;
            }
        """)
        self.exit_btn.clicked.connect(lambda: self.exit_requested.emit())
        layout.addWidget(self.exit_btn)

    def get_all_clickable_buttons(self) -> list:
        return [
            self.undo_btn,
            self.clear_btn,
            self.clickthrough_btn,
            self.workspace_btn,
            self.exit_btn,
        ]

    def _on_clickthrough_clicked(self) -> None:
        self._clickthrough_active = not self._clickthrough_active
        self.set_clickthrough_state(self._clickthrough_active)
        self.toggle_clickthrough.emit(self._clickthrough_active)

    def set_clickthrough_state(self, active: bool) -> None:
        self._clickthrough_active = active
        if active:
            self.clickthrough_btn.setText("Pass Clicks: ON [T]")
            self.clickthrough_btn.setStyleSheet("""
                QPushButton {
                    background-color: #16A34A;
                    color: #FFFFFF;
                    border: 1px solid #22C55E;
                    border-radius: 6px;
                    padding: 4px 10px;
                    font-weight: bold;
                }
            """)
        else:
            self.clickthrough_btn.setText("Pass Clicks: OFF [T]")
            self._style_button(self.clickthrough_btn)

    def _style_button(self, btn: QPushButton) -> None:
        btn.setFont(QFont("Segoe UI", 9))
        btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.12);
                color: #F8FAFC;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.22);
            }
        """)

    def set_gesture(self, gesture: str) -> None:
        color = GESTURE_COLORS.get(gesture, "#64748B")
        text = gesture.replace("_", " ")
        self.gesture_pill.setText(text)
        self.gesture_pill.setStyleSheet(f"""
            background-color: {color};
            color: #FFFFFF;
            border-radius: 6px;
            padding: 4px 10px;
        """)

    def set_tool_info(self, tool_type: ToolType, color_hex: str, thickness: float) -> None:
        if tool_type == ToolType.ERASER:
            self.tool_pill.setText("Eraser")
            self.tool_pill.setStyleSheet("color: #F87171; font-weight: bold;")
        else:
            self.tool_pill.setText(f"Pen: {int(thickness)}px")
            self.tool_pill.setStyleSheet(f"color: {color_hex}; font-weight: bold;")


class DesktopOverlayWindow(QWidget):
    """Full-screen, genuinely transparent window for drawing directly over the Linux desktop."""
    return_to_workspace = pyqtSignal()

    def __init__(self, document: Document, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.document = document
        self.document.add_listener(self.update)

        # Window flags for transparent always-on-top overlay
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.SubWindow
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.StrongFocus)

        # Cursor and tracking state
        self.cursor_nx: float = 0.5
        self.cursor_ny: float = 0.5
        self.cursor_gesture: str = "IDLE"
        self.cursor_visible: bool = False
        self.is_drawing_active: bool = False

        # Touchless Dwell & Pinch State
        self.is_dwelling: bool = False
        self.dwell_progress: float = 0.0
        self.is_pinched: bool = False
        self._dwell_target: Optional[QPushButton] = None
        self._dwell_start_time: float = 0.0
        self._dwell_triggered: bool = False
        self._pinch_triggered: bool = False
        self._last_click_time: float = 0.0

        # Active tool cache
        self.active_tool: ToolType = ToolType.PEN
        self.active_color: str = DEFAULT_PEN_COLOR
        self.active_thickness: float = DEFAULT_PEN_THICKNESS
        self.active_eraser_radius: float = DEFAULT_ERASER_RADIUS

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # Top row: floating HUD centered/right-aligned
        top_hbox = QHBoxLayout()
        top_hbox.addStretch(1)

        self.hud = OverlayMiniHUD(self)
        self.hud.exit_requested.connect(self._exit_overlay)
        self.hud.undo_requested.connect(self._on_undo)
        self.hud.clear_requested.connect(self._on_clear)
        self.hud.toggle_clickthrough.connect(self.set_clickthrough)
        top_hbox.addWidget(self.hud)

        layout.addLayout(top_hbox)
        layout.addStretch(1)

    def set_tool_params(self, tool: ToolType, color: str, thickness: float, eraser_radius: float) -> None:
        self.active_tool = tool
        self.active_color = color
        self.active_thickness = thickness
        self.active_eraser_radius = eraser_radius
        self.hud.set_tool_info(tool, color, thickness)
        self.update()

    def set_clickthrough(self, enabled: bool) -> None:
        """Toggles whether mouse clicks pass directly through to desktop windows."""
        self.setAttribute(Qt.WA_TransparentForMouseEvents, enabled)
        self.hud.set_clickthrough_state(enabled)

    def update_air_cursor(
        self,
        nx: float,
        ny: float,
        gesture: str,
        is_drawing: bool,
        visible: bool = True,
        is_pinched: bool = False,
    ) -> None:
        self.cursor_nx = max(0.0, min(1.0, nx))
        self.cursor_ny = max(0.0, min(1.0, ny))
        self.cursor_gesture = gesture
        self.is_drawing_active = is_drawing
        self.cursor_visible = visible
        self.is_pinched = is_pinched

        self.hud.set_gesture(gesture)

        if not visible:
            self._dwell_target = None
            self.is_dwelling = False
            self.dwell_progress = 0.0
            self.update()
            return

        now = time.time()
        w = float(self.width())
        h = float(self.height())
        px = self.cursor_nx * w
        py = self.cursor_ny * h

        # Magnetic snapping to HUD buttons
        closest_btn: Optional[QPushButton] = None
        min_dist = float("inf")
        for btn in self.hud.get_all_clickable_buttons():
            if btn.isVisible():
                c = self.mapFromGlobal(btn.mapToGlobal(btn.rect().center()))
                dist = math.hypot(px - c.x(), py - c.y())
                if dist < min_dist:
                    min_dist = dist
                    closest_btn = btn

        is_near_btn = (closest_btn is not None and min_dist <= MAGNETIC_SNAP_RADIUS)
        in_cooldown = (now - self._last_click_time) < HOVER_CLICK_HYSTERESIS

        if is_near_btn:
            self.is_drawing_active = False
            if is_pinched and not self._pinch_triggered and not in_cooldown:
                self._pinch_triggered = True
                self._last_click_time = now
                try:
                    QApplication.beep()
                except Exception:
                    pass
                closest_btn.click()
                self.is_dwelling = False
                self.dwell_progress = 0.0
            elif not is_pinched:
                self._pinch_triggered = False
                if closest_btn == self._dwell_target:
                    elapsed = now - self._dwell_start_time
                    progress = min(1.0, elapsed / DWELL_CLICK_TIME)
                    self.is_dwelling = True
                    self.dwell_progress = progress
                    if progress >= 1.0 and not self._dwell_triggered and not in_cooldown:
                        self._dwell_triggered = True
                        self._last_click_time = now
                        try:
                            QApplication.beep()
                        except Exception:
                            pass
                        closest_btn.click()
                        self.is_dwelling = False
                        self.dwell_progress = 0.0
                else:
                    self._dwell_target = closest_btn
                    self._dwell_start_time = now
                    self._dwell_triggered = False
                    self.is_dwelling = True
                    self.dwell_progress = 0.0
        else:
            self._dwell_target = None
            self._dwell_triggered = False
            self._pinch_triggered = False
            self.is_dwelling = False
            self.dwell_progress = 0.0

        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        # Keep background genuinely transparent (alpha = 0)
        painter.fillRect(self.rect(), Qt.transparent)

        # Render document strokes scaled to overlay screen dimensions
        w = float(self.width())
        h = float(self.height())
        self.document.render(painter, w, h, draw_active=True)

        # Draw gesture cursor indicator
        if self.cursor_visible:
            self._draw_cursor(painter, w, h)

        painter.end()

    def _draw_cursor(self, painter: QPainter, w: float, h: float) -> None:
        px = self.cursor_nx * w
        py = self.cursor_ny * h

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        gesture_color = QColor(GESTURE_COLORS.get(self.cursor_gesture, "#64748B"))

        # Dwell progress arc
        if self.is_dwelling and self.dwell_progress > 0.0:
            ring_rect = QRectF(px - 22, py - 22, 44, 44)
            painter.setPen(QPen(QColor(255, 255, 255, 140), 4))
            painter.setBrush(QColor(15, 23, 42, 100))
            painter.drawEllipse(ring_rect)

            progress_pen = QPen(QColor("#00F0FF"), 4.5)
            progress_pen.setCapStyle(Qt.RoundCap)
            painter.setPen(progress_pen)
            painter.setBrush(Qt.NoBrush)
            span_angle = int(-360 * 16 * self.dwell_progress)
            painter.drawArc(ring_rect, 90 * 16, span_angle)

            painter.setPen(QPen(Qt.white, 2))
            painter.setBrush(QColor("#00F0FF"))
            painter.drawEllipse(QPointF(px, py), 5, 5)
            painter.restore()
            return

        if self.is_pinched:
            painter.setPen(QPen(QColor("#16A34A"), 3.5))
            painter.setBrush(QColor(22, 163, 74, 120))
            painter.drawEllipse(QPointF(px, py), 12, 12)
            painter.setPen(QPen(Qt.white, 2))
            painter.setBrush(QColor("#16A34A"))
            painter.drawEllipse(QPointF(px, py), 4, 4)
            painter.restore()
            return

        if self.active_tool == ToolType.ERASER:
            norm_r = self.active_eraser_radius / 1920.0
            r_px = max(10.0, norm_r * w)
            pen = QPen(QColor("#DC2626"), 2, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(QColor(220, 38, 38, 35))
            painter.drawEllipse(QPointF(px, py), r_px, r_px)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#DC2626"))
            painter.drawEllipse(QPointF(px, py), 3, 3)

        elif self.cursor_gesture == "DRAW":
            outer_pen = QPen(gesture_color, 2.5)
            painter.setPen(outer_pen)
            painter.setBrush(QColor(gesture_color.red(), gesture_color.green(), gesture_color.blue(), 50))
            painter.drawEllipse(QPointF(px, py), 14, 14)

            painter.setPen(QPen(Qt.white, 2))
            painter.setBrush(QColor(self.active_color))
            painter.drawEllipse(QPointF(px, py), 6, 6)

        elif self.cursor_gesture == "MOVE_CURSOR":
            pen = QPen(gesture_color, 2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(px, py), 10, 10)
            painter.drawLine(int(px - 16), int(py), int(px - 11), int(py))
            painter.drawLine(int(px + 11), int(py), int(px + 16), int(py))
            painter.drawLine(int(px), int(py - 16), int(px), int(py - 11))
            painter.drawLine(int(px), int(py + 11), int(px), int(py + 16))

        elif self.cursor_gesture == "STOP":
            painter.setPen(QPen(Qt.white, 2))
            painter.setBrush(gesture_color)
            painter.drawEllipse(QPointF(px, py), 8, 8)

        painter.restore()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key in (Qt.Key_Escape, Qt.Key_F9):
            self._exit_overlay()
        elif key == Qt.Key_Z and (event.modifiers() & Qt.ControlModifier):
            self._on_undo()
        elif key == Qt.Key_C:
            self._on_clear()
        elif key == Qt.Key_E:
            # Toggle tool
            new_tool = ToolType.ERASER if self.active_tool == ToolType.PEN else ToolType.PEN
            self.set_tool_params(new_tool, self.active_color, self.active_thickness, self.active_eraser_radius)
        elif key == Qt.Key_T:
            # Toggle click-through
            is_clickthrough = self.testAttribute(Qt.WA_TransparentForMouseEvents)
            self.set_clickthrough(not is_clickthrough)
        else:
            super().keyPressEvent(event)

    def _on_undo(self) -> None:
        self.document.undo()

    def _on_clear(self) -> None:
        self.document.clear()

    def _exit_overlay(self) -> None:
        self.hide()
        self.return_to_workspace.emit()
