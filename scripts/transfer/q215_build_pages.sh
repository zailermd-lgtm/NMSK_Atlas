#!/bin/bash
# Q215: template-only HTML page of the Q215 own-female bundle (build/viewer_f_hr_q215 -> build/q215/viewer_f_hr/); the clinical_* files are staged from clinical/ by
# scripts/clinical/stage_clinical_files.py (needle tool = the private add-on, risk checked, motor points regenerated for this page).  The Z-fitted female page is not touched.
set -eu; cd "$(dirname "$0")/../.."
mkdir -p build/q215/viewer_f_hr
python3 scripts/build_viewer_html.py --bundle build/viewer_f_hr_q215 -o build/q215/viewer_f_hr/atlas_viewer_female.html --external-bin | tail -1
sed -i 's/<title>NMSK Atlas Viewer<\/title>/<title>NMSK Atlas Viewer (VH female)<\/title>/' build/q215/viewer_f_hr/atlas_viewer_female.html
