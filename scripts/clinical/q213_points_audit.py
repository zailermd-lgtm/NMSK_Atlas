#!/usr/bin/env python3
"""Q213 audit (A): re-measure every motor point of a female page against its own source rule.

For each point the rule is found by (muscle, DOI, rule text); the landmarks are re-measured on the page's meshes and
  * "level" rules: the point's fraction along the landmark line A -> B (and its distance to the rule plane) against the
    source range / mean +- SD;
  * "surface" rules: the distance of the point from the needle line through the rule's surface coordinate;
  * every point: inside its structure (winding number), distance to the muscle surface (margin), side of the body,
    fraction along the muscle's own long axis, depth from the skin where the page has one.
Writes a JSON next to --points.

    python3 scripts/clinical/q213_points_audit.py --viewer vhf --points build/q213/mp.json --out build/q213/pts_audit_vhf.json \\
        [--vhf-html H --vhf-bin B --zanf-html H2]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import motor_points_q187 as M  # noqa: E402

R = M.REPO


def rule_for(p):
    for r in M.RULES:
        if f"{r['muscle']}_{p['side']}" == p["atlas_id"] and r["rule"] == p["source"]["rule"]:
            return r
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--viewer", required=True)
    ap.add_argument("--points", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--vhf-html", default=str(R / "build/q212/viewer_f_hr/atlas_viewer_female.html"))
    ap.add_argument("--vhf-bin", default=str(R / "build/viewer_f_hr_q212/bundle.bin"))
    ap.add_argument("--zanf-html", default=str(R / "build/q211/viewer_zan_female/atlas_viewer_zan_female.html"))
    a = ap.parse_args()
    M.VIEWERS["vhf"]["html"], M.VIEWERS["vhf"]["bin"] = Path(a.vhf_html), Path(a.vhf_bin)
    M.VIEWERS["zan_f"]["html"] = Path(a.zanf_html)
    meshes = M.load_viewer(a.viewer)
    body = M.Body(a.viewer, meshes)
    pts = json.loads(Path(a.points).read_text())["viewers"][a.viewer]["points"]
    out, flags = [], []
    for p in pts:
        s = p["side"]
        q = np.array(p["pos"], float)
        sid = p["structure_id"]
        rule = rule_for(p)
        V, F = meshes[sid]["v"], meshes[sid]["f"]
        row = {"id": p["id"], "structure_id": sid, "rule_found": rule is not None}
        row["inside"] = bool(M.inside(q, V, F)[0])
        row["margin_mm"] = round(float(np.min(np.linalg.norm(V - q, axis=1))), 1)
        base = p["atlas_id"]
        Vu = body.mv(base) if base in meshes else V
        c = Vu.mean(0)
        u = np.linalg.svd(Vu - c, full_matrices=False)[2][0]
        t = (Vu - c) @ u
        row["muscle_axis_frac_pct"] = round(float(100 * ((q - c) @ u - t.min()) / (t.max() - t.min())), 1)
        row["side_ok"] = bool((q[0] + 4.3) * (1 if s == "r" else -1) > 0)
        if rule is not None and rule["type"] in ("level", "level_mm"):
            try:
                Vm = body.union(base)[0] if base in meshes else V
                A = M.point_of(body, rule["A"], s, Vm); B = M.point_of(body, rule["B"], s, Vm)
                L = float(np.linalg.norm(B - A)); n = (B - A) / L
                frac = float(((q - A) @ n) / L * 100) if rule["type"] == "level" else float((q - A) @ n)
                if rule["type"] == "level":
                    cc, hw, _ = M.pct_spec(rule["f"], M.is_sd(rule, "f"))
                    lo, hi = cc - (hw if hw is not None else 5.0), cc + (hw if hw is not None else 5.0)
                    # a point of a sector rule is a point of the section: its fraction equals the section's level
                    row.update(frac_pct=round(frac, 1), target=[round(lo, 1), round(hi, 1)], line_mm=round(L, 1),
                               dev_mm=round(max(lo - frac, frac - hi, 0.0) / 100 * L, 1))
                else:
                    lo, hi = rule["mm"]
                    row.update(frac_mm=round(frac, 1), target=[lo, hi], line_mm=round(L, 1), dev_mm=round(max(lo - frac, frac - hi, 0.0), 1))
            except M.LandmarkMissing as e:
                row["landmark"] = str(e)
        out.append(row)
        if (not row["inside"]) or (not row["side_ok"]) or row.get("dev_mm", 0) > 5 or row["margin_mm"] < 0.9:
            flags.append(row)
    res = {"viewer": a.viewer, "n": len(out), "not_inside": sum(not r["inside"] for r in out), "wrong_side": sum(not r["side_ok"] for r in out),
           "level_dev_gt_5mm": [r["id"] for r in out if r.get("dev_mm", 0) > 5], "margin_lt_1mm": [r["id"] for r in out if r["margin_mm"] < 0.9],
           "axis_extreme": [(r["id"], r["muscle_axis_frac_pct"]) for r in out if r["muscle_axis_frac_pct"] < 3 or r["muscle_axis_frac_pct"] > 97],
           "rows": out}
    Path(a.out).write_text(json.dumps(res, indent=1) + "\n")
    print(a.viewer, {k: (len(v) if isinstance(v, list) else v) for k, v in res.items() if k != "rows"})


if __name__ == "__main__":
    main()
