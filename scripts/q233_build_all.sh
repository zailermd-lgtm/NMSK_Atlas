#!/bin/bash
# Q233 full chain (about 6 minutes): patches the four changed pages in-process (no full builds), regenerates the clinical risk tables, builds the pre-pages, then the six final page dirs build/q233/<page>
# with the CURRENT templates (scripts/regen_q233.sh), then the audit. Needs: third_party/hra_vh_f (in the repo), build/viewer_{m,f}_hr_q224 (the published own bundles), build/q222, build/q225 page dirs.
#   scripts/q233_build_all.sh            (re-run it after a new template lands: only the last two steps depend on it; or run scripts/regen_q233.sh alone)
set -eu; cd "$(dirname "$0")/.."
# The pre-pages are rendered from a COMMITTED template revision (Q233_TEMPLATE_REF, default HEAD) so that scripts/verify_regen_q218.py can find the template that reproduces the source page in git
# (a working tree with uncommitted template edits, e.g. another agent's, would otherwise make the verification fail); the FINAL pages are rendered from the working-tree templates by regen_q233.sh.
REF=${Q233_TEMPLATE_REF:-HEAD}; TPL=build/q233_pre/_templates; mkdir -p $TPL
git show $REF:viewer/atlas_viewer.template.html > $TPL/atlas_viewer.template.html; git show $REF:viewer/zan_atlas.template.html > $TPL/zan_atlas.template.html
export Q233_ZAN_TEMPLATE=$PWD/$TPL/zan_atlas.template.html
python3 scripts/transfer/q233_own_f.py                                   # her bundle: + HRA uterus / ovaries / tubes, - male coccyx   -> build/viewer_f_hr_q233, data/derived/Q233_{report_own_f,vertex_diff_f,organs_vhf.npz,hra_to_vhf_transform}
python3 scripts/transfer/q233_own_m.py                                   # his bundle: + Z-filled male genitalia                       -> build/viewer_m_hr_q233
python3 scripts/zanatomy/q233_z_female.py comb_f                         # Combined female: same organs in her frame                     -> build/q233_pre/viewer_zan_female
python3 scripts/zanatomy/q233_z_female.py base_f                         # Base female: organs registered on the Z pelvis, honest wording -> build/q233_pre/viewer_base_female
mkdir -p build/q233_pre/viewer_m_hr build/q233_pre/viewer_f_hr
python3 scripts/build_viewer_html.py --bundle build/viewer_m_hr_q233 -o build/q233_pre/viewer_m_hr/atlas_viewer_male.html --external-bin --template $TPL/atlas_viewer.template.html | tail -1
python3 scripts/build_viewer_html.py --bundle build/viewer_f_hr_q233 -o build/q233_pre/viewer_f_hr/atlas_viewer_female.html --external-bin --template $TPL/atlas_viewer.template.html | tail -1
sed -i 's/<title>NMSK Atlas Viewer<\/title>/<title>NMSK Atlas Viewer (VH female)<\/title>/' build/q233_pre/viewer_f_hr/atlas_viewer_female.html
python3 scripts/clinical/risk_structures_q188.py --viewer vhf --source build/viewer_f_hr_q233 --out-dir clinical/data | tail -1
python3 scripts/clinical/risk_structures_q188.py --viewer vhm --source build/viewer_m_hr_q233 --out-dir clinical/data | tail -1
python3 scripts/clinical/risk_structures_q188.py --viewer zan_f --source build/q233_pre/viewer_zan_female/atlas_viewer_zan_female.html --out-dir clinical/data | tail -1
for d in build/q233_pre/viewer_f_hr build/viewer_f_hr_q233; do python3 scripts/clinical/stage_clinical_files.py $d --viewer vhf | tail -1; done
for d in build/q233_pre/viewer_m_hr build/viewer_m_hr_q233; do python3 scripts/clinical/stage_clinical_files.py $d --viewer vhm | tail -1; done
python3 scripts/clinical/stage_clinical_files.py build/q233_pre/viewer_zan_female --viewer zan_f | tail -1
scripts/regen_q233.sh | tail -2                                          # six final page dirs, verified against their sources (build/q233/_verify/*.json)
python3 scripts/anatomy/q233/audit.py | tail -6                          # data/derived/Q233_sex_audit.{json,md} (after = the Q233 pages)
