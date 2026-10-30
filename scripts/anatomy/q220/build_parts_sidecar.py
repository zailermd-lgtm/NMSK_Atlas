#!/usr/bin/env python3
"""Q220: the per-page `parts_data.json` sidecar of the viewers (public anatomy layer; NOT the clinical_* private files).

    python3 scripts/anatomy/q220/build_parts_sidecar.py --html PAGE.html --body vhm|vhf|zan_m|zan_f|zbase_m|zbase_f -o parts_data.json

Joins (a) data/anatomy/structure_parts.json (Q219: sourced parts, side-agnostic), (b) the page's own mesh ids (read out of the built
page: own pages = bundle-json, Z pages = manifest) and (c) the placed coordinates of that body (data/derived/Q219_parts_<body>.json, or
Q220_parts_<zbase>.json for the two unfitted Z reference bodies).  Every placement is CHECKED against the page's own geometry before it is
shipped: the point must lie on / inside / within its error bound of the page's meshes it was derived from (so a page whose geometry moved
after the placements were computed, e.g. a re-built forearm, loses the placements that no longer fit and keeps their text -- reason
recorded), and nothing is ever labelled 'measured'.
Output: parts (only the ones that resolve to a mesh of this page), mesh_parts (mesh id -> parts), placed, text_only, sets, refs."""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import re
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(HERE.parent / "q219"))

TABLE = REPO / "data/anatomy/structure_parts.json"
TYPE_ORDER = ["head_belly", "origin_part", "insertion_point", "ligament_component", "muscle_tendon_junction", "fascial_passage"]
TYPE_LABEL = {"head_belly": "head", "origin_part": "origin", "insertion_point": "insertion", "ligament_component": "ligament component",
              "muscle_tendon_junction": "MTJ", "fascial_passage": "fascial passage"}
MAPKEY = {"vhm": "vhm", "vhf": "vhf", "zan_m": "zan_m", "zan_f": "zan_f", "zbase_m": "zan_m", "zbase_f": "zan_f"}
GEOFILE = {"vhm": "Q219_parts_vhm.json", "vhf": "Q219_parts_vhf.json", "zan_m": "Q219_parts_zan_m.json", "zan_f": "Q219_parts_zan_f.json",
           "zbase_m": "Q220_parts_zbase_m.json", "zbase_f": "Q220_parts_zbase_f.json"}
SOURCE_CLASSES = {
    "rule_based": "Rule-based: a documented rule applied to this body's own mesh, with the error bound shown",
    "z_fill": "Z-Anatomy fill: the position of a Z-Anatomy mesh (a dedicated part mesh, or a nerve / fascia mesh pair) in this model",
}
SIDE_RE = re.compile(r"_(l|r)$")
ZF_RE = re.compile(r"_zfill\d*$")


# ------------------------------------------------------------------ page meshes
def load_page(html_path: Path):
    """[(id, side, cat, V, F)] of one built page (own or Z)."""
    from platform_wrap import unwrap
    h = unwrap(html_path.read_text(encoding="utf-8"))
    d = html_path.parent
    out = []
    if 'id="bundle-json"' in h:
        from scripts.transfer.bundle_io import decode
        b = json.loads(re.search(r'<script id="bundle-json" type="application/json">(.*?)</script>', h, re.S).group(1))
        files = json.loads(re.search(r"^var BIN_FILES = (.*);$", h, re.M).group(1))
        blob = b"".join(base64.b64decode((d / f["path"]).read_text().strip()) for f in files) if files else \
            base64.b64decode(re.search(r'<script id="bundle-b64" type="text/plain">(.*?)</script>', h, re.S).group(1).strip())
        for e, v, f in decode(b, blob):
            sd = {"right": "r", "left": "l"}.get(e.get("side"))
            if sd is None:
                m = SIDE_RE.search(ZF_RE.sub("", e["id"]))
                sd = m.group(1) if m else "m"
            out.append((e["id"], sd, e["cat"], v.astype(np.float64), f.astype(np.int64)))
        kind = "own"
    else:
        man = json.loads(re.search(r"^window\.__ANATOMY_MANIFEST__=(.*);$", h, re.M).group(1))
        files = json.loads(re.search(r"^window\.__ANATOMY_BIN_FILES__=(.*);$", h, re.M).group(1))
        blob = b"".join(base64.b64decode((d / f["path"]).read_text().strip()) for f in files)
        for r in man["meshes"]:
            q = np.frombuffer(blob, "<u2", r["vc"] * 3, r["vo"]).reshape(-1, 3).astype(np.float64)
            f = np.frombuffer(blob, "<u2", r["ic"] * 3, r["io"]).reshape(-1, 3).astype(np.int64)
            v = np.asarray(r["min"]) + q / 65535.0 * np.asarray(r["span"])
            out.append((r["id"], r.get("side") or "m", r["sys"], v, f))
        kind = "zan"
    return kind, out


