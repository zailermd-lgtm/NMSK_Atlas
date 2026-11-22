#!/usr/bin/env python3
"""Q208 renders (build/q208_renders, git-ignored): the forearm / elbow skin (opaque, coloured per patch, bones black) Q207 | Q208 from four sides, cross sections normal to the forearm axis with the person's own skin,
bones and muscles, the elbow flexion-plane section, and the male urogenital rim before / after.
    PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers python3 scripts/zanatomy/q208_renders.py male|female [--out build/q208_renders]"""
import argparse
import colorsys
import pickle
import shutil
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q207_core as C7  # noqa: E402
from scripts.zanatomy import q208_core as K  # noqa: E402

FA = ("forearm", "elbow", "cubital", "wrist", "region_of_arm", "palm", "dorsum_of_hand", "foveola")


def scene(pg, V, side):
    s = "_" + side
    ids = [i for i in pg.skin_ids if i.endswith(s) and any(k in i for k in FA)]
    hs = [0.0, 0.08, 0.15, 0.3, 0.45, 0.55, 0.62, 0.75, 0.85, 0.95]
    sc = [{"v": V[i], "f": pg.f(i), "color": colorsys.hsv_to_rgb(hs[k % len(hs)], 0.6, 0.95)} for k, i in enumerate(ids)]
    for i in pg.ids:
        if pg.sys(i) == "bone" and i.endswith(s) and any(k in i for k in ("radius", "ulna", "humerus", "metacarpal", "carpal", "scaphoid", "lunate", "triquetrum", "pisiform", "trapezi", "capitate", "hamate")):
            sc.append({"v": pg.v(i), "f": pg.f(i), "color": (0.1, 0.1, 0.1)})
    return sc


def sections(pg, V0, V1, side, out, which):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import trimesh
    from scripts.zanatomy.q207_inflate import OwnSkin
    own = OwnSkin(which)
    s = "_" + side
    W = pg.wrist()[side]
    rad, ulna = pg.v("radius" + s), pg.v("ulna" + s)
    a = np.linalg.svd(np.vstack([rad, ulna]) - np.vstack([rad, ulna]).mean(0), full_matrices=False)[2][0]
    if (W - rad.mean(0)) @ a < 0:
        a = -a
    elb = ulna[np.argmax((ulna - W) @ (-a))]
    e1 = np.cross(a, [0, 0, 1])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(a, e1)
    ts = (0.12, 0.3, 0.5, 0.7, 0.9)
    fig, axs = plt.subplots(2, len(ts), figsize=(4.4 * len(ts), 9))
    for r, (tt, V) in enumerate((("Q207", V0), ("Q208", V1))):
        for k, t in enumerate(ts):
            ax = axs[r, k]
            o = elb + (W - elb) * t
            items = [(own.tm.vertices, own.tm.faces, "g", 1.2)]
            for i in pg.ids:
                sy = pg.sys(i)
                if sy == "skin" and i.endswith(s) and any(q in i for q in K.TUBE + K.ELBOW):
                    items.append((V[i], pg.f(i), "#d04000", 0.9))
                elif sy == "bone" and i.endswith(s) and any(q in i for q in ("radius", "ulna", "humerus")):
                    items.append((pg.v(i), pg.f(i), "k", 1.0))
                elif sy == "muscle" and i.endswith(s):
                    items.append((pg.v(i), pg.f(i), "#b03030", 0.3))
            for v, f, col, lw in items:
                if np.linalg.norm(v - o, axis=1).min() > 110:
                    continue
                for q in trimesh.intersections.mesh_plane(trimesh.Trimesh(v, f, process=False), a, o):
                    ax.plot([(q[0] - o) @ e1, (q[1] - o) @ e1], [(q[0] - o) @ e2, (q[1] - o) @ e2], "-", color=col, lw=lw)
            ax.set_xlim(-80, 80)
            ax.set_ylim(-80, 80)
            ax.set_aspect("equal")
            ax.set_title(f"{tt} t = {t:.2f} (elbow 0 -> wrist 1)", fontsize=8)
            ax.axis("off")
    fig.suptitle(f"{which} {SIDE[side]} forearm: displayed skin (orange), own skin (green), bones (black), muscles (red); sections normal to the forearm axis")
    fig.savefig(out / f"{which}_{SIDE[side]}_forearm_sections.png", dpi=60, bbox_inches="tight")
    plt.close(fig)


