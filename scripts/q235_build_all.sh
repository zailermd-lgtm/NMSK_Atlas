#!/bin/bash
# Q235 full chain: registers the CVH pelvic set onto her pelvis, patches the Imaging-based and Combined female pages in-process (no full builds), regenerates the clinical risk tables, builds the pre-pages, then the two final page
# dirs build/q235/<page> with the CURRENT templates (scripts/regen_q235.sh), then the sex audit. Needs: third_party/cvh_wu2015 (meshes), build/viewer_f_hr_q234 (the Q234 own bundle), build/q234_pre/viewer_{zan_female,base_female}
# (the Q234 pre-pages), data/derived/Q234_hra_meshes.* (only for the audit).
#   scripts/q235_build_all.sh            (~12 min; re-run only the last steps after a template change: scripts/regen_q235.sh)
set -eu; cd "$(dirname "$0")/.."
REF=${Q235_TEMPLATE_REF:-HEAD}; TPL=build/q235_pre/_templates; mkdir -p $TPL
git show $REF:viewer/atlas_viewer.template.html > $TPL/atlas_viewer.template.html; git show $REF:viewer/zan_atlas.template.html > $TPL/zan_atlas.template.html
export Q233_ZAN_TEMPLATE=$PWD/$TPL/zan_atlas.template.html
[ -f data/derived/Q235_cvh_to_vhf_transform.json ] && [ "${Q235_REGISTER:-0}" != 1 ] || python3 scripts/anatomy/q235/register_own.py | tail -1     # CVH bones -> her bones (both side conventions, chirality evidence)
python3 scripts/transfer/q235_own_f.py                                   # her bundle: + clitoris, bulbs, glands, perineal muscles, urethra, perineal body -> build/viewer_f_hr_q235, data/derived/Q235_{report_own_f,vertex_diff_f}.json
python3 scripts/zanatomy/q235_z_female.py comb_f                         # Combined female                                    -> build/q235_pre/viewer_zan_female
python3 scripts/zanatomy/q235_z_female.py base_f                         # Base female: registration + guards, report only (no page: the male-derived pelvis does not accept the structures)
mkdir -p build/q235_pre/viewer_f_hr
python3 scripts/build_viewer_html.py --bundle build/viewer_f_hr_q235 -o build/q235_pre/viewer_f_hr/atlas_viewer_female.html --external-bin --template $TPL/atlas_viewer.template.html | tail -1
sed -i 's/<title>NMSK Atlas Viewer<\/title>/<title>NMSK Atlas Viewer (VH female)<\/title>/' build/q235_pre/viewer_f_hr/atlas_viewer_female.html
python3 scripts/clinical/risk_structures_q188.py --viewer vhf --source build/viewer_f_hr_q235 --out-dir clinical/data | tail -1
python3 scripts/clinical/risk_structures_q188.py --viewer zan_f --source build/q235_pre/viewer_zan_female/atlas_viewer_zan_female.html --out-dir clinical/data | tail -1
for d in build/q235_pre/viewer_f_hr build/viewer_f_hr_q235; do python3 scripts/clinical/stage_clinical_files.py $d --viewer vhf | tail -1; done
python3 scripts/clinical/stage_clinical_files.py build/q235_pre/viewer_zan_female --viewer zan_f | tail -1
scripts/regen_q235.sh | tail -2                                          # the two final page dirs (build/q235/_verify/*.json)
python3 scripts/anatomy/q233/audit.py | tail -6                          # data/derived/Q233_sex_audit.{json,md} (after = the Q235 pages)