def base_variants(mesh_id: str):
    """Candidate side-agnostic structure ids of a mesh id (own: deltoid_r / deltoid_r_zfill203; Z: zan_xxx_muscle_l)."""
    i = SIDE_RE.sub("", ZF_RE.sub("", mesh_id))
    v = [i]
    if i.startswith("zan_"):
        v.append(i[4:])
    for x in list(v):
        for suf in ("_muscle", "_ligament", "_tendon", "_ligaments"):
            if x.endswith(suf):
                v.append(x[: -len(suf)])
    return list(dict.fromkeys(v))


def short_ref(r: dict) -> str:
    """'Rispoli et al. 2009, J Shoulder Elbow Surg 18(3):386-390' from a journal reference (the Q219 table keeps the full citation)."""
    if r["kind"] != "journal":
        return r["citation"]
    c = r["citation"]
    au = c.split(".")[0].split(",")[0]
    m = re.search(r"(\d{4});([^\s]+)$", c)
    jr = re.search(r"\.\s([^.]+?)\s\d{4};", c)
    return f"{au} et al. {m.group(1) if m else ''}, {jr.group(1) if jr else ''} {m.group(2) if m else ''}".replace(" ,", ",").strip()


def r1(x):
    return None if x is None else round(float(x), 1)


# ------------------------------------------------------------------ main build
def build(html: Path, body: str, geo_dir: Path | None = None, check: bool = True):
    table = json.loads(TABLE.read_text(encoding="utf-8"))
    parts = table["parts"]
    refs = table["references"]
    kind, meshes = load_page(html)
    ids = [m[0] for m in meshes]
    idset = set(ids)
    mk = MAPKEY[body]
    gpath = (geo_dir or REPO / "data/derived") / GEOFILE[body]
    geo = json.loads(gpath.read_text(encoding="utf-8"))

    # ---- mesh -> structure -> parts
    struct_ids = {p["structure_id"] for p in parts}
    by_struct = {}
    for i, p in enumerate(parts):
        by_struct.setdefault(p["structure_id"], []).append(i)
    mesh_struct: dict[str, set] = {}

    def add(mesh, st):
        mesh_struct.setdefault(mesh, set()).add(st)

    for p in parts:
        for key in ("structure_ids", "part_ids"):
            for m in p["maps_to"][key][mk]:
                if m in idset:
                    add(m, p["structure_id"])
    # zfill pieces of a mapped mesh, and meshes the Q219 snapshot did not know (e.g. 'zan_tibialis_posterior_muscle_l', a re-built page)
    for (mid, _sd, cat, _v, _f) in meshes:
        if mid in mesh_struct:
            continue
        stripped = ZF_RE.sub("", mid)
        if stripped != mid and stripped in mesh_struct:
            for st in mesh_struct[stripped]:
                add(mid, st)
            continue
        if cat in ("bone", "skin", "vessel", "nerve", "cns", "lymph", "viscera", "organ", "bursa"):
            continue                      # parts are rows about muscles / ligaments / tendons / fascia / joint structures
        for v in base_variants(mid):
            if v in struct_ids:
                add(mid, v)
                break
    # a part whose structure is not itself a mesh of the page (a nerve passage, a junction) is shown on the meshes it was placed from
    for g in geo["placed"]:
        for m in g["mesh_ids"]:
            if m == g.get("bone_mesh"):
                continue
            for x in [m] + [j for j in idset if j.startswith(m + "_zfill")]:
                if x in idset:
                    add(x, g["structure_id"])
    side_of = {m[0]: m[1] for m in meshes}

    used_struct = {st for sts in mesh_struct.values() for st in sts}
    order = sorted(range(len(parts)), key=lambda i: (parts[i]["structure_id"], TYPE_ORDER.index(parts[i]["part_type"]), i))
    keep = [i for i in order if parts[i]["structure_id"] in used_struct]
    pidx = {parts[i]["id"]: n for n, i in enumerate(keep)}

    used_refs = {}
    out_parts = []
    for i in keep:
        p = parts[i]
        for k in p["refs"]:
            used_refs[k] = None
        row = {"id": p["id"], "st": p["structure_id"], "ty": p["part_type"], "n": p["name"], "d": p["description"], "r": p["refs"]}
        if p["verification"] != "verified":
            row["u"] = 1
        for key, f in (("an", "anchor"), ("var", "variability"), ("ev", "evidence"), ("note", "note"), ("set", "set_id")):
            if p.get(f):
                row[key] = p[f]
        if p.get("passes"):
            row["pass"] = p["passes"]
        out_parts.append(row)

    sets = {}
    for s in table["part_sets"]:
        if not any(m in pidx for m in s["member_part_ids"]):
            continue
        byn = {}
        for c in s["reported_counts"]:
            byn.setdefault(c["n"], []).append(short_ref(refs[c["ref"]]).split(",")[0].replace(" et al.", ""))
            used_refs[c["ref"]] = None
        sets[s["id"]] = {"n": s["name"], "counts": [{"n": n, "by": sorted(set(b))} for n, b in sorted(byn.items())], "note": s.get("note")}
    out_refs = {k: {"t": short_ref(refs[k]), "pmid": refs[k].get("pmid"), "doi": refs[k].get("doi"), "k": refs[k]["kind"]} for k in sorted(used_refs)}

    mesh_parts = {}
    for mid, sts in mesh_struct.items():
        lst = sorted({pidx[parts[i]["id"]] for st in sts for i in by_struct[st] if parts[i]["id"] in pidx})
        if lst:
            mesh_parts[mid] = {"s": side_of[mid], "p": lst}

    # ---- placements, checked against THIS page's meshes
    geo_by_id = {}
    for (mid, _sd, _c, V, F) in meshes:
        geo_by_id.setdefault(mid, []).append((V, F))
    trees, boxes = {}, {}

    def surf(mid):
        if mid not in trees:
            pts = []
            for V, F in geo_by_id.get(mid, []):
                pts.append(V)
                if len(F):
                    pts.append(V[F].mean(axis=1))
            P = np.vstack(pts) if pts else np.zeros((0, 3))
            trees[mid] = cKDTree(P) if len(P) else None
            boxes[mid] = (P.min(0), P.max(0)) if len(P) else None
        return trees[mid], boxes[mid]

    def pieces(mid):
        return [mid] + [j for j in geo_by_id if j.startswith(mid + "_zfill")]

    placed, text_only, dropped = [], {}, []
    for t in geo["text_only"]:
        if t["part_id"] in pidx:
            text_only[t["part_id"]] = t["reason"]
    for g in geo["placed"]:
        pid = g["part_id"]
        if pid not in pidx:
            continue
        bone = g.get("bone_mesh")
        carriers = [m for m in g["mesh_ids"] if m != bone]
        carriers = [x for m in carriers for x in pieces(m) if x in idset]
        all_ids = [x for m in g["mesh_ids"] for x in pieces(m) if x in idset]
        pos = np.array(g["position_mm"], float)
        err = g.get("error_bound_mm")
        tol = (err if err is not None else 6.0) + 3.0
        ok, why = True, None
        if check:
            if not carriers:
                ok, why = False, "none of the meshes this position was derived from is in this page"
            else:
                best = 1e9
                inside = False
                for mid in all_ids:
                    tr, bb = surf(mid)
                    if tr is None:
                        continue
                    best = min(best, float(tr.query(pos)[0]))
                    if g["rule"] == "z_part_mesh" and np.all(pos >= bb[0] - 1.0) and np.all(pos <= bb[1] + 1.0):
                        inside = True
                if not inside and best > tol:
                    ok, why = False, f"the position lies {best:.0f} mm from its meshes in this page (> {tol:.0f} mm): the page's geometry differs from the one the position was derived on"
        if not ok:
            dropped.append({"part_id": pid, "side": g["side"], "why": why})
            text_only.setdefault(pid, why)
            continue
        ext = None
        if g.get("bbox_mm"):
            lo, hi = np.array(g["bbox_mm"][0]), np.array(g["bbox_mm"][1])
            ext = round(float(np.linalg.norm(hi - lo)), 0)
        row = {"p": pidx[pid], "s": g["side"], "xyz": [round(float(x), 2) for x in g["position_mm"]], "c": g["source_class"],
               "e": r1(err), "rule": g["rule"], "m": g["method"].split(":")[0], "mt": g["method"], "car": sorted(set(carriers)), "eb": g.get("error_basis")}
        if ext is not None:
            row["ext"] = ext
        placed.append(row)
    # a part with a placement on one side only keeps the geometry file's note for the other side
    partial = {t["part_id"]: t["reason"] for t in geo["text_only"] if t.get("partial") and t["part_id"] in pidx}
    placed_ids = {out_parts[r["p"]]["id"] for r in placed}
    text_only = {k: v for k, v in text_only.items() if k not in placed_ids or k in partial}
    n_file = sum(1 for g in geo["placed"] if g["part_id"] in pidx)
    out = {
        "schema": "nmsk.parts_sidecar.v1", "generated": dt.date.today().isoformat(), "body": body,
        "label": geo.get("label"), "frame": geo.get("frame"),
        "license": "Anatomy layer, CC BY-SA 4.0 compatible: cited facts (data/anatomy/structure_parts.json, Q219) and positions derived from this model's own meshes (rule-based or Z-fill, never measured). No clinical content.",
        "geometry": {"file": "data/derived/" + GEOFILE[body], "derived_on": geo.get("source"), "placements_in_file_for_this_page": n_file,
                     "placements_valid_on_this_page": len(placed), "dropped": dropped},
        "source_classes": SOURCE_CLASSES, "types": TYPE_LABEL,
        "parts": out_parts, "refs": out_refs, "sets": sets, "mesh_parts": mesh_parts, "placed": placed, "partial": partial, "text_only": text_only,
        "counts": {"parts": len(out_parts), "structures": len({p["st"] for p in out_parts}), "meshes_with_parts": len(mesh_parts),
                   "placements": len(placed), "parts_placed": len(placed_ids), "unverified": sum(1 for p in out_parts if p.get("u"))},
    }
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--html", required=True)
    ap.add_argument("--body", required=True, choices=sorted(MAPKEY))
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--no-check", action="store_true", help="skip the check of every placement against the page's geometry")
    a = ap.parse_args()
    out = build(Path(a.html), a.body, check=not a.no_check)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    g = out["geometry"]
    print(json.dumps({"out": a.out, "bytes": Path(a.out).stat().st_size, **out["counts"], "placements_in_file": g["placements_in_file_for_this_page"],
                      "dropped": len(g["dropped"])}))


if __name__ == "__main__":
    main()
