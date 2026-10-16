#!/usr/bin/env python3
"""Q215: run scripts/clinical/motor_points_q187.py on the two OWN pages whose structures changed in Q215 (own female build/q215/viewer_f_hr (the male page is not touched in Q215); the html / bin
override trick of the main session) and MERGE the regenerated viewers into the existing clinical/data/motor_points.json + data/derived/Q187_motor_points_coverage.json (the other viewers stay
byte for byte as the main session left them).

    python3 scripts/clinical/q215_run_motor_points.py --viewers vhm,vhf [--vhm-html H --vhm-bin B --vhf-html H2 --vhf-bin B2] \\
        [--out clinical/data/motor_points.json --coverage data/derived/Q187_motor_points_coverage.json]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import motor_points_q187 as m  # noqa: E402

R = m.REPO
ap = argparse.ArgumentParser()
ap.add_argument("--viewers", default="vhf")
ap.add_argument("--vhm-html", default=str(R / "build/q214/viewer_m_hr/atlas_viewer_male.html"))
ap.add_argument("--vhm-bin", default=str(R / "build/viewer_m_hr_q214/bundle.bin"))
ap.add_argument("--vhf-html", default=str(R / "build/q215/viewer_f_hr/atlas_viewer_female.html"))
ap.add_argument("--vhf-bin", default=str(R / "build/viewer_f_hr_q215/bundle.bin"))
ap.add_argument("--out", default=str(m.OUT_JSON))
ap.add_argument("--coverage", default=str(m.OUT_COVERAGE))
ap.add_argument("--jobs", type=int, default=2)
a = ap.parse_args()
m.VIEWERS["vhm"]["html"] = Path(a.vhm_html)
m.VIEWERS["vhm"]["bin"] = Path(a.vhm_bin)
m.VIEWERS["vhf"]["html"] = Path(a.vhf_html)
m.VIEWERS["vhf"]["bin"] = Path(a.vhf_bin)
keys = a.viewers.split(",")
out, cov = m.run(keys, a.jobs)
old = json.loads(Path(a.out).read_text()) if Path(a.out).exists() else {"schema": out["schema"], "licence": out["licence"], "viewers": {}}
oldc = json.loads(Path(a.coverage).read_text()) if Path(a.coverage).exists() else {"viewers": {}}
for k in keys:
    old["viewers"][k] = out["viewers"][k]
    oldc["viewers"][k] = cov["viewers"][k]
old["generated"] = out["generated"]
oldc.update({k: v for k, v in cov.items() if k != "viewers"})
Path(a.out).write_text(json.dumps(old, indent=1, ensure_ascii=False) + "\n")
Path(a.coverage).write_text(json.dumps(oldc, indent=1, ensure_ascii=False) + "\n")
print("merged", keys, "into", a.out, "and", a.coverage)
