"""
Drawing package for AirDraw Studio.
Provides stroke models, document state management, undo/redo history,
and the virtual canvas widget.
"""

from .stroke import Stroke, StrokePoint, ToolType
from .document import Document
from .canvas import CanvasWidget

__all__ = ["Stroke", "StrokePoint", "ToolType", "Document", "CanvasWidget"]
