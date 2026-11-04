#!/bin/bash
# Q243 full chain (~35 min): HRA v1.10 structures on the pages (in-process patches, no full builds; ship diff 0 unlisted), regenerated clinical risk tables, the pre-pages, then the page dirs build/q243/<page>
# (scripts/regen_q243.sh). Needs: the HRA v1.10 GLBs (scripts/anatomy/q243/hra.py downloads + sha256-checks them from data/derived/Q242_hra_manifest.json into $Q243_HRA_DIR if missing),
# build/viewer_{f,m}_hr_q237 (own bundles), build/q239/<page dirs> (the published pages).
#   scripts/q243_build_all.sh            (re-run only the last step after a template change: scripts/regen_q243.sh)
set -eu; cd "$(dirname "$0")/.."
REF=${Q243_TEMPLATE_REF:-HEAD}; TPL=build/q243_pre/_templates; mkdir -p $TPL
git show $REF:viewer/atlas_viewer.template.html > $TPL/atlas_viewer.template.html; git show $REF:viewer/zan_atlas.template.html > $TPL/zan_atlas.template.html
export Q233_ZAN_TEMPLATE=$PWD/$TPL/zan_atlas.template.html
python3 scripts/anatomy/q243/parts_hra.py --table                                  # data/anatomy/structure_parts_hra_q243.json (uterus / tube sub-parts)
python3 scripts/transfer/q243_own.py own_f                                         # her bundle: vessels + nucleus pulposus + cord   -> build/viewer_f_hr_q243, data/derived/Q243_{report_own_f,vertex_diff_f}.json
python3 scripts/transfer/q243_own.py own_m                                         # his prostate zones: guarded, report only (not shipped)  -> data/derived/Q243_report_own_m.json
python3 scripts/zanatomy/q243_z.py comb_f                                          # Combined female: vessels                         -> build/q243_pre/viewer_zan_female
python3 scripts/zanatomy/q243_z.py base_f                                          # Base female: the vessels that pass the guards    -> build/q243_pre/viewer_base_female
python3 scripts/zanatomy/q243_z.py comb_m                                          # Combined male: prostate zones guarded, report only
python3 scripts/anatomy/q243/zspine_eval.py build/q239/viewer_zan_female atlas_viewer_zan_female -o data/derived/Q243_spine_comb_f.json
python3 scripts/anatomy/q243/parts_hra.py --markers                                # data/derived/Q243_parts_hra.json (marker per part per body, checked against the shipped meshes)
mkdir -p build/q243_pre/viewer_f_hr
python3 scripts/build_viewer_html.py --bundle build/viewer_f_hr_q243 -o build/q243_pre/viewer_f_hr/atlas_viewer_female.html --external-bin --template $TPL/atlas_viewer.template.html | tail -1
sed -i 's/<title>NMSK Atlas Viewer<\/title>/<title>NMSK Atlas Viewer (VH female)<\/title>/' build/q243_pre/viewer_f_hr/atlas_viewer_female.html
for d in viewer_f_hr viewer_zan_female viewer_base_female; do                      # sidecars of the published pages (parts + symmetry are rewritten by regen_q243.sh)
  for f in parts_data.json symmetry_q237.json; do [ -f build/q239/$d/$f ] && cp build/q239/$d/$f build/q243_pre/$d/$f; done
done
python3 scripts/clinical/risk_structures_q188.py --viewer vhf --source build/viewer_f_hr_q243 --out-dir clinical/data | tail -1
python3 scripts/clinical/risk_structures_q188.py --viewer zan_f --source build/q243_pre/viewer_zan_female/atlas_viewer_zan_female.html --out-dir clinical/data | tail -1
for d in build/q243_pre/viewer_f_hr build/viewer_f_hr_q243; do python3 scripts/clinical/stage_clinical_files.py $d --viewer vhf | tail -1; done
python3 scripts/clinical/stage_clinical_files.py build/q243_pre/viewer_zan_female --viewer zan_f | tail -1
scripts/regen_q243.sh own_f zan_f base_f | tail -4                                 # page dirs (build/q243/_verify/*.json)
python3 scripts/anatomy/q233/audit.py | tail -3 || true                            # sex audit (reads the current page dirs)
