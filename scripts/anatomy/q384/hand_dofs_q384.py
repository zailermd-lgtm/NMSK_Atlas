#!/usr/bin/env python3
"""Q384 / E5: finger abduction / adduction, thumb axial rotation and thumb opposition in the pose rig of a Base page.

Owner, 2026-11-22: "in the fingers there is also abduction and adduction, and in the thumb also opposition."

The stored rigs are spliced, not rebuilt (see scripts/anatomy/q338/splice_rig_q338.py), so the new degrees of freedom are
added to the stored joints here; segments, weights and every existing axis stay byte for byte. Idempotent.

  * fingers 2-5, MCP joint: a second axis `abd` through the MCP centre, perpendicular to the flexion axis and to the proximal
    phalanx (MCP centre -> PIP centre). (+) = away from the middle finger; for the middle finger itself (+) = towards the
    thumb side. Range: ROM `finger_mcp_abd` (docs/pose_rom_table.md -- an ASSUMPTION, no published figure could be read).
  * thumb CMC: a third axis `rot` along the metacarpal (CMC centre -> MCP centre), (+) = pronation, the turn that brings
    the pad to face the palm. Range: ROM `thumb_cmc_rot` (Cooney 1981, 17 deg).
  * thumb CMC: `couple` = the Opposition control: one value 0..100 % that sets flexion, palmar abduction and axial rotation
    together, each from the reposition end of its own range to the opposition end. The three ranges are the table's; that
    they run in step along a straight line is a DISPLAY CONVENTION (docs/pose_rom_table.md, coupled motions).

    python3 scripts/anatomy/q384/hand_dofs_q384.py base_m base_f [--src DIR] [--out DIR] [--dry-run]"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / "q241"))
from rom import ROM, rom_meta  # noqa: E402

DATA = REPO / "data/anatomy"
NAMES = {2: "index", 3: "middle", 4: "ring", 5: "little"}
OPP_NOTE = ("Opposition sets CMC flexion, palmar abduction and axial rotation together, each from one end of its own range to the other "
            "(ranges: Cooney 1981; Hamann 2014 records opposition as these three components). That they run in step is a display convention, not a measurement.")


def unit(a):
    a = np.asarray(a, float)
    return a / max(np.linalg.norm(a), 1e-12)


def rot(a, deg):
    a = unit(a); t = np.radians(deg); c, s_ = np.cos(t), np.sin(t); x, y, z = a; u = 1 - c
    return np.array([[c + x*x*u, x*y*u - z*s_, x*z*u + y*s_], [y*x*u + z*s_, c + y*y*u, y*z*u - x*s_], [z*x*u - y*s_, z*y*u + x*s_, c + z*z*u]])


def to_zero_frame(j, a_rest):
    """The viewer composes a joint as Rot(a1, q1) Rot(a2, q2) ... with the axes given at q = 0, and the model pose is q0, not 0:
    in the model pose axis k is carried by the axes before it at their q0. An axis measured on the model's own bones (as
    here) is therefore stored turned back by them, so that IN THE MODEL POSE it is the measured one."""
    R = np.eye(3)
    for d in j["dof"]:
        R = R @ rot(d["a"], d["q0"])
    return R.T @ np.asarray(a_rest, float)


def r5(a):
    return [round(float(v), 5) for v in a]


def patch(rig):
    """adds the dofs to the rig dict in place -> number of joints changed"""
    J = {j["id"]: j for j in rig["joints"]}
    n = 0
    for s in ("l", "r"):
        c3 = np.array(J["f3_mcp_" + s]["c"], float); c2 = np.array(J["f2_mcp_" + s]["c"], float)
        for k in (2, 3, 4, 5):
            j, pip = J["f%d_mcp_%s" % (k, s)], J["f%d_pip_%s" % (k, s)]
            if any(d["k"] == "abd" for d in j["dof"]):
                continue
            c = np.array(j["c"], float)
            d = unit(np.array(pip["c"], float) - c)
            a = unit(np.cross(j["dof"][0]["a"], d))
            away = (c - c3) if k != 3 else (c2 - c3)
            away = unit(away - (away @ d) * d)
            if np.cross(a, d) @ away < 0:
                a = -a
            lo, hi, lab, _src = ROM["finger_mcp_abd"]
            j["dof"].append(dict(k="abd", l=lab if k != 3 else "MCP towards the thumb side (+) / the little finger (-)", a=r5(to_zero_frame(j, a)), lo=float(lo), hi=float(hi), q0=0.0, rk="finger_mcp_abd"))
            j["note"] = "MCP: flexion about the transverse axis, then abduction / adduction about the axis perpendicular to it and to the proximal phalanx; the same abduction range at every flexion angle (ASSUMPTION)"
            n += 1
        j = J["thumb_cmc_" + s]
        if not any(d["k"] == "rot" for d in j["dof"]):
            c = np.array(j["c"], float)
            d = unit(np.array(J["thumb_mcp_" + s]["c"], float) - c)
            a = d.copy()
            abd = [x for x in j["dof"] if x["k"] == "abd"][0]
            palmar = unit(np.cross(abd["a"], d))                      # where the thumb goes in palmar abduction
            pad = np.array(J["f2_mcp_" + s]["c"], float) - np.array(J["thumb_mcp_" + s]["c"], float)
            pad = unit(pad - (pad @ d) * d)                           # at rest the pad faces the index finger
            if np.cross(a, pad) @ (-palmar) < 0:                      # pronation turns the pad back towards the palm
                a = -a
            lo, hi, lab, _src = ROM["thumb_cmc_rot"]
            j["dof"].append(dict(k="rot", l=lab, a=r5(to_zero_frame(j, a)), lo=float(lo), hi=float(hi), q0=0.0, rk="thumb_cmc_rot"))
            n += 1
        if not j.get("couple"):
            parts = []
            for d_ in j["dof"]:
                parts.append([d_["k"], d_["lo"], d_["hi"]])
            j["couple"] = [dict(id="opp", l="Opposition (+) / reposition (0)", lo=0, hi=100, unit="%", parts=parts, note=OPP_NOTE, convention=True)]
            j["note"] = "saddle joint approximated by three axes: flexion across the palm, palmar abduction out of it, axial rotation about the metacarpal; Opposition drives the three together (display convention)"
            n += 1
    used = sorted(set(rig["rom"]) | {"finger_mcp_abd", "thumb_cmc_rot"})
    for k in ("finger_mcp_abd", "thumb_cmc_rot"):
        rig["rom"][k] = [ROM[k][0], ROM[k][1], ROM[k][2], ROM[k][3]]
    rig["rom_meta"].update(rom_meta([k for k in used if k in ("finger_mcp_abd", "thumb_cmc_rot")]))
    if n and "Q384 E5" not in rig["notes"]:
        rig["notes"] += "; Q384 E5: finger MCP abduction / adduction (assumed range), thumb CMC axial rotation (Cooney 1981) and the Opposition control (display convention) added to the stored joints, weights unchanged"
    return n


def run(key, src=None, out=None, dry=False):
    f = (Path(src) if src else DATA) / ("pose_rig_%s.json" % key)
    S0 = json.loads(f.read_text(encoding="utf-8"))
    n = patch(S0["rig"])
    J = {j["id"]: j for j in S0["rig"]["joints"]}
    print("%s: %d joints changed; f2_mcp_l abd axis %s, thumb_cmc_l rot axis %s" % (key, n, J["f2_mcp_l"]["dof"][1]["a"], J["thumb_cmc_l"]["dof"][2]["a"]), flush=True)
    if not dry:
        g = (Path(out) if out else DATA) / ("pose_rig_%s.json" % key)
        g.parent.mkdir(parents=True, exist_ok=True)
        g.write_text(json.dumps(S0, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        print("wrote", g, flush=True)
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("keys", nargs="+", choices=["base_m", "base_f"])
    ap.add_argument("--src"); ap.add_argument("--out"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    for k in a.keys:
        run(k, a.src, a.out, a.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
