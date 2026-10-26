#!/bin/bash
# Builds only. No GPU workloads, capture or installation are invoked.
set -euo pipefail
if [ "$#" -ne 1 ]; then
    echo 'usage: build-darwin.sh NEW_BUILD_DIRECTORY' >&2
    exit 2
fi
HERE=$(cd -- "$(dirname -- "$0")" && pwd)
OUT=$1
umask 077
mkdir "$OUT"
exec > >(tee "$OUT/build.stdout") 2> >(tee "$OUT/build.stderr" >&2)
FLAGS=(-fobjc-arc -fno-modules -Wall -Wextra -Werror -mmacosx-version-min=14.4)
/usr/bin/clang --version
/usr/bin/clang "${FLAGS[@]}" -framework Foundation -framework Metal -framework IOSurface \
    "$HERE/iosurface-pixel-probe.m" -o "$OUT/iosurface-pixel-probe"
/usr/bin/clang "${FLAGS[@]}" -framework Foundation -framework CoreGraphics -framework ScreenCaptureKit -framework ImageIO \
    "$HERE/desktop-capture.m" -o "$OUT/desktop-capture"
/usr/bin/codesign --force --sign - "$OUT/iosurface-pixel-probe"
/usr/bin/codesign --force --sign - "$OUT/desktop-capture"
/usr/bin/codesign --verify --strict "$OUT/iosurface-pixel-probe"
/usr/bin/codesign --verify --strict "$OUT/desktop-capture"
/usr/bin/shasum -a 256 "$HERE"/*.m "$HERE/build-darwin.sh" "$OUT/iosurface-pixel-probe" "$OUT/desktop-capture"
