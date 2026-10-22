#!/bin/bash
# Q236: the six page dirs with the CURRENT templates (structure labels: callouts, abbreviations, legend window), from the latest published page dirs of each page.
# No geometry is recomputed: regen_q232.sh (= regen_cut_q218.sh: page rebuilt from the template + the page's own data literals, geo files byte for byte, parts_data.json, needle files)
# -> stage_clinical_files.py --ultrasound -> index.html -> set_titles_q231.py; then the per-page abbreviation table is written into the page (and index.html).
#   scripts/regen_q236.sh [PAGE ...]      PAGE = own_m own_f zan_m zan_f base_f base_m   (default all six)       output build/q236/<page dir>/  (Q236_OUT)
#   own_m  build/q233/viewer_m_hr         own_f  build/q235/viewer_f_hr         zan_m  build/q233/viewer_zan_vhm
#   zan_f  build/q235/viewer_zan_female   base_f build/q234/viewer_base_female  base_m build/q233/viewer_zan_atlas       (override with SRC_<page>=dir)
set -eu; cd "$(dirname "$0")/.."
export Q232_OUT=${Q236_OUT:-build/q236}
export SRC_own_m=${SRC_own_m:-build/q233/viewer_m_hr} SRC_own_f=${SRC_own_f:-build/q235/viewer_f_hr} SRC_zan_m=${SRC_zan_m:-build/q233/viewer_zan_vhm}
export SRC_zan_f=${SRC_zan_f:-build/q235/viewer_zan_female} SRC_base_f=${SRC_base_f:-build/q234/viewer_base_female} SRC_base_m=${SRC_base_m:-build/q233/viewer_zan_atlas}
python3 scripts/sync_labels_q236.py --check        # the templates carry the current viewer/labels block
PAGES=("$@"); [ ${#PAGES[@]} -gt 0 ] || PAGES=(own_m own_f zan_m zan_f base_f base_m)
PARTS_SIDECAR=0 scripts/regen_q232.sh "${PAGES[@]}"
for p in "${PAGES[@]}"; do v="SRC_$p"; python3 scripts/anatomy/q236/make_abbrevs.py --inject "$Q232_OUT/$(basename "${!v}")"; done
echo Q236_REGEN_DONE
