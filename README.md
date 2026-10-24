# VisionGuard AI
Real-Time Drowsiness Detection System

**Author / Maintainer:** Neelam Mahajan

---

VisionGuard AI is an educational Python computer-vision application that monitors
eye activity from a webcam in real time. It uses MediaPipe Face Mesh to locate
eye landmarks on each frame, calculates the Eye Aspect Ratio (EAR), and displays
an on-screen warning and plays an audible alarm when the measured EAR remains below
the calibrated threshold for a configured duration.

> **Safety disclaimer:** VisionGuard AI is an educational prototype. It is not a
> certified medical device or driving-safety system. Eye closure alone does not
> reliably establish a person's level of alertness. Lighting conditions, glasses,
> camera angle, and individual facial differences all affect measurement accuracy.
> Do not rely on this application as the sole means of determining alertness.

---

## Features

- Live webcam preview with eye-corner landmark markers
- Real-time EAR display with Awake / Calibrating / DROWSY status overlay
- Automatic open-eye baseline calibration on startup
- Keyboard recalibration at any time (`C` key)
- Configurable EAR threshold (automatic or fixed via `--threshold`)
- Time-based closure detection (seconds, not frame count) for consistent
  behaviour across different frame rates
- Optional WAV alarm on Windows (uses the standard-library `winsound` module;
  no extra audio package is required)
- Clean application exit (`Q` key)

---

## Technology Stack

| Component              | Package          | Version used |
|------------------------|------------------|--------------|
| Face landmark detection | `mediapipe`      | 0.10.x       |
| Video capture / render | `opencv-python`  | 4.x / 5.x   |
| Numerical operations   | `numpy`          | 1.26.x       |
| Audio alert (Windows)  | `winsound`       | stdlib       |

Python 3.11 is recommended. Python 3.10 should also work.

---

## Prerequisites

- Windows 10 or 11  
  (the audible alarm uses `winsound`, which is Windows-only; the video detector
  runs on macOS and Linux but the alarm is silently skipped on those platforms)
- Python 3.10 or 3.11 installed and on `PATH`
- A working webcam and operating-system permission to access it
- PowerShell (pre-installed on Windows)

---

## Installation

### 1. Get the project

Clone or download this repository, then open PowerShell **inside the
`VisionGuard AI` folder**:

```powershell
cd "VisionGuardAI-Release"
```

### 2. Create a virtual environment

```powershell
python -m venv .venv
```

### 3. Activate the virtual environment

```powershell
.\.venv\Scripts\Activate.ps1
```

If execution policy blocks the script, run this once first:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

You should see `(.venv)` at the start of your prompt when the environment is active.

### 4. Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The `requirements-no-audio.txt` file contains the same three packages (the
current version uses only stdlib audio, so both files are equivalent).

---

## Running the Application

```powershell
python visionguard.py
```

**On first launch:**

1. Look at the camera with your eyes open and relaxed.
2. The application collects 50 frames to build your personal open-eye baseline.
3. Once calibration completes, the status changes to **Awake** and detection is active.

**Keyboard controls:**

| Key | Action |
|-----|--------|
| `Q` | Quit the application |
| `C` | Recalibrate (rebuild the open-eye baseline) |

---

## Command-Line Options

```powershell
python visionguard.py --help
```

| Option              | Default | Description                                            |
|---------------------|---------|--------------------------------------------------------|
| `--calib-frames N`  | `50`    | Frames used to build the open-eye baseline             |
| `--threshold X`     | auto    | Fixed EAR threshold; skips automatic calibration       |
| `--closure-seconds N` | `1.0` | Continuous eye-closure seconds before the alert fires  |
| `--no-sound`        | off     | Disable the WAV alarm                                  |
| `--camera N`        | `0`     | Webcam index (0 is the default built-in camera)        |

**Examples:**

```powershell
# Fixed threshold with 2-second closure window
python visionguard.py --threshold 0.22 --closure-seconds 2.0

# Silent mode on an external USB camera
python visionguard.py --no-sound --camera 1

# Faster calibration (30 frames instead of 50)
python visionguard.py --calib-frames 30
```

---

## How It Works

1. OpenCV opens the webcam and reads frames continuously.
2. Each frame is converted to RGB and passed to MediaPipe Face Mesh.
3. Face Mesh returns 478 normalised 3-D landmarks. Six landmarks per eye are selected.
4. The **Eye Aspect Ratio (EAR)** is calculated for each eye and averaged:

   ```
   EAR = (vertical_dist_1 + vertical_dist_2) / (2 * horizontal_dist)
   ```

5. EAR values are smoothed with a 5-frame rolling average to reduce jitter.
6. During calibration the median EAR is recorded; the detection threshold is set
   to 78 % of that baseline.
7. When EAR remains below the threshold for `--closure-seconds` continuously,
   status changes to **DROWSY** and the alarm plays once per closure event.
8. When EAR rises back above the threshold, the timer resets and the state
   returns to **Awake**.

---

## Troubleshooting

### Webcam will not open

- Close Zoom, Teams, OBS, or any other application that may have locked the camera.
- Try a different camera index: `python visionguard.py --camera 1`
- On Windows, check *Settings > Privacy & Security > Camera >
  Allow apps to access your camera*.

### Alarm does not play

- Confirm that `sound/alarm.wav` exists inside the project folder.
- Make sure you have not accidentally passed `--no-sound`.
- The alarm is Windows-only; on macOS/Linux it is silently skipped.

### Too many false alerts

- Increase `--closure-seconds` (e.g., `2.0` or `2.5`).
- Press `C` to recalibrate in better lighting.
- Move the camera closer to eye level.

### Not sensitive enough

- Decrease `--closure-seconds`.
- Override the threshold: `--threshold 0.24`.

### ImportError: No module named 'mediapipe' or 'cv2'

The virtual environment is probably not active:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### High CPU usage

Reduce the camera resolution in `visionguard_ai.py` — search for
`CAP_PROP_FRAME_WIDTH` and lower the value (e.g., `320`).

---

## Project Structure

```
VisionGuard AI/
├── visionguard.py           # Entry point — run this file
├── visionguard_ai.py        # Core detection implementation (imported by visionguard.py)
├── requirements.txt         # Python dependencies
├── requirements-no-audio.txt
├── .gitignore
├── README.md
└── sound/
    └── alarm.wav            # WAV file played when drowsiness is detected
```

The `.venv/` directory is created locally during setup and is excluded from
version control by `.gitignore`.

---

## Limitations

- Audible alerts are **Windows-only**; video detection is cross-platform.
- Accuracy degrades under low light, with large head angles, or with
  thick-framed glasses.
- The EAR threshold is person-specific; different users should recalibrate.
- EAR cannot distinguish voluntary blinks from involuntary eye closure.
- This is an educational project and has not been validated against any clinical
  or safety standard.

---

## Quick-Start Reference

```powershell
cd "VisionGuardAI-Release"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python visionguard.py
```
