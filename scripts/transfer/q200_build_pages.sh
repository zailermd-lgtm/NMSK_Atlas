#!/bin/bash
# Q200: template-only HTML pages of the two Q200 own-model bundles (build/viewer_*_hr_q200 -> build/q200/<page>/), current template (Cut mode, Source facet).
set -eu; cd "$(dirname "$0")/../.."
mkdir -p build/q200/viewer_m_hr build/q200/viewer_f_hr
python3 scripts/build_viewer_html.py --bundle build/viewer_m_hr_q200 -o build/q200/viewer_m_hr/atlas_viewer_male.html --external-bin | tail -1
python3 scripts/build_viewer_html.py --bundle build/viewer_f_hr_q200 -o build/q200/viewer_f_hr/atlas_viewer_female.html --external-bin | tail -1
sed -i 's/<title>NMSK Atlas Viewer<\/title>/<title>NMSK Atlas Viewer (VH female)<\/title>/' build/q200/viewer_f_hr/atlas_viewer_female.html
