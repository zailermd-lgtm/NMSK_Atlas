"""Q217: HIS photographs of the left forearm / elbow with the sections of the shipped structures of a page drawn over them (before | after).
    python3 scripts/transfer/q217_sections.py OUT.png y1,y2,... PAGE_BUNDLE_DIR [PAGE_BUNDLE_DIR2]       (a bundle dir = build/viewer_m_hr_q214; two dirs -> two columns)"""
from __future__ import annotations

import colorsys
import json
import sys
import zlib
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q190_render as R  # noqa: E402
from scripts.transfer import q217_photo as PH  # noqa: E402

COL = {"bone": ("#000000", 1.6), "muscle": None, "vessel": ("#d01010", 0.8), "nerve": ("#d8b000", 0.8), "skin": ("#00a0ff", 1.0), "tendon": ("#7070b0", 0.6), "ligament": ("#4060d0", 0.6)}


def mcol(i):
    h = (zlib.crc32(i.encode()) % 1000) / 1000.0
    return colorsys.hsv_to_rgb(h, 0.85, 0.75)


def sections(B_or_dict, side, y, xwin, zwin, ax, label=True):
    from matplotlib.collections import LineCollection
    for i, m in B_or_dict.items():
        if not (i.endswith("_" + side) or "_" + side + "_" in i) and i != "skin":
            continue
        v = m["v"]
        if v[:, 1].min() > y or v[:, 1].max() < y:
            continue
        if m["cat"] == "skin" or i == "skin":
            continue
        L = R.section_lines(v, m["f"], y)
        if not len(L):
            continue
        spec = COL.get(m["cat"])
        if m["cat"] == "muscle":
            ax.add_collection(LineCollection(L, colors=[mcol(i)], linewidths=0.9))
            c = np.asarray(L).reshape(-1, 2).mean(0)
            if label and xwin[0] < c[0] < xwin[1] and zwin[0] < c[1] < zwin[1]:
                ax.text(c[0], c[1], i.replace("_" + side, "").replace("_zfill", "+")[:10], fontsize=4.5, color=mcol(i), ha="center")
        elif spec:
            ax.add_collection(LineCollection(L, colors=spec[0], linewidths=spec[1]))


def load_dir(d):
    from scripts.transfer.q200_bundle import Bundle
    B = Bundle(d)
    out = {}
    for it in B.items:
        e = it["e"]
        v, f = B.mesh(it)
        if len(f) and not e.get("hidden_default"):
            out[e["id"]] = dict(v=v, f=f, cat=e["cat"])
    return out


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out, levels, dirs = sys.argv[1], [int(x) for x in sys.argv[2].split(",")], sys.argv[3:]
    side = "l"
    Ms = [load_dir(d) for d in dirs]
    vol = np.load(PH.CRYO / "cryo_1mm.npy", mmap_mode="r")
    idx = json.loads((PH.CRYO / "cryo_index.json").read_text())
    inst = {r[1]: i for i, r in enumerate(idx)}
    reg = json.loads(PH.REG.read_text())["sides"]["left"]["levels"]
    fig, axs = plt.subplots(len(levels), len(Ms), figsize=(7.5 * len(Ms), 6.0 * len(levels)), squeeze=False)
    xwin, zwin = (-300, -130), (-70, 150)
    for r, y in enumerate(levels):
        k = int(round(PH.Y_OFF - y))
        X0, Y0 = reg[str(k)]["T"]
        im = np.asarray(vol[inst[k]])
        c_hi = min(int((X0 - (xwin[0] - 6.0)) / 0.99), im.shape[1] - 1)
        c_lo = max(int((X0 - (xwin[1] - 6.0)) / 0.99), 0)
        ext = [X0 - c_lo * 0.99 + 6.0, X0 - c_hi * 0.99 + 6.0, Y0 + im.shape[0] * 0.99 - 4.8, Y0 - 4.8]
        for c, M in enumerate(Ms):
            a = axs[r, c]
            a.imshow(im[:, c_lo:c_hi], extent=ext)
            sections(M, side, float(y), xwin, zwin, a)
            a.set_xlim(*xwin)
            a.set_ylim(*zwin)
            a.set_title(f"{Path(dirs[c]).name}  y={y}", fontsize=8)
    plt.tight_layout()
    plt.savefig(out, dpi=60)


if __name__ == "__main__":
    main()


def render_dicts(out, levels, dicts, titles, side="l", xwin=(-300, -130), zwin=(-70, 150), ncol=None, dpi=55):
    """sections of several {id: dict(v, f, cat)} sets over his photograph at each level (rows = levels, columns = sets)"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    vol = np.load(PH.CRYO / "cryo_1mm.npy", mmap_mode="r")
    idx = json.loads((PH.CRYO / "cryo_index.json").read_text())
    inst = {r[1]: i for i, r in enumerate(idx)}
    reg = json.loads(PH.REG.read_text())["sides"]["left"]["levels"]
    fig, axs = plt.subplots(len(levels), len(dicts), figsize=(6.0 * len(dicts), 5.0 * len(levels)), squeeze=False)
    for r, y in enumerate(levels):
        k = int(round(PH.Y_OFF - y))
        X0, Y0 = reg[str(k)]["T"]
        im = np.asarray(vol[inst[k]])
        c_hi = min(int((X0 - (xwin[0] - 6.0)) / 0.99), im.shape[1] - 1)
        c_lo = max(int((X0 - (xwin[1] - 6.0)) / 0.99), 0)
        ext = [X0 - c_lo * 0.99 + 6.0, X0 - c_hi * 0.99 + 6.0, Y0 + im.shape[0] * 0.99 - 4.8, Y0 - 4.8]
        for c, M in enumerate(dicts):
            a = axs[r, c]
            a.imshow(im[:, c_lo:c_hi], extent=ext)
            sections(M, side, float(y), xwin, zwin, a)
            a.set_xlim(*xwin)
            a.set_ylim(*zwin)
            a.set_title(f"{titles[c]}  y={y}", fontsize=8)
    plt.tight_layout()
    plt.savefig(out, dpi=dpi)
    plt.close(fig)
