"""Q191: hand / wrist renders, v7 (before) vs q191 (after) vs her own model: close-ups of both hands from the palmar, dorsal, radial and ulnar side
(layers: Z tissue + bones; Z bones over HER CT bones; Z skin over HER CT skin) and transverse cuts through the palm and the wrist / carpal tunnel.

    PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers python3 scripts/zanatomy/q191_compare_renders.py --before build/viewer_zan_female --after build/viewer_zan_female_q191 --out DIR
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q190_render as R  # noqa: E402
from scripts.zanatomy import q191_hand as H  # noqa: E402
from scripts.zanatomy import trunk_refit_q186c_audit as A186  # noqa: E402

COL = {"muscle": (0.78, 0.22, 0.20), "bone": (0.92, 0.90, 0.78), "nerve": (0.95, 0.80, 0.15), "vessel": (0.2, 0.35, 0.85), "fascia": (0.5, 0.65, 0.85),
       "joint": (0.75, 0.75, 0.78), "bursa": (0.9, 0.9, 0.55), "tendon": (0.9, 0.9, 0.55), "skin": (1.0, 0.55, 0.1), "ligament": (0.75, 0.75, 0.78)}
HER = {"bone": (0.25, 0.45, 0.9), "muscle": (0.2, 0.7, 0.35), "skin": (0.78, 0.78, 0.82)}


def hand_frame(M, side):
    ids = H.bone_ids(side)
    car = np.vstack([M[i]["v"] for i in ids["carpals"]]).mean(0)
    tips = np.vstack([M[i]["v"] for i in ids["phal"] if "distal" in i]).mean(0)
    mc5 = M[ids["mc"][4]]["v"].mean(0); mc2 = M[ids["mc"][1]]["v"].mean(0)
    axis = tips - car; axis /= np.linalg.norm(axis)
    radial = mc2 - mc5; radial -= axis * (radial @ axis); radial /= np.linalg.norm(radial)
    palm = np.cross(axis, radial)
    pc = np.vstack([M[k]["v"] for k in M if k.startswith("zan_skin_palm_") and k.endswith("_" + side)]).mean(0) if any(k.startswith("zan_skin_palm_") and k.endswith("_" + side) for k in M) else car
    if (pc - np.vstack([M[i]["v"] for i in ids["mc"]]).mean(0)) @ palm < 0:
        palm = -palm
    # radial: toward the thumb side (MC1 centroid)
    th = M[ids["mc"][0]]["v"].mean(0) - np.vstack([M[i]["v"] for i in ids["mc"][1:]]).mean(0)
    if th @ radial < 0:
        radial = -radial
    centre = 0.5 * (car + tips)
    return centre, axis, radial, palm


def cam(d):
    d = d / np.linalg.norm(d)
    return {"az": float(np.degrees(np.arctan2(d[0], d[2]))), "el": float(np.degrees(np.arcsin(np.clip(d[1], -1, 1))))}


def scope_ids(M, side, regions, centre, radius=125.0):
    pend = [{"mesh_id": k, "cat": m["sys"]} for k, m in M.items()]
    out = []
    for i in H.scope(pend, regions, side):
        if np.linalg.norm(M[i]["v"].mean(0) - centre) < radius * 1.4 and M[i]["sys"] != "skin":
            out.append(i)
    return out


LAYER_CATS = {"muscles_nerves_vessels": ("muscle", "nerve", "vessel"), "fascia_ligaments": ("fascia", "joint", "ligament", "bursa", "tendon")}


def tissue_scene(M, side, ids, hb, cats):
    sc = [{"v": M[i]["v"], "f": M[i]["f"], "color": COL.get(M[i]["sys"], (0.7, 0.7, 0.7))} for i in ids if M[i]["sys"] in cats and not (M[i]["sys"] == "muscle" and H.NOT_BODY.search(i))]
    sc += [{"v": M[i]["v"], "f": M[i]["f"], "color": COL["bone"]} for i in hb + [f"radius_{side}", f"ulna_{side}"]]
    return sc


def crop(v, f, c, r):
    m = np.linalg.norm(v - c, axis=1) < r
    return v, f[m[f].any(1)]


def run(before, after, out, size=(430, 430), half=80, labels=("v7", "q191"), sides="rl"):
    from PIL import Image, ImageDraw
    from scripts.transfer.zan_to_vhf_whole_body import load_her_meshes, DEFAULT_REPORT
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    her = load_her_meshes()
    regions = json.loads(DEFAULT_REPORT.read_text())["region_of_structure"]
    states = {labels[0]: A186.load_viewer(Path(before)), labels[1]: A186.load_viewer(Path(after))}
    sk = her["skin"]
    for side in sides:
        ids_b = H.bone_ids(side); hb = sum(ids_b.values(), [])
        centre, axis, radial, palm = hand_frame(states[labels[1]], side)
        sv, sf = crop(sk["v"].astype(np.float32), sk["f"], centre, 150)
        dirs = {"palmar": palm, "dorsal": -palm, "radial": radial, "ulnar": -radial}
        for layer in ("muscles_nerves_vessels", "fascia_ligaments", "bones_vs_her_ct", "skin_vs_her_ct"):
            rows = []
            for st, M in states.items():
                ids = scope_ids(M, side, regions, centre)
                sc_base = []
                if layer in LAYER_CATS:
                    sc = tissue_scene(M, side, ids, hb, LAYER_CATS[layer])
                elif layer == "bones_vs_her_ct":
                    sc = [{"v": M[i]["v"], "f": M[i]["f"], "color": COL["bone"]} for i in hb + [f"radius_{side}", f"ulna_{side}"]]
                    if side == "r":
                        sc += [{"v": her[k]["v"].astype(np.float32), "f": her[k]["f"], "color": HER["bone"]} for k in list(H.HER_BONES.values()) + list(H.HER_FOREARM_BONES)]
                else:
                    sc = [{"v": sv, "f": sf, "color": HER["skin"]}] + [{"v": M[i]["v"], "f": M[i]["f"], "color": COL["skin"]} for i in M if M[i]["sys"] == "skin" and i.endswith("_" + side)
                                                                       and H.SKIN_HAND.search(i)]
                views = [{"name": n, **cam(d), "target": centre, "half": half} for n, d in dirs.items()]
                R.render(sc, views, out, size=size, prefix=f"{side}_{layer}_{st}_")
                rows.append(st)
            im = Image.new("RGB", (4 * size[0], 2 * (size[1] + 18)), "white"); dr = ImageDraw.Draw(im)
            for r, st in enumerate(rows):
                for c_, n in enumerate(dirs):
                    im.paste(Image.open(out / f"{side}_{layer}_{st}_{n}.png").convert("RGB"), (c_ * size[0], r * (size[1] + 18) + 18))
                    dr.text((c_ * size[0] + 6, r * (size[1] + 18) + 3), f"{'right' if side == 'r' else 'left'} hand  {layer}  {st}  {n}", fill=(0, 0, 0))
            im.save(out / f"montage_{side}_{layer}.png")
    # transverse cuts: y levels through the palm and the wrist / carpal tunnel (the hands lie along y), plots
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    for side in sides:
        centre, *_ = hand_frame(states[labels[1]], side)
        levels = {"palm": float(np.median(np.vstack([states[labels[1]][i]["v"] for i in H.bone_ids(side)["mc"]])[:, 1])),
                  "carpal_tunnel": float(np.median(np.vstack([states[labels[1]][i]["v"] for i in H.bone_ids(side)["carpals"]])[:, 1]))}
        fig, ax = plt.subplots(2, 2, figsize=(14, 14))
        for r, (lv, y) in enumerate(levels.items()):
            for c_, (st, M) in enumerate(states.items()):
                a = ax[r, c_]
                for p in R.section_lines(sk["v"], sk["f"], y):
                    if np.linalg.norm(p.mean(0) - centre[[0, 2]]) < 120:
                        a.plot(p[:, 0], p[:, 1], "-", color="0.55", lw=0.7)
                for i, m in M.items():
                    if i.endswith("_" + side) and (H.scope([{"mesh_id": i, "cat": m["sys"]}], regions, side) or i in sum(H.bone_ids(side).values(), [])):
                        if np.linalg.norm(m["v"].mean(0) - centre) > 200:
                            continue
                        col = COL.get(m["sys"], (0.5, 0.5, 0.5))
                        for p in R.section_lines(m["v"], m["f"], y):
                            a.plot(p[:, 0], p[:, 1], "-", color=col, lw=1.0 if m["sys"] != "skin" else 0.8)
                if side == "r":
                    for k in list(H.HER_BONES.values()) + list(H.HER_FOREARM_BONES):
                        for p in R.section_lines(her[k]["v"], her[k]["f"], y):
                            a.plot(p[:, 0], p[:, 1], "--", color=HER["bone"], lw=1.2)
                a.set_aspect("equal"); a.set_xlim(centre[0] - 70, centre[0] + 70); a.set_ylim(centre[2] - 70, centre[2] + 70)
                a.set_title(f"{'right' if side == 'r' else 'left'} hand {lv} cut y={y:.0f} mm  {st}  (grey: her CT skin, blue dashed: her CT bones)")
        plt.tight_layout(); plt.savefig(out / f"cuts_{side}.png", dpi=55); plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default=str(REPO / "build" / "viewer_zan_female"))
    ap.add_argument("--after", default=str(REPO / "build" / "viewer_zan_female_q191"))
    ap.add_argument("--out", default=str(REPO / "build" / "viewer_zan_female_q191" / "renders"))
    a = ap.parse_args(argv)
    run(a.before, a.after, a.out)


if __name__ == "__main__":
    main()
