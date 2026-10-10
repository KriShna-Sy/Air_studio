"""
Document model for AirDraw Studio.
Maintains the single source of truth for all drawing strokes,
undo/redo command history, vector stroke erasure, serialization, and high-DPI export.
"""

import json
import os
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Callable
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPainter, QColor, QPen, QImage, QPainterPath

from .stroke import Stroke, ToolType


class Command(ABC):
    """Abstract command for undo/redo operations."""
    @abstractmethod
    def execute(self, document: "Document") -> None:
        pass

    @abstractmethod
    def undo(self, document: "Document") -> None:
        pass


class AddStrokeCommand(Command):
    def __init__(self, stroke: Stroke):
        self.stroke = stroke

    def execute(self, document: "Document") -> None:
        document.strokes.append(self.stroke)

    def undo(self, document: "Document") -> None:
        if document.strokes and document.strokes[-1] is self.stroke:
            document.strokes.pop()
        elif self.stroke in document.strokes:
            document.strokes.remove(self.stroke)


class EraseStrokesCommand(Command):
    def __init__(self, erased_strokes: List[Tuple[int, Stroke]]):
        # Store index and stroke reference to restore exact layering order
        self.erased_strokes = sorted(erased_strokes, key=lambda x: x[0])

    def execute(self, document: "Document") -> None:
        for idx, stroke in reversed(self.erased_strokes):
            if idx < len(document.strokes) and document.strokes[idx] is stroke:
                document.strokes.pop(idx)
            elif stroke in document.strokes:
                document.strokes.remove(stroke)

    def undo(self, document: "Document") -> None:
        for idx, stroke in self.erased_strokes:
            target_idx = min(idx, len(document.strokes))
            document.strokes.insert(target_idx, stroke)


class ClearCanvasCommand(Command):
    def __init__(self, previous_strokes: List[Stroke]):
        self.previous_strokes = list(previous_strokes)

    def execute(self, document: "Document") -> None:
        document.strokes.clear()

    def undo(self, document: "Document") -> None:
        document.strokes = list(self.previous_strokes)


