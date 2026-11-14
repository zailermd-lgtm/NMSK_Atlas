#!/bin/bash
# Q228: stage the ULTRASOUND add-on (simulated B-mode, PRIVATE clinical layer) next to the six viewer pages WITHOUT recomputing geometry.
#
#   scripts/regen_ultrasound_q228.sh [PAGE ...]     PAGE = own_m own_f zan_m zan_f zan_vhm base_f     (default: all six)
#
# Output build/q228/<dir>/ (sources are only read, build/q225* is never written):
#   default   = copy the latest staged imaging pages (Q228_SRC_ROOT, default build/q230: current templates, unified names, Z fits of Q225) file for
#               file, then scripts/clinical/stage_clinical_files.py --ultrasound on each copy = clinical_imaging_tool.js + clinical_imaging_tissues.json
#               (the engine the ultrasound reuses, current versions) + clinical_ultrasound_tool.js + clinical_ultrasound_tissues.json. The ultrasound
#               file is loaded BY the imaging file (optional companion, a published placeholder of the same name is simply replaced); no template line.
#   Q228_REBUILD=1 = instead re-inject the published pages' data literals into the CURRENT templates (scripts/regen_imaging_q226.sh, sources as there:
#               SRC_<page>=dir, TEMPLATE_OWN, TEMPLATE_ZAN; Q226_ALLOW_Q225=1 for build/q225 sources), then stage the same four files.
# Publish = upload the four files (+ the imaging pair already published) to the artifact `files` of the pages the owner chooses (nothing published here).
set -eu; cd "$(dirname "$0")/.."
OUT=${Q228_OUT:-build/q228}; SRCROOT=${Q228_SRC_ROOT:-build/q230}
declare -A DIR=( [own_m]=viewer_m_hr [own_f]=viewer_f_hr [zan_m]=viewer_zan_atlas [zan_f]=viewer_zan_female [zan_vhm]=viewer_zan_vhm [base_f]=viewer_base_female )
PAGES=("$@"); [ ${#PAGES[@]} -gt 0 ] || PAGES=(own_m own_f zan_m zan_f zan_vhm base_f)
for p in "${PAGES[@]}"; do [ -n "${DIR[$p]:-}" ] || { echo "unknown page '$p' (own_m own_f zan_m zan_f zan_vhm base_f)" >&2; exit 2; }; done
if [ "${Q228_REBUILD:-0}" = 1 ]; then
  Q226_OUT="$OUT" scripts/regen_imaging_q226.sh "${PAGES[@]}" | grep -v '^Q226_REGEN_DONE'
else
  for p in "${PAGES[@]}"; do
    src="$SRCROOT/${DIR[$p]}"; dst="$OUT/${DIR[$p]}"
    [ -d "$src" ] || { echo "$p: $src missing (set Q228_SRC_ROOT or use Q228_REBUILD=1)" >&2; exit 2; }
    case "$src" in *q225*) [ "${Q228_ALLOW_Q225:-0}" = 1 ] || { echo "$p: refusing to read $src" >&2; exit 2; };; esac
    mkdir -p "$dst"; cp -a "$src"/. "$dst"/
    echo "$p: copied $src -> $dst"
  done
fi
for p in "${PAGES[@]}"; do python3 scripts/clinical/stage_clinical_files.py --ultrasound "$OUT/${DIR[$p]}"; done
echo Q228_REGEN_DONE
