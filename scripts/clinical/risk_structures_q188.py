#!/usr/bin/env python3
"""Q188 -- risk-structure classes and calibres for the PRIVATE needle-planning add-on.

Writes clinical/data/risk_<viewer>.json (viewer = vhm, vhf, zan_m, zan_f): for every
structure the add-on treats as a risk structure (artery, vein, nerve, pleura/lung,
other organ), its class and an approximate calibre RADIUS in mm. The file holds
measurements only -- no geometry -- and is published next to the viewer as
clinical_risk.json by scripts/clinical/stage_clinical_files.py.

Classification: the table lives in clinical/needle_tool.js between the
/*RISK_TABLE_BEGIN*/ and /*RISK_TABLE_END*/ markers (strict JSON) and is parsed here,
so the browser and this script can never disagree. First matching rule wins.

Calibre method (shape-diameter function): every risk structure's viewing mesh
(all meshes sharing its atlas id, merged) is loaded with trimesh; up to 300
vertices, evenly spread over the vertex list, each cast one ray from just inside
the surface along the INWARD vertex normal (inward = against the outward normal
given by the sign of the mesh's signed volume) to the opposite wall. The median
wall-to-wall distance is the local diameter; the radius is half of it, capped at
half the smallest bounding-box extent. With fewer than 8 rays hitting (open or
degenerate meshes) the radius falls back to |2V/A| (exact for a long cylinder),
then to half the smallest bounding-box extent. Values are approximate (decimated
viewing meshes) and are used only as the calibre term of the heuristic halo.

Usage:
    python3 scripts/clinical/risk_structures_q188.py --viewer all
    python3 scripts/clinical/risk_structures_q188.py --viewer vhm --out-dir clinical/data
"""
from __future__ import annotations

import argparse
import base64
import datetime as _dt
import json
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
MODULE = REPO / "clinical" / "needle_tool.js"
VIEWERS = {
    "vhm": {"kind": "bundle", "dir": REPO / "build" / "viewer_m_hr"},
    "vhf": {"kind": "bundle", "dir": REPO / "build" / "viewer_f_hr"},
    "zan_m": {"kind": "zan", "html": REPO / "build" / "viewer_zan_atlas" / "atlas_viewer_zan_atlas.html"},
    "zan_f": {"kind": "zan", "html": REPO / "build" / "viewer_zan_female" / "atlas_viewer_zan_female.html"},
}
LICENCE = ("PRIVATE -- owner's clinical layer (see clinical/LICENSE_PRIVATE.md). Not CC BY-SA, not for "
           "redistribution. Holds measurements about the anatomy model, not the model.")
METHOD = ("Class: rule table in clinical/needle_tool.js (RISK_TABLE). r_mm: shape-diameter function -- median "
          "wall-to-wall distance along the inward vertex normal over <=300 vertices, halved, capped at half the "
          "smallest bounding-box extent; fallback |2V/A|, then half the smallest extent. Decimated viewing meshes: "
          "approximate, for the calibre term of a heuristic halo only.")


# ---------------------------------------------------------------- classification
def load_risk_table(module_path: Path = MODULE) -> dict:
    txt = module_path.read_text(encoding="utf-8")
    m = re.search(r"/\*RISK_TABLE_BEGIN\*/(.*?)/\*RISK_TABLE_END\*/", txt, re.S)
    if not m:
        raise ValueError(f"no RISK_TABLE markers in {module_path}")
    table = json.loads(m.group(1))
    for r in table["rules"]:
        r["_re"] = re.compile(r["re"]) if r.get("re") else None
    return table


def classify(rec: dict, table: dict) -> str | None:
    """Same rule semantics as classify() in clinical/needle_tool.js."""
    txt = f"{rec.get('name') or ''} {rec.get('id') or ''}".lower()
    for r in table["rules"]:
        if rec.get("cat") not in r["cats"]:
            continue
        if r.get("vt") and rec.get("vt") != r["vt"]:
            continue
        if r["_re"] is not None and not r["_re"].search(txt):
            continue
        return r["cls"]
    return None


# ---------------------------------------------------------------- loading geometry
def load_bundle(d: Path):
    """Specimen viewer bundle: bundle.json + bundle.bin (int16 xyz * quantum, uint16 faces per structure)."""
    meta = json.loads((d / "bundle.json").read_text(encoding="utf-8"))
    raw = (d / "bundle.bin").read_bytes()
    q, off, out = meta["quantum_mm"], 0, []
    for s in meta["structures"]:
        nv, nf = s["nv"], s["nf"]
        pos = np.frombuffer(raw, dtype="<i2", count=nv * 3, offset=off).reshape(-1, 3).astype(np.float64) * q
        off += nv * 6
        idx = np.frombuffer(raw, dtype="<u2", count=nf * 3, offset=off).reshape(-1, 3).astype(np.int64)
        off += nf * 6
        rec = s.get("rec") or {}
        out.append({"id": s["id"], "name": rec.get("name") or s["id"], "cat": s["cat"], "vt": None, "pos": pos, "idx": idx})
    return out, meta.get("frame", "atlas mm")


def _js_value(html: str, name: str):
    i = html.index(name) + len(name)
    j = html.index(";\n", i)
    return json.loads(html[i:j])


