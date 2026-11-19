#!/bin/bash
# Q226: stage the IMAGING add-on (simulated CT / MRI, PRIVATE clinical layer) next to the six viewer pages WITHOUT recomputing geometry.
#
#   scripts/regen_imaging_q226.sh [PAGE ...]     PAGE = own_m own_f zan_m zan_f zan_vhm base_f     (default: all six)
#
# Per page: re-inject the page's own data literals (raw text, geo files byte for byte) into the CURRENT template, which carries the one
# generic hook line <script src="clinical_imaging_tool.js"> (so the public page is still an anatomy-only atlas without the staged files),
# copy every other sibling (clinical_*, parts_data.json), then stage clinical_imaging_tool.js + clinical_imaging_tissues.json
# (scripts/clinical/stage_clinical_files.py --imaging-only). Output: build/q226/<source dir name>/ (sources are only read).
#
# Sources (latest published page dirs; override with SRC_<page>=dir):
#   own_m  build/q224/viewer_m_hr         own male          (own-viewer template)
#   own_f  build/q224/viewer_f_hr         own female
#   zan_m  build/q222/viewer_zan_atlas    Z male BASE
#   zan_f  build/q222/viewer_zan_female   Z female FITTED
#   zan_vhm build/q222/viewer_zan_vhm     Z male FITTED
#   base_f build/q222/viewer_base_female  female BASE (Z generic body, female variant)
# Env: Q226_OUT (default build/q226), TEMPLATE_OWN / TEMPLATE_ZAN (default viewer/*.template.html).
# Z-fit pages being rebuilt elsewhere (build/q225*) are never read or written here (Q226_ALLOW_Q225=1 lifts the guard once Q225 has landed).
set -eu; cd "$(dirname "$0")/.."
OUT=${Q226_OUT:-build/q226}
TOWN=${TEMPLATE_OWN:-viewer/atlas_viewer.template.html}; TZAN=${TEMPLATE_ZAN:-viewer/zan_atlas.template.html}
declare -A SRC=( [own_m]=build/q224/viewer_m_hr [own_f]=build/q224/viewer_f_hr [zan_m]=build/q222/viewer_zan_atlas
                 [zan_f]=build/q222/viewer_zan_female [zan_vhm]=build/q222/viewer_zan_vhm [base_f]=build/q222/viewer_base_female )
declare -A KIND=( [own_m]=own [own_f]=own [zan_m]=zan [zan_f]=zan [zan_vhm]=zan [base_f]=zan )
PAGES=("$@"); [ ${#PAGES[@]} -gt 0 ] || PAGES=(own_m own_f zan_m zan_f zan_vhm base_f)
for p in "${PAGES[@]}"; do
  [ -n "${KIND[$p]:-}" ] || { echo "unknown page '$p' (own_m own_f zan_m zan_f zan_vhm base_f)" >&2; exit 2; }
  v="SRC_$p"; src=${!v:-${SRC[$p]}}
  case "$src" in *q225*) [ "${Q226_ALLOW_Q225:-0}" = 1 ] || { echo "$p: refusing to read $src (Q225 is being built elsewhere; set Q226_ALLOW_Q225=1 once it has landed)" >&2; exit 2; };; esac
  [ -d "$src" ] || { echo "$p: source dir $src missing" >&2; exit 2; }
  name=$(basename "$src"); dst="$OUT/$name"; mkdir -p "$dst"
  html=$(cd "$src" && ls atlas_viewer*.html | head -1)
  if [ "${KIND[$p]}" = own ]; then python3 scripts/rebuild_own_html_from_built.py "$src/$html" -o "$dst/$html" --template "$TOWN" | tail -1
  else python3 scripts/zanatomy/rebuild_html_from_built.py "$src/$html" -o "$dst/$html" --template "$TZAN" | tail -1; fi
  for f in "$src"/*; do
    b=$(basename "$f"); case "$b" in "$html"|index.html|*_geo_[0-9][0-9].txt|clinical_imaging_*) continue;; esac
    cp "$f" "$dst/$b"
  done
  cp "$dst/$html" "$dst/index.html"
  python3 scripts/clinical/stage_clinical_files.py --imaging-only "$dst"
  echo "$p -> $dst"
done
echo Q226_REGEN_DONE
