#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
VisionGuard AI — eye-based drowsiness detector using MediaPipe + OpenCV.

Adapted from the open-source "Drowsiness Detector (Beginner-Friendly)" project.
Original source: https://github.com/[ORIGINAL_REPO_URL_NEEDED]
Modifications by Neelam Mahajan: switched from frame-count to time-based
closure detection, replaced winsound.Beep with a WAV alarm file, and added
the --closure-seconds CLI argument.

Controls:
  Q  -> quit
  C  -> recalibrate (learn baseline EAR again)

CLI options:
  --calib-frames N     number of frames for baseline (default 50)
  --threshold X        override auto threshold (float)
  --closure-seconds N  closed-eye duration to trigger (default 1.0)
  --no-sound           disable alarm
  --camera N           webcam index (default 0)
"""

import argparse
import time
from collections import deque
from pathlib import Path

import numpy as np
import cv2

try:
    import mediapipe as mp
except Exception as e:
    raise SystemExit(
        "Failed to import mediapipe. Install it with:\n"
        "python -m pip install mediapipe\n"
        + str(e)
    )

# ------- Eye landmark indices for MediaPipe Face Mesh --------

# Left eye (on the image, it's the right side of your face)
LEFT = dict(
    corner_left=33,
    corner_right=133,
    upper1=159,
    lower1=145,
    upper2=158,
    lower2=153
)

# Right eye
RIGHT = dict(
    corner_left=362,
    corner_right=263,
    upper1=386,
    lower1=374,
    upper2=385,
    lower2=380
)


def euclid(a, b):
    """Return the Euclidean distance between two 2-D points."""
    return float(np.hypot(a[0] - b[0], a[1] - b[1]))


def eye_aspect_ratio(landmarks_px, eye_idx):
    """
    Calculate Eye Aspect Ratio (EAR) for one eye.

    EAR = (||p2 - p6|| + ||p3 - p5||) / (2 * ||p1 - p4||)
    where p1/p4 are the horizontal corners and p2/p3/p5/p6 are vertical points.
    """
    p1 = landmarks_px[eye_idx["corner_left"]]
    p4 = landmarks_px[eye_idx["corner_right"]]
    p2 = landmarks_px[eye_idx["upper1"]]
    p6 = landmarks_px[eye_idx["lower1"]]
    p3 = landmarks_px[eye_idx["upper2"]]
    p5 = landmarks_px[eye_idx["lower2"]]

    horiz = euclid(p1, p4)
    vert1 = euclid(p2, p6)
    vert2 = euclid(p3, p5)

    if horiz <= 1e-6:
        return 0.0

    return (vert1 + vert2) / (2.0 * horiz)


def draw_status(frame, text, ear, color=(0, 255, 0)):
    """Overlay a status banner and current EAR value onto *frame* in-place."""
    h, w = frame.shape[:2]

    cv2.rectangle(
        frame,
        (10, 10),
        (w - 10, 90),
        (0, 0, 0),
        thickness=-1
    )

    cv2.putText(
        frame,
        f"Status: {text}",
        (20, 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        color,
        2,
        cv2.LINE_AA
    )

    cv2.putText(
        frame,
        f"EAR: {ear:.3f}",
        (20, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (200, 200, 200),
        2,
        cv2.LINE_AA
    )


def play_alarm(enable=True):
    """Play the WAV warning using the Windows built-in winsound module.

    Silently skips on non-Windows platforms or when *enable* is False.
    Audio failures never crash the detection loop.
    """
    if not enable:
        return

    try:
        import winsound
        alarm_path = Path(__file__).parent / "sound" / "alarm.wav"
        winsound.PlaySound(
            str(alarm_path),
            winsound.SND_FILENAME | winsound.SND_ASYNC
        )
    except Exception as e:
        print(f"Could not play alarm sound: {e}")


def main():
    """Entry point: parse arguments and run the detection loop."""
    ap = argparse.ArgumentParser(
        prog="visionguard",
        description="VisionGuard AI: real-time eye-based drowsiness detector"
    )

    ap.add_argument(
        "--calib-frames",
        type=int,
        default=50,
        help="frames used to learn open-eye baseline (default: 50)"
    )

    ap.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="fixed EAR threshold; skips automatic calibration"
    )

    ap.add_argument(
        "--closure-seconds",
        type=float,
        default=1.0,
        help="closed-eye duration in seconds before alert (default: 1.0)"
    )

    ap.add_argument(
        "--no-sound",
        action="store_true",
        help="disable the audible alarm"
    )

    ap.add_argument(
        "--camera",
        type=int,
        default=0,
        help="camera index (default: 0)"
    )

    args = ap.parse_args()

    if args.calib_frames < 1:
        ap.error("--calib-frames must be at least 1")
    if args.closure_seconds <= 0:
        ap.error("--closure-seconds must be greater than 0")

    mp_face_mesh = mp.solutions.face_mesh

    face_mesh = mp_face_mesh.FaceMesh(
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )

    cap = cv2.VideoCapture(args.camera)

    # Set a reasonable resolution for speed and display clarity
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)

    if not cap.isOpened():
        face_mesh.close()
        raise SystemExit(
            "Could not open camera. Try a different --camera index, "
            "or close other applications that may be using the webcam."
        )

    baseline_samples = []
    threshold = args.threshold
    calibrated = threshold is not None
    closed_since = None
    alert_active = False

    # Rolling smoothing window for EAR to reduce jitter
    ear_history = deque(maxlen=5)

    print("VisionGuard AI: press 'C' to recalibrate or 'Q' to quit.")

    try:
        while True:
            ok, frame = cap.read()

            if not ok:
                print("Could not read a frame from the camera.")
                break

            # Convert to RGB for MediaPipe
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res = face_mesh.process(rgb)

            h, w = frame.shape[:2]
            ear = None
            status_color = (0, 165, 255)

            if res.multi_face_landmarks:
                face = res.multi_face_landmarks[0]

                # Convert normalised landmarks to pixel coordinates
                lm = [
                    (int(p.x * w), int(p.y * h))
                    for p in face.landmark
                ]

                left_ear = eye_aspect_ratio(lm, LEFT)
                right_ear = eye_aspect_ratio(lm, RIGHT)

                ear = (left_ear + right_ear) / 2.0
                ear_history.append(ear)
                ear_smoothed = float(np.mean(ear_history))

                # Auto-calibration: collect open-eye EAR samples
                if not calibrated:
                    if len(baseline_samples) < args.calib_frames:
                        baseline_samples.append(ear_smoothed)

                        draw_status(
                            frame,
                            f"Calibrating... {len(baseline_samples)}/{args.calib_frames}",
                            ear_smoothed,
                            (0, 165, 255)
                        )
                    else:
                        baseline = float(np.median(baseline_samples))
                        threshold = baseline * 0.78
                        calibrated = True

                label = "Calibrating"
                status_color = (0, 165, 255)

                if calibrated:
                    if ear_smoothed < threshold:
                        if closed_since is None:
                            closed_since = time.monotonic()

                        closure_duration = time.monotonic() - closed_since
                        if closure_duration >= args.closure_seconds:
                            label = "DROWSY"
                            status_color = (0, 0, 255)
                            if not alert_active:
                                play_alarm(enable=not args.no_sound)
                                alert_active = True
                    else:
                        closed_since = None
                        alert_active = False
                        label = "Awake"
                        status_color = (0, 255, 0)

                draw_status(
                    frame,
                    label,
                    ear_smoothed,
                    status_color
                )

                # Draw small markers on eye corners
                for idx in [
                    LEFT["corner_left"],
                    LEFT["corner_right"],
                    RIGHT["corner_left"],
                    RIGHT["corner_right"]
                ]:
                    cv2.circle(frame, lm[idx], 2, (255, 255, 255), -1)

            else:
                # No face detected — reset closure timer
                ear_history.clear()
                closed_since = None
                alert_active = False

                if threshold is None:
                    draw_status(
                        frame,
                        "No face - calibrate",
                        0.0,
                        (0, 165, 255)
                    )
                else:
                    draw_status(
                        frame,
                        "No face",
                        0.0,
                        (0, 165, 255)
                    )

            cv2.putText(
                frame,
                "Q: Quit  |  C: Recalibrate",
                (10, frame.shape[0] - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (200, 200, 200),
                1,
                cv2.LINE_AA
            )

            cv2.imshow("VisionGuard AI", frame)

            key = cv2.waitKey(1) & 0xFF

            if key in (ord("q"), ord("Q")):
                break

            if key in (ord("c"), ord("C")):
                baseline_samples = []
                threshold = args.threshold
                calibrated = threshold is not None
                closed_since = None
                alert_active = False
                ear_history.clear()

    finally:
        cap.release()
        cv2.destroyAllWindows()
        face_mesh.close()


if __name__ == "__main__":
    main()
