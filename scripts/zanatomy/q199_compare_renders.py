"""Q199 renders, v12 (before) vs q199 (after): close-ups of BOTH elbows from the anterior, posterior, medial and lateral side (layers: bones + muscles; bones + vessels + nerves +
ligaments), sagittal and coronal cuts through the joint (every shipped structure's section line, bones heavy) and the left elbow sections over HER cryosection photographs.

    PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers python3 scripts/zanatomy/q199_compare_renders.py [--before build/viewer_zan_female] [--after build/viewer_zan_female_q199] [--out DIR]
                                                                                              [--photos arm_ds2.npy]   # the cached stack of scripts/cryo/q199_arm_evidence.py
"""
from __future__ import annotations

import argparse
import colorsys
import sys
import zlib
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q190_render as R  # noqa: E402
from scripts.zanatomy import trunk_refit_q186c_audit as A186  # noqa: E402

SEC_COL = {"bone": ("#111111", 1.8), "muscle": ("#b05028", 0.5), "vessel": ("#d01010", 1.0), "nerve": ("#d8b000", 1.0), "tendon": ("#7070b0", 0.6), "ligament": ("#4060d0", 0.9),
           "joint": ("#30a0c0", 0.9), "bursa": ("#80b080", 0.5)}
ELBOW = {"l": np.array([-215.0, 335.0, -45.0]), "r": np.array([205.0, 335.0, -55.0])}


def mcol(i, sysn):
    h = lambda salt: (zlib.crc32(i.encode() + salt) % 100) / 100.0
    if sysn == "bone":
        return (0.93, 0.9, 0.78)
    if sysn == "muscle":
        return colorsys.hsv_to_rgb(0.08 * h(b""), 0.55 + 0.4 * h(b"a"), 0.55 + 0.35 * h(b"b"))
    if sysn == "vessel":
        return (0.15, 0.25, 0.85) if "vein" in i else (0.8, 0.1, 0.1)
    if sysn == "nerve":
        return (0.95, 0.85, 0.1)
    return (0.85, 0.85, 0.9)


def scene(M, side, layers, box=95.0):
    s = "_" + side
    out = []
    for i, m in M.items():
        if not (i.endswith(s) or s + "_" in i) or m["sys"] not in layers:
            continue
        c = m["v"].mean(0)
        if np.linalg.norm(c - ELBOW[side]) > 200 or ("fascia" in i or "septum" in i):
            continue
        out.append({"v": m["v"], "f": m["f"], "color": mcol(i, m["sys"])})
    return out


def montage(rows, path, labels, w=480):
    from PIL import Image, ImageDraw
    ims = [[Image.open(p) for p in r] for r in rows]
    W = Image.new("RGB", (w * len(ims[0]), (w + 24) * len(ims)), "white")
    d = ImageDraw.Draw(W)
    for r, row in enumerate(ims):
        for c, im in enumerate(row):
            W.paste(im, (c * w, r * (w + 24) + 24))
            d.text((c * w + 6, r * (w + 24) + 6), labels[r][c], fill=(0, 0, 0))
    W.save(path)


