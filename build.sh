#!/usr/bin/env bash
# Build the Attendance System backend into a onefile binary using Nuitka.
# Target: Linux x86_64. Output: build/juteatt
#
# Usage on the server:
#   1. SCP this repo to the server
#   2. Run: bash build.sh
#   3. Copy build/juteatt to its final location
#   4. Delete the source directory
#
# System packages required (Debian/Ubuntu):
#   sudo apt-get update && sudo apt-get install -y \
#       build-essential cmake patchelf ccache \
#       libopenblas-dev liblapack-dev libx11-dev libgtk-3-dev \
#       python3 python3-venv python3-dev

set -euo pipefail
cd "$(dirname "$0")"

# Create venv if missing
if [ ! -d venv ] && [ ! -d .venv ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
if [ -d venv ]; then
    # shellcheck disable=SC1091
    source venv/bin/activate
elif [ -d .venv ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

# Install runtime deps + Nuitka
echo "Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
pip install --quiet --upgrade "Nuitka[onefile]"
pip install --quiet git+https://github.com/ageitgey/face_recognition_models

# Compile.
#   --onefile / --standalone                          -> single self-extracting binary
#   --include-package=src                             -> Flask app package
#   --include-package=face_recognition[_models]       -> face recognition runtime
#   --include-package-data=face_recognition_models    -> bundles the .dat weight files
#   --include-package-data=cv2                        -> opencv config/data
#   --assume-yes-for-downloads                        -> auto-accept ccache/depends downloads
#   --remove-output                                   -> clean intermediate build dir
python -m nuitka \
    --onefile \
    --standalone \
    --output-dir=build \
    --output-filename=juteatt \
    --include-package=src \
    --include-package=face_recognition \
    --include-package=face_recognition_models \
    --include-package-data=face_recognition_models \
    --include-package-data=cv2 \
    --assume-yes-for-downloads \
    --remove-output \
    app.py

echo
echo "Build complete: build/juteatt"
echo "Run with: ./build/juteatt"
