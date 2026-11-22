"""Q190: before(v6) / after(q190) / her own model renders of the lumbar-sacral-gluteal-hip-flank region (and transverse cuts).

    python3 scripts/zanatomy/q190_compare_renders.py --before build/viewer_zan_female --after build/viewer_zan_female_q190 --out DIR
PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers is needed (headless Chromium, swiftshader)."""
from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q190_render as R  # noqa: E402
from scripts.zanatomy import q190_views as V  # noqa: E402
from scripts.zanatomy import trunk_refit_q186c_audit as A186  # noqa: E402

LAYER_COL = {"muscle": (0.78, 0.22, 0.20), "bone": (0.92, 0.90, 0.78), "nerve": (0.95, 0.80, 0.15), "vessel": (0.2, 0.35, 0.85),
             "fascia": (0.5, 0.65, 0.85), "cartilage": (0.6, 0.85, 0.9), "joint": (0.8, 0.8, 0.8), "skin": (0.90, 0.74, 0.64)}
HER_COL = {"muscle": (0.80, 0.45, 0.15), "bone": (0.80, 0.86, 0.72), "vessel": (0.2, 0.35, 0.85), "nerve": (0.95, 0.80, 0.15),
           "tendon": (0.9, 0.9, 0.6), "ligament": (0.8, 0.8, 0.8), "cartilage": (0.6, 0.85, 0.9), "fascia": (0.5, 0.65, 0.85), "organ": (0.6, 0.3, 0.4)}
CUTS = (-20, 40, 100, 160, 220, 280)


def zan_scene(M, layers, region_y=(-260, 700)):
    sc = []
    for k, m in M.items():
        if m["sys"] not in layers:
            continue
        c = m["v"].mean(0)
        if not (region_y[0] < c[1] < region_y[1]):
            continue
        sc.append({"v": m["v"], "f": m["f"], "color": LAYER_COL.get(m["sys"], (0.7, 0.7, 0.7))})
    return sc


def her_scene(H, cats, skin=None):
    sc = [{"v": h["v"].astype(np.float32), "f": h["f"], "color": HER_COL.get(h["cat"], (0.7, 0.7, 0.7))} for h in H["her"].values() if h["cat"] in cats]
    if skin:
        sc.append({"v": H["skin_v"], "f": H["skin_f"], "color": LAYER_COL["skin"]})
    return sc


def section_png(sets, y, dest, half=230.0):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, len(sets), figsize=(5.2 * len(sets), 4.6))
    for ax, (label, items) in zip(np.atleast_1d(axs), sets):
        for v, f, col, lw in items:
            seg = R.section_lines(v, f, y)
            if len(seg):
                from matplotlib.collections import LineCollection
                ax.add_collection(LineCollection(seg[:, :, [0, 1]] * np.array([1, 1]), colors=[col], linewidths=lw))
        ax.set_xlim(-half, half); ax.set_ylim(-170, 150); ax.set_aspect("equal"); ax.set_title(f"{label}  y={y}", fontsize=9)
        ax.set_xlabel("x (+ her right)"); ax.set_ylabel("z (+ anterior)"); ax.invert_xaxis()
    fig.tight_layout(); fig.savefig(dest, dpi=80); plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default=str(REPO / "build" / "viewer_zan_female"))
    ap.add_argument("--after", default=str(REPO / "build" / "viewer_zan_female_q190"))
    ap.add_argument("--her-cache", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--views", default=",".join(V.VIEWS))
    args = ap.parse_args(argv)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    Mb, Ma = A186.load_viewer(Path(args.before)), A186.load_viewer(Path(args.after))
    H = pickle.load(open(args.her_cache, "rb"))
    names = args.views.split(",")
    deep = ("muscle", "bone", "nerve", "vessel", "fascia", "cartilage")
    sets = {"skin": (zan_scene(Mb, ("skin",)), zan_scene(Ma, ("skin",)), [{"v": H["skin_v"], "f": H["skin_f"], "color": LAYER_COL["skin"]}]),
            "muscle": (zan_scene(Mb, ("muscle",)), zan_scene(Ma, ("muscle",)), her_scene(H, ("muscle",))),
            "deep": (zan_scene(Mb, deep), zan_scene(Ma, deep), her_scene(H, ("muscle", "bone", "vessel", "nerve", "cartilage", "ligament")))}
    for tag, (b, a, h) in sets.items():
        V.render_set(b, f"{tag}_before", out, names); V.render_set(a, f"{tag}_after", out, names); V.render_set(h, f"{tag}_her", out, names)
    for n in names:
        files, labels = [], []
        for tag, nm in (("skin", "skin"), ("muscle", "muscles"), ("deep", "all deep layers")):
            for kind, lab in (("before", "v6"), ("after", "q190"), ("her", "her own model")):
                files.append(out / f"{tag}_{kind}_{n}.png"); labels.append(f"{nm}: {lab}")
        V.montage(files[:3], labels[:3], out / f"cmp_skin_{n}.png"); V.montage(files[3:6], labels[3:6], out / f"cmp_muscles_{n}.png")
        V.montage(files[6:], labels[6:], out / f"cmp_deep_{n}.png")
        for f_ in files:
            f_.unlink()
    # all-layer 3D with the cut: skin + everything clipped at y (viewed from above)
    allb = zan_scene(Mb, deep + ("skin",)); alla = zan_scene(Ma, deep + ("skin",)); allh = her_scene(H, ("muscle", "bone", "vessel", "nerve", "cartilage", "ligament"), skin=True)
    for y in CUTS[1:5]:
        views = [{"name": f"cut{y}", "az": 180, "el": 70, "target": (0, y - 40, -20), "half": 230, "clip_y": (-1e9, y)}]
        for tag, sc in (("b", allb), ("a", alla), ("h", allh)):
            R.render(sc, views, out, size=(640, 640), prefix=f"all_{tag}_")
        V.montage([out / f"all_{t}_cut{y}.png" for t in "bah"], ["all layers v6", "all layers q190", "her own model"], out / f"cmp_alllayers_cut{y}.png")
        for t in "bah":
            (out / f"all_{t}_cut{y}.png").unlink()
    # transverse section line plots
    zl = lambda M, layers: [(m["v"], m["f"], LAYER_COL[m["sys"]], 0.5 if m["sys"] != "skin" else 1.2) for m in M.values() if m["sys"] in layers]
    hl = [(h["v"].astype(float), h["f"].astype(int), HER_COL.get(h["cat"], (0.6, 0.6, 0.6)), 0.5) for h in H["her"].values() if h["cat"] in ("muscle", "bone", "vessel", "nerve")]
    hl.append((H["skin_v"].astype(float), H["skin_f"].astype(int), LAYER_COL["skin"], 1.2))
    for y in CUTS:
        section_png([("v6", zl(Mb, deep + ("skin",))), ("q190", zl(Ma, deep + ("skin",))), ("her own model", hl)], y, out / f"section_y{y}.png")
    print("renders ->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
