#!/bin/bash
# Q234 full chain: patches the three female pages in-process (no full builds), regenerates the clinical risk tables, builds the pre-pages, then the three final page dirs build/q234/<page>
# with the CURRENT templates (scripts/regen_q234.sh), then the sex audit. Needs: data/derived/Q234_hra_meshes.{npz,json} (scripts/anatomy/q234/hra_q234.py rebuilds them from the HRA GLBs: third_party/hra_vh_f +
# SOURCES_Q234.json, downloaded and sha256-checked if missing), build/viewer_f_hr_q233 (the Q233 own bundle), build/q233_pre/viewer_{zan_female,base_female} (the Q233 pre-pages).
#   scripts/q234_build_all.sh            (~10 min; re-run only the last steps after a template change: scripts/regen_q234.sh)
set -eu; cd "$(dirname "$0")/.."
REF=${Q234_TEMPLATE_REF:-HEAD}; TPL=build/q234_pre/_templates; mkdir -p $TPL
git show $REF:viewer/atlas_viewer.template.html > $TPL/atlas_viewer.template.html; git show $REF:viewer/zan_atlas.template.html > $TPL/zan_atlas.template.html
export Q233_ZAN_TEMPLATE=$PWD/$TPL/zan_atlas.template.html
python3 scripts/transfer/q234_own_f.py                                   # her bundle: + vagina, ligaments, breasts            -> build/viewer_f_hr_q234, data/derived/Q234_{report_own_f,vertex_diff_f}.json
python3 scripts/zanatomy/q234_z_female.py comb_f                         # Combined female                                    -> build/q234_pre/viewer_zan_female
python3 scripts/zanatomy/q234_z_female.py base_f                         # Base female                                        -> build/q234_pre/viewer_base_female
mkdir -p build/q234_pre/viewer_f_hr
python3 scripts/build_viewer_html.py --bundle build/viewer_f_hr_q234 -o build/q234_pre/viewer_f_hr/atlas_viewer_female.html --external-bin --template $TPL/atlas_viewer.template.html | tail -1
sed -i 's/<title>NMSK Atlas Viewer<\/title>/<title>NMSK Atlas Viewer (VH female)<\/title>/' build/q234_pre/viewer_f_hr/atlas_viewer_female.html
python3 scripts/clinical/risk_structures_q188.py --viewer vhf --source build/viewer_f_hr_q234 --out-dir clinical/data | tail -1
python3 scripts/clinical/risk_structures_q188.py --viewer zan_f --source build/q234_pre/viewer_zan_female/atlas_viewer_zan_female.html --out-dir clinical/data | tail -1
for d in build/q234_pre/viewer_f_hr build/viewer_f_hr_q234; do python3 scripts/clinical/stage_clinical_files.py $d --viewer vhf | tail -1; done
python3 scripts/clinical/stage_clinical_files.py build/q234_pre/viewer_zan_female --viewer zan_f | tail -1
scripts/regen_q234.sh | tail -2                                          # three final page dirs (build/q234/_verify/*.json)
python3 scripts/anatomy/q233/audit.py | tail -6                          # data/derived/Q233_sex_audit.{json,md} (after = the Q234 pages)
