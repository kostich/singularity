#!/bin/sh

# Flatpak entry point (installed as /app/bin/singularity).
#
# The in-tree run_singularity.sh points PYTHONPATH at the checkout; inside the
# sandbox the package is installed into the runtime's site-packages, so running
# the module is enough.  The interpreter is the runtime's, never the host's.

exec /usr/bin/python3 -m singularity "$@"

