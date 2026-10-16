#!/bin/bash
# Q214: template-only HTML pages of the two Q214 own-model bundles (build/viewer_{m,f}_hr_q214 -> build/q214/viewer_{m,f}_hr/); the clinical_* files are staged from clinical/ by
# scripts/clinical/stage_clinical_files.py (needle tool = the private add-on, risk + motor points = regenerated / checked for these pages).
set -eu; cd "$(dirname "$0")/../.."
mkdir -p build/q214/viewer_m_hr build/q214/viewer_f_hr
python3 scripts/build_viewer_html.py --bundle build/viewer_m_hr_q214 -o build/q214/viewer_m_hr/atlas_viewer_male.html --external-bin | tail -1
python3 scripts/build_viewer_html.py --bundle build/viewer_f_hr_q214 -o build/q214/viewer_f_hr/atlas_viewer_female.html --external-bin | tail -1
sed -i 's/<title>NMSK Atlas Viewer<\/title>/<title>NMSK Atlas Viewer (VH female)<\/title>/' build/q214/viewer_f_hr/atlas_viewer_female.html
