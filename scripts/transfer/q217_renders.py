#!/usr/bin/env python3
"""Q217 renders of the LEFT elbow / forearm, before | after: 3-D close-ups (lateral, anterior; muscles + bones) and his photographs with the sections of the shipped muscles / bones.
    PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers python3 scripts/transfer/q217_renders.py own|zan [--out build/q217_renders]
Pages: before = q217_paths keys own_m / zan_m (Q214 / Q211 pages), after = own_m_a / zan_m_a (build/q217 pages)."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q217_paths  # noqa: F401,E402
from scripts.zanatomy import q198_load as L  # noqa: E402
from scripts.zanatomy import q190_render as R  # noqa: E402
from scripts.zanatomy import q201_renders as Q  # noqa: E402
from scripts.transfer import q217_sections as SE  # noqa: E402

PAGES = {"own": ("own_m", "own_m_a", np.array([-234.0, 270.0, -36.0]), "own male"), "zan": ("zan_m", "zan_m_a", np.array([-240.0, 284.0, -42.0]), "Z male fitted")}


def to_dict(S):
    return {s["id"]: dict(v=s["v"], f=s["f"], sys=s["sys"], cat=s["sys"]) for s in S}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("which")
    ap.add_argument("--out", default=str(REPO / "build/q217_renders"))
    ap.add_argument("--levels", default="300,270,240,210,180")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    kb, ka, centre, name = PAGES[a.which]
    Mb, Ma = to_dict(L.load(kb)), to_dict(L.load(ka))
    rows = []
    for t, M in (("before", Mb), ("after", Ma)):
        views = [{"name": n, "az": az, "el": 0, "target": centre, "half": 120.0} for n, az in (("anterior", 0), ("lateral", 270), ("posterior", 180), ("medial", 90))]
        R.render(Q.scene(M, "l", ("muscle", "bone"), centre, box=120.0), views, out / f"_tmp_{a.which}_{t}", size=(520, 520))
        rows.append([str(out / f"_tmp_{a.which}_{t}" / f"{v['name']}.png") for v in views])
    Q.montage(rows, out / f"{a.which}_left_elbow_before_after.png", [[f"{t} {v}" for v in ("anterior", "lateral", "posterior", "medial")] for t in ("before", "after")], w=520)
    for t in ("before", "after"):
        shutil.rmtree(out / f"_tmp_{a.which}_{t}", ignore_errors=True)
    lv = [int(x) for x in a.levels.split(",")]
    SE.render_dicts(out / f"{a.which}_left_forearm_sections_before_after.png", lv, [{k: v for k, v in Mb.items() if k.endswith("_l") and v["cat"] in ("muscle", "bone")}, {k: v for k, v in Ma.items() if k.endswith("_l") and v["cat"] in ("muscle", "bone")}],
                    [f"{name} before", f"{name} after"])
    print("renders in", out)


if __name__ == "__main__":
    main()
