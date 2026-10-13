#!/bin/bash
# Q232: headless-Chromium check (scripts/zanatomy/q232_check.py) of one page on the six viewports.
#   scripts/zanatomy/q232_check_all.sh PAGE [THREE_MIN_JS] [merge]     PAGE = own_m own_f zan_m zan_f base_f base_m
#   env: Q232_VIEWPORTS=desktop,phone (default all six), Q232_FULL=desktop,phone (viewports that run the long flow: composition, cut + cap, saved sets), Q232_ROOT=build/q232
# Writes data/derived/Q232_browser_check_<PAGE>.json and screenshots to build/q232_renders/.
set -eu; cd "$(dirname "$0")/../.."
page=$1; three=${2:-${THREE_MIN_JS:-/tmp/three_x/package/build/three.min.js}}
root=${Q232_ROOT:-build/q232}
case $page in
  own_m) d=viewer_m_hr; h=atlas_viewer_male.html; k=own;;
  own_f) d=viewer_f_hr; h=atlas_viewer_female.html; k=own;;
  zan_m) d=viewer_zan_vhm; h=atlas_viewer_zan_male_fitted.html; k=zan;;
  zan_f) d=viewer_zan_female; h=atlas_viewer_zan_female.html; k=zan;;
  base_f) d=viewer_base_female; h=atlas_viewer_base_female.html; k=zan;;
  base_m) d=viewer_zan_atlas; h=atlas_viewer_zan_atlas.html; k=zan;;
  *) echo "unknown page $page" >&2; exit 2;;
esac
mkdir -p build/q232_renders
python3 scripts/zanatomy/q232_check.py "$root/$d" "$h" "$k" "build/q232_renders/$page" "$three" "$page" --json "data/derived/Q232_browser_check_$page.json" ${3:+--merge} > /dev/null
python3 - "$page" <<'PY'
import json, sys
d = json.load(open(f"data/derived/Q232_browser_check_{sys.argv[1]}.json"))
for n, v in d["viewports"].items():
    bad = [k for k, x in v["checks"].items() if x is not True]
    print(sys.argv[1], n, f"{len(v['checks']) - len(bad)}/{len(v['checks'])} ok", "errors:", len(v["errors"]), "FAILED:" if bad else "", bad)
PY
