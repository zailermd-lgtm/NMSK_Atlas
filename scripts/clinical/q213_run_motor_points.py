#!/usr/bin/env python3
"""Q213: run scripts/clinical/motor_points_q187.py on the two female pages that carry the private needle layer
(the html/bin override trick of the main session) and write the two viewers to --out / --coverage.

    python3 scripts/clinical/q213_run_motor_points.py --viewers vhf,zan_f --vhf-html H --vhf-bin B --zanf-html H2 \\
        --out build/q213/mp.json --coverage build/q213/cov.json
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import motor_points_q187 as m  # noqa: E402

R = m.REPO
ap = argparse.ArgumentParser()
ap.add_argument("--viewers", default="vhf,zan_f")
ap.add_argument("--vhf-html", default=str(R / "build/q212/viewer_f_hr/atlas_viewer_female.html"))
ap.add_argument("--vhf-bin", default=str(R / "build/viewer_f_hr_q212/bundle.bin"))
ap.add_argument("--zanf-html", default=str(R / "build/q211/viewer_zan_female/atlas_viewer_zan_female.html"))
ap.add_argument("--out", required=True)
ap.add_argument("--coverage", required=True)
ap.add_argument("--jobs", default="2")
a = ap.parse_args()
m.VIEWERS["vhf"]["html"] = Path(a.vhf_html)
m.VIEWERS["vhf"]["bin"] = Path(a.vhf_bin)
m.VIEWERS["zan_f"]["html"] = Path(a.zanf_html)
sys.argv = ["motor_points_q187.py", "--viewers", a.viewers, "--out", a.out, "--coverage", a.coverage, "--jobs", a.jobs]
sys.exit(m.main())
