"""
Microsoft Word-inspired Ribbon interface for AirDraw Studio.
Organizes commands into styled logical groups (File, Drawing, Brush & Colors, Modes),
includes a large live gesture status banner, custom color picker, and thickness presets.
"""

from typing import List, Tuple, Optional
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QToolButton,
    QPushButton,
    QLabel,
    QSlider,
    QButtonGroup,
    QFrame,
    QColorDialog,
    QComboBox,
)
from PyQt5.QtGui import QFont, QColor, QIcon, QPainter, QPixmap

from config import (
    PRESET_COLORS,
    THICKNESS_PRESETS,
    DEFAULT_PEN_COLOR,
    DEFAULT_PEN_THICKNESS,
    GESTURE_COLORS,
    GESTURE_LABELS,
    THEME_PRIMARY,
    THEME_PRIMARY_HOVER,
    THEME_PRIMARY_LIGHT,
)
from drawing.stroke import ToolType


class RibbonGroup(QFrame):
    """A vertical ribbon group with a title label at the bottom, matching Office 365."""
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet("""
            RibbonGroup {
                border-right: 1px solid #E2E8F0;
                padding-right: 8px;
                margin-right: 4px;
            }
        """)
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(6, 4, 6, 2)
        self._main_layout.setSpacing(4)

        self.content_widget = QWidget()
        self.content_layout = QHBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(6)
        self._main_layout.addWidget(self.content_widget, 1)

        self.title_label = QLabel(title)
        self.title_label.setFont(QFont("Segoe UI", 8))
        self.title_label.setStyleSheet("color: #94A3B8; font-weight: 500;")
        self.title_label.setAlignment(Qt.AlignCenter)
        self._main_layout.addWidget(self.title_label)

    def add_widget(self, widget: QWidget) -> None:
        self.content_layout.addWidget(widget)

    def add_layout(self, layout) -> None:
        self.content_layout.addLayout(layout)


