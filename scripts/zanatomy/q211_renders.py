#!/usr/bin/env python3
"""Q211 renders (build/q211_renders, git-ignored): before | after sections of the repaired zones -- elbow flexion-plane sections (muscles coloured per structure, tubes dotted, bones black, skin grey), shoulder
sagittal sections, the female lumbar column, the male left ankle, the female feet.   python3 scripts/zanatomy/q211_renders.py [male|female]"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q211_core as K  # noqa: E402

OUT = REPO / "build" / "q211_renders"


def secs(pg, i, n, o):
    import trimesh
    return trimesh.intersections.mesh_plane(trimesh.Trimesh(pg.v(i), pg.f(i), process=False), n, o)


def draw(ax, pg, ids, n, o, u1, u2, colors, lw=0.8):
    for i in ids:
        sy = pg.sys(i)
        col = colors.get(i) or {"bone": "k", "skin": "0.7"}.get(sy, "tab:red")
        seg = secs(pg, i, n, o)
        if len(seg) == 0:
            continue
        for q in seg:
            ax.plot([(q[0] - o) @ u1, (q[1] - o) @ u1], [(q[0] - o) @ u2, (q[1] - o) @ u2], "-", color=col, lw=(1.6 if sy == "bone" else lw))
    ax.set_aspect("equal")
    ax.axis("off")


def palette(ids):
    import matplotlib.pyplot as plt
    cm = plt.get_cmap("tab20")
    return {i: cm(k % 20) for k, i in enumerate(ids)}


def near(pg, centre, R, systems=("muscle", "vessel", "nerve", "joint", "bursa", "fascia"), side=None):
    out = []
    for i in pg.ids:
        sy = pg.sys(i)
        if sy not in systems:
            continue
        if side and not (i.endswith("_" + side) or ("_" + side + "_") in i):
            continue
        if (np.linalg.norm(pg.v(i) - centre, axis=1) < R).any():
            out.append(i)
    return out


def fig_pair(which, pgA, pgB, title, centre, n, R, fname, ids=None, bones=None, side=None, half=110, extra=()):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    n = np.asarray(n, float) / np.linalg.norm(n)
    up = np.array([0.0, 1.0, 0.0])
    u1 = np.cross(up, n)
    if np.linalg.norm(u1) < 1e-6:
        u1 = np.array([1.0, 0, 0])
    u1 /= np.linalg.norm(u1)
    u2 = np.cross(n, u1)
    ids = ids or near(pgA, centre, R, side=side)
    bones = bones or [i for i in pgA.ids if pgA.sys(i) == "bone" and (np.linalg.norm(pgA.v(i) - centre, axis=1) < R).any()]
    skin = [i for i in pgA.skin_ids if (np.linalg.norm(pgA.v(i) - centre, axis=1) < R + 60).any()]
    col = palette([i for i in ids if pgA.sys(i) == "muscle"])
    fig, axs = plt.subplots(1, 2, figsize=(18, 9))
    for ax, pg, tt in zip(axs, (pgA, pgB), ("before", "after")):
        draw(ax, pg, skin + bones, n, centre, u1, u2, {}, lw=0.5)
        draw(ax, pg, ids, n, centre, u1, u2, col)
        ax.set_xlim(-half, half)
        ax.set_ylim(-half, half)
        ax.set_title(f"{title}: {tt}", fontsize=11)
    fig.savefig(OUT / fname, dpi=60, bbox_inches="tight")
    plt.close(fig)


def main(which):
    import json
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = K.PAGES[which]
    pgA, pgB = K.load(which), K.load(which, src=cfg["out"])
    rb = json.loads((REPO / f"build/q209_raw/Q198_model_{cfg['key0'] if False else cfg['base_key']}.json").read_text())
    raw = json.loads((REPO / f"build/q211_raw/Q198_model_{cfg['key0']}.json").read_text())
    from scripts.zanatomy.q198_audit import elbow_angles
    import scripts.zanatomy.q211_paths  # noqa: F401
    from scripts.zanatomy.q198_load import load
    from scripts.zanatomy.q198_joints import find_joints
    S = load(cfg["key0"])
    J, B, lev = find_joints(S)
    for j in J:
        side = j["side"]
        if j["name"] == "elbow":
            ea = elbow_angles(j, B, side)
            fig_pair(which, pgA, pgB, f"{which} {side} elbow, flexion-plane section", np.asarray(j["centre"]), ea["epicondylar_axis"], 120, f"{which}_elbow_{side}_flexion_plane.png", side=side, half=130)
        if j["name"] == "shoulder":
            fig_pair(which, pgA, pgB, f"{which} {side} shoulder, sagittal section through the glenohumeral centre", np.asarray(j["centre"]), [1, 0, 0], 100, f"{which}_shoulder_{side}_sagittal.png", side=side, half=110)
    if which == "female":
        c = pgA.v("zan_vertebra_l1").mean(0)
        fig_pair(which, pgA, pgB, "female lumbar column T12 | L1 | L2, sagittal section", c + np.array([-0.0, 25.0, 0.0]), [1, 0, 0], 70, "female_lumbar_sagittal.png", half=90)
        for side in "lr":
            c = pgA.v(f"talus_{side}").mean(0)
            fig_pair(which, pgA, pgB, f"female {side} foot / ankle, sagittal section", c, [1, 0, 0], 100, f"female_foot_{side}_sagittal.png", half=110, side=side)
    else:
        c = pgA.v("talus_l").mean(0)
        fig_pair(which, pgA, pgB, "male left ankle, sagittal section", c, [1, 0, 0], 90, "male_ankle_l_sagittal.png", half=100, side="l")
        fig_pair(which, pgA, pgB, "male left ankle, coronal section", c, [0, 0, 1], 90, "male_ankle_l_coronal.png", half=100, side="l")


if __name__ == "__main__":
    for w in (sys.argv[1:] or ["male", "female"]):
        main(w)
