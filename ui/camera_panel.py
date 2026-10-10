"""
CameraPanel for AirDraw Studio.
Displays live camera feed with aspect ratio preservation, hand skeleton overlay,
device selector, refresh action, and tracking telemetry.
"""

from typing import Optional, List
from PyQt5.QtCore import Qt, QRectF, pyqtSignal, QSize
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QFrame,
    QSizePolicy,
)
from PyQt5.QtGui import QPainter, QImage, QColor, QFont, QPen

from config import (
    GESTURE_COLORS,
    GESTURE_LABELS,
    THEME_PRIMARY,
    THEME_PRIMARY_HOVER,
    THEME_TEXT_PRIMARY,
    THEME_TEXT_MUTED,
)


class VideoDisplayWidget(QWidget):
    """Subwidget that renders the camera frame with strict aspect-ratio preservation."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_image: Optional[QImage] = None
        self.gesture_name: str = "IDLE"
        self.fps: float = 0.0
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(240, 180)

    def set_frame(self, image: QImage) -> None:
        self.current_image = image
        self.update()

    def set_gesture_info(self, gesture: str, fps: float) -> None:
        self.gesture_name = gesture
        self.fps = fps
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        # Background fill
        painter.fillRect(self.rect(), QColor("#0F172A"))

        w = self.width()
        h = self.height()

        if self.current_image is not None and not self.current_image.isNull():
            img_w = self.current_image.width()
            img_h = self.current_image.height()
            aspect = img_w / max(1, img_h)

            if w / h > aspect:
                draw_h = h
                draw_w = int(draw_h * aspect)
            else:
                draw_w = w
                draw_h = int(draw_w / aspect)

            draw_x = (w - draw_w) // 2
            draw_y = (h - draw_h) // 2
            target_rect = QRectF(draw_x, draw_y, draw_w, draw_h)

            painter.drawImage(target_rect, self.current_image)
        else:
            # Standby placeholder
            painter.setPen(QColor("#64748B"))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(self.rect(), Qt.AlignCenter, "Camera Preview\n(Standby)")

        # Render floating status badges on top
        self._draw_overlay_badges(painter)
        painter.end()

    def _draw_overlay_badges(self, painter: QPainter) -> None:
        # FPS readout (top-left)
        fps_text = f"{self.fps:.1f} FPS"
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 160))
        painter.drawRoundedRect(QRectF(8, 8, 64, 22), 4, 4)

        painter.setPen(QColor("#E2E8F0"))
        painter.drawText(QRectF(8, 8, 64, 22), Qt.AlignCenter, fps_text)

        # Gesture pill (top-right)
        color_hex = GESTURE_COLORS.get(self.gesture_name, "#64748B")
        badge_text = self.gesture_name.replace("_", " ")

        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(badge_text) + 24
        pill_rect = QRectF(self.width() - text_width - 8, 8, text_width, 22)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 160))
        painter.drawRoundedRect(pill_rect, 11, 11)

        # Dot
        dot_color = QColor(color_hex)
        painter.setBrush(dot_color)
        painter.drawEllipse(QRectF(pill_rect.left() + 6, pill_rect.top() + 6, 10, 10))

        # Text
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(
            QRectF(pill_rect.left() + 20, pill_rect.top(), text_width - 20, 22),
            Qt.AlignVCenter | Qt.AlignLeft,
            badge_text,
        )


class CameraPanel(QFrame):
    """Panel containing camera preview and camera management controls."""
    camera_selected = pyqtSignal(int)
    refresh_requested = pyqtSignal()
    toggle_camera = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cameraPanel")
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            QFrame#cameraPanel {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Panel Header
        header_layout = QHBoxLayout()
        title_label = QLabel("Camera & Tracking")
        title_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        title_label.setStyleSheet("color: #1E293B;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Video Display
        self.video_widget = VideoDisplayWidget(self)
        layout.addWidget(self.video_widget, 1)

        # Controls Row: Camera Selector & Refresh
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(6)

        cam_lbl = QLabel("Device:")
        cam_lbl.setFont(QFont("Segoe UI", 9))
        cam_lbl.setStyleSheet("color: #64748B;")
        ctrl_layout.addWidget(cam_lbl)

        self.device_combo = QComboBox()
        self.device_combo.setFont(QFont("Segoe UI", 9))
        self.device_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                padding: 3px 8px;
                background: #F8FAFC;
                color: #0F172A;
            }
            QComboBox:hover {
                border-color: #94A3B8;
            }
        """)
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)
        ctrl_layout.addWidget(self.device_combo, 1)

        self.refresh_btn = QPushButton("Scan")
        self.refresh_btn.setFont(QFont("Segoe UI", 9))
        self.refresh_btn.setToolTip("Rescan connected camera devices")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background: #F1F5F9;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                padding: 4px 10px;
                color: #334155;
            }
            QPushButton:hover {
                background: #E2E8F0;
            }
        """)
        self.refresh_btn.clicked.connect(lambda: self.refresh_requested.emit())
        ctrl_layout.addWidget(self.refresh_btn)

        layout.addLayout(ctrl_layout)

        # Start / Stop Toggle Row
        toggle_layout = QHBoxLayout()
        self.toggle_btn = QPushButton("Pause Camera")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setFont(QFont("Segoe UI", 9))
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background: #EFF6FC;
                border: 1px solid #0078D4;
                border-radius: 4px;
                padding: 4px 12px;
                color: #0078D4;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #0078D4;
                color: #FFFFFF;
            }
            QPushButton:checked {
                background: #FEE2E2;
                border-color: #DC2626;
                color: #DC2626;
            }
        """)
        self.toggle_btn.toggled.connect(self._on_toggle_camera)
        toggle_layout.addWidget(self.toggle_btn)

        # Status text
        self.status_label = QLabel("Ready")
        self.status_label.setFont(QFont("Segoe UI", 8))
        self.status_label.setStyleSheet("color: #64748B;")
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        toggle_layout.addWidget(self.status_label, 1)

        layout.addLayout(toggle_layout)

    def set_frame(self, image: QImage) -> None:
        self.video_widget.set_frame(image)

    def set_tracking_telemetry(self, gesture: str, fps: float) -> None:
        self.video_widget.set_gesture_info(gesture, fps)

    def set_available_devices(self, devices: List[int], active_device: int = 0) -> None:
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        if not devices:
            self.device_combo.addItem("No cameras found", -1)
        else:
            for idx in devices:
                self.device_combo.addItem(f"Camera {idx}", idx)
            # Match active
            combo_idx = self.device_combo.findData(active_device)
            if combo_idx >= 0:
                self.device_combo.setCurrentIndex(combo_idx)
        self.device_combo.blockSignals(False)

    def set_status_message(self, message: str, is_error: bool = False) -> None:
        color = "#DC2626" if is_error else "#64748B"
        self.status_label.setStyleSheet(f"color: {color};")
        self.status_label.setText(message)

    def _on_device_changed(self, combo_idx: int) -> None:
        data = self.device_combo.itemData(combo_idx)
        if data is not None and data >= 0:
            self.camera_selected.emit(data)

    def _on_toggle_camera(self, is_paused: bool) -> None:
        if is_paused:
            self.toggle_btn.setText("Resume Camera")
            self.toggle_camera.emit(False)
            self.set_status_message("Camera paused")
        else:
            self.toggle_btn.setText("Pause Camera")
            self.toggle_camera.emit(True)
            self.set_status_message("Camera running")
