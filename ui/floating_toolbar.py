"""
FloatingGlassToolbar for AirDraw Studio.
A futuristic, genuinely translucent glassmorphic floating toolbar.
Sits seamlessly on top of the full-screen drawing canvas, providing
large, touchless-friendly buttons for all drawing tools, colors,
sizes, undo/redo, touchless clear, quick save, fullscreen, and exit.
"""

from typing import List, Tuple, Optional
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QPoint, QSize
from PyQt5.QtWidgets import (
    QFrame,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QLabel,
)
from PyQt5.QtGui import QFont, QColor

from config import (
    PRESET_COLORS,
    DEFAULT_PEN_COLOR,
    DEFAULT_PEN_THICKNESS,
    GESTURE_COLORS,
    GESTURE_LABELS,
)
from drawing.stroke import ToolType


class ColorSwatchPill(QPushButton):
    """Large, touchless-friendly circular color gem."""
    def __init__(self, hex_color: str, name: str, parent=None):
        super().__init__(parent)
        self.hex_color = hex_color
        self.setToolTip(f"Color: {name}")
        self.setFixedSize(30, 30)
        self.setCheckable(True)
        self._is_focused = False
        self._update_style()

    def set_focused(self, focused: bool) -> None:
        if self._is_focused != focused:
            self._is_focused = focused
            self._update_style()

    def setChecked(self, checked: bool) -> None:
        super().setChecked(checked)
        self._update_style()

    def _update_style(self) -> None:
        if self.isChecked():
            border = "3px solid #FFFFFF"
            shadow = "0 0 10px rgba(255, 255, 255, 0.9)"
        elif self._is_focused:
            border = "3px solid #38BDF8"
            shadow = "0 0 12px #38BDF8"
        else:
            border = "1.5px solid rgba(255, 255, 255, 0.35)"
            shadow = "none"

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.hex_color};
                border: {border};
                border-radius: 15px;
            }}
        """)


class GlassButton(QPushButton):
    """Frosted glass pill button with luminous active and magnetic hover states."""
    def __init__(self, text: str, parent=None, is_danger: bool = False, is_accent: bool = False):
        super().__init__(text, parent)
        self.is_danger = is_danger
        self.is_accent = is_accent
        self._is_focused = False
        self.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.setFixedHeight(34)
        self._update_style()

    def set_focused(self, focused: bool) -> None:
        if self._is_focused != focused:
            self._is_focused = focused
            self._update_style()

    def setChecked(self, checked: bool) -> None:
        super().setChecked(checked)
        self._update_style()

    def _update_style(self) -> None:
        if self.is_danger:
            bg = "#DC2626" if not self._is_focused else "#EF4444"
            border = "2px solid #FCA5A5" if self._is_focused else "1px solid #B91C1C"
            fg = "#FFFFFF"
        elif self.isChecked() or self.is_accent:
            bg = "#0078D4" if not self._is_focused else "#0284C7"
            border = "2px solid #38BDF8" if self._is_focused else "1px solid #38BDF8"
            fg = "#FFFFFF"
        elif self._is_focused:
            bg = "rgba(56, 189, 248, 0.35)"
            border = "2px solid #38BDF8"
            fg = "#FFFFFF"
        else:
            bg = "rgba(255, 255, 255, 0.12)"
            border = "1px solid rgba(255, 255, 255, 0.20)"
            fg = "#F1F5F9"

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                border: {border};
                border-radius: 10px;
                color: {fg};
                padding: 4px 12px;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.25);
                border-color: #38BDF8;
            }}
        """)


