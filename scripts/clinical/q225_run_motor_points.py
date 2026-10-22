#!/usr/bin/env python3
"""Q225: run scripts/clinical/motor_points_q187.py on the Z female fitted page (the only Q225 page with the private needle layer) (the html/bin override trick of the main session) and MERGE the
regenerated viewers into the existing clinical/data/motor_points.json + data/derived/Q187_motor_points_coverage.json (the other viewers stay byte for byte as the main session left them).

    python3 scripts/clinical/q225_run_motor_points.py --viewers zan_f \\
        [--zanf-html H2] [--out clinical/data/motor_points.json --coverage data/derived/Q187_motor_points_coverage.json]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import motor_points_q187 as m  # noqa: E402

R = m.REPO
ap = argparse.ArgumentParser()
ap.add_argument("--viewers", default="zan_f")
ap.add_argument("--zanf-html", default=str(R / "build/q225_fit/viewer_zan_female/atlas_viewer_zan_female.html"))
ap.add_argument("--out", default=str(m.OUT_JSON))
ap.add_argument("--coverage", default=str(m.OUT_COVERAGE))
ap.add_argument("--jobs", type=int, default=2)
a = ap.parse_args()
m.VIEWERS["zan_f"]["html"] = Path(a.zanf_html)
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
