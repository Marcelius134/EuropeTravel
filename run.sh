#!/bin/sh
# EuropeTravel: set up on first use, then start the app and open it in the browser.
# Run from a terminal:  ./run.sh
set -e
cd "$(dirname "$0")"

PY=python3
command -v python3 >/dev/null 2>&1 || PY=python
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "Python was not found. Install Python 3.10 or newer, then run this again."
  exit 1
fi

if [ ! -x venv/bin/python ]; then
  echo "Setting up for the first time. This takes a minute..."
  "$PY" -m venv venv
fi
venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements.txt

echo
echo "EuropeTravel is starting at http://127.0.0.1:5000"
echo "Press Ctrl+C here to stop the app."
echo
(sleep 2.5; venv/bin/python -m webbrowser http://127.0.0.1:5000 >/dev/null 2>&1 || true) &
exec venv/bin/python -m flask run