def load_zan(html_path: Path):
    """Z-Anatomy viewer page: manifest + sibling base64 geometry files (uint16 quantised per mesh box)."""
    html = html_path.read_text(encoding="utf-8")
    man = _js_value(html, "window.__ANATOMY_MANIFEST__=")
    files = _js_value(html, "window.__ANATOMY_BIN_FILES__=")
    if files:
        parts = []
        for f in files:
            data = (html_path.parent / f["path"]).read_bytes()
            parts.append(base64.b64decode(data.strip()) if f.get("enc") == "base64" else data)
        BIN = b"".join(parts)
    else:
        i = html.index('window.__ANATOMY_BIN__="') + len('window.__ANATOMY_BIN__="')
        BIN = base64.b64decode(html[i:html.index('"', i)])
    out = []
    for r in man["meshes"]:
        vc, ic = r["vc"], r["ic"]
        qv = np.frombuffer(BIN, dtype="<u2", count=vc * 3, offset=r["vo"]).reshape(-1, 3).astype(np.float64)
        pos = np.asarray(r["min"]) + qv / 65535.0 * np.asarray(r["span"])
        idx = np.frombuffer(BIN, dtype="<u2", count=ic * 3, offset=r["io"]).reshape(-1, 3).astype(np.int64)
        out.append({"id": r.get("id") or r["name"], "name": r["name"], "cat": r.get("sys") or "bone", "vt": r.get("vt"),
                    "pos": pos, "idx": idx})
    return out, "Z-Anatomy model frame (mm, +Y superior)"


# ---------------------------------------------------------------- calibre
def calibre_radius(pos: np.ndarray, idx: np.ndarray, n_rays: int = 300) -> tuple[float, str, int]:
    import trimesh
    ext = pos.max(0) - pos.min(0)
    cap = float(max(ext.min(), 1e-3) / 2)
    if len(idx) == 0 or len(pos) < 4:
        return cap, "bbox", 0
    mesh = trimesh.Trimesh(vertices=pos, faces=idx, process=False)
    vol = float(mesh.volume) if len(idx) else 0.0
    sign = -1.0 if vol < 0 else 1.0
    vn = np.asarray(mesh.vertex_normals) * sign          # outward
    pick = np.unique(np.linspace(0, len(pos) - 1, min(n_rays, len(pos))).astype(int))
    ok = np.linalg.norm(vn[pick], axis=1) > 0.5
    pick = pick[ok]
    hits = 0
    if len(pick):
        d = -vn[pick]
        o = pos[pick] + d * 1e-3
        try:
            loc, ray_i, _ = mesh.ray.intersects_location(o, d, multiple_hits=False)
        except Exception:
            loc, ray_i = np.zeros((0, 3)), np.zeros(0, int)
        if len(ray_i):
            dd = np.linalg.norm(loc - o[ray_i], axis=1)
            dd = dd[dd > 0.05]
            hits = len(dd)
            if hits >= 8:
                return float(min(np.median(dd) / 2, cap)), "sdf", hits
    area = float(mesh.area)
    if area > 0 and abs(vol) > 0:
        return float(min(abs(2 * vol / area), cap)), "2V/A", hits
    return cap, "bbox", hits


# ---------------------------------------------------------------- main
def build(viewer: str, table: dict | None = None, source: Path | None = None) -> dict:
    table = table or load_risk_table()
    cfg = dict(VIEWERS[viewer])
    if source:                                   # another build of the same viewer (bundle dir or Z-Anatomy page)
        cfg["dir" if cfg["kind"] == "bundle" else "html"] = Path(source)
    structs, frame = load_bundle(cfg["dir"]) if cfg["kind"] == "bundle" else load_zan(cfg["html"])
    halo = {k for k, v in table["classes"].items() if v.get("halo")}
    groups: dict[str, dict] = {}
    for s in structs:
        c = classify(s, table)
        if c not in halo:
            continue
        g = groups.setdefault(s["id"], {"id": s["id"], "name": s["name"], "class": c, "pos": [], "idx": [], "n": 0})
        g["idx"].append(s["idx"] + g["n"])
        g["pos"].append(s["pos"])
        g["n"] += len(s["pos"])
    rows, counts = [], {}
    for g in sorted(groups.values(), key=lambda x: x["id"]):
        pos, idx = np.vstack(g["pos"]), np.vstack(g["idx"])
        r, how, hits = calibre_radius(pos, idx)
        rows.append({"id": g["id"], "name": g["name"], "class": g["class"], "r_mm": round(r, 2), "r_method": how, "rays_hit": hits})
        counts[g["class"]] = counts.get(g["class"], 0) + 1
    return {
        "schema": "nmsk.clinical_risk.v1",
        "viewer": viewer,
        "generated": _dt.date.today().isoformat(),
        "licence": LICENCE,
        "frame": frame,
        "method": METHOD,
        "table_version": table.get("version"),
        "counts": counts,
        "structures": rows,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--viewer", default="all", choices=["all", *VIEWERS])
    ap.add_argument("--out-dir", default=str(REPO / "clinical" / "data"))
    ap.add_argument("--source", help="single viewer only: its bundle dir or Z-Anatomy page, instead of the default build")
    a = ap.parse_args(argv)
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    table = load_risk_table()
    for v in (VIEWERS if a.viewer == "all" else [a.viewer]):
        doc = build(v, table, Path(a.source) if a.source and a.viewer != "all" else None)
        p = out / f"risk_{v}.json"
        p.write_text(json.dumps(doc, indent=0, separators=(",", ":")) + "\n", encoding="utf-8")
        meth = {}
        for r in doc["structures"]:
            meth[r["r_method"]] = meth.get(r["r_method"], 0) + 1
        print(f"{v}: {len(doc['structures'])} risk structures {doc['counts']} methods {meth} -> {p} ({p.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
