#!/usr/bin/env sh
# Absorber - start the tray app.
# The interpreter runs from this script's own folder, nothing is hardcoded.
set -e
cd "$(dirname "$0")"
exec "${PYTHON:-python3}" -m absorber "$@"
