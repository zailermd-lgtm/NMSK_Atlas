#!/bin/bash
# Q235: the two female page dirs that got the Chinese Visible Human perineal / urethral structures, with the CURRENT templates, from the Q235 patched pages. No geometry is recomputed here.
#   scripts/regen_q235.sh [PAGE ...]      PAGE = own_f zan_f   (default both)       output build/q235/<page dir>/  (Q235_OUT)
# Patched sources (made by the Q235 scripts, kept in build/q235_pre/, see PROJECT_STATE Q235):
#   own_f  build/q235_pre/viewer_f_hr          <- scripts/transfer/q235_own_f.py (+ build_viewer_html.py + stage_clinical_files.py)
#   zan_f  build/q235_pre/viewer_zan_female    <- scripts/zanatomy/q235_z_female.py comb_f
# Base female: nothing was added (the registration onto its male-derived pelvis is not sound, data/derived/Q235_report_base_f.json): its page stays build/q234/viewer_base_female.
# Step order = scripts/regen_q232.sh (regen_cut_q218.sh -> stage_clinical_files.py --ultrasound -> index.html -> scripts/set_titles_q231.py).
set -eu; cd "$(dirname "$0")/.."
export Q232_OUT=${Q235_OUT:-build/q235}
export SRC_own_f=${SRC_own_f:-build/q235_pre/viewer_f_hr} SRC_zan_f=${SRC_zan_f:-build/q235_pre/viewer_zan_female}
PAGES=("$@"); [ ${#PAGES[@]} -gt 0 ] || PAGES=(own_f zan_f)
PARTS_SIDECAR=1 scripts/regen_q232.sh "${PAGES[@]}"      # changed pages get a fresh parts_data.json sidecar (checked against the page's own geometry)
echo Q235_REGEN_DONE
