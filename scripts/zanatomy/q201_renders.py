"""Q201 renders of the Z-Anatomy model fitted to the VH male, Q195 state (before) vs Q201 (after): his cryosection photographs with the sections of every shipped structure of the arm drawn
over them (elbow, forearm, wrist; the photographs are HIS: scripts/cryo/stream_vhm_cryosections.py -> cryo_1mm.npy, registration data/derived/Q185a2_arm_skin_registration_vhm.json),
3-D close-ups of both elbows / forearms / wrists, sagittal and coronal cuts through the elbow.

    PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers python3 scripts/zanatomy/q201_renders.py --before DIR_OR_DUMP --after DIR_OR_DUMP --cryo SCRATCH/vh_cryo [--out build/q201_renders]
(a dir = a shipped viewer page; a .npz = a full-resolution dump)
"""
from __future__ import annotations

import argparse
import colorsys
import json
import sys
import zlib
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q190_render as R  # noqa: E402

REG = REPO / "data" / "derived" / "Q185a2_arm_skin_registration_vhm.json"
ELBOW = {"l": np.array([-245.0, 275.0, -50.0]), "r": np.array([250.0, 270.0, -50.0])}
WRIST = {"l": np.array([-165.0, 115.0, 105.0]), "r": np.array([150.0, 110.0, 105.0])}
DPI = 60
SEC_COL = {"bone": ("#111111", 1.8), "muscle": ("#b05028", 0.5), "vessel": ("#d01010", 1.0), "nerve": ("#d8b000", 1.0), "tendon": ("#7070b0", 0.6), "ligament": ("#4060d0", 0.9),
           "skin": ("#00a0ff", 1.2), "fascia": ("#909090", 0.4)}


def load_state(p):
    p = Path(p)
    if p.suffix == ".npz":
        from scripts.zanatomy import q190_metrics as Mx
        return {d["id"]: {"v": d["v"], "f": d["f"], "sys": d["cat"]} for d in Mx.load_dump(str(p))}
    from scripts.zanatomy import trunk_refit_q186c_audit as A186
    return A186.load_viewer(p, "atlas_viewer_zan_male_fitted")


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


def scene(M, side, layers, centre, box=110.0):
    s = "_" + side
    out = []
    for i, m in M.items():
        if not (i.endswith(s) or s + "_" in i) or m["sys"] not in layers or "fascia" in i or "septum" in i:
            continue
        if np.linalg.norm(m["v"].mean(0) - centre) > box * 2.2:
            continue
        out.append({"v": m["v"], "f": m["f"], "color": mcol(i, m["sys"])})
    return out


def photo_sections(Mb, Ma, cryo, out, side, levels, xwin, zwin=(-110, 130)):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    vol = np.load(Path(cryo) / "cryo_1mm.npy", mmap_mode="r")
    idx = json.loads((Path(cryo) / "cryo_index.json").read_text())
    inst = {r[1]: i for i, r in enumerate(idx)}
    reg = json.loads(REG.read_text())["sides"]["left" if side == "l" else "right"]["levels"]
    s = "_" + side
    fig, ax = plt.subplots(len(levels), 2, figsize=(14, 6.2 * len(levels)), squeeze=False)
    for r, y in enumerate(levels):
        k = int(round(1880.4 - y))
        T = reg[str(k)]["T"]
        im = np.asarray(vol[inst[k]])
        X0, Y0 = T
        c_hi = min(int((X0 - (xwin[0] - 6.0)) / 0.99), im.shape[1] - 1)
        c_lo = max(int((X0 - (xwin[1] - 6.0)) / 0.99), 0)
        ext = [X0 - c_lo * 0.99 + 6.0, X0 - c_hi * 0.99 + 6.0, Y0 + im.shape[0] * 0.99 - 4.8, Y0 - 4.8]
        for c, (tag, M) in enumerate((("Q195", Mb), ("Q201", Ma))):
            a = ax[r, c]
            a.imshow(im[:, c_lo:c_hi], extent=ext)
            for i, m in M.items():
                if not (i.endswith(s) or s + "_" in i) or m["sys"] not in SEC_COL:
                    continue
                v = m["v"]
                if v[:, 1].min() > y or v[:, 1].max() < y:
                    continue
                L = R.section_lines(v, m["f"], y)
                if len(L):
                    col, w = SEC_COL[m["sys"]]
                    a.add_collection(LineCollection(L, colors=col, linewidths=w))
            a.set_xlim(*xwin if side == "l" else xwin)
            a.set_ylim(*zwin)
            a.set_title(f"{tag}  {side.upper()} arm  y={y}  (black=bone, brown=muscle, red/yellow=vessel/nerve, blue=skin) on HIS photograph", fontsize=9)
    plt.tight_layout()
    plt.savefig(out, dpi=DPI)
    plt.close(fig)


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


def closeups(Mb, Ma, out, side, tag, centre, layers, half=110):
    rows = []
    for t, M in (("Q195", Mb), ("Q201", Ma)):
        views = [{"name": n, "az": az, "el": 0, "target": centre, "half": half}
                 for n, az in (("anterior", 0), ("lateral", 270 if side == "l" else 90), ("posterior", 180), ("medial", 90 if side == "l" else 270))]
        R.render(scene(M, side, layers, centre), views, out / f"_tmp_{side}_{tag}_{t}", size=(480, 480))
        rows.append([str(out / f"_tmp_{side}_{tag}_{t}" / f"{v['name']}.png") for v in views])
    montage(rows, out / f"{tag}_{'left' if side == 'l' else 'right'}.png", [[f"{t} {v}" for v in ("anterior", "lateral", "posterior", "medial")] for t in ("Q195", "Q201")])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--cryo", required=True, help="directory with cryo_1mm.npy + cryo_index.json (scripts/cryo/stream_vhm_cryosections.py)")
    ap.add_argument("--out", default=str(REPO / "build" / "q201_renders"))
    ap.add_argument("--only", default="photos,3d", help="photos,3d")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    Mb, Ma = load_state(a.before), load_state(a.after)
    if "photos" in a.only:
        for side in ("l", "r"):
            xw = (-300, -150) if side == "l" else (150, 300)
            for n, lv in enumerate(((320, 290), (270, 255))):
                photo_sections(Mb, Ma, a.cryo, out / f"photos_elbow_{side}_{n}.png", side, lv, xw, (-110, 30))
            for n, lv in enumerate(((235, 200), (160, 125))):
                photo_sections(Mb, Ma, a.cryo, out / f"photos_forearm_{side}_{n}.png", side, lv, xw if side == "r" else (-290, -140), (-60, 140))
    if "3d" in a.only:
        for side in ("l", "r"):
            for tag, centre, layers, half in (("elbow_muscles", ELBOW[side], ("bone", "muscle"), 100), ("elbow_vessels_nerves", ELBOW[side], ("bone", "vessel", "nerve", "ligament"), 100),
                                              ("forearm_muscles", (ELBOW[side] + WRIST[side]) / 2, ("bone", "muscle"), 130), ("wrist_all", WRIST[side], ("bone", "muscle", "tendon", "vessel", "nerve", "ligament"), 80),
                                              ("bones", (ELBOW[side] + WRIST[side]) / 2, ("bone",), 150)):
                closeups(Mb, Ma, out, side, tag, centre, layers, half)
    import shutil
    for d in out.glob("_tmp_*"):
        shutil.rmtree(d)
    print("renders ->", out)


if __name__ == "__main__":
    main()
