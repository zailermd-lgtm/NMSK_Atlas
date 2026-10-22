#!/usr/bin/env python3
"""Q248 (b): build the rule-based ligaments of one page.   python3 scripts/anatomy/q248/rule_run.py KEY   (KEY = own_m own_f comb_m comb_f base_m base_f)  ->  data/derived/Q248_rule_<KEY>.npz + .json"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rulelig as RL, rule_specs as RS  # noqa: E402


def main(key):
    ctx = RL.Ctx(key)
    res = RS.build(ctx)
    out = HERE.parents[2] / "data/derived"
    arrs, rep = {}, {}
    for e in res:
        r = dict(id=e["id"], status=e["status"], held=e.get("held", []))
        if "report" in e:
            r.update(report=e["report"], side=e["side"], name=e["name"], endpoints=e["endpoints"])
        rep[e["id"]] = r
        if "V" in e:
            arrs[e["id"] + "__v"] = e["V"]; arrs[e["id"] + "__f"] = e["F"]
        print(f"{key} {e['id']:40s} {e['status']:5s} len={e.get('report', {}).get('length_mm')} vol={e.get('report', {}).get('volume_cm3')} {'; '.join(e.get('held', []))}", flush=True)
    np.savez_compressed(out / f"Q248_rule_{key}.npz", **arrs)
    meta = {e["id"]: dict(name=e["name"], latin=e["latin"], side=e["side"], cat=e["cat"], rec=e["rec"]) for e in res if "V" in e}
    (out / f"Q248_rule_{key}.json").write_text(json.dumps(dict(page=key, frame=ctx.F, structures=rep, cards=meta), indent=1, default=float) + "\n")


if __name__ == "__main__":
    main(sys.argv[1])
