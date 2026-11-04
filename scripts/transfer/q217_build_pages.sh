#!/bin/bash
# Q217: template-only HTML page of the Q217 own-male bundle (build/viewer_m_hr_q217 -> build/q217/viewer_m_hr/); the clinical_* files are staged from clinical/ by scripts/clinical/stage_clinical_files.py.
set -eu; cd "$(dirname "$0")/../.."
mkdir -p build/q217/viewer_m_hr
python3 scripts/build_viewer_html.py --bundle build/viewer_m_hr_q217 -o build/q217/viewer_m_hr/atlas_viewer_male.html --external-bin | tail -1
