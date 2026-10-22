"""Q194 renders, v9 (before) vs q194 (after): left forearm palmar / dorsal / radial, right forearm, back and oblique muscles, sacrum skin, close-ups of the fixed structures, and the
left-forearm cross-sections drawn over HER cryosection photographs (the evidence the placement is made from).

    PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers python3 scripts/zanatomy/q194_compare_renders.py [--before build/viewer_zan_female] [--after build/viewer_zan_female_q194] [--out DIR]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q190_render as R  # noqa: E402
from scripts.zanatomy import q191_compare_renders as C  # noqa: E402
from scripts.zanatomy import trunk_refit_q186c_audit as A186  # noqa: E402

COL = C.COL


def scene(M, cats, ids=None, box=None, idre=None):
    out = []
    for k, m in M.items():
        if m["sys"] not in cats:
            continue
        if ids is not None and k not in ids:
            continue
        if idre and not re.search(idre, k):
            continue
        if box is not None:
            c = m["v"].mean(0)
            if np.any(c < box[0]) or np.any(c > box[1]):
                continue
        out.append({"v": m["v"], "f": m["f"], "color": COL.get(m["sys"], (0.6, 0.6, 0.6))})
    return out


def montage(pairs, path, labels):
    from PIL import Image, ImageDraw
    ims = [Image.open(p) for p in pairs]
    w, h = ims[0].size
    W = Image.new("RGB", (w * len(ims), h + 24), "white")
    d = ImageDraw.Draw(W)
    for k, (im, lb) in enumerate(zip(ims, labels)):
        W.paste(im, (k * w, 24))
        d.text((k * w + 6, 6), lb, fill=(0, 0, 0))
    W.save(path)


def photo_sections(Mb, Ma, ids, out, levels=(330, 300, 270, 240, 215)):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    SP_ = REPO / "data" / "derived" / "Q194_left_forearm_photo_masks.npz"
    # the photographs themselves are not committed (Q192 session cache); the masks are: draw the muscle compartment + skin silhouette masks as the background
    P = np.load(SP_)
    from scripts.zanatomy import q194_forearm as F
    G = F.load_photo_masks()
    ys = F.GRID_LO[1] + np.arange(F.GRID_N[1])
    fig, axs = plt.subplots(2, len(levels), figsize=(4 * len(levels), 8))
    for c, y in enumerate(levels):
        iy = int(np.argmin(abs(ys - y)))
        bg = np.zeros(G["skin"].shape[::2] + (3,))
        sk, mu, bo = G["skin"][:, iy, :] > 0.5, G["muscle"][:, iy, :] > 0.5, G["bone"][:, iy, :] > 0.5
        img = np.ones(sk.shape + (3,)) * 0.15
        img[sk] = (0.93, 0.88, 0.7); img[mu] = (0.45, 0.1, 0.1); img[bo & sk & ~mu] = (0.98, 0.97, 0.9)
        for r_, (M, ttl) in enumerate(((Mb, "v9"), (Ma, "q194"))):
            ax = axs[r_, c]
            ax.imshow(img.transpose(1, 0, 2), origin="lower", extent=(F.GRID_LO[0], F.GRID_LO[0] + F.GRID_N[0], F.GRID_LO[2], F.GRID_LO[2] + F.GRID_N[2]))
            for i in ids:
                for a, b in R.section_lines(M[i]["v"], M[i]["f"], y):
                    ax.plot([a[0], b[0]], [a[1], b[1]], "-", color="#2f2" if r_ else "#fb0", lw=0.9)
            for i in ("radius_l", "ulna_l"):
                for a, b in R.section_lines(M[i]["v"], M[i]["f"], y):
                    ax.plot([a[0], b[0]], [a[1], b[1]], "-", color="#08f", lw=1.2)
            ax.set_xlim(-330, -135); ax.set_ylim(-110, 80); ax.set_aspect("equal"); ax.set_title(f"{ttl}  y={y}", fontsize=9); ax.axis("off")
    plt.tight_layout()
    plt.savefig(out, dpi=70)
    plt.close(fig)


def run(before, after, out, size=(640, 640)):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    Mb, Ma = A186.load_viewer(Path(before)), A186.load_viewer(Path(after))
    hand = {s: {"b": C.hand_frame(Mb, s), "a": C.hand_frame(Ma, s)} for s in "lr"}
    made = []

    def two(name, cats, view, **kw):
        for tag, M in (("v9", Mb), ("q194", Ma)):
            R.render(scene(M, cats, **kw), [{**view, "name": f"{name}_{tag}"}], out, size=size)
        montage([out / f"{name}_v9.png", out / f"{name}_q194.png"], out / f"{name}.png", ["v9 (before)", "q194 (after)"])
        made.append(name)

    for s, nm in (("l", "left"), ("r", "right")):
        ids = {i for i, m in Ma.items() if i.endswith("_" + s) and m["sys"] in ("muscle", "nerve", "vessel", "bone", "fascia", "tendon") and abs(m["v"].mean(0)[0]) > 120 and 20 < m["v"].mean(0)[1] < 340}
        cen, axis, radial, palm = hand[s]["a"]
        fa_c = np.vstack([Ma[f"radius_{s}"]["v"], Ma[f"ulna_{s}"]["v"]]).mean(0)
        for vname, d in (("palmar", palm), ("dorsal", -palm), ("radial", radial)):
            cm = C.cam(d)
            two(f"forearm_{nm}_{vname}", ("muscle", "nerve", "vessel", "bone"), {"az": cm["az"], "el": cm["el"], "target": fa_c.tolist(), "half": 170}, ids=ids)
    two("back_muscles", ("muscle", "bone"), {"az": 180, "el": 5, "target": [0, 250, -60], "half": 330}, box=(np.array([-300, -200, -300]), np.array([300, 700, 300])))
    two("back_oblique", ("muscle", "bone"), {"az": 150, "el": 20, "target": [0, 250, -60], "half": 330}, box=(np.array([-300, -200, -300]), np.array([300, 700, 300])))
    two("sacrum_skin_back", ("skin",), {"az": 180, "el": 15, "target": [0, -40, -100], "half": 150}, box=(np.array([-400, -250, -400]), np.array([400, 150, 400])))
    two("sacrum_skin_oblique", ("skin",), {"az": 150, "el": 20, "target": [0, -40, -100], "half": 150}, box=(np.array([-400, -250, -400]), np.array([400, 150, 400])))
    two("sacrum_muscles", ("muscle", "bone"), {"az": 180, "el": 15, "target": [0, -40, -100], "half": 190}, box=(np.array([-300, -250, -300]), np.array([300, 150, 300])))
    two("upper_back_fixed", ("muscle", "bone", "ligament", "vessel", "nerve"), {"az": 170, "el": 10, "target": [0, 540, -60], "half": 130},
        idre=r"rhomboid|supraspinous|intervertebral_disc_(c7|t[1-4])|deep_branch_of_transverse|subclavius|musculophrenic|cephalic|pectoralis_major|trapezius|vertebra")
    ids = {i for i, m in Ma.items() if i.endswith("_l") and m["sys"] == "muscle" and C.H.NOT_BODY.search(i) is None and 215 < m["v"].mean(0)[1] < 340 and m["v"].mean(0)[0] < -120}
    photo_sections(Mb, Ma, sorted(ids), out / "left_forearm_sections_over_photo_masks.png")
    made.append("left_forearm_sections_over_photo_masks")
    return made


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default=str(REPO / "build" / "viewer_zan_female"))
    ap.add_argument("--after", default=str(REPO / "build" / "viewer_zan_female_q194"))
    ap.add_argument("--out", default=str(REPO / "build" / "viewer_zan_female_q194" / "renders"))
    a = ap.parse_args(argv)
    print(run(a.before, a.after, a.out))


if __name__ == "__main__":
    main()
