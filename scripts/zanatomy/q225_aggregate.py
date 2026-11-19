#!/usr/bin/env python3
"""Q225: the UNCHANGED Q204 aggregator over the Q225 raw runs (build/q225_raw[_merged]) -> build/q225_agg/Q204_anatomy_audit.json (full, git-ignored; the committed outputs are the compact Q225_audit_*.json)."""
import json, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import scripts.zanatomy.q225_paths  # noqa: F401,E402
from scripts.zanatomy import q204_aggregate as A  # noqa: E402

TMP = REPO / "build" / "q225_agg"; TMP.mkdir(exist_ok=True)
t = TMP / "Q198_anatomy_audit.json"
if not t.exists():
    t.symlink_to(REPO / "data/derived/Q198_anatomy_audit.json")
A.DER = TMP
A.RAW = REPO / "build" / "q225_raw"; A.RAWM = REPO / "build" / "q225_raw_merged"
A.PAGE_DIR.update({"z_male": "build/q222/viewer_zan_atlas", "z_base_f": "build/q222/viewer_base_female", "z_male_fit": "build/q225_fit/viewer_zan_vhm", "z_female_fit": "build/q225_fit/viewer_zan_female",
                   "own_m": "build/q221/viewer_m_hr (+build/viewer_m_hr_q217)", "own_f": "build/q222/viewer_f_hr (+build/viewer_f_hr_q216)"})
A.main()
