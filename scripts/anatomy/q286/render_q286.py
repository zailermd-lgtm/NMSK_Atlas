"""Q286 slice renders: the shipped structures' label contours on the body's own CT (one PNG per body).
    python3 scripts/anatomy/q286/render_q286.py vhm|vhf HEAD_CT TORSO_CT"""
import sys, json
from pathlib import Path
import numpy as np, nibabel as nib
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
REPO = Path(__file__).resolve().parents[3]; T = REPO / "data/ct_sources/task_outputs"
body, hct, tct = sys.argv[1:4]
HG = {int(k): v for k, v in json.loads((REPO / "mappings/totalsegmentator_head_glands_cavities_labels.json").read_text())["labels"].items()}
hrep = json.loads((REPO / f"data/derived/Q286_{body}_head_report.json").read_text())
srep = json.loads((REPO / f"data/derived/Q286_{body}_spine_report.json").read_text())
show = {"parotid_gland_right", "parotid_gland_left", "submandibular_gland_right", "submandibular_gland_left", "eye_lens_right", "eye_lens_left", "soft_palate",
        "eye_right", "eye_left"}
H = np.asarray(nib.load(hct).dataobj); S = np.asarray(nib.load(str(T / f"{body}_head_glands_cavities.nii.gz")).dataobj)
V = np.asarray(nib.load(tct).dataobj); D = np.asarray(nib.load(str(T / f"{body}_vertebrae_body.nii.gz")).dataobj)
fig, ax = plt.subplots(2, 3, figsize=(15, 10))
cols = plt.cm.tab10(np.linspace(0, 1, 10))
def panel(a, img, lab, ids, title, win=(-160, 240)):
    a.imshow(img.T, cmap="gray", vmin=win[0], vmax=win[1], origin="lower")
    for n, k in enumerate(ids):
        m = (lab == k).T
        if m.any(): a.contour(m, levels=[0.5], colors=[cols[n % 10]], linewidths=0.8)
    a.set_title(title, fontsize=9); a.axis("off")
inv = {v: k for k, v in HG.items()}
for j, cls in enumerate(["submandibular_gland_right", "parotid_gland_right", "eye_lens_right"]):
    z = int(np.argwhere(S == inv[cls])[:, 2].mean())
    ids = [inv[c] for c in show]
    panel(ax[0, j], H[:, :, z], S[:, :, z], ids, f"{body} head axial z{z} ({cls}; shipped: {', '.join(s for s in hrep['shipped'])[:60]})")
x = int(np.argwhere(S == inv["soft_palate"])[:, 0].mean())
panel(ax[1, 0], H[x, :, :], S[x, :, :], [inv["soft_palate"], inv["hard_palate"]], f"{body} head sagittal x{x} (soft / hard palate)")
xs = int(np.argwhere(D == 2)[:, 0].mean())
zz = np.argwhere(D == 2)[:, 2]; z0, z1 = max(zz.min() - 20, 0), min(zz.max() + 20, D.shape[2] - 1)
panel(ax[1, 1], V[xs, :, z0:z1], D[xs, :, z0:z1], [1, 2], f"{body} spine sagittal x{xs}: vertebral bodies + discs (TS vertebrae_body)", win=(-200, 1000))
cv = zz.max() - 60
panel(ax[1, 2], V[xs, :, cv:zz.max() + 10], D[xs, :, cv:zz.max() + 10], [1, 2], f"{body} cervical discs (shipped: {', '.join(srep['shipped']) or 'none'})", win=(-200, 1000))
fig.tight_layout(); out = T / f"{body}_q286_render.png"; fig.savefig(out, dpi=80); print(out)
