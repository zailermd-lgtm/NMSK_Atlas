#!/bin/bash
# Q250: the two page dirs (Base · Female, Combined · Female) from the Q250 pre-pages (scripts/q250_build_all.sh) with the CURRENT committed templates (+ the SUBJECT_LABELS lines of the later syncs):
# regen_q232.sh -> abbreviations (Q236) -> calibre (Q240) -> Q237 symmetry sidecar -> Q243 parts / vessel calibre -> Q241 pose rig (rebuilt for the new skeleton) -> titles (Q231 names).  No geometry is recomputed here.
#   scripts/regen_q250.sh [PAGE ...]      PAGE = zan_f base_f      (default both)       output build/q250/<page dir>/
set -eu; cd "$(dirname "$0")/.."
TPLD=${Q250_TPL_DIR:-build/q250_pre/_templates_regen}; mkdir -p "$TPLD"
if [ "${Q250_TPL_WORKTREE:-0}" = 1 ]; then cp viewer/atlas_viewer.template.html viewer/zan_atlas.template.html "$TPLD/"
else git show "${Q250_TEMPLATE_REF:-HEAD}:viewer/atlas_viewer.template.html" > "$TPLD/atlas_viewer.template.html"; git show "${Q250_TEMPLATE_REF:-HEAD}:viewer/zan_atlas.template.html" > "$TPLD/zan_atlas.template.html"; fi
python3 scripts/sync_subjects_q243.py --dir "$TPLD" | tail -1
[ -f scripts/sync_subjects_q248.py ] && python3 scripts/sync_subjects_q248.py --dir "$TPLD" | tail -1
export NMSK_TEMPLATE_DIR=$PWD/$TPLD
export Q232_OUT=${Q250_OUT:-build/q250}
PRE=${Q250_PRE:-build/q250_pre}
export SRC_zan_f=${SRC_zan_f:-$PRE/viewer_zan_female} SRC_base_f=${SRC_base_f:-$PRE/viewer_base_female}
export SRC_own_f=${SRC_own_f:-build/q244/viewer_f_hr} SRC_own_m=${SRC_own_m:-build/q244/viewer_m_hr} SRC_zan_m=${SRC_zan_m:-build/q244/viewer_zan_vhm} SRC_base_m=${SRC_base_m:-build/q244/viewer_zan_atlas}
PAGES=("$@"); [ ${#PAGES[@]} -gt 0 ] || PAGES=(zan_f base_f)
declare -A KEY=( [zan_f]=comb_f [base_f]=base_f ); declare -A BODY=( [zan_f]=zan_f [base_f]=zbase_f )
PARTS_SIDECAR=0 scripts/regen_q232.sh "${PAGES[@]}"
for p in "${PAGES[@]}"; do
  v="SRC_$p"; s="${!v}"; d="$Q232_OUT/$(basename "$s")"
  python3 scripts/anatomy/q236/make_abbrevs.py --inject "$d"
  python3 scripts/anatomy/q243/calibre_add.py "${KEY[$p]}" "$d"
  python3 scripts/anatomy/q240/make_calibre.py --inject "$d"
  python3 scripts/anatomy/q237/build_sidecar.py "${KEY[$p]}" "$s" -o "$d/symmetry_q237.json" | tail -1
  if [ "$p" = zan_f ]; then python3 scripts/anatomy/q243/parts_hra.py --inject "$d" --body "${BODY[$p]}"; fi   # base_f: the uterus / tube markers were recomputed with the new pelvis registration by q250/parts_sidecar.py (pre-page)
  env "Q241_SRC_${KEY[$p]}=$PWD/$d" python3 scripts/anatomy/q241/make_pose_rig.py "${KEY[$p]}" | tail -1
  python3 scripts/anatomy/q241/make_pose_rig.py --inject "$d" | tail -1
done
for p in "${PAGES[@]}"; do v="SRC_$p"; python3 scripts/set_titles_q231.py "$Q232_OUT/$(basename "${!v}")" | tail -n 1; done
echo Q250_REGEN_DONE
