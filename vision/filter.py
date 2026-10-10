"""
Trajectory and landmark smoothing filters for AirDraw Studio.
Implements the One Euro Filter (Casiez et al., CHI 2012) and Exponential Moving Average (EMA)
to eliminate high-frequency hand jitter while preserving zero-lag fast movements.
"""

import math
import time
from typing import Tuple, Optional


class LowPassFilter:
    def __init__(self, alpha: float = 0.5):
        self._alpha = max(0.0, min(1.0, alpha))
        self._y: Optional[float] = None
        self._s: Optional[float] = None

    def set_alpha(self, alpha: float) -> None:
        self._alpha = max(0.0, min(1.0, alpha))

    def filter(self, value: float, alpha: Optional[float] = None) -> float:
        if alpha is not None:
            self.set_alpha(alpha)
        if self._y is None:
            s = value
        else:
            s = self._alpha * value + (1.0 - self._alpha) * self._s
        self._y = value
        self._s = s
        return s

    def last_value(self) -> Optional[float]:
        return self._y

    def reset(self) -> None:
        self._y = None
        self._s = None


class OneEuroFilter1D:
    def __init__(
        self,
        freq: float = 30.0,
        min_cutoff: float = 1.0,
        beta: float = 0.007,
        d_cutoff: float = 1.0,
    ):
        self.freq = max(1e-4, freq)
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.x_filter = LowPassFilter()
        self.dx_filter = LowPassFilter()
        self.last_time: Optional[float] = None

    def _alpha(self, rate: float, cutoff: float) -> float:
        tau = 1.0 / (2.0 * math.pi * max(1e-4, cutoff))
        te = 1.0 / max(1e-4, rate)
        return 1.0 / (1.0 + tau / te)

    def filter(self, x: float, timestamp: Optional[float] = None) -> float:
        if self.last_time is not None and timestamp is not None and timestamp > self.last_time:
            self.freq = 1.0 / (timestamp - self.last_time)
        self.last_time = timestamp

        prev_x = self.x_filter.last_value()
        dx = 0.0 if prev_x is None else (x - prev_x) * self.freq
        edx = self.dx_filter.filter(dx, self._alpha(self.freq, self.d_cutoff))
        cutoff = self.min_cutoff + self.beta * abs(edx)
        return self.x_filter.filter(x, self._alpha(self.freq, cutoff))

    def reset(self) -> None:
        self.x_filter.reset()
        self.dx_filter.reset()
        self.last_time = None


class OneEuroFilter:
    """2D One Euro Filter for smoothing (x, y) coordinates."""
    def __init__(
        self,
        freq: float = 30.0,
        min_cutoff: float = 1.2,
        beta: float = 0.008,
        d_cutoff: float = 1.0,
    ):
        self.fx = OneEuroFilter1D(freq, min_cutoff, beta, d_cutoff)
        self.fy = OneEuroFilter1D(freq, min_cutoff, beta, d_cutoff)

    def filter(self, x: float, y: float, timestamp: Optional[float] = None) -> Tuple[float, float]:
        t = timestamp if timestamp is not None else time.time()
        return (self.fx.filter(x, t), self.fy.filter(y, t))

    def reset(self) -> None:
        self.fx.reset()
        self.fy.reset()


class EMAFilter2D:
    """Exponential Moving Average filter for 2D points."""
    def __init__(self, alpha: float = 0.55):
        self.alpha = max(0.01, min(0.99, alpha))
        self.last_x: Optional[float] = None
        self.last_y: Optional[float] = None

    def filter(self, x: float, y: float, timestamp: Optional[float] = None) -> Tuple[float, float]:
        if self.last_x is None or self.last_y is None:
            self.last_x = x
            self.last_y = y
            return (x, y)
        self.last_x = self.alpha * x + (1.0 - self.alpha) * self.last_x
        self.last_y = self.alpha * y + (1.0 - self.alpha) * self.last_y
        return (self.last_x, self.last_y)

    def reset(self) -> None:
        self.last_x = None
        self.last_y = None


class PointSmoother:
    """
    Coordinates calibration, horizontal mirroring, and trajectory smoothing.
    Maps camera normalized coordinates to comfortable drawing space.
    """
    def __init__(
        self,
        mode: str = "one_euro",
        margin_x: float = 0.15,
        margin_y: float = 0.15,
        mirror: bool = True,
        one_euro_min_cutoff: float = 1.2,
        one_euro_beta: float = 0.008,
        ema_alpha: float = 0.55,
    ):
        self.mode = mode
        self.margin_x = margin_x
        self.margin_y = margin_y
        self.mirror = mirror
        
        self.one_euro = OneEuroFilter(
            min_cutoff=one_euro_min_cutoff,
            beta=one_euro_beta,
        )
        self.ema = EMAFilter2D(alpha=ema_alpha)

    def reset(self) -> None:
        self.one_euro.reset()
        self.ema.reset()

    def process(self, raw_cam_x: float, raw_cam_y: float, timestamp: Optional[float] = None) -> Tuple[float, float]:
        """
        1. Horizontally mirrors camera x so moving right moves right on screen.
        2. Maps comfort margin [margin, 1-margin] to full [0, 1] canvas.
        3. Applies selected smoothing filter.
        """
        # Step 1: Mirroring
        x = (1.0 - raw_cam_x) if self.mirror else raw_cam_x
        y = raw_cam_y

        # Step 2: Margin calibration
        span_x = max(0.1, 1.0 - 2.0 * self.margin_x)
        span_y = max(0.1, 1.0 - 2.0 * self.margin_y)
        mapped_x = (x - self.margin_x) / span_x
        mapped_y = (y - self.margin_y) / span_y
        clamped_x = max(0.0, min(1.0, mapped_x))
        clamped_y = max(0.0, min(1.0, mapped_y))

        # Step 3: Smoothing
        if self.mode == "one_euro":
            return self.one_euro.filter(clamped_x, clamped_y, timestamp)
        elif self.mode == "ema":
            return self.ema.filter(clamped_x, clamped_y, timestamp)
        else:
            return (clamped_x, clamped_y)
