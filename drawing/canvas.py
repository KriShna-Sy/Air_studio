"""
CanvasWidget for AirDraw Studio.
Full-screen, transparent/frosted camera background drawing workspace.
Renders the live camera in the background on CPU, displays vector strokes in real-time,
and renders the air cursor with radial dwell progress and pinch indicators.
"""

from typing import Optional
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import (
    QPainter,
    QColor,
    QPen,
    QBrush,
    QMouseEvent,
    QPaintEvent,
    QImage,
    QFont,
)

from config import (
    GESTURE_COLORS,
    DEFAULT_PEN_COLOR,
    DEFAULT_PEN_THICKNESS,
    DEFAULT_ERASER_RADIUS,
    DEFAULT_BG_OPACITY,
)
from .document import Document
from .stroke import ToolType


class CanvasWidget(QWidget):
    def __init__(self, document: Document, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.document = document
        self.document.add_listener(self.update)

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        # Active tools for manual mouse fallback
        self.active_tool: ToolType = ToolType.PEN
        self.active_color: str = DEFAULT_PEN_COLOR
        self.active_thickness: float = DEFAULT_PEN_THICKNESS
        self.active_eraser_radius: float = DEFAULT_ERASER_RADIUS

        # Background state
        self.background_image: Optional[QImage] = None
        self.bg_scrim_opacity: float = 0.30  # Soft white tint over blurred camera for high contrast

        # Air Gesture Cursor state
        self.cursor_nx: float = 0.5
        self.cursor_ny: float = 0.5
        self.cursor_gesture: str = "IDLE"
        self.cursor_visible: bool = False
        self.is_air_drawing: bool = False

        # Touchless Dwell & Pinch State
        self.dwell_progress: float = 0.0
        self.is_dwelling: bool = False
        self.is_pinched: bool = False

        # Mouse interaction state
        self._is_mouse_drawing: bool = False

    def set_tool(self, tool: ToolType) -> None:
        self.active_tool = tool
        self.update()

    def set_color(self, hex_color: str) -> None:
        self.active_color = hex_color
        self.update()

    def set_thickness(self, thickness: float) -> None:
        self.active_thickness = max(1.0, float(thickness))
        self.update()

    def set_eraser_radius(self, radius: float) -> None:
        self.active_eraser_radius = max(5.0, float(radius))
        self.update()

    def set_background_image(self, image: QImage) -> None:
        """Called by camera thread with the CPU blurred/translucent frame."""
        self.background_image = image
        self.update()

    def set_dwell_state(self, is_dwelling: bool, progress: float) -> None:
        self.is_dwelling = is_dwelling
        self.dwell_progress = max(0.0, min(1.0, progress))
        self.update()

    def update_air_cursor(
        self,
        nx: float,
        ny: float,
        gesture: str,
        is_drawing: bool,
        visible: bool = True,
        is_pinched: bool = False,
    ) -> None:
        """Called by camera tracking thread to update real-time cursor."""
        self.cursor_nx = max(0.0, min(1.0, nx))
        self.cursor_ny = max(0.0, min(1.0, ny))
        self.cursor_gesture = gesture
        self.is_air_drawing = is_drawing
        self.cursor_visible = visible
        self.is_pinched = is_pinched
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        w = float(self.width())
        h = float(self.height())

        # 1. Render Background
        if self.background_image is not None and not self.background_image.isNull():
            # Draw the camera frame covering the full screen
            painter.drawImage(self.rect(), self.background_image)
            # Draw soft translucent scrim so ink lines and ribbon pop with clarity
            scrim_alpha = int(255 * self.bg_scrim_opacity)
            painter.fillRect(self.rect(), QColor(255, 255, 255, scrim_alpha))
        else:
            # Fallback neutral workspace background
            painter.fillRect(self.rect(), QColor("#F1F5F9"))

        # 2. Render all document strokes across the screen
        self.document.render(painter, w, h, draw_active=True)

        # 3. Render fingertip air cursor
        if self.cursor_visible:
            self._draw_cursor(painter, w, h)

        painter.end()

    def _draw_cursor(self, painter: QPainter, w: float, h: float) -> None:
        px = self.cursor_nx * w
        py = self.cursor_ny * h

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        gesture_color = QColor(GESTURE_COLORS.get(self.cursor_gesture, "#64748B"))

        # 1. If Dwelling on UI element: Draw radial progress fill ring!
        if self.is_dwelling and self.dwell_progress > 0.0:
            ring_rect = QRectF(px - 22, py - 22, 44, 44)
            # Background guide ring
            painter.setPen(QPen(QColor(255, 255, 255, 120), 4))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(ring_rect)

            # Active animated progress arc (clockwise fill)
            progress_pen = QPen(QColor("#0078D4"), 4)
            progress_pen.setCapStyle(Qt.RoundCap)
            painter.setPen(progress_pen)
            span_angle = int(-360 * 16 * self.dwell_progress)
            painter.drawArc(ring_rect, 90 * 16, span_angle)

            # Center target dot
            painter.setPen(QPen(Qt.white, 2))
            painter.setBrush(QColor("#0078D4"))
            painter.drawEllipse(QPointF(px, py), 6, 6)
            painter.restore()
            return

        # 2. Pinch indication
        if self.is_pinched:
            painter.setPen(QPen(QColor("#16A34A"), 3))
            painter.setBrush(QColor(22, 163, 74, 80))
            painter.drawEllipse(QPointF(px, py), 10, 10)
            painter.restore()
            return

        # 3. Standard drawing / cursor states
        if self.active_tool == ToolType.ERASER:
            norm_radius = self.active_eraser_radius / 1920.0
            r_px = max(10.0, norm_radius * w)

            pen = QPen(QColor("#DC2626"), 2, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(QColor(220, 38, 38, 30))
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

        else:
            painter.setPen(QPen(QColor(100, 116, 139, 180), 1.5))
            painter.setBrush(QColor(255, 255, 255, 180))
            painter.drawEllipse(QPointF(px, py), 6, 6)

        painter.restore()

    # Mouse fallback
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            nx = event.x() / max(1.0, float(self.width()))
            ny = event.y() / max(1.0, float(self.height()))
            self._is_mouse_drawing = True
            if self.active_tool == ToolType.PEN:
                self.document.start_stroke(
                    tool=ToolType.PEN,
                    color=self.active_color,
                    thickness=self.active_thickness,
                    x=nx,
                    y=ny,
                )
            elif self.active_tool == ToolType.ERASER:
                norm_radius = self.active_eraser_radius / 1920.0
                self.document.erase_at(nx, ny, norm_radius)
            self.cursor_nx = nx
            self.cursor_ny = ny
            self.cursor_visible = True
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        nx = event.x() / max(1.0, float(self.width()))
        ny = event.y() / max(1.0, float(self.height()))
        self.cursor_nx = nx
        self.cursor_ny = ny
        self.cursor_visible = True
        if self._is_mouse_drawing:
            if self.active_tool == ToolType.PEN:
                self.document.add_point_to_active(nx, ny)
            elif self.active_tool == ToolType.ERASER:
                norm_radius = self.active_eraser_radius / 1920.0
                self.document.erase_at(nx, ny, norm_radius)
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self._is_mouse_drawing:
            self._is_mouse_drawing = False
            if self.active_tool == ToolType.PEN:
                self.document.finish_stroke()
            self.update()
