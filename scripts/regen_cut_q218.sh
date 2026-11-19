#!/bin/bash
# Q218: regenerate viewer pages with the CURRENT templates (cut mode with slice thickness) WITHOUT recomputing any geometry,
# from the latest page dirs, into build/q218/<page dir name>/ (sources are only read). Same method as Q197.
#
#   scripts/regen_cut_q218.sh [PAGE ...]        PAGE = own_m own_f zan_m zan_f base_f base_m   (default: all six)
#   Q220 run (cut + slice + parts, into build/q220):  Q218_OUT=build/q220 Q218_CLINICAL_LIVE=build/q218/_clinical_live scripts/regen_cut_q218.sh
#
# Sources (override per page with SRC_<page>=dir, e.g. after Q217 lands:
#   SRC_own_m=build/q217/viewer_m_hr SRC_zan_m=build/q217/viewer_zan_vhm scripts/regen_cut_q218.sh own_m zan_m):
#   own_m  build/q214/viewer_m_hr           own male            (own-viewer template)
#   own_f  build/q216/viewer_f_hr           own female (VH female title kept from the source page)
#   zan_m  build/q211/viewer_zan_vhm        Z male fitted       (Z template)
#   zan_f  build/q213/viewer_zan_female     Z female fitted
#   base_f build/q202/viewer_base_female    base female (Z generic body)
#   base_m build/q197/viewer_zan_atlas      base male (Z reference body)
# What it does per page: re-injects the page's own data literals into the new template (scripts/rebuild_own_html_from_built.py /
# scripts/zanatomy/rebuild_html_from_built.py: raw text, geo files copied byte for byte), copies every other sibling file of the
# source dir (clinical_* etc.; if the source has none and build/q218/_clinical_live/<page>/ exists, those), refreshes
# clinical_needle_tool.js from clinical/needle_tool.js (Q218: halos/picks honour the slice; NEEDLE_REFRESH=0 copies it verbatim),
# writes index.html = the page, then scripts/verify_regen_q218.py proves source = old template + data and new = current template + data
# (JSON per page in build/q218/_verify/, outside the page dirs). A source dir restored from a published artifact carries the service's
# document skeleton; it is removed (scripts/platform_wrap.py) so the output is the raw builder page again.
# Q220: also writes the page's public sidecar parts_data.json (sourced parts + placed markers of THIS page's body; every placement is checked
# against the page's own geometry, scripts/anatomy/q220/build_parts_sidecar.py; PARTS_SIDECAR=0 skips it).
set -eu; cd "$(dirname "$0")/.."
OUT=${Q218_OUT:-build/q218}
declare -A SRC=( [own_m]=build/q214/viewer_m_hr [own_f]=build/q216/viewer_f_hr [zan_m]=build/q211/viewer_zan_vhm
                 [zan_f]=build/q213/viewer_zan_female [base_f]=build/q202/viewer_base_female [base_m]=build/q197/viewer_zan_atlas )
declare -A KIND=( [own_m]=own [own_f]=own [zan_m]=zan [zan_f]=zan [base_f]=zan [base_m]=zan )
declare -A BODY=( [own_m]=vhm [own_f]=vhf [zan_m]=zan_m [zan_f]=zan_f [base_f]=zbase_f [base_m]=zbase_m )   # which Q219 / Q220 placement set belongs to the page
CLIVE=${Q218_CLINICAL_LIVE:-$OUT/_clinical_live}
PAGES=("$@"); [ ${#PAGES[@]} -gt 0 ] || PAGES=(own_m own_f zan_m zan_f base_f base_m)
for p in "${PAGES[@]}"; do
  [ -n "${KIND[$p]:-}" ] || { echo "unknown page '$p' (own_m own_f zan_m zan_f base_f base_m)" >&2; exit 2; }
  v="SRC_$p"; src=${!v:-${SRC[$p]}}
  [ -d "$src" ] || { echo "$p: source dir $src missing" >&2; exit 2; }
  name=$(basename "$src"); dst="$OUT/$name"
  html=$(cd "$src" && ls atlas_viewer*.html | head -1)
  mkdir -p "$dst"
  if [ "${KIND[$p]}" = own ]; then python3 scripts/rebuild_own_html_from_built.py "$src/$html" -o "$dst/$html" | tail -1
  else python3 scripts/zanatomy/rebuild_html_from_built.py "$src/$html" -o "$dst/$html" | tail -1; fi
  for f in "$src"/*; do                                  # every other sibling (clinical_*), geo files were copied by the rebuild
    b=$(basename "$f"); case "$b" in "$html"|index.html|*_geo_[0-9][0-9].txt) continue;; esac
    cp "$f" "$dst/$b"
  done
  if ! ls "$src"/clinical_* >/dev/null 2>&1 && [ -d "$CLIVE/$p" ]; then cp "$CLIVE/$p"/clinical_* "$dst/"; fi
  if [ -f "$dst/clinical_needle_tool.js" ] && [ "${NEEDLE_REFRESH:-1}" = 1 ]; then cp clinical/needle_tool.js "$dst/clinical_needle_tool.js"; fi
  if [ "${PARTS_SIDECAR:-1}" = 1 ]; then python3 scripts/anatomy/q220/build_parts_sidecar.py --html "$dst/$html" --body "${BODY[$p]}" -o "$dst/parts_data.json" | cut -c1-400; fi
  [ -f "$src/index.html" ] && cp "$dst/$html" "$dst/index.html"
  # verification against the source (the _clinical_live fallback files are not in the source: compare them separately)
  mkdir -p "$OUT/_verify"
  python3 scripts/verify_regen_q218.py "${KIND[$p]}" "$src" "$dst" | tee "$OUT/_verify/$name.json" | cut -c1-400
  echo "$p -> $dst"
done
echo Q218_REGEN_DONE
