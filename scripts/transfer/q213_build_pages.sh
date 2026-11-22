#!/bin/bash
# Q213: template-only HTML page of the Q213 own-female bundle (build/viewer_f_hr_q213 -> build/q213/viewer_f_hr/); the clinical_* files are staged from clinical/ by
# scripts/clinical/stage_clinical_files.py (needle tool = the private add-on, risk + motor points = regenerated for this page).  The Z page (build/q213/viewer_zan_female) is written by
# scripts/zanatomy/q213_zfit.py (in-process patch of the published Q211 page).
set -eu; cd "$(dirname "$0")/../.."
mkdir -p build/q213/viewer_f_hr
python3 scripts/build_viewer_html.py --bundle build/viewer_f_hr_q213 -o build/q213/viewer_f_hr/atlas_viewer_female.html --external-bin | tail -1
sed -i 's/<title>NMSK Atlas Viewer<\/title>/<title>NMSK Atlas Viewer (VH female)<\/title>/' build/q213/viewer_f_hr/atlas_viewer_female.html
