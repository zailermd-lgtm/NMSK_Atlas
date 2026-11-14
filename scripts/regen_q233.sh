#!/bin/bash
# Q233: the six final page dirs with the CURRENT templates, from the Q233 patched pages (changed pages) and the published dirs (unchanged pages). No geometry is recomputed here.
#   scripts/regen_q233.sh [PAGE ...]      PAGE = own_m own_f zan_m zan_f base_f base_m   (default all six)       output build/q233/<page dir>/  (Q233_OUT)
# Patched sources (made by the Q233 scripts, kept in build/q233_pre/, see PROJECT_STATE Q233):
#   own_m  build/q233_pre/viewer_m_hr           <- scripts/transfer/q233_own_m.py + build_viewer_html.py + stage_clinical_files.py   (Z-filled male genitalia)
#   own_f  build/q233_pre/viewer_f_hr           <- scripts/transfer/q233_own_f.py (HRA uterus / ovaries / tubes, male coccyx removed)
#   zan_f  build/q233_pre/viewer_zan_female     <- scripts/zanatomy/q233_z_female.py comb_f   (same organs on the Combined female)
#   base_f build/q233_pre/viewer_base_female    <- scripts/zanatomy/q233_z_female.py base_f   (organs registered on the Z pelvis; honest wording / name)
#   zan_m  build/q225/viewer_zan_vhm, base_m build/q222/viewer_zan_atlas   unchanged (published)
# Re-run after a NEW TEMPLATE lands (Q232): this script only needs the sources above; set the template dirs through the repo's viewer/*.template.html (current checkout).
# Step order = scripts/regen_q232.sh: regen_cut_q218.sh (page + geo byte-identical to the source, parts_data.json, needle files) -> stage_clinical_files.py --ultrasound (imaging + ultrasound files)
# -> index.html -> set_titles_q231.py (unified names; base female = 'Base · Female (male-derived body)').
set -eu; cd "$(dirname "$0")/.."
export Q232_OUT=${Q233_OUT:-build/q233}
export SRC_own_m=${SRC_own_m:-build/q233_pre/viewer_m_hr} SRC_own_f=${SRC_own_f:-build/q233_pre/viewer_f_hr} SRC_zan_f=${SRC_zan_f:-build/q233_pre/viewer_zan_female} SRC_base_f=${SRC_base_f:-build/q233_pre/viewer_base_female}
PAGES=("$@"); [ ${#PAGES[@]} -gt 0 ] || PAGES=(own_m own_f zan_m zan_f base_f base_m)
CH=(); UN=()   # changed pages get a fresh parts_data.json sidecar (checked against the page's own geometry); the unchanged pages keep the published one (a rebuild only changes its "generated" date)
for p in "${PAGES[@]}"; do case "$p" in own_m|own_f|zan_f|base_f) CH+=("$p");; *) UN+=("$p");; esac; done
[ ${#CH[@]} -eq 0 ] || PARTS_SIDECAR=1 scripts/regen_q232.sh "${CH[@]}"
[ ${#UN[@]} -eq 0 ] || PARTS_SIDECAR=0 scripts/regen_q232.sh "${UN[@]}"
echo Q233_REGEN_DONE
