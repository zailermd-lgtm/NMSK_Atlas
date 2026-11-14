#!/bin/bash
# Q212: template-only HTML pages of the two Q212 own-model bundles (build/viewer_*_hr_q212 -> build/q212/<page>/); clinical_* copied unchanged from the Q203 page dirs.
set -eu; cd "$(dirname "$0")/../.."
mkdir -p build/q212/viewer_m_hr build/q212/viewer_f_hr
python3 scripts/build_viewer_html.py --bundle build/viewer_m_hr_q212 -o build/q212/viewer_m_hr/atlas_viewer_male.html --external-bin | tail -1
python3 scripts/build_viewer_html.py --bundle build/viewer_f_hr_q212 -o build/q212/viewer_f_hr/atlas_viewer_female.html --external-bin | tail -1
sed -i 's/<title>NMSK Atlas Viewer<\/title>/<title>NMSK Atlas Viewer (VH female)<\/title>/' build/q212/viewer_f_hr/atlas_viewer_female.html
for p in viewer_m_hr viewer_f_hr; do for f in build/q203/$p/clinical_*; do cp -p "$f" build/q212/$p/; done; done
