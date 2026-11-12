#!/bin/sh

# Small shell wrapper to assist with executing Singularity 2030

DIR="$(dirname "$0")"
PYTHON=${PYTHON:-python3}
PYPATH=${DIR}${PYTHONPATH:+:${PYTHONPATH}}

# Clear Python cache to ensure changes are picked up
find "${DIR}" -name "__pycache__" -type d -exec rm -rf {} +
find "${DIR}" -name "*.pyc" -delete

PYTHONPATH="${PYPATH}" "${PYTHON}" -m singularity "$@"
