"""
Configuration module for AirDraw Studio.
Centralizes paths, camera settings, gesture thresholds, and UI styling constants.
"""

import os
from pathlib import Path

APP_NAME = "AirDraw Studio"
APP_SUBTITLE = "Gesture-Controlled Drawing Workspace & Desktop Overlay"
APP_VERSION = "1.0.0"

# Model paths
DEFAULT_MODEL_PATH = os.path.expanduser("~/mediapipe_models/hand_landmarker.task")
ALTERNATIVE_MODEL_PATHS = [
    Path.home() / "mediapipe_models" / "hand_landmarker.task",
    Path(__file__).parent / "assets" / "hand_landmarker.task",
]

# Camera & Tracking
DEFAULT_CAMERA_INDEX = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
TARGET_FPS = 30
MAX_CAMERAS_TO_SCAN = 6

# MediaPipe HandLandmarker configuration
MIN_DETECTION_CONFIDENCE = 0.5
MIN_TRACKING_CONFIDENCE = 0.5
MIN_PRESENCE_CONFIDENCE = 0.5
NUM_HANDS = 1

# Active normalized drawing area (webcam comfort margin)
# Hand coordinates outside [margin, 1-margin] are clamped smoothly to the edge of the canvas.
ACTIVE_MARGIN_X = 0.08
ACTIVE_MARGIN_Y = 0.08

# Touchless Finger UI Interaction (Dwell & Pinch Clicking)
DWELL_CLICK_TIME = 0.50       # Seconds of hovering on a button to trigger click
PINCH_CLICK_THRESHOLD = 0.22  # Distance between index and thumb relative to palm size
MAGNETIC_SNAP_RADIUS = 40     # Pixels radius for magnetic snapping to buttons
HOVER_CLICK_HYSTERESIS = 0.20 # Cooldown seconds after click before another click triggers

# Background rendering modes (CPU-optimized)
BG_MODE_BLURRED = "blurred"       # Soft CPU frosted glass camera
BG_MODE_DIMMED = "dimmed"         # Dark-tinted camera
BG_MODE_CLEAR = "clear"           # Direct camera feed
BG_MODE_WHITE = "white"           # Solid white sheet
DEFAULT_BG_MODE = BG_MODE_BLURRED
DEFAULT_BG_OPACITY = 0.70         # Opacity of camera background
FAST_BLUR_SIZE = (240, 180)       # Downscale size for sub-millisecond CPU GaussianBlur

# Landmark smoothing parameters
SMOOTHING_MODE = "one_euro"  # "one_euro", "ema", or "none"
ONE_EURO_MIN_CUTOFF = 1.2    # Lower = smoother at low speeds (Hz)
ONE_EURO_BETA = 0.008        # Higher = less lag during fast movements
ONE_EURO_D_CUTOFF = 1.0      # Derivative cutoff (Hz)
EMA_ALPHA = 0.55             # Exponential moving average factor if chosen

# Gesture hysteresis & stability
GESTURE_ENTER_DRAW_FRAMES = 2    # Consecutive frames needed to start drawing
GESTURE_EXIT_DRAW_FRAMES = 1     # Immediate cutoff when finger folds to prevent ink drag
GESTURE_FIST_CONFIRM_FRAMES = 2  # Consecutive frames to register stop/fist

# Drawing presets
DEFAULT_PEN_COLOR = "#2563EB"    # Classic royal blue
DEFAULT_PEN_THICKNESS = 6.0
DEFAULT_ERASER_RADIUS = 24.0
MIN_PEN_THICKNESS = 1.0
MAX_PEN_THICKNESS = 40.0

PRESET_COLORS = [
    ("#0F172A", "Slate Black"),
    ("#DC2626", "Crimson Red"),
    ("#EA580C", "Vibrant Orange"),
    ("#F59E0B", "Amber Yellow"),
    ("#16A34A", "Forest Green"),
    ("#06B6D4", "Cyan"),
    ("#2563EB", "Royal Blue"),
    ("#7C3AED", "Electric Purple"),
    ("#DB2777", "Deep Pink"),
    ("#FFFFFF", "White"),
]

THICKNESS_PRESETS = [2.0, 4.0, 6.0, 10.0, 16.0, 24.0]

# Virtual Document Canvas
CANVAS_INTERNAL_WIDTH = 1920
CANVAS_INTERNAL_HEIGHT = 1080
CANVAS_ASPECT_RATIO = 16.0 / 9.0  # W / H

# Ribbon & Theme Colors (Inspired by Microsoft Word Fluent Design)
THEME_PRIMARY = "#0078D4"       # Office 365 Blue
THEME_PRIMARY_HOVER = "#106EBE"
THEME_PRIMARY_LIGHT = "#EFF6FC"
THEME_WORKSPACE_BG = "#F1F5F9"   # Modern slate background
THEME_CANVAS_BORDER = "#CBD5E1"
THEME_PANEL_BG = "#FFFFFF"
THEME_TEXT_PRIMARY = "#1E293B"
THEME_TEXT_MUTED = "#64748B"

# Gesture status badge colors
GESTURE_COLORS = {
    "DRAW": "#16A34A",         # Green
    "MOVE_CURSOR": "#2563EB",  # Blue
    "STOP": "#DC2626",         # Red
    "IDLE": "#64748B",         # Slate / gray
    "ERROR": "#D97706",        # Amber
}

GESTURE_LABELS = {
    "DRAW": "DRAWING (Index Finger)",
    "MOVE_CURSOR": "CURSOR MOVEMENT (Open Palm)",
    "STOP": "FIST / STOPPED",
    "IDLE": "IDLE / NO HAND",
    "ERROR": "CAMERA ERROR",
}
