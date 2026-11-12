#!/bin/sh

# Rebuild the Flatpak and install it system-wide.
#
#   ./rebuild-flatpak.sh
#
# Idempotent: builds from scratch every run (--force-clean) and reinstalls
# (--reinstall).  The first run needs network access for the runtime and SDK;
# the system-wide install needs sudo.  flatpak-builder itself runs as your user.

set -eu

APP_ID=io.github.singularity.Singularity2030
RUNTIME_BRANCH=25.08
RUNTIME="org.freedesktop.Platform//$RUNTIME_BRANCH"
SDK="org.freedesktop.Sdk//$RUNTIME_BRANCH"
LOCAL_REMOTE=singularity-local

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
MANIFEST="$ROOT/flatpak/$APP_ID.yml"
METAINFO="$ROOT/flatpak/$APP_ID.metainfo.xml"
BUILD="$ROOT/build/flatpak"
REPO="$BUILD/repo"

say() { printf '\n== %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# Run a command as root: directly when already root, otherwise through sudo.
as_root() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        die "root is required for: $*"
    fi
}

install_tool() {
    tool=$1
    say "$tool is missing, installing it"
    if command -v dnf >/dev/null 2>&1; then
        as_root dnf install -y "$tool"
    elif command -v apt-get >/dev/null 2>&1; then
        as_root apt-get install -y "$tool"
    elif command -v pacman >/dev/null 2>&1; then
        as_root pacman -S --noconfirm "$tool"
    elif command -v zypper >/dev/null 2>&1; then
        as_root zypper install -y "$tool"
    else
        die "install '$tool' with your package manager and re-run"
    fi
}

[ -f "$MANIFEST" ] || die "no manifest at $MANIFEST"
[ -f "$METAINFO" ] || die "no AppStream metadata at $METAINFO"

# flatpak-builder runs the build inside a bwrap sandbox that has to be able to
# read the build tree, and a root bwrap cannot enter a mode-700 home directory
# (it fails deep inside rofiles with a bare "Permission denied").  Build as the
# user; the system-wide steps below use sudo on their own.
if [ "$(id -u)" -eq 0 ] && [ "${REBUILD_FLATPAK_ALLOW_ROOT:-0}" != 1 ]; then
    die "run this as your normal user, not as root — flatpak-builder must build
       from a directory it can read, and this script calls sudo itself.
       (REBUILD_FLATPAK_ALLOW_ROOT=1 overrides, e.g. in a root-owned container.)"
fi

for tool in flatpak flatpak-builder; do
    command -v "$tool" >/dev/null 2>&1 || install_tool "$tool"
    command -v "$tool" >/dev/null 2>&1 || die "$tool is still missing"
done

say "flatpak $(flatpak --version), flatpak-builder $(flatpak-builder --version)"

# --- metadata ----------------------------------------------------------------

# The store page is part of the product: a bad AppStream file is a wrong name,
# a dead link or no screenshots in the software center. --no-net checks the
# file rather than this machine's connection and this repository's visibility;
# the URL and image reachability checks need the repository to be public.
if command -v appstreamcli >/dev/null 2>&1; then
    say "validating the AppStream metadata"
    appstreamcli validate --no-net "$METAINFO" \
        || die "appstreamcli rejected $METAINFO"
else
    say "appstreamcli is not installed; skipping the AppStream check"
fi

# --- remotes and runtimes ----------------------------------------------------

if ! flatpak remotes --system --columns=name 2>/dev/null | grep -qx flathub; then
    say "adding the flathub remote system-wide"
    as_root flatpak remote-add --system --if-not-exists flathub \
        https://dl.flathub.org/repo/flathub.flatpakrepo
fi

for ref in "$SDK" "$RUNTIME"; do
    if flatpak info "$ref" >/dev/null 2>&1; then
        say "$ref already installed"
    else
        say "installing $ref"
        as_root flatpak install --system -y --noninteractive flathub "$ref"
    fi
done

# --- build -------------------------------------------------------------------

