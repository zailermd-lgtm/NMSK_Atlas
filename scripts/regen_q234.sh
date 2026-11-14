#!/bin/bash
# Q234: the three female page dirs with the CURRENT templates, from the Q234 patched pages. No geometry is recomputed here.
#   scripts/regen_q234.sh [PAGE ...]      PAGE = own_f zan_f base_f   (default all three)       output build/q234/<page dir>/  (Q234_OUT)
# Patched sources (made by the Q234 scripts, kept in build/q234_pre/, see PROJECT_STATE Q234):
#   own_f  build/q234_pre/viewer_f_hr          <- scripts/transfer/q234_own_f.py (+ build_viewer_html.py + stage_clinical_files.py)   vagina, ligaments, breasts on the Imaging-based female
#   zan_f  build/q234_pre/viewer_zan_female    <- scripts/zanatomy/q234_z_female.py comb_f
#   base_f build/q234_pre/viewer_base_female   <- scripts/zanatomy/q234_z_female.py base_f
# Step order = scripts/regen_q232.sh (regen_cut_q218.sh -> stage_clinical_files.py --ultrasound -> index.html -> scripts/set_titles_q231.py).
set -eu; cd "$(dirname "$0")/.."
export Q232_OUT=${Q234_OUT:-build/q234}
export SRC_own_f=${SRC_own_f:-build/q234_pre/viewer_f_hr} SRC_zan_f=${SRC_zan_f:-build/q234_pre/viewer_zan_female} SRC_base_f=${SRC_base_f:-build/q234_pre/viewer_base_female}
PAGES=("$@"); [ ${#PAGES[@]} -gt 0 ] || PAGES=(own_f zan_f base_f)
PARTS_SIDECAR=1 scripts/regen_q232.sh "${PAGES[@]}"      # changed pages get a fresh parts_data.json sidecar (checked against the page's own geometry)
echo Q234_REGEN_DONE
