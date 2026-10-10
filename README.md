# AirDraw Studio 🎨🖐️

[![Python 3.10+](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![PyQt5](https://img.shields.io/badge/GUI-PyQt5-green.svg)](https://pypi.org/project/PyQt5/)
[![MediaPipe Tasks](https://img.shields.io/badge/Vision-MediaPipe%20Tasks-orange.svg)](https://developers.google.com/mediapipe)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.x-red.svg)](https://opencv.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests: 25 Passing](https://img.shields.io/badge/Tests-25%20Passed-brightgreen.svg)]()

> **Gesture-Controlled Real-Time Drawing Workspace and Transparent Desktop Overlay for Linux/Ubuntu.**  
> Completely touchless and mouse-free. Draw in the air with your index finger, navigate floating options by hand, and trigger selections with a pinch or dwell.

---

## 🌟 Overview

**AirDraw Studio** turns any standard webcam into a high-precision, low-latency spatial drawing instrument. Built from the ground up for modern Linux desktop environments, it leverages Google's **MediaPipe Tasks Vision API** (`HandLandmarker` in video streaming mode) and **PyQt5** to provide a fluid, 100% mouse-free creative experience.

Unlike conventional webcam drawing prototypes, AirDraw Studio operates on **pure CPU** with zero GPU bottlenecks, projects the user softly into the background canvas, floats a translucent glass HUD on top of the view, and introduces **magnetic target snapping** with tactile **"BOOM!"** selection triggers (pinch or dwell).

---

## ✨ Key Features

### 1. 🪟 Dual Operating Modes
* **Mode A — Floating Glass Workspace**: Full-screen virtual drawing paper with your live webcam feed softly blurred into the background on CPU (0.54ms per frame). A floating translucent glass toolbar sits seamlessly on top of the canvas—leaving 100% of the screen available for drawing.
* **Mode B — Desktop Drawing Overlay**: True per-pixel transparent (`Qt.WA_TranslucentBackground`) full-screen overlay over your actual desktop windows, IDE, browser, or terminal. Draw annotations directly over active applications. Includes a glassmorphic HUD and a toggleable **Click-Through mode (`T`)**.
* **Unified Document Model**: Strokes, active tools, colors, brush thickness, and Undo/Redo histories are seamlessly shared between Workspace and Desktop Overlay modes.

### 2. 🖐️ 100% Touchless Hand Navigation & "BOOM!" Selection
* **Zero Mouse Dependency**: You never need to touch a mouse or keyboard.
* **🎯 Magnetic Target Snapping**: As your hand approaches any toolbar button, color gem, or tool (within 40px), focus automatically snaps and locks onto that button, eliminating jitter or hand tremor.
* **💥 "BOOM!" Selection Triggers**:
  * **Pinch Click**: Bring your thumb and index fingertip together for an instant selection.
  * **Dwell Click (`0.50s`)**: Rest your finger over any button to fill a bright cyan radial progress gauge around your cursor.
* **Tri-Feedback Confirmation**: Every selection provides immediate multi-sensory feedback:
  1. 🔊 **Audio Chime**: Audible click confirmation via `QApplication.beep()`.
  2. 💥 **Shockwave Ripple**: An expanding neon ripple ring bursts from the button center.
  3. 📋 **Floating Toast Badge**: A non-modal glass notification pills up (e.g. `✓ Tool: Eraser`, `✓ Color: Royal Blue`, `✓ Canvas Cleared`).
* **🚫 Zero Modal Windows**: No blocking OS popups (`QFileDialog`, `QColorDialog`, `QMessageBox`). Clear canvas is a safe two-step in-place confirmation, and PNG exports save directly to `~/Pictures` with one touch.

### 3. ⚡ Ultra-Low CPU Utilization (Zero GPU Locks)
* **CPU XNNPACK Delegate**: MediaPipe inference runs entirely on CPU cores, avoiding GPU driver locks, Wayland buffer stalls, or VRAM contention.
* **Sub-Millisecond Background Blur**: Live mirror frames are downscaled and filtered via OpenCV Gaussian blur in **0.54 ms per frame**.
* **Monotonic High-Precision Timing**: MediaPipe video-mode timestamps increase monotonically, preventing timestamp jitter and inference drops.
* **One Euro Filter**: Mathematical dual-cutoff adaptive filter (Casiez et al., CHI 2012) damps micro-tremors during slow aiming while introducing zero lag during fast strokes.

### 4. 🖌️ Vector Drawing Engine
* **Midpoint Quadratic Bézier Interpolation**: Smooths raw fingertip sample points into continuous curves without gaps or angular zig-zags.
* **Vector Contact Eraser**: Sweeps a circular radius across existing vector segments, slicing or deleting intersecting strokes with full undo support.
* **10 Preset Colors + Quick Thicknesses**: Black, Blue, Cyan, Green, Amber, Red, Purple, White, and discrete touchless sizes (`2px`, `6px`, `12px`, `24px`).

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    Cam[Webcam V4L2 /dev/videoX] -->|Raw BGR Frame| Worker[CameraThread QThread]
    
    subgraph Vision Pipeline (CPU)
        Worker -->|Downscale + GaussianBlur 0.54ms| CPU_BG[Live Blurred Background]
        Worker -->|RGB + Monotonic Timestamp| MP[MediaPipe HandLandmarker Video Mode]
        MP -->|21 3D Landmarks| Norm[Scale-Invariant Landmark Normalizer]
        Norm -->|Palm Wrist-to-MCP Metric| Pose[Geometric Gesture Classifier]
        Norm -->|Fingertip Coordinates| Smoother[One Euro Filter / Margins]
        Norm -->|Index + Thumb Distance| Pinch[Pinch Detector]
    end

    Smoother -->|nx, ny| Coord[MainWindow / Overlay Coordinator]
    Pose -->|DRAW / CURSOR / STOP / IDLE| Coord
    Pinch -->|is_pinched| Coord
    CPU_BG -->|QImage Background| Canvas[CanvasWidget QPainter]

    subgraph Touchless UI & Drawing
        Coord -->|Proximity Check <40px| Magnet[Magnetic Snapping]
        Magnet -->|Hover Dwell 0.5s or Pinch| Boom[BOOM! Trigger + Audio Beep + Ripple]
        Boom -->|Actions| Tools[Floating Glass Toolbar]
        Coord -->|Air Cursor Coordinates| OverlayLayer[CursorOverlay Top-Level Widget]
        Coord -->|Drawing Points| Doc[Vector Document Model & Undo Stack]
        Doc -->|Bézier Curves| Canvas
    end
```

---

## 🖐️ Gesture Recognition Matrix

| Gesture | Hand Pose | Action | Visual Status Indicator |
| :---: | :---: | :--- | :---: |
| **DRAW** | ☝️ **Index finger extended**, others folded | Draws smooth vector strokes following fingertip | 🟢 `DRAWING` (Green pill) |
| **MOVE CURSOR** | 🖐️ **Open palm**, all 5 fingers extended | Moves the air crosshair cursor without leaving ink | 🔵 `MOVE CURSOR` (Blue pill) |
| **STOP / FIST** | ✊ **Closed fist**, all fingers clenched | Immediately freezes drawing, preserves existing strokes | 🔴 `STOP` (Red pill) |
| **PINCH CLICK** | 🤏 **Thumb + Index tips touching** | Instant "BOOM!" selection on any hovered button/color | 🟢 Green pulse ring |
| **DWELL CLICK** | ⏳ **Finger resting over button for 0.5s** | Fills electric progress ring, then "BOOM!" triggers action | 💠 Cyan radial arc |
| **IDLE** | ✋ **No hand detected / tracking lost** | Safely terminates active stroke with zero stray marks | ⚪ `IDLE / NO HAND` (Gray pill) |

---

## ⌨️ Shortcuts & Air Controls

| Input / Gesture | Context | Action |
| :--- | :--- | :--- |
| **Dwell (0.50s)** | Touchless HUD | Triggers hover-click on focused tool, color, or exit button |
| **Pinch (Thumb+Index)** | Touchless HUD | Instantly triggers click on focused tool without waiting |
| `F9` | Global | **Toggle Drawing Mode** (Workspace $\leftrightarrow$ Desktop Overlay) |
| `F11` | Workspace | **Toggle Fullscreen Mode** |
| `Esc` | Overlay | **Exit Desktop Overlay** and return to Workspace |
| `T` | Overlay | **Toggle Click-Through Mode** (pass mouse events to desktop apps) |
| `Ctrl + Z` | Any | Undo last stroke |
| `Ctrl + Y` | Any | Redo last stroke |
| `Ctrl + S` / `Ctrl + E` | Workspace | Quick export canvas to `~/Pictures/AirDraw_<timestamp>.png` |
| `Ctrl + N` | Workspace | Clear canvas and start fresh document |
| `C` | Overlay | Clear all overlay strokes |
| `E` | Overlay | Toggle Pen / Eraser tool |

---

## 🚀 Getting Started

### Prerequisites

* **Operating System**: Ubuntu 20.04+, Debian 11+, or any modern Linux distribution with an X11 or Wayland desktop session.
* **Python**: Python 3.10, 3.11, or 3.12.
* **Webcam**: Standard USB or integrated UVC webcam (`/dev/video0`).

### 1. Install System Dependencies

On Ubuntu / Debian:

```bash
sudo apt update
sudo apt install -y python3-venv libgl1-mesa-glx libxcb-xinerama0 v4l-utils
```

### 2. Clone the Repository

```bash
git clone https://github.com/your-username/AirDraw-Studio.git
cd AirDraw-Studio
```

### 3. Set Up Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. MediaPipe Model Asset

The required Google MediaPipe model (`assets/hand_landmarker.task`) is pre-bundled in the repository. If you ever need to restore or update it:

```bash
curl -Lo assets/hand_landmarker.task https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task
```

### 5. Launch the Application

```bash
python main.py
```

---

## ⚙️ CLI Options

```bash
# Launch with a specific camera index (e.g. external USB camera at index 1)
python main.py --camera 1

# Launch directly into full-screen transparent Desktop Overlay mode
python main.py --overlay

# Run self-diagnostic headless verification
python main.py --test-headless
```

---

## 🧪 Automated Testing

AirDraw Studio includes an extensive test suite covering unit math, signal filters, geometric classification, touchless interaction, and GUI lifecycles:

```bash
PYTHONPATH=. python -m unittest discover tests -v
```

```
test_clear_canvas_and_undo (tests.test_document.TestDocument) ................... ok
test_json_project_persistence (tests.test_document.TestDocument) ............... ok
test_png_export (tests.test_document.TestDocument) ............................. ok
test_stroke_creation_and_finish (tests.test_document.TestDocument) ............. ok
test_undo_and_redo_stroke (tests.test_document.TestDocument) ................... ok
test_vector_eraser_and_undo (tests.test_document.TestDocument) ................. ok
test_end_to_end_gesture_drawing_pipeline (tests.test_end_to_end_gestures) ...... ok
test_one_euro_filter_reset (tests.test_filters.TestFilters) .................... ok
test_one_euro_filter_stability (tests.test_filters.TestFilters) ................ ok
test_point_smoother_mirror_and_margin (tests.test_filters.TestFilters) ......... ok
test_draw_gesture_raw (tests.test_gestures.TestGestureRecognizer) .............. ok
test_empty_landmarks_return_idle (tests.test_gestures.TestGestureRecognizer) ... ok
test_hysteresis_enter_draw (tests.test_gestures.TestGestureRecognizer) ......... ok
test_idle_or_uncertain_gesture_raw (tests.test_gestures.TestGestureRecognizer) .. ok
test_instant_exit_from_draw (tests.test_gestures.TestGestureRecognizer) ........ ok
test_move_cursor_gesture_raw (tests.test_gestures.TestGestureRecognizer) ....... ok
test_stop_gesture_raw (tests.test_gestures.TestGestureRecognizer) .............. ok
test_workspace_and_overlay_lifecycle (tests.test_gui_integration) .............. ok
test_magnetic_snap_and_dwell_click (tests.test_touchless_interaction) .......... ok
test_pinch_click_immediate_trigger (tests.test_touchless_interaction) .......... ok
test_toolbar_hover_inhibits_ink (tests.test_touchless_interaction) ............. ok
test_touchless_clear_canvas_two_step (tests.test_touchless_interaction) ........ ok
test_touchless_color_selection (tests.test_touchless_interaction) .............. ok
test_camera_probe (tests.test_vision_camera.TestVisionCamera) .................. ok
test_hand_tracker_init (tests.test_vision_camera.TestVisionCamera) ............. ok
----------------------------------------------------------------------
Ran 25 tests in 7.523s — OK
```

---

## 📂 Project Structure

```
AirDraw_Studio/
├── assets/
│   └── hand_landmarker.task     # Google MediaPipe Vision model asset (7.5 MB)
├── drawing/
│   ├── __init__.py
│   ├── stroke.py                # Vector Stroke & StrokePoint with Bézier interpolation
│   ├── document.py              # Single source of truth: Command Undo/Redo & PNG export
│   └── canvas.py                # Full-screen CanvasWidget with CPU blurred background
├── vision/
│   ├── __init__.py
│   ├── filter.py                # One Euro Filter & active margin coordinate calibrator
│   ├── gesture_recognizer.py    # Scale-invariant geometric finger classifier & hysteresis
│   ├── hand_tracker.py          # MediaPipe Tasks HandLandmarker wrapper (VIDEO mode)
│   └── camera_thread.py         # Dedicated QThread capture loop & 0.54ms CPU blur
├── ui/
│   ├── __init__.py
│   ├── floating_toolbar.py      # Floating translucent glass HUD & touchless controls
│   ├── cursor_overlay.py        # Top-level overlay: air cursor, dwell arc, shockwave ripple, toasts
│   ├── overlay_window.py        # Mode B: Per-pixel transparent desktop overlay window
│   ├── ribbon.py                # Office 365 classic ribbon interface (optional view)
│   ├── camera_panel.py          # Dockable live camera diagnostics & device picker
│   └── main_window.py           # Application coordinator & touchless magnetic snapping
├── tests/
│   ├── test_document.py
│   ├── test_end_to_end_gestures.py
│   ├── test_filters.py
│   ├── test_gestures.py
│   ├── test_gui_integration.py
│   ├── test_touchless_interaction.py
│   └── test_vision_camera.py
├── config.py                    # Centralized settings, thresholds, colors, and timings
├── main.py                      # Application entry point with CLI parser & High-DPI support
├── requirements.txt             # Verified Python dependencies
├── CONTRIBUTING.md              # Open source contribution guidelines
├── LICENSE                      # MIT Open Source License
└── README.md                    # Project documentation
```

---

## 🔧 Troubleshooting & Linux Notes

### 1. Camera Access (`Device busy` or Permission Denied)
If the camera fails to initialize, ensure your Linux user belongs to the `video` group:
```bash
sudo usermod -a -G video $USER
```
*(Log out and back in for permissions to take effect).* To check connected video devices:
```bash
v4l2-ctl --list-devices
```

### 2. Qt Platform & OpenCV Plugin Isolation
Some system OpenCV builds override `QT_QPA_PLATFORM_PLUGIN_PATH` to point to a minimal OpenCV Qt plugin directory lacking `libqxcb.so`. AirDraw Studio automatically sanitizes the environment before Qt initialization to ensure the correct PyQt5 XCB platform plugins are loaded seamlessly.

### 3. Transparent Overlay on Wayland vs X11
Mode B leverages per-pixel alpha composition (`Qt.WA_TranslucentBackground`).
* On **X11**, any standard compositor (`picom`, Mutter, KWin, Compiz) provides instantaneous transparent composition.
* On **Wayland**, translucent composition is supported natively by Mutter (GNOME) and KWin (KDE). If you experience opaque window borders in custom tiled window managers, launch with `QT_QPA_PLATFORM=xcb python main.py`.

---

## 📜 License

This project is open-source software licensed under the **[MIT License](LICENSE)**.

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](https://github.com/your-username/AirDraw-Studio/issues) or read [CONTRIBUTING.md](CONTRIBUTING.md) to get started.