class FloatingGlassToolbar(QFrame):
    """
    Floating transparent glass toolbar.
    All options are transparent and easily targeted by hand without modal windows.
    """
    tool_changed = pyqtSignal(ToolType)
    color_changed = pyqtSignal(str)
    thickness_changed = pyqtSignal(float)
    clear_requested = pyqtSignal()
    undo_requested = pyqtSignal()
    redo_requested = pyqtSignal()
    save_png_requested = pyqtSignal()
    toggle_overlay_mode = pyqtSignal()
    toggle_fullscreen_requested = pyqtSignal()
    close_app_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("glassToolbar")
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self.active_tool: ToolType = ToolType.PEN
        self.active_color: str = DEFAULT_PEN_COLOR
        self.active_thickness: float = DEFAULT_PEN_THICKNESS

        self._color_swatches: List[ColorSwatchPill] = []
        self._size_buttons: List[GlassButton] = []
        self._focused_button: Optional[QPushButton] = None

        # Two-step clear confirmation timer
        self._clear_confirm_pending: bool = False
        self._clear_timer = QTimer(self)
        self._clear_timer.setSingleShot(True)
        self._clear_timer.setInterval(3500)
        self._clear_timer.timeout.connect(self._reset_clear_button)

        self._init_ui()

    def _init_ui(self) -> None:
        self.setStyleSheet("""
            QFrame#glassToolbar {
                background-color: rgba(15, 23, 42, 0.82);
                border: 1px solid rgba(255, 255, 255, 0.22);
                border-radius: 20px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        # 1. Gesture Status Indicator
        self.status_container = QFrame()
        self.status_container.setStyleSheet("""
            background-color: rgba(0, 0, 0, 0.35);
            border-radius: 10px;
            padding: 2px 8px;
        """)
        status_layout = QHBoxLayout(self.status_container)
        status_layout.setContentsMargins(4, 2, 6, 2)
        status_layout.setSpacing(6)

        self.dot_label = QLabel()
        self.dot_label.setFixedSize(10, 10)
        self.dot_label.setStyleSheet("background-color: #64748B; border-radius: 5px;")
        status_layout.addWidget(self.dot_label)

        self.status_text = QLabel("IDLE")
        self.status_text.setFont(QFont("Segoe UI", 8, QFont.Bold))
        self.status_text.setStyleSheet("color: #E2E8F0;")
        status_layout.addWidget(self.status_text)
        layout.addWidget(self.status_container)

        self._add_separator(layout)

        # 2. Drawing Tools (Pen & Eraser)
        self.pen_btn = GlassButton("✏️ Pen")
        self.pen_btn.setCheckable(True)
        self.pen_btn.setChecked(True)
        self.pen_btn.clicked.connect(lambda: self._select_tool(ToolType.PEN))
        layout.addWidget(self.pen_btn)

        self.eraser_btn = GlassButton("🧹 Eraser")
        self.eraser_btn.setCheckable(True)
        self.eraser_btn.clicked.connect(lambda: self._select_tool(ToolType.ERASER))
        layout.addWidget(self.eraser_btn)

        self._add_separator(layout)

        # 3. Transparent Color Swatches (8 Vibrant Palette Gems)
        color_sub_layout = QHBoxLayout()
        color_sub_layout.setSpacing(5)
        for hex_code, name in PRESET_COLORS[:8]:
            swatch = ColorSwatchPill(hex_code, name)
            if hex_code.lower() == self.active_color.lower():
                swatch.setChecked(True)
            swatch.clicked.connect(lambda _, c=hex_code, s=swatch: self._select_color(c, s))
            self._color_swatches.append(swatch)
            color_sub_layout.addWidget(swatch)
        layout.addLayout(color_sub_layout)

        self._add_separator(layout)

        # 4. Thickness Buttons (No fiddly sliders!)
        sizes = [(2.0, "2px"), (6.0, "6px"), (12.0, "12px"), (24.0, "24px")]
        for thick_val, label_text in sizes:
            s_btn = GlassButton(label_text)
            s_btn.setCheckable(True)
            if thick_val == self.active_thickness:
                s_btn.setChecked(True)
            s_btn.clicked.connect(lambda _, t=thick_val, b=s_btn: self._select_thickness(t, b))
            self._size_buttons.append(s_btn)
            layout.addWidget(s_btn)

        self._add_separator(layout)

        # 5. History & Document Actions
        self.undo_btn = GlassButton("↩️ Undo")
        self.undo_btn.clicked.connect(lambda: self.undo_requested.emit())
        layout.addWidget(self.undo_btn)

        self.redo_btn = GlassButton("↪️ Redo")
        self.redo_btn.clicked.connect(lambda: self.redo_requested.emit())
        layout.addWidget(self.redo_btn)

        self.clear_btn = GlassButton("🗑️ Clear")
        self.clear_btn.clicked.connect(self._on_clear_clicked)
        layout.addWidget(self.clear_btn)

        self.save_btn = GlassButton("💾 Save")
        self.save_btn.clicked.connect(lambda: self.save_png_requested.emit())
        layout.addWidget(self.save_btn)

        self._add_separator(layout)

        # 6. Mode & Window Controls
        self.overlay_btn = GlassButton("🪟 Overlay [F9]", is_accent=True)
        self.overlay_btn.clicked.connect(lambda: self.toggle_overlay_mode.emit())
        layout.addWidget(self.overlay_btn)

        self.fullscreen_btn = GlassButton("⛶")
        self.fullscreen_btn.setToolTip("Toggle Fullscreen [F11]")
        self.fullscreen_btn.clicked.connect(lambda: self.toggle_fullscreen_requested.emit())
        layout.addWidget(self.fullscreen_btn)

        self.close_btn = GlassButton("✕ Exit", is_danger=True)
        self.close_btn.clicked.connect(lambda: self.close_app_requested.emit())
        layout.addWidget(self.close_btn)

    def _add_separator(self, layout: QHBoxLayout) -> None:
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: rgba(255, 255, 255, 0.22); margin: 4px 1px;")
        layout.addWidget(sep)

    def get_all_clickable_buttons(self) -> List[QPushButton]:
        """Returns all buttons in the toolbar for magnetic proximity snapping."""
        buttons: List[QPushButton] = [self.pen_btn, self.eraser_btn]
        buttons.extend(self._color_swatches)
        buttons.extend(self._size_buttons)
        buttons.extend([
            self.undo_btn,
            self.redo_btn,
            self.clear_btn,
            self.save_btn,
            self.overlay_btn,
            self.fullscreen_btn,
            self.close_btn,
        ])
        return buttons

    def set_focused_button(self, button: Optional[QPushButton]) -> None:
        """Sets luminous magnetic focus on a button when hovered by hand."""
        if self._focused_button is not None and self._focused_button != button:
            if hasattr(self._focused_button, "set_focused"):
                self._focused_button.set_focused(False)
            else:
                self._focused_button.setStyleSheet(self._focused_button.styleSheet())

        self._focused_button = button
        if self._focused_button is not None:
            if hasattr(self._focused_button, "set_focused"):
                self._focused_button.set_focused(True)

    def set_gesture_status(self, gesture: str) -> None:
        color_hex = GESTURE_COLORS.get(gesture, "#64748B")
        label_text = GESTURE_LABELS.get(gesture, gesture)
        self.dot_label.setStyleSheet(f"background-color: {color_hex}; border-radius: 5px;")
        self.status_text.setText(label_text)
        self.status_text.setStyleSheet(f"color: {color_hex}; font-weight: bold;")

    def _select_tool(self, tool: ToolType) -> None:
        self.active_tool = tool
        self.pen_btn.setChecked(tool == ToolType.PEN)
        self.eraser_btn.setChecked(tool == ToolType.ERASER)
        self.tool_changed.emit(tool)

    def _select_color(self, hex_code: str, active_swatch: ColorSwatchPill) -> None:
        self.active_color = hex_code
        for swatch in self._color_swatches:
            swatch.setChecked(swatch == active_swatch)
        # Auto-switch to Pen when color is selected
        self._select_tool(ToolType.PEN)
        self.color_changed.emit(hex_code)

    def _select_thickness(self, thick: float, active_btn: GlassButton) -> None:
        self.active_thickness = thick
        for b in self._size_buttons:
            b.setChecked(b == active_btn)
        self.thickness_changed.emit(thick)

    def _on_clear_clicked(self) -> None:
        """Touchless two-step clear canvas confirmation."""
        if not self._clear_confirm_pending:
            self._clear_confirm_pending = True
            self.clear_btn.setText("⚠️ Confirm Clear?")
            self.clear_btn.setStyleSheet("""
                QPushButton {
                    background-color: #D97706;
                    border: 2px solid #FDE68A;
                    border-radius: 10px;
                    color: #FFFFFF;
                    padding: 4px 12px;
                    font-weight: bold;
                }
            """)
            self._clear_timer.start()
        else:
            self._reset_clear_button()
            self.clear_requested.emit()

    def _reset_clear_button(self) -> None:
        self._clear_confirm_pending = False
        self._clear_timer.stop()
        self.clear_btn.setText("🗑️ Clear")
        if hasattr(self.clear_btn, "_update_style"):
            self.clear_btn._update_style()
