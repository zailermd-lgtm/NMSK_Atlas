#!/bin/bash
# Q249: the six page dirs with the rule-based pelvic / perineal nerves from the Q249 pre-pages (scripts/anatomy/q249/build_pages.py: in-process patches of the latest page dirs build/q248/* and build/q250/*, ship diff 0 unlisted),
# with the CURRENT templates (working tree, Q249_TPL_REF=HEAD to use the committed ones) + the SUBJECT_LABELS lines of the later syncs.  No geometry is recomputed here.
#   scripts/regen_q249.sh [PAGE ...]      PAGE = own_m own_f zan_m zan_f base_f base_m      (default all six)       output build/q249/<page dir>/ (Q249_OUT)
# Step order (scripts/regen_q248.sh): regen_q232.sh -> abbreviations (Q236) -> calibre (Q249 nerves added, Q240 inject) -> Q237 symmetry sidecar -> Q241 pose rig (rebuilt: the structure set changed) -> titles (Q231).
# The needle-risk tables clinical/data/risk_{vhf,vhm,zan_m,zan_f}.json must be regenerated BEFORE this script (scripts/clinical/risk_structures_q188.py --viewer V --source PRE_PAGE; see scripts/q249_build_all.sh).
set -eu; cd "$(dirname "$0")/.."
TPLD=${Q249_TPL_DIR:-build/q249_pre/_templates_regen}; mkdir -p "$TPLD"
if [ "${Q249_TPL_REF:-}" != "" ]; then git show "$Q249_TPL_REF:viewer/atlas_viewer.template.html" > "$TPLD/atlas_viewer.template.html"; git show "$Q249_TPL_REF:viewer/zan_atlas.template.html" > "$TPLD/zan_atlas.template.html"
else cp viewer/atlas_viewer.template.html viewer/zan_atlas.template.html "$TPLD/"; fi
for s in scripts/sync_subjects_q243.py scripts/sync_subjects_q248.py scripts/sync_subjects_q249.py; do python3 $s --dir "$TPLD" | tail -1; done
export NMSK_TEMPLATE_DIR=$PWD/$TPLD
export Q232_OUT=${Q249_OUT:-build/q249}
PRE=${Q249_PRE:-build/q249_pre}
export SRC_own_m=${SRC_own_m:-$PRE/viewer_m_hr} SRC_own_f=${SRC_own_f:-$PRE/viewer_f_hr} SRC_zan_m=${SRC_zan_m:-$PRE/viewer_zan_vhm}
export SRC_zan_f=${SRC_zan_f:-$PRE/viewer_zan_female} SRC_base_f=${SRC_base_f:-$PRE/viewer_base_female} SRC_base_m=${SRC_base_m:-$PRE/viewer_zan_atlas}
[ -f data/anatomy/calibre.json ] || { echo "data/anatomy/calibre.json missing: run scripts/anatomy/q240/make_calibre.py" >&2; exit 2; }
PAGES=("$@"); [ ${#PAGES[@]} -gt 0 ] || PAGES=(own_m own_f zan_m zan_f base_f base_m)
declare -A KEY=( [own_m]=own_m [own_f]=own_f [zan_m]=comb_m [zan_f]=comb_f [base_f]=base_f [base_m]=base_m )
PARTS_SIDECAR=0 scripts/regen_q232.sh "${PAGES[@]}"
for p in "${PAGES[@]}"; do
  v="SRC_$p"; s="${!v}"; d="$Q232_OUT/$(basename "$s")"
  python3 scripts/anatomy/q236/make_abbrevs.py --inject "$d"
  [ "${Q249_CAL_DONE:-0}" = 1 ] || python3 scripts/anatomy/q249/calibre_add.py "${KEY[$p]}" "$d"
  python3 scripts/anatomy/q240/make_calibre.py --inject "$d"
  python3 scripts/anatomy/q237/build_sidecar.py "${KEY[$p]}" "$s" -o "$d/symmetry_q237.json" | tail -1
  if [ "${Q249_POSE:-1}" = 1 ]; then
    env "Q241_SRC_${KEY[$p]}=$PWD/$d" python3 scripts/anatomy/q241/make_pose_rig.py "${KEY[$p]}" | tail -1
    python3 scripts/anatomy/q241/make_pose_rig.py --inject "$d" | tail -1
  fi
done
for p in "${PAGES[@]}"; do v="SRC_$p"; python3 scripts/set_titles_q231.py "$Q232_OUT/$(basename "${!v}")" | tail -n 1; done
echo Q249_REGEN_DONE
