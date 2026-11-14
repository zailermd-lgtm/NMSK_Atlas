#!/bin/bash
# Q237 full chain (~25 min): classification + asymmetry of the six current pages (data/derived/Q237_pairing.{json,md}), the mirror fill of the missing / listed-defect sides on the six pages (in-process patches, no
# full builds; ship diff 0 unlisted), regenerated clinical risk tables, the pre-pages, then the six final page dirs build/q237/<page> (scripts/regen_q237.sh) with the Symmetric view.
# Needs: build/viewer_{m_hr_q233,f_hr_q235} (own bundles), build/q233/{viewer_zan_vhm,viewer_zan_atlas}, build/q234/viewer_base_female, build/q235/viewer_zan_female (the current page dirs),
# build/q225_raw*/Q204_regions_*.json (the Q198 / Q204 audit rows = the listed defects; git-ignored, rebuilt by scripts/zanatomy/q225_*.py).
#   scripts/q237_build_all.sh          (re-run only the last step after a template change: scripts/regen_q237.sh)
set -eu; cd "$(dirname "$0")/.."
REF=${Q237_TEMPLATE_REF:-HEAD}; TPL=build/q237_pre/_templates; mkdir -p $TPL
git show $REF:viewer/atlas_viewer.template.html > $TPL/atlas_viewer.template.html; git show $REF:viewer/zan_atlas.template.html > $TPL/zan_atlas.template.html
export Q233_ZAN_TEMPLATE=$PWD/$TPL/zan_atlas.template.html
python3 scripts/anatomy/q237/pairing.py | tail -7                                  # steps 1 + 2: data/derived/Q237_pairing.json
python3 scripts/transfer/q237_own.py own_m                                          # his bundle: + mirror fills            -> build/viewer_m_hr_q237, data/derived/Q237_{fill_own_m,vertex_diff_m}.json
python3 scripts/transfer/q237_own.py own_f                                          # her bundle                            -> build/viewer_f_hr_q237
for k in comb_m comb_f base_m base_f; do python3 scripts/zanatomy/q237_z.py $k | tail -2; done      # -> build/q237_pre/<page dir>
mkdir -p build/q237_pre/viewer_m_hr build/q237_pre/viewer_f_hr
python3 scripts/build_viewer_html.py --bundle build/viewer_m_hr_q237 -o build/q237_pre/viewer_m_hr/atlas_viewer_male.html --external-bin --template $TPL/atlas_viewer.template.html | tail -1
python3 scripts/build_viewer_html.py --bundle build/viewer_f_hr_q237 -o build/q237_pre/viewer_f_hr/atlas_viewer_female.html --external-bin --template $TPL/atlas_viewer.template.html | tail -1
sed -i 's/<title>NMSK Atlas Viewer<\/title>/<title>NMSK Atlas Viewer (VH female)<\/title>/' build/q237_pre/viewer_f_hr/atlas_viewer_female.html
python3 scripts/clinical/risk_structures_q188.py --viewer vhm --source build/viewer_m_hr_q237 --out-dir clinical/data | tail -1
python3 scripts/clinical/risk_structures_q188.py --viewer vhf --source build/viewer_f_hr_q237 --out-dir clinical/data | tail -1
python3 scripts/clinical/risk_structures_q188.py --viewer zan_f --source build/q237_pre/viewer_zan_female/atlas_viewer_zan_female.html --out-dir clinical/data | tail -1
python3 scripts/clinical/risk_structures_q188.py --viewer zan_m --source build/q237_pre/viewer_zan_atlas/atlas_viewer_zan_atlas.html --out-dir clinical/data | tail -1
for d in build/q237_pre/viewer_m_hr build/viewer_m_hr_q237; do python3 scripts/clinical/stage_clinical_files.py $d --viewer vhm | tail -1; done
for d in build/q237_pre/viewer_f_hr build/viewer_f_hr_q237; do python3 scripts/clinical/stage_clinical_files.py $d --viewer vhf | tail -1; done
python3 scripts/clinical/stage_clinical_files.py build/q237_pre/viewer_zan_female --viewer zan_f | tail -1
python3 scripts/clinical/stage_clinical_files.py build/q237_pre/viewer_zan_atlas --viewer zan_m | tail -1
scripts/regen_q237.sh | tail -3                                                      # six final page dirs (build/q237/_verify/*.json)
python3 scripts/anatomy/q237/after_counts.py build/q237 | tail -6
python3 scripts/anatomy/q237/report_md.py
