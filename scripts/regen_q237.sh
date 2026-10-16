#!/bin/bash
# Q237: the six final page dirs with the Symmetric-view fragment (and the mirror Source class), from the Q237 patched pre-pages. No geometry is recomputed here.
#   scripts/regen_q237.sh [PAGE ...]      PAGE = own_m own_f zan_m zan_f base_f base_m   (default all six)      output build/q237/<page dir>/  (Q237_OUT)
# Templates: PRIVATE copies in build/q237_pre/_templates_sym = the committed templates (HEAD) + the Q237 fragment / hooks (scripts/sync_symview_q237.py), so an uncommitted edit of another change
# (e.g. the Q236 labels UI in the working tree) cannot break the build. After that change has landed (templates committed, `python3 scripts/sync_symview_q237.py` run on viewer/), re-sync with
#   Q237_TPL_WORKTREE=1 scripts/regen_q237.sh        (uses the working-tree viewer/*.template.html: both changes in every page; geometry untouched)
# Sources = the Q237 pre-pages (scripts/q237_build_all.sh); override one with SRC_<page>=dir. Step order = scripts/regen_q232.sh (regen_cut_q218.sh -> clinical files -> index.html -> scripts/set_titles_q231.py),
# then the page's symmetry_q237.json sidecar (scripts/anatomy/q237/build_sidecar.py).
set -eu; cd "$(dirname "$0")/.."
TPLD=${Q237_TPL_DIR:-build/q237_pre/_templates_sym}
mkdir -p "$TPLD"
if [ "${Q237_TPL_WORKTREE:-0}" = 1 ]; then cp viewer/atlas_viewer.template.html viewer/zan_atlas.template.html "$TPLD/"
else git show "${Q237_TEMPLATE_REF:-HEAD}:viewer/atlas_viewer.template.html" > "$TPLD/atlas_viewer.template.html"; git show "${Q237_TEMPLATE_REF:-HEAD}:viewer/zan_atlas.template.html" > "$TPLD/zan_atlas.template.html"; fi
python3 scripts/sync_symview_q237.py --dir "$TPLD" | tail -2
export NMSK_TEMPLATE_DIR=$PWD/$TPLD
export Q232_OUT=${Q237_OUT:-build/q237}
export SRC_own_m=${SRC_own_m:-build/q237_pre/viewer_m_hr} SRC_own_f=${SRC_own_f:-build/q237_pre/viewer_f_hr} SRC_zan_m=${SRC_zan_m:-build/q237_pre/viewer_zan_vhm}
export SRC_zan_f=${SRC_zan_f:-build/q237_pre/viewer_zan_female} SRC_base_f=${SRC_base_f:-build/q237_pre/viewer_base_female} SRC_base_m=${SRC_base_m:-build/q237_pre/viewer_zan_atlas}
PAGES=("$@"); [ ${#PAGES[@]} -gt 0 ] || PAGES=(own_m own_f zan_m zan_f base_f base_m)
PARTS_SIDECAR=1 scripts/regen_q232.sh "${PAGES[@]}"
declare -A KEY=( [own_m]=own_m [own_f]=own_f [zan_m]=comb_m [zan_f]=comb_f [base_f]=base_f [base_m]=base_m )
for p in "${PAGES[@]}"; do
  v="SRC_$p"; d="$Q232_OUT/$(basename "${!v}")"
  python3 scripts/anatomy/q237/build_sidecar.py "${KEY[$p]}" "${!v}" -o "$d/symmetry_q237.json" | tail -1
done
echo Q237_REGEN_DONE
