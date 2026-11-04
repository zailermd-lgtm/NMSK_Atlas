#!/usr/bin/env python3
"""Q249: build the rule-based nerves of one page.   python3 scripts/anatomy/q249/run_rule.py KEY [--only roots,pudendal,...]
KEY = own_m own_f comb_m comb_f base_m base_f  ->  data/derived/Q249_rule_<KEY>.npz (vertices float32, faces int32 of the SHIPPED nerves) + .json (reports of shipped + held + skipped).
Page sources: Q249_SRC_<key> or the Q248 / Q250 page dirs below (the latest published pages)."""
from __future__ import annotations
import json, os, sys, time
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[2]
SRC = {"own_m": "build/q248/viewer_m_hr", "own_f": "build/q248/viewer_f_hr", "comb_m": "build/q248/viewer_zan_vhm", "base_m": "build/q248/viewer_zan_atlas",
       "base_f": "build/q250/viewer_base_female", "comb_f": "build/q250/viewer_zan_female"}
for k, d in SRC.items():
    os.environ.setdefault("Q248_SRC_" + k, os.environ.get("Q249_SRC_" + k, str(REPO / d)))
sys.path.insert(0, str(HERE))
import lm, rule_nerves as RN  # noqa: E402


def pair_symmetry(B, P):
    """left / right pairs: length ratio and the mean distance between the mirrored (about the midline) left path and the right path.  Held (both sides) if the length ratio exceeds 2.2, or - pelvic / back nerves only,
    the limb nerves stand on arms that are posed differently on the two sides - if the mirrored paths are more than 30 mm apart."""
    from scipy.spatial import cKDTree
    xm = P.F["x_mid"]; by = {e["id"]: e for e in B.out if e.get("status") == "ship"}; rep = {}
    for i, e in list(by.items()):
        if not i.endswith("_l") or i[:-2] + "_r" not in by:
            continue
        r = by[i[:-2] + "_r"]
        pl = e["path"].copy(); pl[:, 0] = 2 * xm - pl[:, 0]; pr = r["path"]
        d = float((cKDTree(pr).query(pl)[0].mean() + cKDTree(pl).query(pr)[0].mean()) / 2)
        L1, L2 = e["report"]["length_mm"], r["report"]["length_mm"]; ratio = max(L1, L2) / min(L1, L2)
        limb = i.startswith(("recurrent", "posterior_femoral"))
        bad = ratio > 2.2 or (not limb and d > 30.0)
        rep[i[:-2]] = dict(length_l=L1, length_r=L2, length_ratio=round(ratio, 2), mirrored_path_distance_mm=round(d, 1), held=bad)
        e["report"]["pair_symmetry"] = r["report"]["pair_symmetry"] = rep[i[:-2]]
        if bad:
            why = f"left / right pair not symmetric: length ratio {ratio:.2f}, mirrored paths {d:.0f} mm apart"
            for x in (e, r):
                x["status"] = "held"; x.setdefault("held", []).append(why)
    return rep


def main(key, only=None):
    t = time.time()
    P = lm.Pel(key)
    B = RN.build(P, only=only)
    out = REPO / "data/derived"
    sym = pair_symmetry(B, P)
    arrs, rep = {}, {}
    for e in B.out:
        r = dict(id=e["id"], status=e["status"], held=e.get("held", []))
        if "report" in e:
            r.update(report=e["report"], side=e["side"], name=e["name"], latin=e["latin"], region=e.get("region"), calibre_kind=e.get("cal_kind"))
        rep[e["id"]] = r
        if "V" in e and e["status"] == "ship":
            arrs[e["id"] + "__v"] = np.asarray(e["V"], np.float32); arrs[e["id"] + "__f"] = np.asarray(e["F"], np.int32)
            arrs[e["id"] + "__p"] = np.asarray(e["path"], np.float32); arrs[e["id"] + "__d"] = np.asarray(e["d"], np.float32)
        print(f"{key} {e['id']:38s} {e['status']:5s} len={e.get('report', {}).get('length_mm')} d={e.get('report', {}).get('diameter_mm')} {'; '.join(e.get('held', []))}", flush=True)
    np.savez_compressed(out / f"Q249_rule_{key}.npz", **arrs)
    cards = {e["id"]: dict(name=e["name"], latin=e["latin"], side=e["side"], cat="nerve", rec=e["rec"]) for e in B.out if e["status"] == "ship"}
    sk = B.skipped
    meta = dict(page=key, frame=P.F, sacrum=P.sac, landmark_notes=P.notes, structures=rep, cards=cards, skipped=sk, seconds=round(time.time() - t, 1),
                landmarks={k: np.round(v, 2).tolist() for k, v in P.lm.items() if not k.endswith(("normal_l", "normal_r"))})
    (out / f"Q249_rule_{key}.json").write_text(json.dumps(meta, indent=1, default=float) + "\n")
    ship = sum(1 for e in B.out if e["status"] == "ship"); print(f"{key}: shipped {ship}, held {sum(1 for e in B.out if e['status'] == 'held')}, skipped (already on page) {len(sk)}; {round(time.time() - t)} s")


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1].split(","); a = [x for x in a if x != sys.argv[sys.argv.index("--only") + 1]]
    main(a[0], only)
