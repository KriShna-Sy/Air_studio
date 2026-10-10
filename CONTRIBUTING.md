# Contributing to AirDraw Studio

Thank you for your interest in contributing to **AirDraw Studio**! We welcome community contributions, bug fixes, feature enhancements, and documentation improvements.

---

## 🛠️ Development Setup

1. **Fork and clone the repository**:
   ```bash
   git clone https://github.com/your-username/AirDraw-Studio.git
   cd AirDraw-Studio
   ```

2. **Create a Python virtual environment** (Python 3.10 – 3.12 recommended):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install system dependencies** (on Ubuntu / Debian):
   ```bash
   sudo apt update
   sudo apt install -y libgl1-mesa-glx libxcb-xinerama0 v4l-utils
   ```

4. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Ensure the MediaPipe model asset exists**:
   The model `assets/hand_landmarker.task` is bundled with the repository. If needed, you can re-download it from Google Cloud Storage:
   ```bash
   curl -Lo assets/hand_landmarker.task https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task
   ```

---

## 🧪 Running Automated Tests

Before submitting any Pull Request, ensure that all unit and GUI integration tests pass:

```bash
PYTHONPATH=. python -m unittest discover tests -v
```

All 25 automated tests verify:
* Mathematical One Euro Filter jitter damping and monotonic timing.
* Geometric scale-invariant gesture classification and hysteresis cutoffs.
* Vector stroke interpolation, Bézier midpoints, and contact segment erasure.
* Command-pattern Undo/Redo stacks and serialization.
* Full touchless interaction: magnetic snapping, dwell progress, pinch triggers, and ink suppression.
* GUI window lifecycle and transparent overlay composition.

---

## 📝 Code Conventions

- **Formatting**: Adhere to [PEP 8](https://peps.python.org/pep-0008/) style guidelines.
- **CPU Efficiency**: Keep all real-time processing local and CPU-optimized. Avoid blocking the Qt main GUI loop or introducing GPU locks.
- **Type Hints & Docstrings**: Preserve explicit Python type annotations and informative docstrings.
- **Modularity**:
  - `vision/`: MediaPipe hand landmarker, V4L2 acquisition, signal filtering, and gesture recognition.
  - `drawing/`: Vector document model, Bézier stroke curves, and canvas rendering.
  - `ui/`: Floating glass HUD, cursor overlay, transparent desktop overlay, and window coordination.

---

## 🚀 Submitting a Pull Request

1. Create a descriptive feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Commit your changes with clear, semantic commit messages:
   ```bash
   git commit -m "feat(ui): add radial pie menu for quick color switching"
   ```
3. Push to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
4. Open a Pull Request against the `main` branch with a summary of changes and test results.

---

## 📄 License

By contributing, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).
