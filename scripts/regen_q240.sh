#!/bin/bash
# Q240: the six page dirs with the CURRENT templates (view-dependent part markers, vessel / nerve label levels) from the Q238 page dirs (= Q236 labels + Q237 symmetric view).
# No geometry is recomputed: regen_q232.sh (= regen_cut_q218.sh: page rebuilt from the template + the page's own data literals, geo files byte for byte, every sibling file incl.
# parts_data.json and symmetry_q237.json copied) -> clinical files -> index.html -> titles; then the per-page abbreviation table (Q236) and the per-page calibre table (Q240) are
# written into the page (and index.html).
#   scripts/regen_q240.sh [PAGE ...]      PAGE = own_m own_f zan_m zan_f base_f base_m   (default all six)      output build/q240/<page dir>/  (Q240_OUT)
#   sources build/q238/{viewer_m_hr,viewer_f_hr,viewer_zan_vhm,viewer_zan_female,viewer_base_female,viewer_zan_atlas}   (override with SRC_<page>=dir)
#   data/anatomy/calibre.json must exist (python3 scripts/anatomy/q240/make_calibre.py; it reads the geometry of the latest page dirs once).
set -eu; cd "$(dirname "$0")/.."
export Q232_OUT=${Q240_OUT:-build/q240}
export SRC_own_m=${SRC_own_m:-build/q238/viewer_m_hr} SRC_own_f=${SRC_own_f:-build/q238/viewer_f_hr} SRC_zan_m=${SRC_zan_m:-build/q238/viewer_zan_vhm}
export SRC_zan_f=${SRC_zan_f:-build/q238/viewer_zan_female} SRC_base_f=${SRC_base_f:-build/q238/viewer_base_female} SRC_base_m=${SRC_base_m:-build/q238/viewer_zan_atlas}
python3 scripts/sync_labels_q236.py --check && python3 scripts/sync_parts_ui_q220.py --check        # the templates carry the current shared blocks
[ -f data/anatomy/calibre.json ] || { echo "data/anatomy/calibre.json missing: run scripts/anatomy/q240/make_calibre.py" >&2; exit 2; }
PAGES=("$@"); [ ${#PAGES[@]} -gt 0 ] || PAGES=(own_m own_f zan_m zan_f base_f base_m)
PARTS_SIDECAR=0 scripts/regen_q232.sh "${PAGES[@]}"
for p in "${PAGES[@]}"; do
  v="SRC_$p"; d="$Q232_OUT/$(basename "${!v}")"
  python3 scripts/anatomy/q236/make_abbrevs.py --inject "$d"
  python3 scripts/anatomy/q240/make_calibre.py --inject "$d"
done
echo Q240_REGEN_DONE