mkdir -p "$BUILD"

# flatpak-builder starts with --force-clean, which deletes the app dir itself;
# it cannot delete a tree that a root run left behind, and the failure it then
# prints ("Couldn't empty app dir: unlinkat(...): Permission denied") points at
# the wrong thing entirely. Say what happened and how to fix it.
if [ -n "$(find "$BUILD" ! -user "$(id -un)" -print -quit 2>/dev/null)" ]; then
    die "$BUILD contains files owned by another user, most likely from a run
       as root. flatpak-builder cannot clear them. Remove the tree and re-run:
           sudo rm -rf '$BUILD'"
fi

say "building $APP_ID"
flatpak-builder \
    --force-clean \
    --repo="$REPO" \
    --state-dir="$BUILD/state" \
    "$BUILD/build" \
    "$MANIFEST"

# --- install system-wide -----------------------------------------------------

# A local remote is what lets the system installation update and uninstall by
# ref; the repo directory is the one flatpak-builder just wrote.
say "publishing to the system installation"
as_root flatpak remote-add --system --if-not-exists --no-gpg-verify \
    "$LOCAL_REMOTE" "file://$REPO"
as_root flatpak install --system --reinstall --noninteractive -y \
    "$LOCAL_REMOTE" "$APP_ID"

# What a software center warns about comes from here. Three sockets and shared
# memory, no devices and no filesystem access; the audio socket is the one that
# also permits recording, because Flatpak has no playback-only socket.
say "what the sandbox is allowed to do"
flatpak info --system --show-permissions "$APP_ID" | awk '
    /^\[Context\]/ { inside = 1; print; next }
    /^\[/          { inside = 0 }
    inside'

# --- smoke test --------------------------------------------------------------

say "smoke-testing the installed Flatpak (headless)"

SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
    flatpak run --command=python3 "$APP_ID" -c \
    'import pygame, numpy, polib, singularity
print("pygame", pygame.version.ver, "| SDL", pygame.version.SDL)
print("numpy", numpy.__version__, "| polib", polib.__version__)
print("package", singularity.__file__)'

music_count=$(SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
    flatpak run --command=python3 "$APP_ID" -c \
    'import glob, os, singularity
base = os.path.join(os.path.dirname(singularity.__file__), "music")
print(len(glob.glob(os.path.join(base, "**", "*.ogg"), recursive=True)))')
printf 'soundtrack: %s Ogg tracks installed\n' "$music_count"
[ "$music_count" -gt 0 ] || die "no soundtrack in the package"

SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
    flatpak run "$APP_ID" --help >/dev/null

# The sandbox asks for --socket=wayland and --socket=fallback-x11, so SDL must
# come up on Wayland here. Nothing forces SDL_VIDEODRIVER anywhere -- the point
# is to prove the packaged app picks Wayland by itself, the same way the
# checkout does. An X11-only host has no WAYLAND_DISPLAY and is skipped.
if [ -n "${WAYLAND_DISPLAY:-}" ]; then
    say "checking the sandbox really gets the Wayland driver"
    driver=$(env -u DISPLAY flatpak run --command=python3 "$APP_ID" -c \
        'import pygame; pygame.display.init(); print(pygame.display.get_driver())' \
        2>/dev/null | tail -n 1)
    printf 'display driver inside the sandbox: %s\n' "$driver"
    [ "$driver" = wayland ] || die "the sandbox did not get Wayland (got '$driver')"
else
    say "no Wayland session here (WAYLAND_DISPLAY unset); skipping the driver check"
fi

printf '\nALL FLATPAK STEPS PASSED\n'

cat <<EOF

Installed system-wide as $APP_ID.

  run:        flatpak run $APP_ID
  list:       flatpak list --system --app --columns=application,version
  saves:      ~/.var/app/$APP_ID/data/singularity/saves/
  remove:     sudo flatpak uninstall --system $APP_ID
              sudo flatpak remote-delete --system $LOCAL_REMOTE
EOF