def flexion(pg, V0, V1, side, out, which):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import trimesh
    from scripts.zanatomy.q207_inflate import OwnSkin
    own = OwnSkin(which)
    s = "_" + side
    W = pg.wrist()[side]
    rad, ulna, hum = pg.v("radius" + s), pg.v("ulna" + s), pg.v("humerus" + s)
    fa = np.linalg.svd(np.vstack([rad, ulna]) - np.vstack([rad, ulna]).mean(0), full_matrices=False)[2][0]
    if (W - rad.mean(0)) @ fa < 0:
        fa = -fa
    ha = np.linalg.svd(hum - hum.mean(0), full_matrices=False)[2][0]
    if ha @ fa < 0:
        ha = -ha
    n = np.cross(ha, fa)
    n /= np.linalg.norm(n)
    elb = ulna[np.argmax((ulna - W) @ (-fa))]
    u1 = fa + ha
    u1 /= np.linalg.norm(u1)
    u2 = np.cross(n, u1)
    fig, axs = plt.subplots(2, 3, figsize=(18, 11))
    for r, (tt, V) in enumerate((("Q207", V0), ("Q208", V1))):
        for k, off in enumerate((-30.0, 0.0, 30.0)):
            ax = axs[r, k]
            o = elb + n * off
            items = [(own.tm.vertices, own.tm.faces, "g", 1.0)]
            for i in pg.ids:
                sy = pg.sys(i)
                if sy == "skin" and i.endswith(s) and any(q in i for q in K.TUBE + K.ELBOW + K.ARM_NB):
                    items.append((V[i], pg.f(i), "#d04000", 1.0))
                elif sy == "bone" and i.endswith(s) and any(q in i for q in ("radius", "ulna", "humerus")):
                    items.append((pg.v(i), pg.f(i), "k", 0.8))
            for v, f, col, lw in items:
                for q in trimesh.intersections.mesh_plane(trimesh.Trimesh(v, f, process=False), n, o):
                    ax.plot([(q[0] - o) @ u1, (q[1] - o) @ u1], [(q[0] - o) @ u2, (q[1] - o) @ u2], "-", color=col, lw=lw)
            ax.set_xlim(-90, 90)
            ax.set_ylim(-50, 110)
            ax.set_aspect("equal")
            ax.set_title(f"{tt}: flexion-plane section {off:+.0f} mm", fontsize=9)
            ax.axis("off")
    fig.savefig(out / f"{which}_{SIDE[side]}_elbow_flexion_sections.png", dpi=55, bbox_inches="tight")
    plt.close(fig)


def uro(pg, V0, V1, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import trimesh
    ids = ("zan_skin_urogenital_region_l", "zan_skin_urogenital_region_r")
    nb = ids + tuple(f"zan_skin_{n}_{s}" for n in ("anal_region", "anterior_region_of_thigh") for s in "lr")
    cols = {ids[0]: "r", ids[1]: "b"}
    fig, axs = plt.subplots(2, 3, figsize=(18, 11))
    for r, (tt, V) in enumerate((("Q207", V0), ("Q208", V1))):
        for k, xo in enumerate((-1.0, -8.0, -16.0)):
            ax = axs[r, k]
            for i in nb:
                seg = trimesh.intersections.mesh_plane(trimesh.Trimesh(V[i], pg.f(i), process=False), [1, 0, 0], [xo, 0, 0])
                col = cols.get(i, "0.45")
                for q in seg:
                    ax.plot([q[0][2], q[1][2]], [q[0][1], q[1][1]], "-", color=col, lw=0.9)
            ax.set_xlim(-10, 130)
            ax.set_ylim(-160, -30)
            ax.set_aspect("equal")
            ax.set_title(f"{tt}: x = {xo} mm (red / blue = urogenital l / r, grey = anal and thigh)", fontsize=8)
    fig.savefig(out / "male_urogenital_rim_before_after.png", dpi=50, bbox_inches="tight")
    plt.close(fig)


SIDE = {"l": "left", "r": "right"}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("which", choices=["male", "female"])
    ap.add_argument("--out", default=str(REPO / "build" / "q208_renders"))
    ap.add_argument("--no3d", action="store_true")
    a = ap.parse_args(argv)
    out = Path(out := a.out)
    out.mkdir(parents=True, exist_ok=True)
    pg, raw = K.load(a.which)
    V0 = {i: pg.v(i) for i in pg.skin_ids}
    V1 = pickle.load(open(K.state_path(a.which, "uro"), "rb"))[0]
    for side in "rl":
        sections(pg, V0, V1, side, out, a.which)
        flexion(pg, V0, V1, side, out, a.which)
    if a.which == "male":
        uro(pg, V0, V1, out)
    if not a.no3d:
        from scripts.zanatomy import q190_render as R
        from scripts.zanatomy import q201_renders as RR
        for side in "rl":
            s = "_" + side
            W = pg.wrist()[side]
            centre = 0.5 * (W + pg.v("ulna" + s)[np.argmax((pg.v("ulna" + s) - W) @ (pg.v("ulna" + s).mean(0) - W))])
            rows = []
            for t, V in (("Q207", V0), ("Q208", V1)):
                views = [{"name": n, "az": az, "el": 0, "target": centre, "half": 190} for n, az in (("anterior", 0), ("lateral", 270 if side == "l" else 90), ("posterior", 180), ("medial", 90 if side == "l" else 270))]
                tmp = out / f"_tmp_{a.which}_{side}_{t}"
                R.render(scene(pg, V, side), views, tmp, size=(480, 480))
                rows.append([str(tmp / f"{v['name']}.png") for v in views])
            RR.montage(rows, out / f"{a.which}_{SIDE[side]}_forearm_skin_3d.png", [[f"{t} {v}" for v in ("anterior", "lateral", "posterior", "medial")] for t in ("Q207", "Q208")])
        for d in out.glob("_tmp_*"):
            shutil.rmtree(d)
    print("renders ->", out)


if __name__ == "__main__":
    main()
