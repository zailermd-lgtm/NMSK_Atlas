"""Q195 renders: Z-Anatomy male fitted to the VH male vs his own reconstruction (build/viewer_m_hr*), side by side.

    python3 scripts/zanatomy/q195_renders.py --fitted build/viewer_zan_male_fitted_q195 --own build/viewer_m_hr_q193 --out DIR [--tag s1]

Orthographic flat-shaded WebGL2 renders in headless Chromium (swiftshader, scripts/zanatomy/q190_render.py): front / back / right side / oblique for
skin, muscles+bones, deep layers; transverse cuts (shoulder, chest, abdomen, pelvis, thigh) as line plots with his CT skin outline."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.zanatomy import q190_render as R  # noqa: E402

COL = {"skin": (0.93, 0.78, 0.68), "muscle": (0.78, 0.25, 0.22), "bone": (0.92, 0.9, 0.82), "organ": (0.35, 0.55, 0.75), "vessel": (0.2, 0.3, 0.8),
       "nerve": (0.95, 0.85, 0.2), "tendon": (0.9, 0.85, 0.6), "ligament": (0.8, 0.8, 0.6), "cartilage": (0.6, 0.85, 0.85), "fascia": (0.85, 0.6, 0.6)}
VIEWS = [("front", 0, 0), ("back", 180, 0), ("right", 90, 0), ("oblique", 35, 15)]
CUTS = {"shoulder": 575.0, "chest": 450.0, "abdomen": 200.0, "pelvis": 0.0, "thigh": -250.0}


def load_fitted(d: Path):
    from scripts.zanatomy.trunk_refit_q186c_audit import load_viewer
    stem = next(Path(d).glob("*.html")).stem
    M = load_viewer(Path(d), stem)
    return {k: {"v": m["v"], "f": m["f"], "cat": m["sys"]} for k, m in M.items()}


def load_own(d: Path):
    from scripts.transfer.bundle_io import read_bundle_dir, meshes_by_id
    M = meshes_by_id(*read_bundle_dir(d))
    return {k: {"v": m["v"].astype(float), "f": m["f"], "cat": "skin" if k == "skin" else m["cat"]} for k, m in M.items()}


def scene(M, layers):
    out = []
    for k, m in M.items():
        if m["cat"] in layers and len(m["f"]):
            out.append({"v": m["v"], "f": m["f"], "color": COL.get(m["cat"], (0.6, 0.6, 0.6))})
    return out


def full_views(prefix):
    return [{"name": f"{prefix}_{n}", "az": az, "el": el, "target": (0, -60, 0), "half": 1000.0} for n, az, el in VIEWS]


def cut_figure(Mf, Mo, skin, path, ys=CUTS):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(2, len(ys), figsize=(4.2 * len(ys), 8.4))
    for j, (name, y) in enumerate(ys.items()):
        for i, (M, title) in enumerate(((Mf, "Z-Anatomy fitted to him"), (Mo, "his own reconstruction"))):
            ax = axs[i, j]
            for k, m in M.items():
                c = m["cat"]
                if c == "skin" and M is Mf:
                    col, lw = "tab:orange", 0.7
                elif c == "muscle":
                    col, lw = "tab:red", 0.4
                elif c == "bone":
                    col, lw = "0.3", 0.8
                elif c == "organ":
                    col, lw = "tab:blue", 0.6
                else:
                    continue
                v = m["v"]
                if v[:, 1].min() > y or v[:, 1].max() < y:
                    continue
                seg = R.section_lines(v, m["f"], y)
                for s in seg:
                    ax.plot(s[:, 0], s[:, 1], color=col, lw=lw)
            if skin is not None:
                for s in R.section_lines(skin["v"], skin["f"], y):
                    ax.plot(s[:, 0], s[:, 1], color="k", lw=0.8)
            ax.set_aspect("equal")
            ax.set_xlim(-330, 330); ax.set_ylim(-180, 200)
            ax.set_title(f"{name} y={y:.0f} -- {title}", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--fitted", required=True)
    ap.add_argument("--own", default=str(REPO / "build" / "viewer_m_hr_q193"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", default="")
    a = ap.parse_args(argv)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    pre = (a.tag + "_") if a.tag else ""
    Mf, Mo = load_fitted(Path(a.fitted)), load_own(Path(a.own))
    from scripts.ribs_from_ct_labels import load_skin
    sk = load_skin("vhm")
    skin = {"v": np.asarray(sk.vertices, float), "f": np.asarray(sk.faces)}
    layer_sets = {"skin": ("skin",), "muscles": ("muscle", "bone", "tendon", "fascia"), "deep": ("bone", "organ", "vessel", "cartilage")}
    for lname, layers in layer_sets.items():
        R.render(scene(Mf, layers), full_views(f"{pre}fitted_{lname}"), out)
        R.render(scene(Mo, ("skin",) if lname == "skin" else layers), full_views(f"{pre}own_{lname}"), out)
        print("rendered", lname)
    cut_figure(Mf, Mo, skin, out / f"{pre}cuts.png")
    print("cuts done")


if __name__ == "__main__":
    main()
