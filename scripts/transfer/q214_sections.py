#!/usr/bin/env python3
"""Q214 axial sections (build/q214_renders, git-ignored): the neck of one Q214 own page at height y with the added splenius muscles (blue = capitis, red = cervicis), the neighbouring muscles (orange), the bones
(black), the skin (grey) and, for the female, her own cryosection splenius compartment (green, build/q214/splenius_own.npz) -- the position cross-check recorded on the card.

    python3 scripts/transfer/q214_sections.py vhm|vhf Y [OUT.png]"""
import sys
from pathlib import Path

import numpy as np
import trimesh
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.transfer import q214_targets as T  # noqa: E402

NEIGH = ("trapezius", "semispinalis", "longissimus", "spinalis", "multifidus", "levator_scap", "sternoclei", "rhomboid", "obliquus", "rectus_capitis", "iliocostalis")


def main():
    body, y = sys.argv[1], float(sys.argv[2])
    out = sys.argv[3] if len(sys.argv) > 3 else str(REPO / f"build/q214_renders/{body}_neck_section_y{int(y)}.png")
    A, N = Bundle(T.BODY[body]["src"]), Bundle(T.BODY[body]["out"])
    new = {it["e"]["id"] for it in N.items[len(A.items):]}
    fig, ax = plt.subplots(1, 2, figsize=(15, 7), sharex=True, sharey=True)

    def sec(a, v, f, col, lw=1.0, label=None):
        try:
            s = trimesh.Trimesh(v, f, process=False).section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0])
        except Exception:  # noqa
            return
        if s is None:
            return
        first = True
        for e in s.entities:
            p = s.vertices[e.points]
            a.plot(p[:, 0], p[:, 2], color=col, lw=lw, label=label if first else None)
            first = False
    for k, (B, a) in enumerate(((A, ax[0]), (N, ax[1]))):
        for it in B.items:
            e = it["e"]
            v, f = B.mesh(it)
            if len(f) == 0 or v[:, 1].min() > y or v[:, 1].max() < y or e.get("hidden_default"):
                continue
            if e["id"] == "skin":
                sec(a, v, f, "0.6")
            elif e["cat"] == "bone":
                sec(a, v, f, "k")
            elif e["id"] in new:
                sec(a, v, f, "tab:blue" if "capitis" in e["id"] else "tab:red", 2.2, e["id"])
            elif e["cat"] == "muscle" and any(n in e["id"] for n in NEIGH):
                sec(a, v, f, "tab:orange", 0.8)
        if k == 1 and body == "vhf" and (REPO / "build/q214/splenius_own.npz").exists():
            d = np.load(REPO / "build/q214/splenius_own.npz")
            for s_ in "rl":
                sec(a, d[f"splenius_capitis_{s_}_v"], d[f"splenius_capitis_{s_}_f"], "tab:green", 1.6, "her cryo splenius compartment" if s_ == "r" else None)
        a.set_aspect("equal")
        a.invert_yaxis()
        a.set_title(("BEFORE (source bundle)" if k == 0 else "AFTER (Q214)") + f"  {body}  y={y:g} mm (x right, z anterior down)")
        if k == 1:
            a.legend(loc="lower right", fontsize=8)
        a.set_xlim(-110, 110)
        a.set_ylim(40, -130)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(out, dpi=80)
    print("wrote", out)


if __name__ == "__main__":
    main()
