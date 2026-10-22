#!/usr/bin/env python3
"""Q210 renders (build/q210_renders, git-ignored): the male genital structures vs the urogenital skin (sagittal sections, opaque skin 3D) and the forearm vs trunk skin contact (sections normal to the forearm axis,
opaque skin 3D), Q208 | Q210.
    PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers python3 scripts/zanatomy/q210_renders.py [--no3d]"""
import argparse
import pickle
import shutil
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q210_core as K  # noqa: E402
from scripts.zanatomy import q210_contact as CT  # noqa: E402

OUT = REPO / "build" / "q210_renders"
GEN_NB = K.UROS + tuple(f"zan_skin_{n}_{s}" for n in ("anal_region", "anterior_region_of_thigh", "hypogastric_region", "inguinal_region") for s in "lr")


def genital_sections(pg, V0, V1):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import trimesh
    cols = plt.get_cmap("tab20")
    fig, axs = plt.subplots(2, 3, figsize=(24, 14))
    for r, (tt, V) in enumerate((("Q208", V0), ("Q210", V1))):
        for k, xo in enumerate((-2.0, -9.0, 12.0)):
            ax = axs[r, k]
            for i in GEN_NB:
                seg = trimesh.intersections.mesh_plane(trimesh.Trimesh(V[i], pg.f(i), process=False), [1, 0, 0], [xo, 0, 0])
                for q in seg:
                    ax.plot([q[0][2], q[1][2]], [q[0][1], q[1][1]], "-", color="#c07000" if i in K.UROS else "0.45", lw=0.9)
            for j, i in enumerate(K.GEN_MAIN + K.GEN_EXTRA):
                v = pg.v(i)
                m = np.abs(v[:, 0] - xo) < 5
                ax.plot(v[m, 2], v[m, 1], ".", ms=3, color=cols(j % 20), label=i[4:22] if k == 0 else None)
            ax.set_xlim(-30, 140)
            ax.set_ylim(-160, 10)
            ax.set_aspect("equal")
            ax.set_title(f"{tt}: x = {xo} mm (orange / grey = urogenital / neighbouring skin sections, dots = structure vertices within 5 mm)", fontsize=8)
    axs[0, 0].legend(fontsize=6, ncol=2)
    fig.savefig(OUT / "male_genital_sections_before_after.png", dpi=45, bbox_inches="tight")
    plt.close(fig)


def contact_sections(pg, V0, V1):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import trimesh
    from scripts.zanatomy.q207_inflate import OwnSkin
    own = OwnSkin("male")
    Fs = {s: CT.forearm_ids(pg, s) for s in "lr"}
    for side in "lr":
        rb = np.vstack([pg.v(f"radius_{side}"), pg.v(f"ulna_{side}")])
        c0 = rb.mean(0)
        ax_ = np.linalg.svd(rb - c0, full_matrices=False)[2][0]
        t_ = (rb - c0) @ ax_
        palm = pg.v(f"zan_skin_palm_{side}").mean(0)
        if (palm - c0) @ ax_ < 0:
            ax_ = -ax_
            t_ = -t_
        u = np.cross(ax_, [0, 1.0, 0])
        u /= np.linalg.norm(u)
        w = np.cross(ax_, u)
        ts = np.linspace(t_.min() + 0.15 * np.ptp(t_), t_.max() - 0.15 * np.ptp(t_), 4)
        fig, axs = plt.subplots(2, 4, figsize=(24, 12))
        for r, (tt, V) in enumerate((("Q208", V0), ("Q210", V1))):
            for k, t in enumerate(ts):
                ax = axs[r, k]
                o = c0 + ax_ * t
                items = [(own.tm.vertices, own.tm.faces, "g", 1.0)]
                for i in pg.skin_ids:
                    if "nail_plate" in i or "perionyx" in i:
                        continue
                    vv = V[i]
                    if np.linalg.norm(vv - o, axis=1).min() > 170:
                        continue
                    items.append((vv, pg.f(i), "#d04000" if i in Fs[side] else "#1a4bd0", 0.9))
                for i in pg.ids:
                    if pg.sys(i) in ("bone", "muscle") and np.linalg.norm(pg.v(i) - o, axis=1).min() < 150:
                        items.append((pg.v(i), pg.f(i), "0.15" if pg.sys(i) == "bone" else "0.7", 0.4))
                for (v, f, col, lw) in items:
                    seg = trimesh.intersections.mesh_plane(trimesh.Trimesh(v, f, process=False), ax_, o)
                    for q in seg:
                        ax.plot([(q[0] - o) @ u, (q[1] - o) @ u], [(q[0] - o) @ w, (q[1] - o) @ w], "-", color=col, lw=lw)
                ax.set_xlim(-130, 130)
                ax.set_ylim(-130, 130)
                ax.set_aspect("equal")
                ax.set_title(f"{tt}, {side} forearm, section at {100 * (t - t_.min()) / np.ptp(t_):.0f} % (green own skin, red forearm skin, blue other skin)", fontsize=8)
        fig.savefig(OUT / f"male_forearm_trunk_sections_{'left' if side == 'l' else 'right'}.png", dpi=40, bbox_inches="tight")
        plt.close(fig)


