#!/bin/bash
# Q243: the page dirs with the HRA v1.10 structures (female pelvic vessels, nucleus pulposus, spinal cord segments; uterus / tube parts), from the Q243 pre-pages, with the CURRENT committed templates
# (+ the two SUBJECT_LABELS lines of scripts/sync_subjects_q243.py). No geometry is recomputed here.
#   scripts/regen_q243.sh [PAGE ...]      PAGE = own_f zan_f base_f own_m zan_m      (default: own_f zan_f)       output build/q243/<page dir>/  (Q243_OUT)
# Sources = build/q243_pre/<page dir> (scripts/q243_build_all.sh); override one with SRC_<page>=dir. Templates: PRIVATE copies in build/q243_pre/_templates_regen = the committed templates
# (HEAD, or Q243_TEMPLATE_REF) + the SUBJECT_LABELS lines, so an uncommitted edit of another change in the working tree (Q241 pose, Q240 labels UI) cannot break the build; Q243_TPL_WORKTREE=1 uses the
# working-tree templates instead. Step order = scripts/regen_q241.sh: regen_q232.sh -> abbreviations (Q236) -> calibre (Q240), then the Q237 symmetry sidecar and the Q243 parts (uterus / tube sub-parts).
set -eu; cd "$(dirname "$0")/.."
TPLD=${Q243_TPL_DIR:-build/q243_pre/_templates_regen}
mkdir -p "$TPLD"
if [ "${Q243_TPL_WORKTREE:-0}" = 1 ]; then cp viewer/atlas_viewer.template.html viewer/zan_atlas.template.html "$TPLD/"
else git show "${Q243_TEMPLATE_REF:-HEAD}:viewer/atlas_viewer.template.html" > "$TPLD/atlas_viewer.template.html"; git show "${Q243_TEMPLATE_REF:-HEAD}:viewer/zan_atlas.template.html" > "$TPLD/zan_atlas.template.html"; fi
python3 scripts/sync_subjects_q243.py --dir "$TPLD" | tail -1
export NMSK_TEMPLATE_DIR=$PWD/$TPLD
export Q232_OUT=${Q243_OUT:-build/q243}
export SRC_own_f=${SRC_own_f:-build/q243_pre/viewer_f_hr} SRC_zan_f=${SRC_zan_f:-build/q243_pre/viewer_zan_female} SRC_base_f=${SRC_base_f:-build/q243_pre/viewer_base_female}
export SRC_own_m=${SRC_own_m:-build/q239/viewer_m_hr} SRC_zan_m=${SRC_zan_m:-build/q239/viewer_zan_vhm} SRC_base_m=${SRC_base_m:-build/q239/viewer_zan_atlas}
[ -f data/anatomy/calibre.json ] || { echo "data/anatomy/calibre.json missing: run scripts/anatomy/q240/make_calibre.py" >&2; exit 2; }
PAGES=("$@"); [ ${#PAGES[@]} -gt 0 ] || PAGES=(own_f zan_f)
PARTS_SIDECAR=0 scripts/regen_q232.sh "${PAGES[@]}"
declare -A KEY=( [own_m]=own_m [own_f]=own_f [zan_m]=comb_m [zan_f]=comb_f [base_f]=base_f [base_m]=base_m )
declare -A BODY=( [own_f]=vhf [zan_f]=zan_f [base_f]=zbase_f )
for p in "${PAGES[@]}"; do
  v="SRC_$p"; s="${!v}"; d="$Q232_OUT/$(basename "$s")"
  python3 scripts/anatomy/q236/make_abbrevs.py --inject "$d"
  python3 scripts/anatomy/q243/calibre_add.py "${KEY[$p]}" "$d"          # the new vessels into data/anatomy/calibre.json (additive) ...
  python3 scripts/anatomy/q240/make_calibre.py --inject "$d"             # ... then the page's table into the page html
  python3 scripts/anatomy/q237/build_sidecar.py "${KEY[$p]}" "$s" -o "$d/symmetry_q237.json" | tail -1
  if [ -n "${BODY[$p]:-}" ]; then python3 scripts/anatomy/q243/parts_hra.py --inject "$d" --body "${BODY[$p]}"; fi
done
echo Q243_REGEN_DONE
