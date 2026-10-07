#!/usr/bin/env python3
"""Q198 elbow close-ups (READ-ONLY): anterior / posterior / medial / lateral surface views (WebGL, headless Chromium swiftshader) + sagittal and coronal cut
sections (matplotlib) of the elbow of both arms of one model, bones visible.   python3 scripts/zanatomy/q198_renders.py MODEL [--highlight]
Outputs build/q198_renders/<model>/elbow_<side>_<view>[_hl].png"""
from __future__ import annotations
import argparse, json, re, sys, zlib
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))
from scripts.zanatomy.q198_load import load, MODELS  # noqa: E402
from scripts.zanatomy import q190_render as R  # noqa: E402

OUT = REPO / "build" / "q198_renders"
DER = REPO / "data" / "derived"
SOFT = {"muscle", "joint", "insertion", "tendon", "ligament", "cartilage"}


def color_of(s, hl=None):
    i = s["id"]
    if hl and i in hl:
        return hl[i]
    h = (zlib.crc32(i.encode()) % 1000) / 1000.0
    if s["sys"] == "bone":
        return (0.93, 0.91, 0.80)
    if s["sys"] == "muscle":
        return (0.62 + 0.25 * h, 0.16 + 0.12 * h, 0.14 + 0.10 * h)
    if s["sys"] == "vessel":
        return (0.15, 0.30, 0.90) if ("vein" in i or "_v_" in i or i.endswith("_v") or "veins" in i) else (0.92, 0.10, 0.10)
    if s["sys"] == "nerve":
        return (0.97, 0.85, 0.10)
    if s["sys"] == "cartilage":
        return (0.55, 0.78, 0.95)
    return (0.90, 0.78, 0.55)


def elbow_json(model, side):
    r = json.loads((DER / f"Q198_model_{model}.json").read_text())
    for j in r["junctions"]:
        if j["name"] == "elbow" and j["side"] == side:
            return j
    return None


def frame(j, side):
    c = np.asarray(j["centre_mm"], float)
    ea = j.get("elbow_angles") or {}
    h = np.asarray(ea.get("humerus_axis", j["axis"]), float); f = np.asarray(ea.get("forearm_axis", j["axis"]), float); e = np.asarray(ea.get("epicondylar_axis", [1, 0, 0]), float)
    return c, h, f, e


def region_scene(S, side, c, r=135, hl=None, sysset=None, bones_only_side=True):
    from scipy.spatial import cKDTree
    from scripts.zanatomy.q198_core import surf_points
    arm = [s for s in S if s["sys"] == "bone" and s["side"] == side and re.match(rf"^(humerus|radius|ulna)_{side}", s["id"])]
    ap = np.concatenate([surf_points(b["v"], b["f"], 3.0, cap=8000) for b in arm]) if arm else None
    atree = cKDTree(ap) if ap is not None else None
    sc = []
    for s in S:
        if s["sys"] == "skin" or s["id"] == "skin":
            continue
        if s["sys"] not in ({"bone", "vessel", "nerve"} | SOFT):
            continue
        if s["side"] not in (side,):
            continue
        v, f = s["v"], s["f"]
        if len(f) == 0 or np.linalg.norm(v - c, axis=1).min() > r:
            continue
        cen = v[f].mean(1)
        keep = np.linalg.norm(cen - c, axis=1) < r
        if atree is not None and s["sys"] != "bone":
            keep &= atree.query(cen)[0] < 62               # arm tissue only: faces within 62 mm of the humerus / radius / ulna (drops the trunk wall)
        if keep.sum() < 2:
            continue
        sc.append({"v": v, "f": f[keep], "color": color_of(s, hl)})
    return sc


def surface_views(model, side, S, j, hl=None, tag=""):
    c, h, f, e = frame(j, side)
    sc = region_scene(S, side, c, hl=hl)
    lat_az = 270 if side == "l" else 90
    views = [dict(name=f"elbow_{side}_anterior{tag}", az=0, el=0, target=c, half=95),
             dict(name=f"elbow_{side}_posterior{tag}", az=180, el=0, target=c, half=95),
             dict(name=f"elbow_{side}_lateral{tag}", az=lat_az, el=0, target=c, half=95),
             dict(name=f"elbow_{side}_medial{tag}", az=(lat_az + 180) % 360, el=0, target=c, half=95)]
    R.render(sc, views, OUT / model, size=(520, 520))


