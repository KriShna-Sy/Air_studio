"""
Unit tests for OneEuroFilter, EMAFilter2D, and PointSmoother coordinate calibration.
"""

import unittest
from vision.filter import OneEuroFilter, EMAFilter2D, PointSmoother


class TestFilters(unittest.TestCase):
    def test_one_euro_filter_stability(self):
        f = OneEuroFilter(freq=30.0, min_cutoff=1.0, beta=0.007)
        # Sequence of small jitter around 0.5
        t = 0.0
        val = (0.5, 0.5)
        for i in range(10):
            t += 0.033
            jitter_x = 0.5 + (0.01 if i % 2 == 0 else -0.01)
            val = f.filter(jitter_x, 0.5, timestamp=t)
        
        # After filtering jitter, output should remain very close to 0.5
        self.assertAlmostEqual(val[0], 0.5, delta=0.02)
        self.assertAlmostEqual(val[1], 0.5, delta=0.01)

    def test_one_euro_filter_reset(self):
        f = OneEuroFilter()
        f.filter(0.1, 0.1, timestamp=0.0)
        f.reset()
        self.assertIsNone(f.fx.last_time)

    def test_point_smoother_mirror_and_margin(self):
        smoother = PointSmoother(
            mode="none",
            margin_x=0.10,
            margin_y=0.10,
            mirror=True,
        )

        # Center in camera raw space: (0.5, 0.5)
        # Mirrored x: 1.0 - 0.5 = 0.5
        # Margin mapped: (0.5 - 0.10) / (1 - 0.20) = 0.40 / 0.80 = 0.5
        mx, my = smoother.process(0.5, 0.5)
        self.assertAlmostEqual(mx, 0.5, places=5)
        self.assertAlmostEqual(my, 0.5, places=5)

        # Raw camera x = 0.9 (far right of camera image)
        # Mirrored x: 1.0 - 0.9 = 0.10 -> corresponds to left margin edge (0.0)
        mx_edge, _ = smoother.process(0.9, 0.5)
        self.assertAlmostEqual(mx_edge, 0.0, places=5)

        # Raw camera x = 0.1 (far left of camera image)
        # Mirrored x: 1.0 - 0.1 = 0.90 -> corresponds to right margin edge (1.0)
        mx_right, _ = smoother.process(0.1, 0.5)
        self.assertAlmostEqual(mx_right, 1.0, places=5)


if __name__ == "__main__":
    unittest.main()
