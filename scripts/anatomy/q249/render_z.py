#!/usr/bin/env python3
"""Q249: painter's-algorithm renders (matplotlib, no GL) of the pelvic nerves of a Z-family page (the Z viewer is a raw WebGL page without three.js): posterior, right-sagittal and inferior views with the pelvic bones,
the pudendal / gluteal / rectal vessels, the page's own nerves (grey) and the new rule-based nerves (colours as render_check.py).
    python3 scripts/anatomy/q249/render_z.py KEY PAGE_DIR OUT_PREFIX          KEY = comb_f comb_m base_f base_m (also works for the own pages)"""
from __future__ import annotations
import json, os, re, sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts/anatomy/q248"))
key, page_dir, prefix = sys.argv[1:4]
os.environ["Q248_SRC_" + key] = str(REPO / page_dir)
import lig_pages as PG  # noqa: E402
E = PG.load(key)
new = set(json.loads((REPO / f"data/derived/Q249_shipped_{key}.json").read_text()))
L = json.loads((REPO / f"data/derived/Q249_rule_{key}.json").read_text())["landmarks"]
xm = json.loads((REPO / f"data/derived/Q249_rule_{key}.json").read_text())["frame"]["x_mid"]
c = np.array([0.5 * (L["IS_l"][0] + L["IS_r"][0]), 0.5 * (L["IS_r"][1] + L["promontory"][1]) - 10, 0.5 * (L["IS_r"][2] + L["promontory"][2])])


def grp(i):
    if re.match(r"s[1-4]_ventral_ramus|lumbosacral_trunk", i): return "#d62828"
    if re.match(r"(pudendal_n|inferior_rectal_n|perineal_n|dorsal_n_)", i): return "#ff8c00"
    if re.match(r"(inferior_gluteal|nerve_to_obturator|nerve_to_quadratus|posterior_femoral)", i): return "#e0b800"
    if re.match(r"(nerve_to_levator|nerve_to_coccygeus|coccygeal_plexus|anococcygeal)", i): return "#1f9d8f"
    if re.search(r"hypogastric|splanchnic", i): return "#8e44ad"
    if re.search(r"medial_branch|dorsal_ramus", i): return "#0077cc"
    if re.match(r"(iliohypogastric|ilioinguinal|genitofemoral)", i): return "#5aa000"
    return "#ff00ff"


items = []   # (id, v, f, color, alpha, kind)
for i, e in E.items():
    b = i.split("#")[0]
    if i in new: items.append((i, e["v"], e["f"], grp(i), 1.0, "nerve"))
    elif e["sys"] == "bone" and (b in ("hip_bone_l", "hip_bone_r", "sacrum", "coccyx", "sacrum#1", "sacrum#2") or i.startswith("sacrum")) and "zfill" not in i: items.append((i, e["v"], e["f"], "#d8d2c0", 0.55, "bone"))
    elif e["sys"] == "vessel" and re.search(r"(internal_pudendal|inferior_rectal|inferior_gluteal)", b): items.append((i, e["v"], e["f"], "#a00020" if re.search(r"artery|_a_|_a$", b) else "#2050c0", 0.8, "vessel"))
    elif e["sys"] == "nerve" and re.match(r"(zan_)?(pudendal_n|nerve_to_quadratus_femoris|posterior_femoral_cutaneous_n)", b): items.append((i, e["v"], e["f"], "#999999", 0.7, "nerve0"))


def proj(v, view):
    if view == "posterior": return np.c_[v[:, 0], v[:, 1]], -v[:, 2]                     # viewer behind: far = anterior (larger z) drawn first
    if view == "sagittal": return np.c_[-v[:, 2], v[:, 1]], v[:, 0]                      # viewer on the right: anterior to the left, near = larger x
    return np.c_[v[:, 0], v[:, 2]], -v[:, 1]                                             # inferior view: near = lowest y


vd = {"posterior": np.array([0, 0, -1.0]), "sagittal": np.array([1.0, 0, 0]), "inferior": np.array([0, -1.0, 0])}
for view in ("posterior", "sagittal", "inferior"):
    polys, depth, col, alp = [], [], [], []
    for i, v, f, color, al, kind in items:
        if view == "sagittal" and i.endswith("_l") and kind != "bone": continue
        if view == "sagittal" and kind == "bone" and re.search(r"_l$", i): continue
        if kind in ("bone", "vessel") and view != "inferior" and False: continue
        if len(f) > 3000 and kind == "bone": f = f[::2]
        p, d = proj(v, view); tri = v[f]
        n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-9
        sh = 0.45 + 0.55 * np.abs(n @ vd[view])
        base = np.array(matplotlib.colors.to_rgb(color))
        polys.append(p[f]); depth.append(d[f].mean(1)); col.append(np.c_[base[None] * sh[:, None], np.full(len(f), al)])
    polys = np.concatenate(polys); depth = np.concatenate(depth); col = np.concatenate(col)
    o = np.argsort(depth)
    fig, ax = plt.subplots(figsize=(8, 9), dpi=110)
    ax.add_collection(PolyCollection(polys[o], facecolors=col[o], edgecolors="none", linewidths=0))
    cx, cy = (c[0], c[1]) if view == "posterior" else ((-c[2] - 10, c[1]) if view == "sagittal" else (c[0], c[2]))
    h = 150 if view != "inferior" else 130
    ax.set_xlim(cx - h * 0.85, cx + h * 0.85); ax.set_ylim(cy - h, cy + h) if view != "inferior" else ax.set_ylim(cy - h, cy + h)
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_title(f"{key}: pelvic nerves, {view} view (rule-based; bones grey-beige, vessels red / blue, Z page nerves grey)", fontsize=8)
    fig.savefig(f"{prefix}_{view}.png", bbox_inches="tight"); plt.close(fig)
print("rendered", prefix, "items", len(items))
