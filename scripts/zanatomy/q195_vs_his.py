"""Q195: error of every Z structure that has a measured counterpart of HIS (his own mesh, same atlas id, or the organ groups of q195_refine) -- before (Q195 stage 1
= bone fit + clamp) and after (the refined build): two-way median surface distance (partial-aware for his cut meshes, Q190 chamfer).

    python3 scripts/zanatomy/q195_vs_his.py --before s1_dump.npz --after B_dump.npz --out data/derived/Q195_vs_his.json"""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True); ap.add_argument("--after", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    from scripts.zanatomy import body_ctx; body_ctx.configure("vhm")
    from scripts.zanatomy import q190_metrics as Mx, q190_refine as Q, q195_refine as R
    from scripts.transfer.zan_to_vhf_whole_body import load_her_meshes
    his = load_her_meshes()
    S0 = {d["id"]: d for d in Mx.load_dump(a.before)}
    S1 = {d["id"]: d for d in Mx.load_dump(a.after)}
    reg = json.loads(body_ctx.REGION_REPORT.read_text())["region_of_structure"]
    units = {}
    for k in S1:
        if k in his and his[k]["cat"] != "skin" and k != "skin":
            units[k] = ([k], k)
    for hid, zids in R.ORGAN_GROUPS.items():
        if hid in his and all(z in S1 for z in zids):
            units["group:" + hid] = (zids, hid)
    rows = {}
    for key, (zids, hid) in units.items():
        hv, hf = his[hid]["v"].astype(float), his[hid]["f"].astype(np.int64)
        if len(hv) < 50 or len(hf) == 0:
            continue
        ref = Q.Ref(hv, hf)
        def cat(S):
            V, F, o = [], [], 0
            for z in zids:
                V.append(S[z]["v"]); F.append(S[z]["f"] + o); o += len(S[z]["v"])
            return np.vstack(V), np.vstack(F)
        v0, f0 = cat(S0); v1, f1 = cat(S1)
        cover = (ref.tree.query(v0[::7])[0] <= Q.PARTIAL_NEAR_MM).mean()
        partial = bool(cover < Q.PARTIAL_COVER)
        b, c = Q.chamfer(v0, f0, ref, partial=partial), Q.chamfer(v1, f1, ref, partial=partial)
        rows[key] = {"his_id": hid, "cat": his[hid]["cat"], "region": reg.get(zids[0], "organ" if key.startswith("group:") else "?"), "partial_his_mesh": partial,
                     "before_mm": round(b[2], 2), "after_mm": round(c[2], 2)}
    def agg(sel):
        if not sel: return None
        b = np.array([r["before_mm"] for r in sel]); c = np.array([r["after_mm"] for r in sel])
        return {"n": len(sel), "before_median": round(float(np.median(b)), 2), "after_median": round(float(np.median(c)), 2),
                "before_max": round(float(b.max()), 1), "after_max": round(float(c.max()), 1)}
    summ = {"all": agg(list(rows.values())), "bones": agg([r for r in rows.values() if r["cat"] == "bone"]),
            "soft_tissue": agg([r for r in rows.values() if r["cat"] not in ("bone", "organ")]), "organs": agg([r for r in rows.values() if r["cat"] == "organ"])}
    for rg in sorted({r["region"] for r in rows.values()}):
        summ["region:" + rg] = agg([r for r in rows.values() if r["region"] == rg and r["cat"] != "bone"])
    Path(a.out).write_text(json.dumps({"summary": summ, "per_structure": rows}, indent=1))
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