class ColorSwatchButton(QPushButton):
    """Circular color swatch button with active ring indicator."""
    def __init__(self, hex_color: str, name: str, parent=None):
        super().__init__(parent)
        self.hex_color = hex_color
        self.setToolTip(name)
        self.setFixedSize(24, 24)
        self.setCheckable(True)
        self._update_style()

    def setChecked(self, checked: bool) -> None:
        super().setChecked(checked)
        self._update_style()

    def _update_style(self) -> None:
        border = "2px solid #0078D4" if self.isChecked() else "1px solid #CBD5E1"
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.hex_color};
                border: {border};
                border-radius: 12px;
            }}
            QPushButton:hover {{
                border: 2px solid #64748B;
            }}
        """)


class GestureStatusBanner(QFrame):
    """Large, prominent live gesture indicator badge displayed persistently in Ribbon corner."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("gestureStatusBanner")
        self.setFixedHeight(34)
        self.setStyleSheet("""
            QFrame#gestureStatusBanner {
                background-color: #F8FAFC;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                margin-right: 8px;
                margin-top: 2px;
                margin-bottom: 2px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 2, 10, 2)
        layout.setSpacing(8)

        self.dot_label = QLabel()
        self.dot_label.setFixedSize(12, 12)
        layout.addWidget(self.dot_label)

        self.title_label = QLabel("GESTURE:")
        self.title_label.setFont(QFont("Segoe UI", 8, QFont.Bold))
        self.title_label.setStyleSheet("color: #64748B;")
        layout.addWidget(self.title_label)

        self.status_label = QLabel("IDLE / NO HAND")
        self.status_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.status_label.setStyleSheet("color: #1E293B;")
        layout.addWidget(self.status_label)

        self.set_gesture("IDLE")

    def set_gesture(self, gesture: str) -> None:
        color_hex = GESTURE_COLORS.get(gesture, "#64748B")
        label_text = GESTURE_LABELS.get(gesture, gesture)

        self.dot_label.setStyleSheet(f"""
            background-color: {color_hex};
            border-radius: 7px;
        """)
        self.status_label.setText(label_text)
        self.status_label.setStyleSheet(f"color: {color_hex}; font-weight: bold;")


class RibbonBar(QWidget):
    # Signals
    tool_changed = pyqtSignal(ToolType)
    color_changed = pyqtSignal(str)
    thickness_changed = pyqtSignal(float)
    clear_requested = pyqtSignal()
    undo_requested = pyqtSignal()
    redo_requested = pyqtSignal()
    new_doc_requested = pyqtSignal()
    open_doc_requested = pyqtSignal()
    save_doc_requested = pyqtSignal()
    save_as_requested = pyqtSignal()
    export_png_requested = pyqtSignal()
    toggle_overlay_mode = pyqtSignal()
    toggle_camera_panel = pyqtSignal(bool)
    smoothing_changed = pyqtSignal(str)
    close_app_requested = pyqtSignal()
    toggle_fullscreen_requested = pyqtSignal()
    bg_mode_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_color = DEFAULT_PEN_COLOR
        self.active_thickness = DEFAULT_PEN_THICKNESS
        self.active_tool = ToolType.PEN

        self._color_buttons: List[ColorSwatchButton] = []

        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Tab Widget container for Ribbon Tabs
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(f"""
            QTabWidget {{
                background-color: #FFFFFF;
            }}
            QTabWidget::pane {{
                border-top: 1px solid #CBD5E1;
                border-bottom: 1px solid #E2E8F0;
                background-color: #FFFFFF;
            }}
            QTabBar {{
                background-color: #F8FAFC;
            }}
            QTabBar::tab {{
                background-color: #F8FAFC;
                color: #475569;
                padding: 6px 22px;
                min-height: 28px;
                font-family: "Segoe UI";
                font-size: 10pt;
                font-weight: 500;
                border: none;
                border-bottom: 2px solid transparent;
            }}
            QTabBar::tab:selected {{
                color: {THEME_PRIMARY};
                font-weight: 600;
                border-bottom: 3px solid {THEME_PRIMARY};
                background-color: #FFFFFF;
            }}
            QTabBar::tab:hover:!selected {{
                color: {THEME_PRIMARY_HOVER};
                background-color: #F1F5F9;
            }}
        """)

        # Tab 1: Home / Draw
        draw_tab = QWidget()
        draw_layout = QHBoxLayout(draw_tab)
        draw_layout.setContentsMargins(12, 6, 12, 6)
        draw_layout.setSpacing(6)

        # 1. Tools Group
        tools_group = RibbonGroup("Drawing Tools", draw_tab)
        self.pen_btn = QToolButton()
        self.pen_btn.setText("Pen")
        self.pen_btn.setCheckable(True)
        self.pen_btn.setChecked(True)
        self.pen_btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.pen_btn.setToolTip("Freehand gesture drawing pen (Index finger)")
        self._style_tool_button(self.pen_btn)
        self.pen_btn.clicked.connect(lambda: self._set_tool(ToolType.PEN))

        self.eraser_btn = QToolButton()
        self.eraser_btn.setText("Eraser")
        self.eraser_btn.setCheckable(True)
        self.eraser_btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.eraser_btn.setToolTip("Eraser (Contact or circle stroke erasure)")
        self._style_tool_button(self.eraser_btn)
        self.eraser_btn.clicked.connect(lambda: self._set_tool(ToolType.ERASER))

        self.clear_btn = QToolButton()
        self.clear_btn.setText("Clear")
        self.clear_btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.clear_btn.setToolTip("Clear canvas (With confirmation)")
        self._style_tool_button(self.clear_btn, is_action=True)
        self.clear_btn.clicked.connect(lambda: self.clear_requested.emit())

        tools_group.add_widget(self.pen_btn)
        tools_group.add_widget(self.eraser_btn)
        tools_group.add_widget(self.clear_btn)
        draw_layout.addWidget(tools_group)

        # 2. Brush & Color Group
        color_group = RibbonGroup("Color & Thickness", draw_tab)
        color_vbox = QVBoxLayout()
        color_vbox.setSpacing(4)

        # Swatches grid
        palette_hbox = QHBoxLayout()
        palette_hbox.setSpacing(4)
        for hex_code, name in PRESET_COLORS[:8]:
            btn = ColorSwatchButton(hex_code, name)
            if hex_code.lower() == self.active_color.lower():
                btn.setChecked(True)
            btn.clicked.connect(lambda _, c=hex_code, b=btn: self._select_color(c, b))
            self._color_buttons.append(btn)
            palette_hbox.addWidget(btn)

        self.custom_color_btn = QPushButton("Custom...")
        self.custom_color_btn.setFont(QFont("Segoe UI", 8))
        self.custom_color_btn.setStyleSheet("""
            QPushButton {
                background: #F1F5F9;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                padding: 2px 6px;
                color: #334155;
            }
            QPushButton:hover {
                background: #E2E8F0;
            }
        """)
        self.custom_color_btn.clicked.connect(self._open_custom_color_dialog)
        palette_hbox.addWidget(self.custom_color_btn)
        color_vbox.addLayout(palette_hbox)

        # Thickness slider row
        thick_hbox = QHBoxLayout()
        thick_hbox.setSpacing(6)
        thick_label = QLabel("Size:")
        thick_label.setFont(QFont("Segoe UI", 8))
        thick_label.setStyleSheet("color: #64748B;")
        thick_hbox.addWidget(thick_label)

        self.thick_slider = QSlider(Qt.Horizontal)
        self.thick_slider.setRange(1, 36)
        self.thick_slider.setValue(int(self.active_thickness))
        self.thick_slider.setFixedWidth(120)
        self.thick_slider.valueChanged.connect(self._on_thickness_slider)
        thick_hbox.addWidget(self.thick_slider)

        self.thick_value_label = QLabel(f"{int(self.active_thickness)} px")
        self.thick_value_label.setFont(QFont("Segoe UI", 8, QFont.Bold))
        self.thick_value_label.setStyleSheet("color: #334155; min-width: 32px;")
        thick_hbox.addWidget(self.thick_value_label)

        # Quick preset thickness buttons
        for sz in [3, 8, 16]:
            preset_btn = QPushButton(f"{sz}")
            preset_btn.setFixedSize(22, 20)
            preset_btn.setFont(QFont("Segoe UI", 7))
            preset_btn.setStyleSheet("""
                QPushButton {
                    background: #F8FAFC;
                    border: 1px solid #CBD5E1;
                    border-radius: 3px;
                    color: #475569;
                }
                QPushButton:hover {
                    background: #E2E8F0;
                }
            """)
            preset_btn.clicked.connect(lambda _, s=sz: self.set_thickness(float(s)))
            thick_hbox.addWidget(preset_btn)

        color_vbox.addLayout(thick_hbox)
        color_group.add_layout(color_vbox)
        draw_layout.addWidget(color_group)

        # 3. History Group
        hist_group = RibbonGroup("History", draw_tab)
        self.undo_btn = QToolButton()
        self.undo_btn.setText("Undo")
        self.undo_btn.setToolTip("Undo stroke (Ctrl+Z)")
        self._style_tool_button(self.undo_btn, is_action=True)
        self.undo_btn.clicked.connect(lambda: self.undo_requested.emit())

        self.redo_btn = QToolButton()
        self.redo_btn.setText("Redo")
        self.redo_btn.setToolTip("Redo stroke (Ctrl+Y)")
        self._style_tool_button(self.redo_btn, is_action=True)
        self.redo_btn.clicked.connect(lambda: self.redo_requested.emit())

        hist_group.add_widget(self.undo_btn)
        hist_group.add_widget(self.redo_btn)
        draw_layout.addWidget(hist_group)

        # 4. Mode Switcher Group
        mode_group = RibbonGroup("Drawing Mode", draw_tab)
        self.overlay_mode_btn = QPushButton("Desktop Overlay\n[F9]")
        self.overlay_mode_btn.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.overlay_mode_btn.setToolTip("Switch to transparent full-screen desktop drawing overlay (F9)")
        self.overlay_mode_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME_PRIMARY_LIGHT};
                border: 1px solid {THEME_PRIMARY};
                border-radius: 6px;
                padding: 6px 14px;
                color: {THEME_PRIMARY};
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {THEME_PRIMARY};
                color: #FFFFFF;
            }}
        """)
        self.overlay_mode_btn.clicked.connect(lambda: self.toggle_overlay_mode.emit())
        mode_group.add_widget(self.overlay_mode_btn)
        draw_layout.addWidget(mode_group)

        draw_layout.addStretch(1)
        self.tab_widget.addTab(draw_tab, "Draw")

        # Persistent corner controls across all ribbon tabs
        corner_widget = QWidget(self)
        corner_layout = QHBoxLayout(corner_widget)
        corner_layout.setContentsMargins(0, 0, 8, 0)
        corner_layout.setSpacing(6)

        self.status_banner = GestureStatusBanner(corner_widget)
        corner_layout.addWidget(self.status_banner)

        self.fullscreen_btn = QPushButton("⛶")
        self.fullscreen_btn.setToolTip("Toggle Fullscreen Mode [F11]")
        self.fullscreen_btn.setFixedSize(32, 32)
        self.fullscreen_btn.setFont(QFont("Segoe UI", 12))
        self.fullscreen_btn.setStyleSheet("""
            QPushButton {
                background: #F1F5F9;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                color: #334155;
            }
            QPushButton:hover {
                background: #E2E8F0;
            }
        """)
        self.fullscreen_btn.clicked.connect(lambda: self.toggle_fullscreen_requested.emit())
        corner_layout.addWidget(self.fullscreen_btn)

        self.close_btn = QPushButton("✕ Exit")
        self.close_btn.setToolTip("Close Application (Hover or Pinch with finger)")
        self.close_btn.setFixedSize(70, 32)
        self.close_btn.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #DC2626;
                color: #FFFFFF;
                border: 1px solid #B91C1C;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #EF4444;
            }
        """)
        self.close_btn.clicked.connect(lambda: self.close_app_requested.emit())
        corner_layout.addWidget(self.close_btn)

        self.tab_widget.setCornerWidget(corner_widget, Qt.TopRightCorner)

        # Tab 2: File Operations
        file_tab = QWidget()
        file_layout = QHBoxLayout(file_tab)
        file_layout.setContentsMargins(12, 6, 12, 6)
        file_layout.setSpacing(8)

        file_group = RibbonGroup("Document Management", file_tab)
        new_btn = QPushButton("New Canvas (Ctrl+N)")
        self._style_ribbon_button(new_btn)
        new_btn.clicked.connect(lambda: self.new_doc_requested.emit())
        file_group.add_widget(new_btn)

        open_btn = QPushButton("Open Project (Ctrl+O)")
        self._style_ribbon_button(open_btn)
        open_btn.clicked.connect(lambda: self.open_doc_requested.emit())
        file_group.add_widget(open_btn)

        save_btn = QPushButton("Save Project (Ctrl+S)")
        self._style_ribbon_button(save_btn)
        save_btn.clicked.connect(lambda: self.save_doc_requested.emit())
        file_group.add_widget(save_btn)

        save_as_btn = QPushButton("Save As...")
        self._style_ribbon_button(save_as_btn)
        save_as_btn.clicked.connect(lambda: self.save_as_requested.emit())
        file_group.add_widget(save_as_btn)

        export_btn = QPushButton("Export PNG (Ctrl+E)")
        export_btn.setFont(QFont("Segoe UI", 9, QFont.Bold))
        export_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME_PRIMARY};
                border: 1px solid {THEME_PRIMARY_HOVER};
                border-radius: 4px;
                padding: 6px 14px;
                color: #FFFFFF;
            }}
            QPushButton:hover {{
                background-color: {THEME_PRIMARY_HOVER};
            }}
        """)
        export_btn.clicked.connect(lambda: self.export_png_requested.emit())
        file_group.add_widget(export_btn)

        file_layout.addWidget(file_group)
        file_layout.addStretch()
        self.tab_widget.addTab(file_tab, "File")

        # Tab 3: Settings & View
        settings_tab = QWidget()
        set_layout = QHBoxLayout(settings_tab)
        set_layout.setContentsMargins(12, 6, 12, 6)
        set_layout.setSpacing(8)

        view_group = RibbonGroup("View Options", settings_tab)
        self.toggle_cam_btn = QPushButton("Hide Camera Panel")
        self.toggle_cam_btn.setCheckable(True)
        self._style_ribbon_button(self.toggle_cam_btn)
        self.toggle_cam_btn.toggled.connect(self._on_toggle_camera_panel)
        view_group.add_widget(self.toggle_cam_btn)
        set_layout.addWidget(view_group)

        smooth_group = RibbonGroup("Trajectory Smoothing", settings_tab)
        self.smooth_combo = QComboBox()
        self.smooth_combo.addItems(["One Euro Filter (Recommended)", "Exponential Moving Average", "None"])
        self.smooth_combo.currentIndexChanged.connect(self._on_smoothing_combo)
        smooth_group.add_widget(self.smooth_combo)
        set_layout.addWidget(smooth_group)

        bg_group = RibbonGroup("Canvas Background", settings_tab)
        self.bg_combo = QComboBox()
        self.bg_combo.addItems(["Blurred Camera (CPU)", "Dimmed Camera", "Clear Camera", "Solid White"])
        self.bg_combo.currentIndexChanged.connect(self._on_bg_mode_combo)
        bg_group.add_widget(self.bg_combo)
        set_layout.addWidget(bg_group)

        set_layout.addStretch()
        self.tab_widget.addTab(settings_tab, "Settings")

        main_layout.addWidget(self.tab_widget)

    def _style_tool_button(self, btn: QToolButton, is_action: bool = False) -> None:
        btn.setFont(QFont("Segoe UI", 9))
        btn.setFixedSize(54, 52)
        btn.setStyleSheet(f"""
            QToolButton {{
                background: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                color: #334155;
                font-weight: 500;
            }}
            QToolButton:hover {{
                background: #F1F5F9;
                border-color: #CBD5E1;
            }}
            QToolButton:checked {{
                background: {THEME_PRIMARY_LIGHT};
                border: 2px solid {THEME_PRIMARY};
                color: {THEME_PRIMARY};
                font-weight: 600;
            }}
        """)

    def _style_ribbon_button(self, btn: QPushButton) -> None:
        btn.setFont(QFont("Segoe UI", 9))
        btn.setStyleSheet("""
            QPushButton {
                background: #F8FAFC;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                padding: 6px 12px;
                color: #334155;
            }
            QPushButton:hover {
                background: #E2E8F0;
            }
        """)

    def _set_tool(self, tool: ToolType) -> None:
        self.active_tool = tool
        self.pen_btn.setChecked(tool == ToolType.PEN)
        self.eraser_btn.setChecked(tool == ToolType.ERASER)
        self.tool_changed.emit(tool)

    def _select_color(self, hex_color: str, active_btn: ColorSwatchButton) -> None:
        self.active_color = hex_color
        for btn in self._color_buttons:
            btn.setChecked(btn is active_btn)
        self.color_changed.emit(hex_color)

    def _open_custom_color_dialog(self) -> None:
        col = QColorDialog.getColor(QColor(self.active_color), self, "Select Drawing Color")
        if col.isValid():
            hex_code = col.name()
            self.active_color = hex_code
            for btn in self._color_buttons:
                btn.setChecked(False)
            self.color_changed.emit(hex_code)

    def _on_thickness_slider(self, val: int) -> None:
        self.active_thickness = float(val)
        self.thick_value_label.setText(f"{val} px")
        self.thickness_changed.emit(self.active_thickness)

    def set_thickness(self, val: float) -> None:
        self.active_thickness = val
        self.thick_slider.setValue(int(val))
        self.thick_value_label.setText(f"{int(val)} px")
        self.thickness_changed.emit(val)

    def set_gesture_status(self, gesture: str) -> None:
        self.status_banner.set_gesture(gesture)

    def _on_toggle_camera_panel(self, checked: bool) -> None:
        if checked:
            self.toggle_cam_btn.setText("Show Camera Panel")
            self.toggle_camera_panel.emit(False)
        else:
            self.toggle_cam_btn.setText("Hide Camera Panel")
            self.toggle_camera_panel.emit(True)

    def _on_smoothing_combo(self, index: int) -> None:
        modes = ["one_euro", "ema", "none"]
        if index < len(modes):
            self.smoothing_changed.emit(modes[index])

    def _on_bg_mode_combo(self, index: int) -> None:
        modes = ["blurred", "dimmed", "clear", "white"]
        if index < len(modes):
            self.bg_mode_changed.emit(modes[index])
