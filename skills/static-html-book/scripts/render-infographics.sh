#!/usr/bin/env bash
# infographics/*.html を 1280x720（deviceScaleFactor 2）の PNG にする。
# 使い方: tools/render-infographics.sh [infographics/chXX-*.html ...]
# 本のディレクトリで実行する（infographics/ と src/images/ を CWD から見る）。
set -euo pipefail
CHROME="${CHROME:-chrome}"
to_native() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s' "$1"; fi; }
profile="$(mktemp -d)"
trap 'rm -rf "$profile"' EXIT
targets=("$@")
if [ ${#targets[@]} -eq 0 ]; then targets=(infographics/ch*.html); fi
for f in "${targets[@]}"; do
  name="$(basename "$f" .html)"
  src="$(to_native "$(cd "$(dirname "$f")" && pwd)/$(basename "$f")")"
  out="$(to_native "$(pwd)/src/images/${name}.png")"
  # ウィンドウ枠の分だけビューポートが小さくなるため、大きめに撮って左上を切り出す
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars \
    --user-data-dir="$(to_native "$profile")" \
    --force-device-scale-factor=2 --window-size=1400,900 \
    --screenshot="$out" "file:///${src#/}" >/dev/null 2>&1
  python - "$out" <<'PY'
import sys
from PIL import Image
p = sys.argv[1]
im = Image.open(p)
if im.size[0] < 2560 or im.size[1] < 1440:
    sys.exit(f"screenshot too small: {im.size}")
im.crop((0, 0, 2560, 1440)).save(p, optimize=True)
PY
  echo "rendered: src/images/${name}.png"
done
