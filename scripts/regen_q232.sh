#!/bin/bash
# Q232: regenerate the six pages with the CURRENT templates (selection INVERT + per-group display states) from the currently PUBLISHED page dirs, WITHOUT
# recomputing geometry, then stage the clinical add-ons as published (needle files from the sources, imaging + ultrasound files from clinical/), the
# unified titles, and index.html. Output build/q232/<page dir>/ = page + geo files + parts_data.json + clinical_* (+ index.html). Nothing is published.
#
#   scripts/regen_q232.sh [PAGE ...]      PAGE = own_m own_f zan_m zan_f base_f base_m   (default all six)
#   override a source with SRC_<page>=dir (defaults = the published page dirs below); output root Q232_OUT (default build/q232)
#
#   own_m  build/q224/viewer_m_hr          Imaging-based male       own_f  build/q224/viewer_f_hr         Imaging-based female
#   zan_m  build/q225/viewer_zan_vhm       Combined male            zan_f  build/q225/viewer_zan_female   Combined female
#   base_f build/q222/viewer_base_female   Base female              base_m build/q222/viewer_zan_atlas    Base male
set -eu; cd "$(dirname "$0")/.."
OUT=${Q232_OUT:-build/q232}
declare -A SRC=( [own_m]=build/q224/viewer_m_hr [own_f]=build/q224/viewer_f_hr [zan_m]=build/q225/viewer_zan_vhm
                 [zan_f]=build/q225/viewer_zan_female [base_f]=build/q222/viewer_base_female [base_m]=build/q222/viewer_zan_atlas )
PAGES=("$@"); [ ${#PAGES[@]} -gt 0 ] || PAGES=(own_m own_f zan_m zan_f base_f base_m)
export Q218_OUT="$OUT"
export PARTS_SIDECAR=${PARTS_SIDECAR:-0}          # the published pages' parts_data.json is copied unchanged (a rebuild only changes its "generated" date)
for p in "${PAGES[@]}"; do
  [ -n "${SRC[$p]:-}" ] || { echo "unknown page '$p'" >&2; exit 2; }
  v="SRC_$p"; export "$v=${!v:-${SRC[$p]}}"
done
scripts/regen_cut_q218.sh "${PAGES[@]}"                      # page + geo (byte for byte) + parts_data.json + the sources' needle files, verified against the sources
for p in "${PAGES[@]}"; do
  v="SRC_$p"; d="$OUT/$(basename "${!v}")"
  python3 scripts/clinical/stage_clinical_files.py --ultrasound "$d"      # clinical_imaging_* + clinical_ultrasound_* (current clinical/ versions)
  html=$(cd "$d" && ls atlas_viewer*.html | head -1)
  cp "$d/$html" "$d/index.html"
  python3 scripts/set_titles_q231.py "$d" | cut -c1-200
done
echo Q232_REGEN_DONE