def sections(Mb, Ma, side, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    s = "_" + side
    xc = -222.0 if side == "l" else 218.0
    xw = (-290, -150) if side == "l" else (150, 290)

    def draw(ax, M, axis, val, win, title):
        p, q = [k for k in range(3) if k != axis]
        for i, m in M.items():
            if not (i.endswith(s) or s + "_" in i) or m["sys"] not in SEC_COL:
                continue
            v = m["v"]
            if v.min(0)[axis] > val or v.max(0)[axis] < val:
                continue
            L = R.section_lines(v[:, [p, axis, q]], m["f"], val)
            if not len(L):
                continue
            if axis == 0:
                L = L[:, :, ::-1]
            c, w = SEC_COL[m["sys"]]
            ax.add_collection(LineCollection(L, colors=c, linewidths=w))
        ax.set_xlim(*win[0]); ax.set_ylim(*win[1]); ax.set_aspect("equal"); ax.set_title(title, fontsize=10); ax.grid(alpha=0.25)

    fig, ax = plt.subplots(2, 3, figsize=(21, 13))
    for r, (tag, M) in enumerate((("v12", Mb), ("Q199", Ma))):
        draw(ax[r, 0], M, 0, xc, ((-130, 70), (260, 430)), f"{tag} sagittal x={xc:g} (horizontal z, up y)")
        draw(ax[r, 1], M, 0, xc + (-14 if side == "l" else 14), ((-130, 70), (260, 430)), f"{tag} sagittal x={xc + (-14 if side == 'l' else 14):g}")
        draw(ax[r, 2], M, 2, -55.0, (xw, (260, 430)), f"{tag} coronal z=-55 (horizontal x)")
    plt.tight_layout()
    plt.savefig(out, dpi=45)
    plt.close(fig)


def photo_sections(Mb, Ma, stack, out, levels=(470, 430, 380, 350, 338, 331, 324, 317)):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    A = np.load(stack, mmap_mode="r")
    PX, AZ, AX = 0.33, -166.4, 352.2
    fig, ax = plt.subplots(2, 4, figsize=(28, 14))
    for a, y in zip(ax.flat, levels):
        c0, c1, r0, r1 = 700, 960, 0, 330
        ext = [AX - PX * 2 * c0, AX - PX * 2 * c1, AZ + PX * 2 * r1, AZ + PX * 2 * r0]
        a.imshow(A[630 - y][r0:r1, c0:c1], extent=ext)
        for M, col, ls in ((Mb, "magenta", "--"), (Ma, "cyan", "-")):
            for n in ("humerus_l", "radius_l", "ulna_l"):
                for P in sec2d(M[n]["v"], M[n]["f"], y):
                    a.plot(P[:, 0], P[:, 1], col, lw=1.3, ls=ls)
        a.set_title(f"y={y}   magenta dashed = v12 bones, cyan = Q199 bones", fontsize=9)
        a.set_xlim(ext[0], ext[1]); a.set_ylim(ext[2], ext[3])
    plt.tight_layout()
    plt.savefig(out, dpi=45)
    plt.close(fig)


def sec2d(v, f, y):
    import trimesh
    s = trimesh.Trimesh(v, f, process=False).section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0])
    return [] if s is None else [np.asarray(p)[:, [0, 2]] for p in s.discrete]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--before", default=str(REPO / "build" / "viewer_zan_female"))
    ap.add_argument("--after", default=str(REPO / "build" / "viewer_zan_female_q199"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--photos", default=None)
    a = ap.parse_args(argv)
    out = Path(a.out or Path(a.after) / "renders")
    out.mkdir(parents=True, exist_ok=True)
    Mb, Ma = A186.load_viewer(Path(a.before)), A186.load_viewer(Path(a.after))
    for side in ("l", "r"):
        for name, layers in (("muscles", ("bone", "muscle")), ("vessels_nerves", ("bone", "vessel", "nerve", "ligament", "joint"))):
            rows = []
            for tag, M in (("v12", Mb), ("q199", Ma)):
                views = [{"name": f"{n}", "az": az, "el": 0, "target": ELBOW[side], "half": 95}
                         for n, az in (("anterior", 0), ("lateral", 270 if side == "l" else 90), ("posterior", 180), ("medial", 90 if side == "l" else 270))]
                R.render(scene(M, side, layers), views, out / f"_tmp_{side}_{name}_{tag}", size=(480, 480))
                rows.append([str(out / f"_tmp_{side}_{name}_{tag}" / f"{v['name']}.png") for v in views])
            montage(rows, out / f"elbow_{'left' if side == 'l' else 'right'}_{name}.png", [[f"{t} {v}" for v in ("anterior", "lateral", "posterior", "medial")] for t in ("v12", "Q199")])
        sections(Mb, Ma, side, out / f"elbow_{'left' if side == 'l' else 'right'}_sagittal_coronal.png")
    if a.photos:
        photo_sections(Mb, Ma, a.photos, out / "left_elbow_bones_over_her_photographs.png")
    import shutil
    for d in out.glob("_tmp_*"):
        shutil.rmtree(d)
    print("renders ->", out)


if __name__ == "__main__":
    main()
