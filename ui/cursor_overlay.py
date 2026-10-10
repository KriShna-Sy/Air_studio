"""
CursorOverlay for AirDraw Studio.
A top-level, transparent overlay widget that renders the air cursor,
the animated dwell progress ring, the instant pinch indicator,
the "BOOM" click shockwave ripple animation, and floating toast notifications.
Guaranteed to render ON TOP of all toolbars, buttons, and UI controls.
"""

import time
from typing import Optional
from PyQt5.QtCore import Qt, QPoint, QRectF, QTimer
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QFont

from config import GESTURE_COLORS


class CursorOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.NoFocus)

        # Cursor State
        self.cursor_pos = QPoint(-100, -100)
        self.cursor_visible = False
        self.cursor_gesture = "IDLE"
        self.active_color = "#2563EB"

        # Dwell & Pinch State
        self.is_dwelling = False
        self.dwell_progress = 0.0
        self.is_pinched = False

        # "BOOM" Click Ripple Animation State
        self.ripple_center = QPoint(-100, -100)
        self.ripple_radius = 0.0
        self.ripple_alpha = 0
        self.ripple_color = QColor("#38BDF8")
        self._ripple_timer = QTimer(self)
        self._ripple_timer.setInterval(16)  # ~60 FPS
        self._ripple_timer.timeout.connect(self._update_ripple)

        # Floating Toast Notification State
        self.toast_message: Optional[str] = None
        self.toast_color = QColor("#38BDF8")
        self.toast_start_time = 0.0
        self._toast_timer = QTimer(self)
        self._toast_timer.setInterval(30)
        self._toast_timer.timeout.connect(self._update_toast)

    def set_cursor_state(
        self,
        px: int,
        py: int,
        gesture: str,
        visible: bool,
        active_color: str,
        is_pinched: bool = False,
    ) -> None:
        self.cursor_pos = QPoint(px, py)
        self.cursor_gesture = gesture
        self.cursor_visible = visible
        self.active_color = active_color
        self.is_pinched = is_pinched
        self.update()

    def set_dwell_state(self, is_dwelling: bool, progress: float) -> None:
        self.is_dwelling = is_dwelling
        self.dwell_progress = max(0.0, min(1.0, progress))
        self.update()

    def trigger_boom_ripple(self, center: QPoint, color_hex: str = "#38BDF8") -> None:
        """Triggers an expanding luminous shockwave ring on selection."""
        self.ripple_center = center
        self.ripple_radius = 12.0
        self.ripple_alpha = 255
        self.ripple_color = QColor(color_hex)
        self._ripple_timer.start()
        self.update()

    def _update_ripple(self) -> None:
        self.ripple_radius += 3.8
        self.ripple_alpha = max(0, self.ripple_alpha - 18)
        if self.ripple_alpha <= 0 or self.ripple_radius > 75:
            self._ripple_timer.stop()
            self.ripple_alpha = 0
        self.update()

    def show_toast(self, message: str, color_hex: str = "#38BDF8") -> None:
        """Displays a floating non-blocking translucent glass toast banner."""
        self.toast_message = message
        self.toast_color = QColor(color_hex)
        self.toast_start_time = time.time()
        self._toast_timer.start()
        self.update()

    def _update_toast(self) -> None:
        elapsed = time.time() - self.toast_start_time
        if elapsed > 2.5:
            self.toast_message = None
            self._toast_timer.stop()
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # 1. Render "BOOM" Click Ripple Shockwave
        if self.ripple_alpha > 0:
            ripple_pen = QPen(
                QColor(
                    self.ripple_color.red(),
                    self.ripple_color.green(),
                    self.ripple_color.blue(),
                    self.ripple_alpha,
                ),
                3.5,
            )
            painter.setPen(ripple_pen)
            painter.setBrush(
                QColor(
                    self.ripple_color.red(),
                    self.ripple_color.green(),
                    self.ripple_color.blue(),
                    int(self.ripple_alpha * 0.25),
                )
            )
            painter.drawEllipse(
                self.ripple_center,
                int(self.ripple_radius),
                int(self.ripple_radius),
            )

        # 2. Render Air Fingertip Cursor and Dwell Progress Ring
        if self.cursor_visible:
            px = self.cursor_pos.x()
            py = self.cursor_pos.y()
            gesture_color = QColor(GESTURE_COLORS.get(self.cursor_gesture, "#64748B"))

            # A. If Dwelling over a button: Radial Progress Ring
            if self.is_dwelling and self.dwell_progress > 0.0:
                ring_rect = QRectF(px - 24, py - 24, 48, 48)
                # Outer track
                painter.setPen(QPen(QColor(255, 255, 255, 140), 4))
                painter.setBrush(QColor(15, 23, 42, 100))
                painter.drawEllipse(ring_rect)

                # Active filled electric arc
                progress_pen = QPen(QColor("#00F0FF"), 4.5)
                progress_pen.setCapStyle(Qt.RoundCap)
                painter.setPen(progress_pen)
                painter.setBrush(Qt.NoBrush)
                span_angle = int(-360 * 16 * self.dwell_progress)
                painter.drawArc(ring_rect, 90 * 16, span_angle)

                # Center crosshair dot
                painter.setPen(QPen(Qt.white, 2))
                painter.setBrush(QColor("#00F0FF"))
                painter.drawEllipse(self.cursor_pos, 5, 5)

            # B. If Pinched: Green Pinch Ring
            elif self.is_pinched:
                painter.setPen(QPen(QColor("#16A34A"), 3.5))
                painter.setBrush(QColor(22, 163, 74, 120))
                painter.drawEllipse(self.cursor_pos, 12, 12)
                painter.setPen(QPen(Qt.white, 2))
                painter.setBrush(QColor("#16A34A"))
                painter.drawEllipse(self.cursor_pos, 4, 4)

            # C. Standard Gesture Cursor States
            else:
                if self.cursor_gesture == "DRAW":
                    # Drawing outer ring
                    painter.setPen(QPen(gesture_color, 2.5))
                    painter.setBrush(
                        QColor(gesture_color.red(), gesture_color.green(), gesture_color.blue(), 60)
                    )
                    painter.drawEllipse(self.cursor_pos, 14, 14)

                    # Inner active color core
                    painter.setPen(QPen(Qt.white, 2))
                    painter.setBrush(QColor(self.active_color))
                    painter.drawEllipse(self.cursor_pos, 6, 6)

                elif self.cursor_gesture == "MOVE_CURSOR":
                    # Navigation Crosshair
                    painter.setPen(QPen(gesture_color, 2.5))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawEllipse(self.cursor_pos, 10, 10)
                    painter.drawLine(px - 16, py, px - 11, py)
                    painter.drawLine(px + 11, py, px + 16, py)
                    painter.drawLine(px, py - 16, px, py - 11)
                    painter.drawLine(px, py + 11, px, py + 16)

                elif self.cursor_gesture == "STOP":
                    painter.setPen(QPen(Qt.white, 2))
                    painter.setBrush(gesture_color)
                    painter.drawEllipse(self.cursor_pos, 8, 8)

                else:
                    painter.setPen(QPen(QColor(100, 116, 139, 180), 1.5))
                    painter.setBrush(QColor(255, 255, 255, 180))
                    painter.drawEllipse(self.cursor_pos, 6, 6)

        # 3. Render Floating Toast Banner Notification
        if self.toast_message is not None:
            elapsed = time.time() - self.toast_start_time
            alpha = 240
            if elapsed > 1.8:
                fade_progress = (elapsed - 1.8) / 0.7
                alpha = int(max(0, 240 * (1.0 - fade_progress)))

            font = QFont("Segoe UI", 12, QFont.Bold)
            painter.setFont(font)
            metrics = painter.fontMetrics()
            text_w = metrics.horizontalAdvance(self.toast_message)
            toast_w = text_w + 48
            toast_h = 42
            toast_x = (self.width() - toast_w) // 2
            toast_y = self.height() - 85

            toast_rect = QRectF(toast_x, toast_y, toast_w, toast_h)
            painter.setPen(
                QPen(
                    QColor(
                        self.toast_color.red(),
                        self.toast_color.green(),
                        self.toast_color.blue(),
                        alpha,
                    ),
                    2,
                )
            )
            painter.setBrush(QColor(15, 23, 42, alpha))
            painter.drawRoundedRect(toast_rect, 14, 14)

            painter.setPen(QColor(255, 255, 255, alpha))
            painter.drawText(toast_rect, Qt.AlignCenter, self.toast_message)

        painter.end()
