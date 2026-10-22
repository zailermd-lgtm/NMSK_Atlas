#!/bin/bash
# Q236: headless-Chromium check (scripts/anatomy/q236/browser_check.py) of one page of build/q236 on the four viewports.
#   scripts/anatomy/q236/browser_check_all.sh PAGE [THREE_MIN_JS]       PAGE = own_m own_f zan_m zan_f base_f base_m
#   env: Q236_VIEWPORTS=desktop,laptop,tablet,phone (default all four), Q236_FULL=desktop,phone (viewports that run the long flow: cut mode, persistence, timing), Q236_ROOT=build/q236
# Writes data/derived/Q236_browser_check_<PAGE>.json and screenshots to build/q236_renders/.
set -eu; cd "$(dirname "$0")/../../.."
page=$1; three=${2:-${THREE_MIN_JS:-/tmp/three_x/package/build/three.min.js}}
root=${Q236_ROOT:-build/q236}
case $page in
  own_m) d=viewer_m_hr; h=atlas_viewer_male.html;;
  own_f) d=viewer_f_hr; h=atlas_viewer_female.html;;
  zan_m) d=viewer_zan_vhm; h=atlas_viewer_zan_male_fitted.html;;
  zan_f) d=viewer_zan_female; h=atlas_viewer_zan_female.html;;
  base_f) d=viewer_base_female; h=atlas_viewer_base_female.html;;
  base_m) d=viewer_zan_atlas; h=atlas_viewer_zan_atlas.html;;
  *) echo "unknown page $page" >&2; exit 2;;
esac
mkdir -p build/q236_renders data/derived
python3 scripts/anatomy/q236/browser_check.py "$root/$d" "$h" "build/q236_renders/$page" "$page" --json "data/derived/Q236_browser_check_$page.json" --three "$three"
