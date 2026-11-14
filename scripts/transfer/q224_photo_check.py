#!/usr/bin/env python3
"""Q224: his 1 mm cryosection photographs under the bridge of the right femoral vein (the 62 mm gap y -98 .. -36): axial sections of the Q224 vein mesh drawn on the registered photographs every 6 mm
(scripts/transfer/q224_photo.py: Q174 / Q173 mapping, evidence check only).  -> data/derived/Q224_photo_check_femoral_v_r.png (+ build/q224_renders/)."""
import sys
from pathlib import Path

import numpy as np
import trimesh
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer import q224_photo as PH  # noqa: E402
from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.transfer.q224_common import BODIES  # noqa: E402

bdir = sys.argv[1] if len(sys.argv) > 1 else str(BODIES["m"]["out_bundle"])
g = Bundle(bdir).get("femoral_v_r")
tm = trimesh.Trimesh(g["v"], g["f"], process=False)
ph = PH.Photos()
ys = [-34, -40, -46, -52, -58, -64, -70, -76, -82, -88, -94, -100]
fig, axs = plt.subplots(3, 4, figsize=(16, 12))
for ax, y in zip(axs.ravel(), ys):
    sec = tm.section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0])
    pl = [np.asarray(p) for p in sec.discrete] if sec is not None else []
    cx = float(np.mean([p[:, 0].mean() for p in pl])) if pl else 70.0
    cz = float(np.mean([p[:, 2].mean() for p in pl])) if pl else 45.0
    im, off = ph.crop(y, "right", (cx, cz), half=40)
    ax.imshow(im)
    ax.set_title(f"y={y} mm" + ("  (measured stump)" if y in (-34, -100) else "  (rule-based bridge)"))
    for p in pl:
        r, c = PH.Photos.to_px(np.column_stack([p[:, 0], np.full(len(p), y), p[:, 2]]), "right")
        ax.plot(c - off[1], r - off[0], "-", color="lime", lw=1.5)
    ax.axis("off")
fig.suptitle("Own male: right femoral vein (green outline = Q224 mesh) on HIS 1 mm cryosection photographs, 40 mm window; the stump sections (y -34, -100) sit on the clotted vessel, the bridge between them is rule-based", fontsize=11)
plt.tight_layout()
out = REPO / "build/q224_renders"
out.mkdir(parents=True, exist_ok=True)
plt.savefig(out / "photo_check_femoral_v_r.png", dpi=70)
plt.savefig(REPO / "data/derived/Q224_photo_check_femoral_v_r.png", dpi=55)
print("done")
