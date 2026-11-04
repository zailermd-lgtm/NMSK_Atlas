#!/bin/bash
# Q225 clinical regeneration for the Z FEMALE fitted page (the only Z-fitted page with the private needle layer; the Z male fitted page has no clinical files).
# Run after scripts/zanatomy/q225_pack.py female wrote build/q225_fit/viewer_zan_female: risk table regenerated (vessels / nerves moved), motor points of zan_f regenerated and MERGED into
# clinical/data/motor_points.json + the Q187 coverage (other viewers byte for byte), clinical files staged into the page dir.  Then the cut-slice + parts regeneration:
#   Q218_OUT=build/q225 SRC_zan_m=build/q225_fit/viewer_zan_vhm SRC_zan_f=build/q225_fit/viewer_zan_female scripts/regen_cut_q218.sh zan_m zan_f
set -u; cd "$(dirname "$0")/../.."
L=build/q225_logs; mkdir -p $L
python3 - <<'PY'
import json
from pathlib import Path
c = json.loads(Path("data/derived/Q187_motor_points_coverage.json").read_text())["viewers"]["zan_f"]
m = json.loads(Path("clinical/data/motor_points.json").read_text())["viewers"]["zan_f"]
Path("data/derived/Q225_motor_points_coverage_before.json").write_text(json.dumps({"viewer": "zan_f", "coverage": c, "n_points": len(m.get("points", m.get("muscles", [])))}, indent=1))
PY
python3 scripts/clinical/risk_structures_q188.py --viewer zan_f --source build/q225_fit/viewer_zan_female/atlas_viewer_zan_female.html --out-dir clinical/data > $L/risk_zan_f.log 2>&1
python3 scripts/clinical/q225_run_motor_points.py --viewers zan_f --jobs 2 > $L/motor_points_zan_f.log 2>&1
python3 scripts/clinical/stage_clinical_files.py build/q225_fit/viewer_zan_female --viewer zan_f > $L/stage_zan_f.log 2>&1
echo CLINICAL_DONE > $L/clinical_done.flag
