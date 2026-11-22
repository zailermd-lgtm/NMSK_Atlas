#!/bin/bash
# Q197: regenerate the six viewer pages with the current templates WITHOUT recomputing any geometry, one at a time,
# into NEW directories build/q197/<page>/ (the existing build/viewer_* dirs are only read).
#   own male/female : scripts/build_viewer_html.py --template-only path (existing bundle.json/bundle.b64 -> the same
#                     base64 geo files byte for byte, new page); the female page keeps its "(VH female)" title.
#   Z-Anatomy pages : scripts/zanatomy/rebuild_html_from_built.py (data literals + geo files lifted out of the built
#                     page, wording block chosen from the manifest's variant, new template filled).
# Clinical add-on files are not copied (the main session stages them: scripts/clinical/stage_clinical_files.py).
set -eu; cd "$(dirname "$0")/.."
OUT=${Q197_OUT:-build/q197}
own() {  # <bundle dir> <page dir name> <html name> <female?>
  mkdir -p "$OUT/$2"
  python3 scripts/build_viewer_html.py --bundle "$1" -o "$OUT/$2/$3" --external-bin | tail -1
  [ "${4:-}" = f ] && sed -i 's/<title>NMSK Atlas Viewer<\/title>/<title>NMSK Atlas Viewer (VH female)<\/title>/' "$OUT/$2/$3"
  return 0
}
zan() {  # <built html> <page dir name>
  python3 scripts/zanatomy/rebuild_html_from_built.py "$1" -o "$OUT/$2/$(basename "$1")"
}
own build/viewer_m_hr_q193 viewer_m_hr atlas_viewer_male.html
own build/viewer_f_hr_q193 viewer_f_hr atlas_viewer_female.html f
zan build/viewer_zan_atlas/atlas_viewer_zan_atlas.html viewer_zan_atlas
zan build/viewer_base_female_q196/atlas_viewer_base_female.html viewer_base_female
zan build/viewer_zan_male_fitted_q195/atlas_viewer_zan_male_fitted.html viewer_zan_male_fitted
zan build/viewer_zan_female/atlas_viewer_zan_female.html viewer_zan_female
echo Q197_REBUILD_DONE
