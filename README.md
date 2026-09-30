# Visual Measurement & Metrology Studio

A local Windows computer-vision metrology application for measuring real-world objects with a standard USB camera. It combines reference-object, ArUco, manual and fixed-camera calibration with contour-based dimensional measurement, multi-part tracking, tolerance inspection, history, CSV export and demo recording.

> **Status:** engineering / prototyping tool. It is not a certified metrology instrument. Measurement accuracy depends on calibration, optics, camera geometry, lighting, perspective and scene quality.

## Overview

The application converts image pixels into physical dimensions after calibration and then measures one or more parts directly in the camera, video or image view. The core measurement pipeline uses OpenCV contour extraction, rotated minimum-area rectangles, midpoint geometry and pixel-to-metric calibration. The desktop application adds camera handling, calibration workflows, distortion correction, stable tracking, quality-control logic, persistence and export.

The dimensional-measurement approach is inspired by the public `opencv-object-dimension-estimator` reference implementation and the well-known PyImageSearch object-dimension method. This repository contains the desktop application and its own workflow around that approach.

## Main features

- Live USB/webcam measurement
- Video-file and still-image input
- Millimetres, centimetres and inches
- Multiple parts measured in the same frame
- Width, height, angle, area and perimeter
- Pixel center plus calibrated X/Y plane coordinates
- Persistent part IDs between frames
- Border/partial-object rejection
- Measurement smoothing and stability detection
- Automatic capture when a result becomes stable
- PASS / FAIL dimensional tolerance inspection
- Saved part presets and tolerances
- Measurement history and CSV export
- Annotated screenshots and demo video recording
- Dark PySide6 desktop interface

## Calibration modes

### Reference Object
A known object in the scene defines the pixel-to-metric scale. The left-most suitable contour can be used as the reference and its physical width is entered by the operator.

### ArUco Marker
OpenCV ArUco markers provide an automatic scale reference. The marker side length is entered in real-world units and the detected marker is excluded from the measured-parts list.

### Manual Calibration
Two clicks define an image segment; the operator enters its real length and the application calculates the scale.

### Fixed Camera Calibration
Once a stable camera/working-plane scale has been established it can be stored as a profile for a fixed setup, avoiding the need to keep the reference object in every frame.

## Camera calibration and lens distortion

A separate camera-calibration workflow supports chessboard / ChArUco observations and stores camera matrix and lens-distortion coefficients for a specific camera resolution. When **Lens Distortion Correction** is enabled, the frame is undistorted before dimensional analysis.

Camera calibration and pixel/mm scale calibration are intentionally separate steps: one corrects optical geometry, while the other establishes the physical scale of the working plane.

## Measurement pipeline

```text
Camera / Video / Image
        ↓
Optional lens undistortion
        ↓
ROI / working area
        ↓
Grayscale + blur
        ↓
Canny / Threshold / Adaptive Threshold
        ↓
Morphology
        ↓
External contours
        ↓
Area and border filtering
        ↓
Rotated minimum-area rectangle
        ↓
Pixel-to-metric calibration
        ↓
Dimensions + tracking + tolerance result
```

The automatic detection mode can fall back between contour-generation strategies when a scene becomes empty or noisy. Advanced settings expose contour-area limits, thresholding and morphology parameters.

## Part tracking and smoothing

Detected parts are associated between frames using spatial overlap and center proximity. A track can survive short detection gaps, which helps keep a stable part number while objects move slightly.

Smoothing modes reduce contour jitter without hiding large real changes. Stability logic checks a recent measurement window and can automatically save a measurement once it remains within a configured band.

## Quality control

The **Quality** panel supports nominal width and height with either symmetric or separate upper/lower tolerances. The overall result is `FAIL` if any configured dimension is outside its allowed range.

Part presets are stored in `config/parts.json`, allowing repeated inspection of known components.

## History and export

The application can store timestamped measurements including part ID, width, height, angle and PASS/FAIL state. Results can be exported to CSV for later inspection or production records.

## Installation

Recommended environment:

- Windows 10/11
- Python 3.10+
- USB or integrated camera

Run:

```bat
install.bat
```

The installer creates `.venv`, installs the dependencies and runs installation checks. Then start the application with:

```bat
start.bat
```

Main dependencies:

- PySide6
- OpenCV Contrib
- NumPy

`opencv-contrib-python` is used because the application requires ArUco / ChArUco support.

## Project structure

```text
app/            PySide6 application, panels, settings and main workflow
calibration/    ArUco, camera, reference, manual and perspective calibration
capture/        Webcam, video and image sources
measurement/    Contour detection, geometry and dimensional calculations
tracking/       Multi-part association and persistence
visualization/  Measurement overlays and rendering
export/         CSV and measurement export
recording/      Demonstration video recording
config/         Application and part presets
tests/          Installation and smoke tests
```

## Planned media

Project screenshots and demonstration video will be added to this repository separately.

## Privacy

Normal measurement and video processing is local. Camera frames do not need to be uploaded to a cloud service.

## License and attribution

Original application code in this repository is released under the **Apache License 2.0**. See [LICENSE](LICENSE).

The dimensional-measurement approach references:

- `claire-devv/opencv-object-dimension-estimator`
- the PyImageSearch object-dimension workflow using contour extraction, `minAreaRect`, side midpoints and pixel-to-metric calibration

OpenCV, PySide6/Qt and other dependencies remain under their respective upstream licenses. See [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

## Responsible use

Do not use this software as the sole basis for safety-critical, legal-metrology or certified quality decisions without independently validating the complete camera, calibration and measurement setup.
