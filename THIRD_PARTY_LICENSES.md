# Third-party software and references

This repository contains original application code and depends on third-party libraries installed separately.

## OpenCV
OpenCV is used for image processing, contour extraction, camera calibration, ArUco / ChArUco and geometry. See the upstream OpenCV repository and its license.

## Qt for Python / PySide6
PySide6 provides the desktop GUI. Qt for Python is distributed under its upstream licensing terms (including LGPL/GPL/commercial options depending on use).

## NumPy
NumPy is used for numerical processing and remains under its upstream BSD license.

## OpenH264
The application can use Cisco OpenH264 for H.264 demo recording. The DLL is not distributed in this repository; installation/runtime code may obtain it separately. Review Cisco's OpenH264 binary license before redistribution.

## Measurement-method reference
The dimensional-measurement workflow was inspired by the public project:
https://github.com/claire-devv/opencv-object-dimension-estimator

That project demonstrates contour detection, rotated bounding boxes and pixel-to-metric calibration from a known reference object. No third-party project is endorsed by or affiliated with this repository.
