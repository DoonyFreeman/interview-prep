#!/usr/bin/env bash
# Render lesson screenshot mockups (HTML) to PNG with headless Google Chrome.
#
#   scripts/render_lesson_screens.sh [course-slug] [name...]
#
# Sources: scripts/lesson-screens/<course>/<name>.html — each declares its frame
# with <meta name="screen-size" content="WIDTHxHEIGHT">.
# Output:  frontend/public/lesson-media/<course>/<name>.png (served as
#          /lesson-media/<course>/<name>.png, referenced from lesson markdown).
# ponytail: plain Chrome CLI, no Playwright — the only dependency is Chrome itself.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
course="${1:-team-processes}"
shift || true
src="$root/scripts/lesson-screens/$course"
out="$root/frontend/public/lesson-media/$course"
chrome="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
scale="${SCALE:-2}"

mkdir -p "$out"
names=("$@")
if [ ${#names[@]} -eq 0 ]; then
  for f in "$src"/*.html; do names+=("$(basename "$f" .html)"); done
fi

for name in "${names[@]}"; do
  html="$src/$name.html"
  size=$(sed -n 's/.*name="screen-size" content="\([0-9]*x[0-9]*\)".*/\1/p' "$html" | head -1)
  [ -n "$size" ] || { echo "no screen-size meta in $html" >&2; exit 1; }
  "$chrome" --headless=new --disable-gpu --hide-scrollbars \
    --force-device-scale-factor="$scale" --window-size="${size/x/,}" \
    --screenshot="$out/$name.png" "file://$html" >/dev/null 2>&1
  echo "$name.png  ($size @${scale}x)"
done
