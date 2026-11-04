#!/usr/bin/env python3
"""Q207 renders (build/q207_renders, git-ignored): the skin with the hand / wrist bones, Q206 page | Q207 page (opaque skin: a bone that pokes through shows), cross sections of the skin and bones
along the forearm axis, and the male urogenital patch before / after.
    PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers python3 scripts/zanatomy/q207_renders.py male|female [--out build/q207_renders]"""
import argparse
import re
import shutil
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q207_core as C  # noqa: E402

HAND = re.compile(r"metacarpal|finger_of_hand|scaphoid|lunate|triquetrum|pisiform|trapezi|capitate|hamate|radius|ulna")


def scene(page, side, centre, box=130.0):
    s = "_" + side
    out = []
    for i, e in page.S.items():
        sy = e["m"]["sys"]
        if sy == "skin" and i.endswith(s) and C.LIMB_SKIN_RE.search(i) and "foot" not in i:
            out.append({"v": e["v"], "f": e["f"], "color": (0.86, 0.7, 0.6)})
        elif sy == "bone" and i.endswith(s) and HAND.search(i) and "foot" not in i:
            out.append({"v": e["v"], "f": e["f"], "color": (0.15, 0.2, 0.9) if "radius" in i or "ulna" in i else (0.95, 0.9, 0.1)})
    return out


def sections(which, old, new, side, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import trimesh
    W = new.wrist()[side]
    s = "_" + side
    rad = new.v("radius" + s)
    c = rad.mean(0)
    ax = np.linalg.svd(rad - c, full_matrices=False)[2][0]
    if ax[1] < 0:
        ax = -ax
    e1 = np.cross(ax, [0, 0, 1]); e1 /= np.linalg.norm(e1); e2 = np.cross(ax, e1)
    ts = (-70, -40, -10, 15, 40, 70)
    fig, axs = plt.subplots(2, len(ts), figsize=(4 * len(ts), 8.4))
    for r, (tt, P) in enumerate((("Q206", old), ("Q207", new))):
        for k, t in enumerate(ts):
            a = axs[r, k]
            o = W - ax * t
            for i, e in P.S.items():
                sy = e["m"]["sys"]
                if sy == "skin" and i.endswith(s) and C.LIMB_SKIN_RE.search(i) and "foot" not in i:
                    col, lw = "#c08060", 0.9
                elif sy == "bone" and i.endswith(s) and HAND.search(i) and "foot" not in i:
                    col, lw = "k", 1.1
                elif sy in ("vessel", "nerve") and i.endswith(s) and np.linalg.norm(e["v"] - o, axis=1).min() < 40:
                    col, lw = ("#d01010" if sy == "vessel" else "#d8b000"), 0.5
                else:
                    continue
                if np.linalg.norm(e["v"] - o, axis=1).min() > 90:
                    continue
                seg = trimesh.intersections.mesh_plane(trimesh.Trimesh(e["v"], e["f"], process=False), ax, o)
                for q in seg:
                    a.plot([(q[0] - o) @ e1, (q[1] - o) @ e1], [(q[0] - o) @ e2, (q[1] - o) @ e2], "-", color=col, lw=lw)
            a.set_xlim(-70, 70); a.set_ylim(-70, 70); a.set_aspect("equal"); a.set_title(f"{tt}  {t:+d} mm along the forearm axis", fontsize=8); a.axis("off")
    fig.suptitle(f"{which} {'left' if side == 'l' else 'right'} wrist: skin (brown), bones (black), vessels (red), nerves (yellow); sections normal to the forearm axis")
    fig.savefig(out / f"{which}_{'left' if side == 'l' else 'right'}_wrist_sections.png", dpi=70, bbox_inches="tight")
    plt.close(fig)


def uro(old, new, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import trimesh
    fig, axs = plt.subplots(2, 4, figsize=(24, 12))
    ids = ("zan_skin_urogenital_region_l", "zan_skin_urogenital_region_r")
    for r, (tt, P) in enumerate((("Q206", old), ("Q207", new))):
        for k, xo in enumerate((-1.0, -8.0, -16.0)):
            a = axs[r, k]
            for i in P.skin_ids:
                v = P.v(i)
                if abs(v[:, 0] - xo).min() > 25 or np.linalg.norm(v - np.array([xo, -85, 40]), axis=1).min() > 80:
                    continue
                seg = trimesh.intersections.mesh_plane(trimesh.Trimesh(v, P.f(i), process=False), [1, 0, 0], [xo, 0, 0])
                col = "r" if i == ids[0] else ("b" if i == ids[1] else "0.5")
                for q in seg:
                    a.plot([q[0][2], q[1][2]], [q[0][1], q[1][1]], "-", color=col, lw=0.9)
            a.set_xlim(-10, 130); a.set_ylim(-160, -30); a.set_aspect("equal"); a.set_title(f"{tt}: section x = {xo} mm (red = left half, blue = right half, grey = neighbours)")
        a = axs[r, 3]
        for i in P.skin_ids:
            v = P.v(i)
            if np.linalg.norm(v - np.array([0, -85, 40]), axis=1).min() > 60:
                continue
            col = "r" if i == ids[0] else ("b" if i == ids[1] else "0.6")
            m = np.linalg.norm(v - np.array([0, -85, 40]), axis=1) < 90
            a.scatter(v[m, 0], v[m, 2], s=2, c=col)
        a.set_xlim(-70, 70); a.set_ylim(0, 125); a.set_aspect("equal"); a.set_title(f"{tt}: seen from below (x, z)")
    fig.savefig(out / "male_urogenital_before_after.png", dpi=50, bbox_inches="tight")
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("which", choices=["male", "female"])
    ap.add_argument("--out", default=str(REPO / "build" / "q207_renders"))
    ap.add_argument("--no3d", action="store_true")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    cfg = C.PAGES[a.which]
    old, new = C.Page(a.which), C.Page(a.which, src=cfg["out"])
    for side in "rl":
        sections(a.which, old, new, side, out)
    if a.which == "male":
        uro(old, new, out)
    if not a.no3d:
        from scripts.zanatomy import q190_render as R
        from scripts.zanatomy import q201_renders as RR
        for side in "rl":
            hb = np.vstack([e["v"] for i, e in new.S.items() if i.endswith("_" + side) and e["m"]["sys"] == "bone" and HAND.search(i) and "foot" not in i])
            centre = hb.mean(0)
            rows = []
            for t, P in (("Q206", old), ("Q207", new)):
                views = [{"name": n, "az": az, "el": 0, "target": centre, "half": 120} for n, az in (("anterior", 0), ("lateral", 270 if side == "l" else 90), ("posterior", 180), ("medial", 90 if side == "l" else 270))]
                tmp = out / f"_tmp_{a.which}_{side}_{t}"
                R.render(scene(P, side, centre), views, tmp, size=(480, 480))
                rows.append([str(tmp / f"{v['name']}.png") for v in views])
            RR.montage(rows, out / f"{a.which}_{'left' if side == 'l' else 'right'}_skin_bones_3d.png", [[f"{t} {v}" for v in ("anterior", "lateral", "posterior", "medial")] for t in ("Q206", "Q207")])
        for d in out.glob("_tmp_*"):
            shutil.rmtree(d)
    print("renders ->", out)


if __name__ == "__main__":
    main()