def scene(pg, V, ids_a, ids_b, bones=True, region=None):
    sc = []
    for i in pg.skin_ids:
        if "nail_plate" in i or "perionyx" in i:
            continue
        if region is not None and np.linalg.norm(V[i] - region[0], axis=1).min() > region[1]:
            continue
        col = (0.95, 0.45, 0.1) if i in ids_a else (0.2, 0.4, 0.9) if i in ids_b else (0.9, 0.78, 0.68)
        sc.append({"v": V[i], "f": pg.f(i), "color": col})
    return sc


def renders3d(pg, V0, V1, Fs, Ts):
    from scripts.zanatomy import q190_render as R
    from scripts.zanatomy import q201_renders as RR
    # genital: opaque skin of the pelvis + the genital structures (those outside the skin show)
    ctr = np.array([0.0, -85.0, 70.0])
    views = [{"name": "anterior", "az": 0, "el": 0, "target": ctr, "half": 90}, {"name": "lateral_right", "az": 90, "el": 0, "target": ctr, "half": 90},
             {"name": "oblique", "az": 40, "el": 20, "target": ctr, "half": 90}, {"name": "inferior_oblique", "az": 30, "el": -35, "target": ctr, "half": 90}]
    rows = []
    for t, V in (("Q208", V0), ("Q210", V1)):
        sc = scene(pg, V, K.UROS, (), region=(ctr, 140))
        pal = [(0.1, 0.6, 0.2), (0.85, 0.1, 0.1), (0.1, 0.1, 0.8), (0.7, 0.1, 0.7), (0.0, 0.7, 0.7), (0.9, 0.6, 0.0)]
        for j, i in enumerate(K.GEN_MAIN):
            sc.append({"v": pg.v(i), "f": pg.f(i), "color": pal[j % len(pal)]})
        tmp = OUT / f"_tmp_gen_{t}"
        R.render(sc, views, tmp, size=(480, 480))
        rows.append([str(tmp / f"{v['name']}.png") for v in views])
    RR.montage(rows, OUT / "male_genital_skin_3d.png", [[f"{t} {v['name']}" for v in views] for t in ("Q208", "Q210")])
    # forearm | trunk: opaque skin (forearm orange, the trunk / thigh patches that crossed blue)
    allf = np.vstack([V0[i] for i in Fs + Ts])
    c = allf.mean(0)
    views = [{"name": "anterior", "az": 0, "el": 0, "target": c, "half": 260}, {"name": "top", "az": 0, "el": 70, "target": c, "half": 260}, {"name": "lateral_right", "az": 90, "el": 15, "target": c, "half": 260},
             {"name": "lateral_left", "az": 270, "el": 15, "target": c, "half": 260}]
    rows = []
    for t, V in (("Q208", V0), ("Q210", V1)):
        sc = scene(pg, V, Fs, Ts)
        tmp = OUT / f"_tmp_ct_{t}"
        R.render(sc, views, tmp, size=(480, 480))
        rows.append([str(tmp / f"{v['name']}.png") for v in views])
    RR.montage(rows, OUT / "male_forearm_trunk_skin_3d.png", [[f"{t} {v['name']}" for v in views] for t in ("Q208", "Q210")])
    for d in OUT.glob("_tmp_*"):
        shutil.rmtree(d)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--no3d", action="store_true")
    a = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    pg, raw = K.load()
    V0 = {i: pg.v(i) for i in pg.skin_ids}
    V1 = pickle.load(open(K.state_path("contact"), "rb"))[0]
    crep = pickle.load(open(K.state_path("contact"), "rb"))[1]
    genital_sections(pg, V0, V1)
    contact_sections(pg, V0, V1)
    if not a.no3d:
        renders3d(pg, V0, V1, crep["F"], crep["T"])
    print("renders ->", OUT)


if __name__ == "__main__":
    main()
