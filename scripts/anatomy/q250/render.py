"""Q250: simple painter's-algorithm renders (matplotlib, no GL) of the bones of one or several pages, for before / after comparison.
    render.py OUT.png VIEW LABEL=PAGE_DIR:STEM [LABEL=PAGE_DIR:STEM ...] [--pelvis|--body]
VIEW = anterior | superior | lateral. --pelvis: hip bones, sacrum, coccyx, L5-L3, femoral heads; --body: all bones + the skin as a point silhouette."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q205_pages as P5  # noqa: E402

PELVIC = ("hip_bone_l", "hip_bone_r", "sacrum", "coccyx", "zan_vertebra_l5", "zan_vertebra_l4", "femur_l", "femur_r")


def proj(v, view):
    if view == "anterior":
        return np.c_[-v[:, 0], v[:, 1]], v[:, 2]
    if view == "superior":
        return np.c_[v[:, 0], v[:, 2]], v[:, 1]
    return np.c_[-v[:, 2], v[:, 1]], v[:, 0]          # lateral: viewer on the patient's right, anterior to the left


def draw(ax, S, view, mode, color):
    polys, depth, shade = [], [], []
    L = np.array([0.3, 0.5, 0.8]); L /= np.linalg.norm(L)
    for i, e in S.items():
        if e["m"]["sys"] != "bone":
            continue
        if mode == "pelvis":
            if i not in PELVIC:
                continue
            if i.startswith("femur"):
                v0 = e["v"]; keep = v0[:, 1] > v0[:, 1].max() - 70
                f = e["f"][keep[e["f"]].all(1)]
            else:
                f = e["f"]
        else:
            f = e["f"][::2] if len(e["f"]) > 4000 else e["f"]
        v = e["v"]
        p, d = proj(v, view)
        tri = v[f]
        n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-9
        if view == "anterior":
            vd = np.array([0, 0, 1.0])
        elif view == "superior":
            vd = np.array([0, 1.0, 0])
        else:
            vd = np.array([1.0, 0, 0])
        sh = np.abs(n @ vd) * 0.6 + 0.4 * np.abs(n @ L)
        polys.append(p[f]); depth.append(d[f].mean(1)); shade.append(sh)
    polys = np.concatenate(polys); depth = np.concatenate(depth); shade = np.concatenate(shade)
    o = np.argsort(depth)
    c = np.array(matplotlib.colors.to_rgb(color))[None, :] * (0.35 + 0.65 * np.clip(shade[o], 0, 1))[:, None]
    ax.add_collection(PolyCollection(polys[o], facecolors=c, edgecolors="none", linewidths=0))
    if mode == "body":
        sk = np.vstack([e["v"] for e in S.values() if e["m"]["sys"] == "skin"])
        p, _ = proj(sk, view); ax.scatter(p[:, 0], p[:, 1], s=0.15, c="0.7", zorder=0)
    ax.set_aspect("equal"); ax.autoscale_view()


def main():
    out, view = sys.argv[1], sys.argv[2]
    mode = "body" if "--body" in sys.argv else "pelvis"
    items = [a for a in sys.argv[3:] if "=" in a]
    fig, axes = plt.subplots(1, len(items), figsize=(6.2 * len(items) if mode == "pelvis" else 4.2 * len(items), 6.2 if mode == "pelvis" else 12))
    axes = np.atleast_1d(axes)
    cols = ["#c9b79c", "#d9a066", "#9cc0c9", "#b0a0c9"]
    xl = yl = None
    for k, (ax, it) in enumerate(zip(axes, items)):
        lab, rest = it.split("=", 1); d, stem = rest.split(":")
        man, blob = P5.load_page(REPO / d if not Path(d).is_absolute() else d, stem)
        S = P5.decode(man, blob)
        draw(ax, S, view, mode, cols[k % 4]); ax.set_title(lab, fontsize=10); ax.set_xticks([]); ax.set_yticks([])
        if mode == "pelvis":
            ax.set_xlim(-190, 190) if view != "lateral" else ax.set_xlim(-140, 120); ax.set_ylim(-80, 170) if view == "anterior" or view == "lateral" else ax.set_ylim(-170, 90)
        else:
            ax.set_xlim(-400, 400) if view != "lateral" else ax.set_xlim(-200, 200); ax.set_ylim(-900, 900)
    plt.tight_layout(); plt.savefig(out, dpi=75); print(out)


if __name__ == "__main__":
    main()
