#!/bin/bash
# Q228: stage the ULTRASOUND add-on (simulated B-mode, PRIVATE clinical layer) next to the six viewer pages WITHOUT recomputing geometry.
#
#   scripts/regen_ultrasound_q228.sh [PAGE ...]     PAGE = own_m own_f zan_m zan_f zan_vhm base_f     (default: all six)
#
# = scripts/regen_imaging_q226.sh with output build/q228 (page rebuilt from the published page's data literals + the CURRENT template, which carries the
# one generic imaging hook), then scripts/clinical/stage_clinical_files.py --ultrasound on each output dir: clinical_imaging_tool.js +
# clinical_imaging_tissues.json (the engine the ultrasound reuses) + clinical_ultrasound_tool.js + clinical_ultrasound_tissues.json. The ultrasound
# file is loaded BY the imaging file (optional companion), so no template line is needed. Sources are only read; build/q225* is never touched
# (the Q226 guard applies: Q226_ALLOW_Q225=1 SRC_<page>=dir lifts it once Q225 has landed).
# Env: Q228_OUT (default build/q228) plus everything regen_imaging_q226.sh understands (SRC_<page>, TEMPLATE_OWN, TEMPLATE_ZAN).
set -eu; cd "$(dirname "$0")/.."
OUT=${Q228_OUT:-build/q228}
Q226_OUT="$OUT" scripts/regen_imaging_q226.sh "$@" | grep -v '^Q226_REGEN_DONE'
declare -A DIR=( [own_m]=build/q224/viewer_m_hr [own_f]=build/q224/viewer_f_hr [zan_m]=build/q222/viewer_zan_atlas [zan_f]=build/q222/viewer_zan_female
                 [zan_vhm]=build/q222/viewer_zan_vhm [base_f]=build/q222/viewer_base_female )
PAGES=("$@"); [ ${#PAGES[@]} -gt 0 ] || PAGES=(own_m own_f zan_m zan_f zan_vhm base_f)
for p in "${PAGES[@]}"; do
  v="SRC_$p"; src=${!v:-${DIR[$p]}}; dst="$OUT/$(basename "$src")"
  python3 scripts/clinical/stage_clinical_files.py --ultrasound "$dst"
done
echo Q228_REGEN_DONE
