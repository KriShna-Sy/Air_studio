"""
Unit tests for CameraThread discovery and HandTracker initialization.
"""

import unittest
import numpy as np
from vision.hand_tracker import HandTracker
from vision.camera_thread import CameraThread


class TestVisionCamera(unittest.TestCase):
    def test_hand_tracker_init(self):
        tracker = HandTracker()
        self.assertIsNotNone(tracker.landmarker)

        # Process a blank frame
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        landmarks, tip = tracker.process_frame(blank, timestamp_ms=100)
        self.assertIsNone(landmarks)
        self.assertIsNone(tip)

        tracker.close()

    def test_camera_probe(self):
        devices = CameraThread.probe_available_cameras(max_to_scan=4)
        self.assertIsInstance(devices, list)
        print(f"Discovered camera devices in test: {devices}")


if __name__ == "__main__":
    unittest.main()