def section_view(model, side, S, j, plane, hl=None, tag=""):
    import trimesh
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    c, h, f, e = frame(j, side)
    hb = h / np.linalg.norm(h) + f / np.linalg.norm(f)
    hb = hb - np.dot(hb, e) * e; hb /= np.linalg.norm(hb)            # mean limb direction (shoulder -> wrist), perpendicular to the epicondylar axis
    n = np.cross(e, hb); n /= np.linalg.norm(n)
    if n[2] < 0:
        n = -n                                                       # anterior-ish
    if plane == "sagittal":
        normal, ua, va = e, n, -hb                                   # image x = anterior, y = up (towards the shoulder)
    else:
        normal, ua, va = n, np.array([-1.0, 0, 0]), -hb              # image x = patient's left (viewer sees from the front)
        ua = ua - np.dot(ua, normal) * normal; ua /= np.linalg.norm(ua)
    va = va - np.dot(va, ua) * ua; va /= np.linalg.norm(va)
    fig, ax = plt.subplots(figsize=(5.2, 5.2), dpi=100)
    zr = 110
    order = {"muscle": 1, "joint": 1, "insertion": 1, "tendon": 1, "cartilage": 2, "vessel": 3, "nerve": 3, "bone": 4}
    for s in sorted([x for x in S if x["sys"] in order and x["side"] in (side,)], key=lambda x: order[x["sys"]]):
        v, f_ = s["v"], s["f"]
        if np.linalg.norm(v - c, axis=1).min() > zr * 1.6:
            continue
        seg = trimesh.intersections.mesh_plane(trimesh.Trimesh(v, f_, process=False), normal, c, return_faces=False)
        if len(seg) == 0:
            continue
        col = color_of(s, hl)
        P = np.stack([((seg - c) @ ua), ((seg - c) @ va)], axis=-1)
        from matplotlib.collections import LineCollection
        lw = 1.6 if s["sys"] == "bone" else 0.9
        ax.add_collection(LineCollection(P, colors=[col], linewidths=lw))
    # skin outline
    sk = [x for x in S if x["sys"] == "skin" or x["id"] == "skin"]
    for s in sk:
        if np.linalg.norm(s["v"] - c, axis=1).min() > 160:
            continue
        seg = trimesh.intersections.mesh_plane(trimesh.Trimesh(s["v"], s["f"], process=False), normal, c, return_faces=False)
        if len(seg):
            P = np.stack([((seg - c) @ ua), ((seg - c) @ va)], axis=-1)
            from matplotlib.collections import LineCollection
            ax.add_collection(LineCollection(P, colors=[(0, 0, 0)], linewidths=0.6))
    ax.set_xlim(-zr, zr); ax.set_ylim(-zr, zr); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title(f"{plane} cut" + ("  (x: anterior ->, y: up)" if plane == "sagittal" else "  (x: patient left ->, y: up)"), fontsize=7)
    (OUT / model).mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / model / f"elbow_{side}_{plane}{tag}.png", bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("model"); ap.add_argument("--highlight", action="store_true")
    a = ap.parse_args()
    S = load(a.model)
    hl = None
    if a.highlight and (DER / "Q198_anatomy_audit.json").exists():
        aud = json.loads((DER / "Q198_anatomy_audit.json").read_text())
        hl = {}
        for d in aud["models"][a.model]["defects"]:
            if d.get("region") == "elbow" and d.get("structure") and d["severity"] >= 2:
                hl[d["structure"]] = (1.0, 0.0, 0.85) if d["severity"] == 3 else (1.0, 0.55, 0.0)
    for side in ("l", "r"):
        j = elbow_json(a.model, side)
        if j is None:
            print(a.model, side, "no elbow junction (bones absent)")
            # still draw what exists around the expected position: skip
            continue
        tag = "_hl" if a.highlight else ""
        surface_views(a.model, side, S, j, hl, tag)
        for pl in ("sagittal", "coronal"):
            section_view(a.model, side, S, j, pl, hl, tag)
        print(a.model, side, "rendered", flush=True)


if __name__ == "__main__":
    main()
