#!/usr/bin/env bash
# Q299 phase 2, in order. SRC is the build dir the previous round left as current; with no argument it is asked of
# the one place that declares it (scripts/anatomy/q241/model.SRC), which is what the hard-coded build/q297 here used
# to name -- that directory was deleted in Q310. Run from anywhere; this script cd's to the repository root itself.
set -euo pipefail
cd "$(dirname "$0")/../../.."
SRC="${1:-$(python3 -c 'import sys; sys.path.insert(0, "scripts/anatomy/q241"); import model; print(model.build_root())')}"
OUT="${2:-build/q299}"
# REF: the dir whose pages equal what is LIVE right now. Q298 published from /dev/shm/q298/final without creating a
# build dir, so that is the reference while it survives; otherwise $SRC and Q298's own additions have to be
# declared in --expect-changed as well.
REF="${3:-}"
if [ -z "$REF" ]; then if [ -d /dev/shm/q298/final ]; then REF=/dev/shm/q298/final; elif [ -d /dev/shm/q299/q298_ref ]; then REF=/dev/shm/q299/q298_ref; else REF="$SRC"; fi; fi
echo "src=$SRC ref=$REF out=$OUT"
PRE=/dev/shm/q299/pre
FIN=/dev/shm/q299/final

echo "=== 1. the shared cut-face module: the minimum drawn width"
python3 scripts/anatomy/q299/patch_cutcap_q299.py
python3 scripts/sync_q227.py                       # the templates carry a copy of cut_cap.js; Q296 lesson D

echo "=== 2. the pages: the containment fix (geometry) + the pelvic-proportion cards"
rm -rf "$PRE"
python3 scripts/anatomy/q299/fix_contain299.py build --src "$SRC" --out "$PRE"

echo "=== 3. the pose rig: fresh entries for the replaced geometries only"
mkdir -p /dev/shm/q299/fresh
for kv in base_f:viewer_base_female comb_f:viewer_zan_female comb_m:viewer_zan_vhm; do
  k="${kv%%:*}"; d="${kv#*:}"
  python3 scripts/anatomy/q299/fresh_rig299.py "$k" "$PRE/$d" "/dev/shm/q299/fresh/pose_rig_$k.json"
done
python3 scripts/anatomy/q299/fix_contain299.py rig --pages base_f,comb_f,comb_m

echo "=== 4. the template regen of all six pages"
rm -rf "$FIN"
python3 scripts/regen_template_only.py all --src "$PRE" --out "$FIN" --ref "$REF" \
  --expect-changed index.html,nmsk-q298,parts_data.json,plexus_groups.json,symmetry_q237.json,__ANATOMY_files,__ANATOMY_manifest,nmsk-pose-rig,atlas_viewer_base_female_geo_00.txt,atlas_viewer_base_female_geo_01.txt,atlas_viewer_base_female_geo_02.txt,atlas_viewer_zan_female_geo_00.txt,atlas_viewer_zan_female_geo_02.txt,atlas_viewer_zan_male_fitted_geo_00.txt,atlas_viewer_zan_male_fitted_geo_01.txt,atlas_viewer_zan_male_fitted_geo_02.txt

echo "=== 5. the documentation and the hub"
python3 scripts/anatomy/q299/patch_docs_q299.py

echo "=== 6. put the final pages on disk and re-point the model loader"
rm -rf "$OUT"; mkdir -p "$OUT"; cp -r "$FIN"/* "$OUT"/
echo "now: sed the SRC map in scripts/anatomy/q241/model.py to $OUT, re-run the containment audit against it,"
echo "then scripts/sync_*.py --check, pytest, verify_q299.py, and publish."