class Document:
    def __init__(self, aspect_ratio: float = 16.0 / 9.0):
        self.aspect_ratio = aspect_ratio
        self.strokes: List[Stroke] = []
        self.active_stroke: Optional[Stroke] = None
        
        self.undo_stack: List[Command] = []
        self.redo_stack: List[Command] = []
        
        self.file_path: Optional[str] = None
        self.is_modified: bool = False
        self._listeners: List[Callable[[], None]] = []

    def add_listener(self, callback: Callable[[], None]) -> None:
        """Subscribes a callback to document modification events."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[], None]) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify(self) -> None:
        self.is_modified = True
        for callback in self._listeners:
            try:
                callback()
            except Exception:
                pass

    # Stroke building lifecycle
    def start_stroke(self, tool: ToolType, color: str, thickness: float, x: float, y: float) -> Stroke:
        """Starts a new active stroke at normalized coordinates (x, y)."""
        # If an active stroke was somehow left open, finish it first
        if self.active_stroke is not None:
            self.finish_stroke()

        stroke = Stroke(tool=tool, color=color, thickness=thickness)
        stroke.add_point(x, y)
        self.active_stroke = stroke
        self._notify()
        return stroke

    def add_point_to_active(self, x: float, y: float) -> None:
        """Adds a normalized point to the ongoing stroke with duplicate filtering."""
        if self.active_stroke is None:
            return

        # Avoid adding redundant points too close to the last one
        if self.active_stroke.points:
            last = self.active_stroke.points[-1]
            dx = (x - last.x) * self.aspect_ratio
            dy = y - last.y
            if (dx * dx + dy * dy) < 1e-6:
                return

        self.active_stroke.add_point(x, y)
        self._notify()

    def finish_stroke(self) -> Optional[Stroke]:
        """Finalizes the active stroke and registers it in the undo stack."""
        if self.active_stroke is None:
            return None

        stroke = self.active_stroke
        self.active_stroke = None

        if stroke.point_count() > 0:
            cmd = AddStrokeCommand(stroke)
            cmd.execute(self)
            self.undo_stack.append(cmd)
            self.redo_stack.clear()
            self._notify()
            return stroke
        return None

    def cancel_active_stroke(self) -> None:
        """Cancels the current stroke without adding it to history."""
        if self.active_stroke is not None:
            self.active_stroke = None
            self._notify()

    # Vector Eraser
    def erase_at(self, cx: float, cy: float, radius: float) -> int:
        """
        Removes any strokes that intersect the eraser circle at (cx, cy).
        Accounting for canvas aspect ratio to ensure uniform circular brush.
        Pushes an EraseStrokesCommand to undo history.
        """
        erased: List[Tuple[int, Stroke]] = []
        for idx, stroke in enumerate(self.strokes):
            if stroke.intersects_circle(cx, cy, radius, self.aspect_ratio):
                erased.append((idx, stroke))

        if erased:
            cmd = EraseStrokesCommand(erased)
            cmd.execute(self)
            self.undo_stack.append(cmd)
            self.redo_stack.clear()
            self._notify()
            return len(erased)
        return 0

    # Undo / Redo / Clear
    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self.redo_stack) > 0

    def undo(self) -> bool:
        if not self.can_undo():
            return False
        cmd = self.undo_stack.pop()
        cmd.undo(self)
        self.redo_stack.append(cmd)
        self._notify()
        return True

    def redo(self) -> bool:
        if not self.can_redo():
            return False
        cmd = self.redo_stack.pop()
        cmd.execute(self)
        self.undo_stack.append(cmd)
        self._notify()
        return True

    def clear(self) -> None:
        """Clears all strokes with full undo support."""
        if not self.strokes and self.active_stroke is None:
            return
        if self.active_stroke:
            self.cancel_active_stroke()
        if self.strokes:
            cmd = ClearCanvasCommand(self.strokes)
            cmd.execute(self)
            self.undo_stack.append(cmd)
            self.redo_stack.clear()
            self._notify()

    # Rendering
    def render(self, painter: QPainter, width: float, height: float, draw_active: bool = True) -> None:
        """
        Renders all strokes onto the provided QPainter scaled to (width, height).
        Applies antialiased high-quality pen styling.
        """
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        # Draw committed strokes
        for stroke in self.strokes:
            self._draw_single_stroke(painter, stroke, width, height)

        # Draw ongoing active stroke
        if draw_active and self.active_stroke is not None:
            self._draw_single_stroke(painter, self.active_stroke, width, height)

        painter.restore()

    def _draw_single_stroke(self, painter: QPainter, stroke: Stroke, width: float, height: float) -> None:
        if stroke.is_empty():
            return
        
        path = stroke.build_painter_path(width, height)
        # Stroke thickness is scaled proportionally to document width / 1920 base
        scale_factor = width / 1920.0
        pen_width = max(1.0, stroke.thickness * scale_factor)

        pen = QPen(QColor(stroke.color))
        pen.setWidthF(pen_width)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)

        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

    # Export & Persistence
    def render_to_image(self, width: int = 1920, height: int = 1080, transparent: bool = False) -> QImage:
        """Renders the document into an offscreen QImage at target pixel resolution."""
        image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
        if transparent:
            image.fill(Qt.transparent)
        else:
            image.fill(Qt.white)

        painter = QPainter(image)
        self.render(painter, float(width), float(height), draw_active=False)
        painter.end()
        return image

    def export_to_png(self, filepath: str, width: int = 1920, height: int = 1080, transparent: bool = False) -> bool:
        """Exports the document to a PNG file at clean full resolution."""
        try:
            image = self.render_to_image(width, height, transparent=transparent)
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            return image.save(filepath, "PNG")
        except Exception:
            return False

    def to_dict(self) -> dict:
        return {
            "format": "AirDrawStudio",
            "version": "1.0",
            "aspect_ratio": self.aspect_ratio,
            "strokes": [s.to_dict() for s in self.strokes],
        }

    def save_to_file(self, filepath: str) -> bool:
        """Saves document strokes to JSON project file."""
        try:
            data = self.to_dict()
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self.file_path = filepath
            self.is_modified = False
            return True
        except Exception:
            return False

    def load_from_file(self, filepath: str) -> bool:
        """Loads strokes from JSON project file."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.strokes = [Stroke.from_dict(s) for s in data.get("strokes", [])]
            self.aspect_ratio = float(data.get("aspect_ratio", 16.0 / 9.0))
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.active_stroke = None
            self.file_path = filepath
            self.is_modified = False
            self._notify()
            return True
        except Exception:
            return False
