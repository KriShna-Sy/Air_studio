"""
Stroke and Tool data models for AirDraw Studio.
Stores vector stroke points in normalized canvas coordinates [0.0, 1.0].
"""

import math
import time
from enum import Enum
from typing import List, Tuple, Dict, Any, Optional
from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QPainterPath, QColor, QPen


class ToolType(str, Enum):
    PEN = "pen"
    ERASER = "eraser"


class StrokePoint:
    __slots__ = ("x", "y", "timestamp")

    def __init__(self, x: float, y: float, timestamp: Optional[float] = None):
        self.x = float(x)
        self.y = float(y)
        self.timestamp = timestamp if timestamp is not None else time.time()

    def to_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)

    def to_dict(self) -> Dict[str, Any]:
        return {"x": self.x, "y": self.y, "timestamp": self.timestamp}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrokePoint":
        return cls(x=data["x"], y=data["y"], timestamp=data.get("timestamp"))


def _dist_point_to_segment(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    """Calculates Euclidean distance from point (px, py) to line segment (x1, y1)-(x2, y2)."""
    dx = x2 - x1
    dy = y2 - y1
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq < 1e-12:
        return math.hypot(px - x1, py - y1)
    
    # Project point onto segment
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / seg_len_sq))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)


class Stroke:
    def __init__(
        self,
        tool: ToolType = ToolType.PEN,
        color: str = "#2563EB",
        thickness: float = 6.0,
        points: Optional[List[StrokePoint]] = None,
    ):
        self.tool = tool
        self.color = color
        self.thickness = float(thickness)
        self.points: List[StrokePoint] = points if points is not None else []
        self._cached_path: Optional[QPainterPath] = None
        self._cache_scale: Optional[Tuple[float, float]] = None

    def add_point(self, x: float, y: float, timestamp: Optional[float] = None) -> None:
        """Adds a normalized point [0.0, 1.0] to the stroke."""
        self.points.append(StrokePoint(x, y, timestamp))
        self._cached_path = None  # Invalidate cache

    def point_count(self) -> int:
        return len(self.points)

    def is_empty(self) -> bool:
        return len(self.points) == 0

    def intersects_circle(self, cx: float, cy: float, radius: float, aspect_ratio: float = 16.0 / 9.0) -> bool:
        """
        Tests if this stroke passes within normalized radius of (cx, cy).
        Accounting for canvas aspect ratio so circle is not distorted into an ellipse.
        """
        if len(self.points) == 0:
            return False
        
        # Single point test
        if len(self.points) == 1:
            dx = (self.points[0].x - cx) * aspect_ratio
            dy = self.points[0].y - cy
            return math.hypot(dx, dy) <= radius

        # Segment tests
        for i in range(len(self.points) - 1):
            p1 = self.points[i]
            p2 = self.points[i + 1]
            # Scale x by aspect ratio for isotropic metric
            dist = _dist_point_to_segment(
                cx * aspect_ratio, cy,
                p1.x * aspect_ratio, p1.y,
                p2.x * aspect_ratio, p2.y
            )
            if dist <= radius:
                return True
        return False

    def build_painter_path(self, width: float, height: float) -> QPainterPath:
        """
        Constructs a smoothed QPainterPath scaled to target pixel dimensions.
        Uses midpoint quadratic Bezier spline interpolation to prevent polygonal jaggedness.
        """
        if self._cached_path is not None and self._cache_scale == (width, height):
            return self._cached_path

        path = QPainterPath()
        if not self.points:
            self._cached_path = path
            self._cache_scale = (width, height)
            return path

        pts = [QPointF(p.x * width, p.y * height) for p in self.points]

        if len(pts) == 1:
            # Single tap dot: draw tiny line or circle
            p = pts[0]
            path.moveTo(p.x(), p.y())
            path.lineTo(p.x() + 0.1, p.y() + 0.1)
        elif len(pts) == 2:
            path.moveTo(pts[0])
            path.lineTo(pts[1])
        else:
            path.moveTo(pts[0])
            for i in range(1, len(pts) - 1):
                p_curr = pts[i]
                p_next = pts[i + 1]
                mid_x = (p_curr.x() + p_next.x()) * 0.5
                mid_y = (p_curr.y() + p_next.y()) * 0.5
                path.quadTo(p_curr, QPointF(mid_x, mid_y))
            # Line to last point
            path.lineTo(pts[-1])

        self._cached_path = path
        self._cache_scale = (width, height)
        return path

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool.value,
            "color": self.color,
            "thickness": self.thickness,
            "points": [p.to_dict() for p in self.points],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Stroke":
        pts = [StrokePoint.from_dict(p) for p in data.get("points", [])]
        tool_val = data.get("tool", ToolType.PEN.value)
        return cls(
            tool=ToolType(tool_val) if tool_val in [t.value for t in ToolType] else ToolType.PEN,
            color=data.get("color", "#2563EB"),
            thickness=float(data.get("thickness", 6.0)),
            points=pts,
        )
