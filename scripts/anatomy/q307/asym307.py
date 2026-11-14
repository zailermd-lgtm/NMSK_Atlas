"""Q307: on the two Imaging pages, find every nerve where the two sides do not come from the same source or
do not have the same extent -- the failure mode Q307 found behind the owner's "everything must exist AND be in
the right place": Q304 added a transferred, full-length nerve on ONE side and left the pre-Q304 stub standing
on the other, so the page carries two contradictory meshes under one name (Imaging F's left femoral nerve is a
26 mm stub in the groin while its right femoral nerve is the full 485 mm nerve).

Length is measured along each mesh's OWN principal axis (a nerve is a tube, so its bbox diagonal over-reads
when the limb is oblique, which the Combined/Imaging poses are)."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts" / "anatomy" / "q307"))
import place307 as P  # noqa: E402


def axis_len(v):
    c = v.mean(0)
    u = np.linalg.svd(v - c, full_matrices=False)[2][0]
    t = (v - c) @ u
    return float(t.max() - t.min())


def scan(key):
    m = P.MODEL.Model(key)
    cal = P.calibre_nerves(key)
    by = {}
    for x in m.S:
        by.setdefault(x["id"], []).append(x)
    groups = {}
    for i in cal:
        if i not in by:
            continue
        v = np.vstack([x["v"] for x in by[i]])
        rec = dict(id=i, side=by[i][0]["side"], src=by[i][0].get("src"), n=int(len(v)),
                   axis_len_mm=round(axis_len(v), 1))
        groups.setdefault(P.base_id(i), []).append(rec)
    rows = []
    for b, rs in sorted(groups.items()):
        sides = {r["side"]: r for r in rs}
        srcs = {r["src"] for r in rs}
        lens = [r["axis_len_mm"] for r in rs]
        ratio = (max(lens) / max(1e-6, min(lens))) if len(lens) > 1 else 1.0
        bad = []
        if len(rs) > 1 and len(srcs) > 1:
            bad.append("sources differ")
        if ratio >= 2.0:
            bad.append(f"length ratio {ratio:.1f}x")
        if "m" in sides and len(rs) > 1:
            bad.append("an unsided mesh coexists with sided ones")
        if bad:
            rows.append(dict(base=b, why="; ".join(bad), members=rs,
                             worst_ratio=round(ratio, 2), shortest_mm=min(lens), longest_mm=max(lens)))
    del m
    return dict(page=key, n_nerve=len(cal), n_groups=len(groups), offenders=rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", default="own_m,own_f")
    ap.add_argument("--out", default="/dev/shm/q307")
    a = ap.parse_args()
    out = {}
    for k in a.pages.split(","):
        r = scan(k)
        out[k] = r
        print(f"=== {k}: {r['n_nerve']} nerve meshes, {r['n_groups']} nerve names, {len(r['offenders'])} with a side/source mismatch")
        for o in sorted(r["offenders"], key=lambda o: -o["worst_ratio"]):
            print(f"  {o['base']:52s} {o['why']}")
            for mm in o["members"]:
                print(f"      {mm['id']:46s} side={mm['side']} len={mm['axis_len_mm']:7.1f} mm  n={mm['n']:5d}  src={mm['src']}")
    Path(a.out).mkdir(parents=True, exist_ok=True)
    json.dump(out, open(Path(a.out) / "Q307_side_source_mismatch.json", "w"), indent=1)


if __name__ == "__main__":
    main()
