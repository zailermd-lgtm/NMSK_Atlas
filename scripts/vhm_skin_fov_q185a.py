"""Q185a: badge HIS skin record with the CT field-of-view cut (no skin is made up beyond it).

    python3 scripts/vhm_skin_fov_q185a.py measure [--sweep data/derived/Q185a_sweep_vhm.json]  # -> data/derived/Q185a_skin_fov_vhm.json
    python3 scripts/vhm_skin_fov_q185a.py stamp                                                 # badge build/vh/ct_vhm_skin (rebuild step)

His skin (ct_vhm_skin, scripts/cryo/vhm_whole_body_skin.py) is surfaced from his CT blocks, whose transverse field of view
ends at atlas x = -233.4 / +246.6 mm: the surface is closed by flat caps there, and whatever of his arms lies beyond is
not covered. The placement sweep (scripts/placement_sweep_q185.py) now counts vertices beyond those planes (1 mm inside
the skin's own x extent) as "skin unknown", not "outside skin". `measure` lists the records of his bundle that have
any vertex there (from a sweep report), grouped by region; `stamp` writes the badge onto the skin record's manifest.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
OUT = REPO / "data" / "derived" / "Q185a_skin_fov_vhm.json"
SWEEP = REPO / "data" / "derived" / "Q185a_sweep_vhm.json"
SKIN = REPO / "build" / "vh" / "ct_vhm_skin"


def measure(sweep: Path) -> int:
    import numpy as np
    from scripts.placement_sweep_q185 import fov_cut
    from scripts.ribs_from_ct_labels import load_skin
    sk = load_skin("vhm").vertices; lo, hi = fov_cut(sk)
    S = json.loads(sweep.read_text())["vhm"]["structures"]
    aff = {a: r for a, r in S.items() if (r.get("skin_unknown_frac") or 0) > 0}
    by = {}
    for a, r in sorted(aff.items(), key=lambda x: -x[1]["skin_unknown_frac"]):
        by.setdefault(r.get("region") or r["cat"], []).append(
            {"id": a, "skin_unknown_frac": r["skin_unknown_frac"], "outside_skin_frac_incl_fov": r.get("outside_skin_frac_incl_fov"),
             "outside_skin_frac": r["outside_skin_frac"]})
    # where along the body the cut actually removes skin: y range of cap vertices (on the planes)
    cap = {s: sk[np.abs(sk[:, 0] - x) < 1.0] for s, x in (("left_x_min", float(sk[:, 0].min())), ("right_x_max", float(sk[:, 0].max())))}
    rep = {"_README": (__doc__ or "").strip().splitlines(),
           "skin_x_extent_mm": [round(float(sk[:, 0].min()), 1), round(float(sk[:, 0].max()), 1)],
           "fov_planes_mm": [round(lo, 1), round(hi, 1)],
           "cap_y_range_mm": {k: [round(float(v[:, 1].min()), 1), round(float(v[:, 1].max()), 1)] if len(v) else None for k, v in cap.items()},
           "n_records_beyond": len(aff), "by_region": by, "sweep": str(sweep.relative_to(REPO))}
    OUT.write_text(json.dumps(rep, indent=1))
    print(f"wrote {OUT.relative_to(REPO)}: planes {rep['fov_planes_mm']}, {len(aff)} records beyond; caps {rep['cap_y_range_mm']}")
    return 0


def badge_text(rep: dict) -> str:
    (xl, xr), cy = rep["skin_x_extent_mm"], rep["cap_y_range_mm"]
    ylo = min(v[0] for v in cy.values() if v); yhi = max(v[1] for v in cy.values() if v)
    regs = ", ".join(f"{k} {len(v)}" for k, v in sorted(rep["by_region"].items(), key=lambda x: -len(x[1])))
    top = ", ".join(x["id"] for v in rep["by_region"].values() for x in v if x["skin_unknown_frac"] >= 0.2)
    return (f"FIELD-OF-VIEW CUT (Q185a): his skin is surfaced from his CT, whose field of view ends at x = {xl:.0f} mm and "
            f"x = +{xr:.0f} mm; the surface is closed by flat caps on those planes (atlas y {ylo:.0f}..{yhi:.0f} mm: the "
            f"lateral upper arms, elbows and proximal forearms), and NOTHING beyond them is skin-covered. "
            f"{rep['n_records_beyond']} of his structures reach past the cut ({regs}; >= 20 % of their vertices: "
            f"{top or 'none'}): they are not outside his body, the skin is missing there. A real source (his own "
            "cryosection photographs of the arms) is queued; no skin is synthesised.")


def stamp() -> int:
    rep = json.loads(OUT.read_text())
    m = json.loads((SKIN / "manifest.json").read_text())
    for s in m["structures"]:
        if s["atlas_id"] == "skin":
            s["procedural_badge"] = badge_text(rep); s["fov_cut_mm"] = rep["fov_planes_mm"]
    (SKIN / "manifest.json").write_text(json.dumps(m, indent=2))
    print("stamped ct_vhm_skin")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["measure", "stamp"]); ap.add_argument("--sweep", default=str(SWEEP))
    a = ap.parse_args(argv)
    return measure(Path(a.sweep)) if a.cmd == "measure" else stamp()


if __name__ == "__main__":
    sys.exit(main())
