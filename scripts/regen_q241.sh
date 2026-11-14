#!/bin/bash
# Q241: the six page dirs with the POSE fragment (joint pose controls + the page's pose rig) from the current page dirs (Q238 = Q236 labels + Q237 symmetric view). No geometry is recomputed.
#   scripts/regen_q241.sh [PAGE ...]      PAGE = own_m own_f zan_m zan_f base_f base_m   (default all six)      output build/q241/<page dir>/  (Q241_OUT)
# Templates: PRIVATE copies in build/q241_pre/_templates = the committed templates (HEAD, or Q241_TEMPLATE_REF) + the Q241 fragment / hooks (scripts/sync_pose_q241.py), so an uncommitted edit of
# another change in the working tree cannot break the build. After the pose fragment is committed to viewer/, build from the working tree:   Q241_TPL_WORKTREE=1 scripts/regen_q241.sh
# Sources = the page dirs below (override with SRC_<page>=dir). Step order = scripts/regen_q240.sh (regen_q232.sh -> abbreviations -> calibre), then the pose rig of each page (data/anatomy/pose_rig_<key>.json,
# made by scripts/anatomy/q241/make_pose_rig.py; --inject checks the geometry of the page against the rig).
set -eu; cd "$(dirname "$0")/.."
TPLD=${Q241_TPL_DIR:-build/q241_pre/_templates}
mkdir -p "$TPLD"
if [ "${Q241_TPL_WORKTREE:-0}" = 1 ]; then cp viewer/atlas_viewer.template.html viewer/zan_atlas.template.html "$TPLD/"
else git show "${Q241_TEMPLATE_REF:-HEAD}:viewer/atlas_viewer.template.html" > "$TPLD/atlas_viewer.template.html"; git show "${Q241_TEMPLATE_REF:-HEAD}:viewer/zan_atlas.template.html" > "$TPLD/zan_atlas.template.html"; fi
python3 scripts/sync_pose_q241.py --dir "$TPLD" | tail -2
export NMSK_TEMPLATE_DIR=$PWD/$TPLD
export Q232_OUT=${Q241_OUT:-build/q241}
export SRC_own_m=${SRC_own_m:-build/q238/viewer_m_hr} SRC_own_f=${SRC_own_f:-build/q238/viewer_f_hr} SRC_zan_m=${SRC_zan_m:-build/q238/viewer_zan_vhm}
export SRC_zan_f=${SRC_zan_f:-build/q238/viewer_zan_female} SRC_base_f=${SRC_base_f:-build/q238/viewer_base_female} SRC_base_m=${SRC_base_m:-build/q238/viewer_zan_atlas}
[ -f data/anatomy/calibre.json ] || { echo "data/anatomy/calibre.json missing: run scripts/anatomy/q240/make_calibre.py" >&2; exit 2; }
PAGES=("$@"); [ ${#PAGES[@]} -gt 0 ] || PAGES=(own_m own_f zan_m zan_f base_f base_m)
PARTS_SIDECAR=0 scripts/regen_q232.sh "${PAGES[@]}"
for p in "${PAGES[@]}"; do
  v="SRC_$p"; d="$Q232_OUT/$(basename "${!v}")"
  python3 scripts/anatomy/q236/make_abbrevs.py --inject "$d"
  python3 scripts/anatomy/q240/make_calibre.py --inject "$d"
  python3 scripts/anatomy/q241/make_pose_rig.py --inject "$d"
done
echo Q241_REGEN_DONE
