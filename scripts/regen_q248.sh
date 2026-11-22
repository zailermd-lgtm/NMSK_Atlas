#!/bin/bash
# Q248: the six page dirs with the new ligaments (Z-Anatomy ligaments carried onto the Imaging-based pages, CVH anococcygeal ligament, rule-based pelvic floor / patellar ligaments) from the Q248 pre-pages
# (scripts/anatomy/q248/build_pages.py), with the CURRENT committed templates (+ the SUBJECT_LABELS lines of scripts/sync_subjects_q248.py). No geometry is recomputed here.
#   scripts/regen_q248.sh [PAGE ...]      PAGE = own_m own_f zan_m zan_f base_f base_m      (default all six)       output build/q248/<page dir>/  (Q248_OUT)
# Step order = scripts/regen_q243.sh: regen_q232.sh -> make_abbrevs --inject -> make_calibre --inject -> Q237 symmetry sidecar (build_sidecar.py), then the pose rig of every page whose structures changed
# (make_pose_rig.py KEY with Q241_SRC_<key> = the new page dir, then --inject). Templates: PRIVATE copies = the committed templates (HEAD, or Q248_TEMPLATE_REF) + the SUBJECT_LABELS lines; Q248_TPL_WORKTREE=1 uses the working tree.
set -eu; cd "$(dirname "$0")/.."
TPLD=${Q248_TPL_DIR:-build/q248_pre/_templates_regen}
mkdir -p "$TPLD"
if [ "${Q248_TPL_WORKTREE:-0}" = 1 ]; then cp viewer/atlas_viewer.template.html viewer/zan_atlas.template.html "$TPLD/"
else git show "${Q248_TEMPLATE_REF:-HEAD}:viewer/atlas_viewer.template.html" > "$TPLD/atlas_viewer.template.html"; git show "${Q248_TEMPLATE_REF:-HEAD}:viewer/zan_atlas.template.html" > "$TPLD/zan_atlas.template.html"; fi
python3 scripts/sync_subjects_q248.py --dir "$TPLD" | tail -1
export NMSK_TEMPLATE_DIR=$PWD/$TPLD
export Q232_OUT=${Q248_OUT:-build/q248}
PRE=${Q248_PRE:-build/q248_pre}
export SRC_own_m=${SRC_own_m:-$PRE/viewer_m_hr} SRC_own_f=${SRC_own_f:-$PRE/viewer_f_hr} SRC_zan_m=${SRC_zan_m:-$PRE/viewer_zan_vhm}
export SRC_zan_f=${SRC_zan_f:-$PRE/viewer_zan_female} SRC_base_f=${SRC_base_f:-$PRE/viewer_base_female} SRC_base_m=${SRC_base_m:-$PRE/viewer_zan_atlas}
[ -f data/anatomy/calibre.json ] || { echo "data/anatomy/calibre.json missing: run scripts/anatomy/q240/make_calibre.py" >&2; exit 2; }
PAGES=("$@"); [ ${#PAGES[@]} -gt 0 ] || PAGES=(own_m own_f zan_m zan_f base_f base_m)
declare -A KEY=( [own_m]=own_m [own_f]=own_f [zan_m]=comb_m [zan_f]=comb_f [base_f]=base_f [base_m]=base_m )
PARTS_SIDECAR=0 scripts/regen_q232.sh "${PAGES[@]}"
for p in "${PAGES[@]}"; do
  v="SRC_$p"; s="${!v}"; d="$Q232_OUT/$(basename "$s")"
  python3 scripts/anatomy/q236/make_abbrevs.py --inject "$d"
  python3 scripts/anatomy/q240/make_calibre.py --inject "$d"
  python3 scripts/anatomy/q237/build_sidecar.py "${KEY[$p]}" "$s" -o "$d/symmetry_q237.json" | tail -1
  if [ "${Q248_POSE:-1}" = 1 ]; then
    env "Q241_SRC_${KEY[$p]}=$PWD/$d" python3 scripts/anatomy/q241/make_pose_rig.py "${KEY[$p]}" | tail -1
    python3 scripts/anatomy/q241/make_pose_rig.py --inject "$d" | tail -1
  fi
done
echo Q248_REGEN_DONE
