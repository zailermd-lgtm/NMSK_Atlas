#!/usr/bin/env python3
"""Q213: audit of the TARGET MUSCLES (the muscles that carry motor points) on the two FEMALE needle-layer pages.

Reads (never writes) the published geometry of
  own female   build/q212/viewer_f_hr + build/viewer_f_hr_q212/bundle.bin       (key vhf)
  Z female fit build/q211/viewer_zan_female                                      (key zan_f)
  Z base fem.  build/q202/viewer_base_female   (the unfitted Z source, volume reference)
  own male     build/q212/viewer_m_hr + build/viewer_m_hr_q212/bundle.bin       (carry-over reference)
and the Q204 per-structure rows (inside bone / outside skin / defects) of the same pages.
Writes data/derived/Q213_target_muscle_audit.json.

    python3 scripts/clinical/q213_audit.py [--out PATH]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parent))
import motor_points_q187 as M  # noqa: E402

REPO = M.REPO
PAGES = {
    "vhf": dict(html=REPO / "build/q212/viewer_f_hr/atlas_viewer_female.html", bin=REPO / "build/viewer_f_hr_q212/bundle.bin",
                rows=REPO / "build/q212_raw/Q204_regions_own_f.json"),
    "zan_f": dict(html=REPO / "build/q211/viewer_zan_female/atlas_viewer_zan_female.html", rows=REPO / "build/q211_raw/Q204_regions_q211_f.json"),
    "zbase_f": dict(html=REPO / "build/q202/viewer_base_female/atlas_viewer_base_female.html"),
    "vhm": dict(html=REPO / "build/q212/viewer_m_hr/atlas_viewer_male.html", bin=REPO / "build/viewer_m_hr_q212/bundle.bin"),
}
# the corrected pages (Q213): only used by the render / after-audit, not by main()
PAGES_AFTER = {
    "vhf_q213": dict(html=REPO / "build/q213/viewer_f_hr/atlas_viewer_female.html", bin=REPO / "build/viewer_f_hr_q213/bundle.bin"),
    "zan_f_q213": dict(html=REPO / "build/q213/viewer_zan_female/atlas_viewer_zan_female.html"),
}
VOX = 4.0


def load(key):
    """Meshes grouped per id (the motor-point loader) plus the per-id metadata."""
    p = PAGES.get(key) or PAGES_AFTER[key]
    kind = "own" if "bin" in p else "zan"
    M.VIEWERS["_q213"] = {"kind": kind, "html": p["html"], **({"bin": p["bin"]} if "bin" in p else {}), "label": key}
    meshes = M.load_viewer("_q213")
    meta = {}
    if kind == "own":
        h = Path(p["html"]).read_text(encoding="utf-8")
        b = json.loads(re.search(r'<script id="bundle-json" type="application/json">(.*?)</script>', h, re.S).group(1))
        for e in b["structures"]:
            meta.setdefault(e["id"], {"subject": e.get("subject"), "side": e.get("side"), "name": e["rec"].get("name")})
    return meshes, meta


def vol_cm3(V, F):
    """|signed volume| (cm3); the face winding of some pages is inverted, open meshes are approximate."""
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    return abs(float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0 / 1000.0))


def pieces(meshes, mu, s, own):
    """Ids of one muscle-side: the measured/base mesh plus its badged Z-fill continuations (own pages)."""
    if own:
        pat = re.compile(re.escape(f"{mu}_{s}") + r"(_zfill\w*)?")
    else:
        pat = re.compile(re.escape(f"{mu}_{s}"))
    return [k for k in meshes if pat.fullmatch(k) and meshes[k]["cat"] == "muscle"]


def grid_inside(ids, meshes, box=None, vox=VOX):
    V = np.vstack([meshes[i]["v"] for i in ids])
    lo, hi = (V.min(0), V.max(0)) if box is None else box
    g = [np.arange(lo[k], hi[k] + vox, vox) for k in range(3)]
    G = np.stack(np.meshgrid(*g, indexing="ij"), -1).reshape(-1, 3)
    ins = np.zeros(len(G), bool)
    for i in ids:
        v, f = meshes[i]["v"], meshes[i]["f"]
        sel = np.all((G >= v.min(0) - 1) & (G <= v.max(0) + 1), axis=1)
        if sel.any():
            ins[sel] |= trimesh.Trimesh(v, f, process=False).contains(G[sel])
    return G, ins


def iou(idsA, mA, idsB, mB):
    VA = np.vstack([mA[i]["v"] for i in idsA]); VB = np.vstack([mB[i]["v"] for i in idsB])
    lo = np.minimum(VA.min(0), VB.min(0)); hi = np.maximum(VA.max(0), VB.max(0))
    if np.prod((hi - lo) / VOX) > 4e6:
        return None
    G, a = grid_inside(idsA, mA, (lo, hi)); _, b = grid_inside(idsB, mB, (lo, hi))
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else None


def axis_len(V):
    c = V.mean(0)
    u = np.linalg.svd(V - c, full_matrices=False)[2][0]
    t = (V - c) @ u
    return float(np.percentile(t, 99) - np.percentile(t, 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "data/derived/Q213_target_muscle_audit.json"))
    a = ap.parse_args()
    data = {k: load(k) for k in PAGES}
    rows = {k: {r["id"]: r for r in json.loads(Path(PAGES[k]["rows"]).read_text())["rows"]} for k in ("vhf", "zan_f")}
    targets = sorted({r["muscle"] for r in M.RULES} | set(M.NOT_COVERED_REASON))
    out = {}
    for mu in targets:
        for s in "rl":
            e = {"muscle": mu, "side": s}
            ids = {}
            for k in PAGES:
                meshes = data[k][0]
                own = "bin" in PAGES[k]
                ids[k] = pieces(meshes, mu, s, own)
            # Z parts (deltoid, triceps, pectoralis major, psoas/iliacus, palmaris, tibialis posterior, splenius cervicis)
            zp = {"deltoid": [f"zan_{x}_part_of_deltoid_muscle_{s}" for x in ("clavicular", "acromial", "scapular_spinal")],
                  "triceps_brachii": [f"zan_{x}_head_of_triceps_brachii_{s}" for x in ("long", "medial", "lateral")],
                  "pectoralis_major": [f"zan_{x}_of_pectoralis_major_muscle_{s}" for x in ("clavicular_head", "sternocostal_head", "abdominal_part")],
                  "iliopsoas": [f"zan_psoas_major_{s}", f"zan_iliacus_muscle_{s}"],
                  "palmaris_longus": [f"zan_palmaris_longus_muscle_{s}"],
                  "tibialis_posterior": [f"zan_tibialis_posterior_muscle_{s}"],
                  "splenius_cervicis": [f"zan_splenius_colli_muscle_{s}"]}.get(mu)
            if zp:
                for k in ("zan_f", "zbase_f"):
                    ids[k] = [i for i in zp if i in data[k][0]]
                if mu == "palmaris_longus":
                    ids["vhf"] = [i for i in zp if i in data["vhf"][0]]
            e["ids"] = ids
            vols = {k: round(sum(vol_cm3(data[k][0][i]["v"], data[k][0][i]["f"]) for i in ids[k]), 1) if ids[k] else None for k in PAGES}
            e["vol_cm3"] = vols
            # voxel-union volume (parity inside test, 4 mm grid): robust to inverted windings / overlapping Z-fill pieces
            e["vox_cm3"] = {}
            for k in PAGES:
                if ids[k]:
                    _, ins = grid_inside(ids[k], data[k][0])
                    e["vox_cm3"][k] = round(float(ins.sum()) * VOX ** 3 / 1000.0, 1)
                else:
                    e["vox_cm3"][k] = None
            e["centroid"] = {k: [round(float(x), 1) for x in np.vstack([data[k][0][i]["v"] for i in ids[k]]).mean(0)] if ids[k] else None for k in PAGES}
            e["length_mm"] = {k: round(axis_len(np.vstack([data[k][0][i]["v"] for i in ids[k]])), 1) if ids[k] else None for k in PAGES}
            if ids["vhf"]:
                b = ids["vhf"][0]
                e["own_base_piece"] = b
                e["own_subject"] = data["vhf"][1].get(b, {}).get("subject")
                r = rows["vhf"].get(b, {})
                e["own_cls"] = r.get("cls")
                e["own_q204"] = {kk: r.get(kk) for kk in ("inside_bone_pct", "outside_skin_pct", "overlap_pct", "islands", "flat_caps")}
                e["own_defects"] = [(d["check"], d["severity"], d.get("detail")) for d in r.get("defects", []) if d["severity"] >= 2]
                e["own_zfill_pieces"] = ids["vhf"][1:]
            if ids["zan_f"]:
                r = rows["zan_f"].get(ids["zan_f"][0], {})
                e["zfit_q204"] = {kk: r.get(kk) for kk in ("inside_bone_pct", "outside_skin_pct", "overlap_pct", "islands", "flat_caps")}
                e["zfit_defects"] = [(d["check"], d["severity"], d.get("detail")) for d in r.get("defects", []) if d["severity"] >= 2]
            if ids["vhf"] and ids["zan_f"]:
                c1, c2 = np.array(e["centroid"]["vhf"]), np.array(e["centroid"]["zan_f"])
                e["own_vs_zfit_centroid_mm"] = round(float(np.linalg.norm(c1 - c2)), 1)
                e["own_vs_zfit_iou"] = None if (iou(ids["vhf"], data["vhf"][0], ids["zan_f"], data["zan_f"][0]) is None) else round(iou(ids["vhf"], data["vhf"][0], ids["zan_f"], data["zan_f"][0]), 3)
            out[f"{mu}_{s}"] = e
            print(mu, s, vols, e.get("own_cls"), e.get("own_vs_zfit_centroid_mm"), e.get("own_vs_zfit_iou"), flush=True)
    Path(a.out).write_text(json.dumps(out, indent=1, default=str) + "\n")
    print("wrote", a.out)


if __name__ == "__main__":
    main()
