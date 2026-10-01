#!/usr/bin/env python3
"""Q186 (owner: "zanatomy models being missing few things as penile skin, face skin, etc. review and
verify all details"): account for EVERY object of the pinned Z-Anatomy release in the two Z-Anatomy
reference viewers (male: build/viewer_zan_atlas, female-fitted: build/viewer_zan_female).

One row per source object (all 9 FBX files, meshes AND group nodes; listed by
scripts/zanatomy/list_fbx_objects.py into build/zanatomy/source_objects.json): whether it ships in each
viewer (under which id, alone or concatenated with other source objects) or the exact reason it does
not. Then a defect sweep of what each viewer actually ships (decoded from the built page): zero
triangles, unknown layer, missing left/right counterpart, side label vs position, isolated meshes,
inside-out closed meshes, duplicate geometry, labels carrying raw suffixes or two ids sharing one label.

    python3 scripts/zanatomy/zan_inventory_audit.py [--out data/derived/Q186_zan_inventory.json]
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

DERIVED = REPO / "data" / "derived"
SOURCE_OBJECTS = REPO / "build" / "zanatomy" / "source_objects.json"
VIEWERS = {
    "male": (REPO / "build/viewer_zan_atlas/atlas_viewer_zan_atlas.html", DERIVED / "Q157_zan_atlas_report.json"),
    "female": (REPO / "build/viewer_zan_female/atlas_viewer_zan_female.html", DERIVED / "Q168_zan_female_report.json"),
}
TEMPLATE_LAYERS = {"bone", "cartilage", "joint", "insertion", "muscle", "fascia", "bursa", "nerve", "cns",
                   "vessel", "lymph", "viscera"}

_SUFFIX_RE = re.compile(r"\.([A-Za-z0-9]+)$")
DECAL_SUFFIXES = {"ol", "or", "el", "er"}
HAIR_NAMES = ("Hairs of head", "Hairs of eyebrow", "Eyelashes", "Pubic hairs")

REASONS = {
    "shipped": "ships as its own structure",
    "shipped_merged": "ships, concatenated with other source object(s) into one structure (matched atlas id "
                      "made of several Z-Anatomy sub-parts, or both sides under a side-less id)",
    "group_node": "Blender empty / collection node -- carries no geometry",
    "reference_diagram": "References100.fbx: UI planes, body lines, movement arrows -- not anatomy",
    "pin_marker": "label pin / leader line (.i/.j suffix) -- not tissue",
    "source_placeholder": "fewer than 12 vertices in the source (8-vertex box, 4-vertex plane, empty mesh) -- "
                          "the source has no real geometry for it",
    "excluded_nc_licensed": "non-commercial licence (Inner Ear CC BY-NC-SA 4.0 / Kidney CC BY-NC 4.0 credits "
                            "in Resources/Models/License.txt) -- excluded by the licensing rule",
    "zero_face_curve": "wireframe curve with vertices but no triangles -- not a surface",
    "hair_not_shipped": "hair: extracted, not shipped by default (the template colours by layer, so hair would "
                        "draw as a skin-coloured cap); --with-hair ships it",
    "origin_insertion_decal": "Z-Anatomy origin/insertion highlight decal (.ol/.or/.el/.er) of a structure "
                              "that ships",
    "ui_highlight_duplicate": "smaller copy of a structure that ships (same system, side and name)",
    "copy_in_other_system": "same structure (same side and name) already ships from another Z-Anatomy system",
    "muscle_footprint_on_bone": "a muscle's attachment footprint drawn on the bone (Skeletal system copy)",
    "male_only_not_on_female": "male-only structure, removed from the female-fitted variant",
    "not_shipped_unexplained": "not shipped and no rule explains it -- a build defect to fix",
}


def strip_suffix(name: str) -> str:
    return _SUFFIX_RE.sub("", name)


def suffix_of(name: str) -> str | None:
    m = _SUFFIX_RE.search(name)
    return m.group(1).lower() if m else None


def side_of(name: str) -> str | None:
    s = suffix_of(name)
    if s in {"l", "el", "ol", "e1l", "e2l", "e3l", "o1l", "o2l", "o3l"}:
        return "left"
    if s in {"r", "er", "or", "e1r", "e2r", "e3r", "o1r", "o2r", "o3r"}:
        return "right"
    return None


# ------------------------------------------------------------------ per-object accounting (pure)
def classify_objects(source_objects: list[dict], inventory: dict, namemap: dict,
                     provenance: dict, shipped_ids: set, dropped_ids: set | None = None) -> list[dict]:
    """source_objects: [{name, file, system, type, vertex_count?, face_count?}] (every object of every FBX);
    inventory: {name: inventory record} of the EXTRACTED objects (main + Integument, keyed by name;
    a name extracted twice from different files is keyed by (system, name) instead);
    provenance: {shipped id: {route, sources}} from the build report; shipped_ids: ids in the built page;
    dropped_ids: ids the variant removed on purpose (female: male-only).
    Returns one row per source object: {file, system, name, type, status, reason, mesh_id?, merged_with?}."""
    dropped_ids = dropped_ids or set()
    nm_status = {e["zanatomy_name"]: e["status"] for e in namemap.get("entries", [])}
    src_to_id: dict = {}      # source object name -> the id it is part of
    id_sources: dict = {}
    for mid, p in provenance.items():
        id_sources[mid] = p["sources"]
        for s in p["sources"]:
            src_to_id[s] = mid
    shipped_keys = set()      # (system, side, base) of every shipped source object
    shipped_side_base = {}    # (side, base) -> system
    for s, mid in src_to_id.items():
        if mid not in shipped_ids:
            continue
        rec = inventory.get(s)
        if rec is None:
            continue
        key = (rec["system"], rec.get("side"), strip_suffix(s))
        shipped_keys.add(key)
        shipped_side_base.setdefault(key[1:], rec["system"])
    muscular_bases = {strip_suffix(n) for n, r in inventory.items() if r["system"] == "Muscular"}

    rows = []
    for o in source_objects:
        row = {"file": o["file"], "system": o["system"], "name": o["name"], "type": o["type"]}
        if o["type"] == "MESH":
            row["vertex_count"], row["face_count"] = o.get("vertex_count"), o.get("face_count")
        rows.append(row)
        rec = inventory.get(o["name"]) if o["type"] == "MESH" else None
        if rec is not None and rec["system"] != o["system"]:
            rec = None  # same name in another file (e.g. "Cross Section X")
        if o["type"] != "MESH":
            row["reason"] = "group_node"
        elif o["file"] == "References100.fbx":
            row["reason"] = "reference_diagram"
        elif rec is None and suffix_of(o["name"]) in ("i", "j"):
            row["reason"] = "pin_marker"
        elif rec is None:
            row["reason"] = "source_placeholder"
        elif not rec.get("license", "CC-BY-SA-4.0").startswith("CC-BY-SA") or \
                nm_status.get(o["name"]) == "excluded_nc_licensed":
            row["reason"] = "excluded_nc_licensed"
        elif rec["face_count"] == 0:
            row["reason"] = "zero_face_curve"
        elif o["system"] == "Integument" and strip_suffix(o["name"]) in HAIR_NAMES and \
                o["name"] not in src_to_id:
            row["reason"] = "hair_not_shipped"
        else:
            mid = src_to_id.get(o["name"])
            if mid is not None and mid in shipped_ids:
                row["mesh_id"] = mid
                others = [s for s in id_sources[mid] if s != o["name"]]
                row["reason"] = "shipped_merged" if others else "shipped"
                if others:
                    row["merged_with"] = others
            elif mid is not None and mid in dropped_ids:
                row["mesh_id"] = mid
                row["reason"] = "male_only_not_on_female"
            else:
                side, base = rec.get("side"), strip_suffix(o["name"])
                if (rec["system"], side, base) in shipped_keys:
                    row["reason"] = ("origin_insertion_decal" if suffix_of(o["name"]) in DECAL_SUFFIXES
                                     else "ui_highlight_duplicate")
                elif (side, base) in shipped_side_base:
                    row["reason"] = "copy_in_other_system"
                    row["ships_from"] = shipped_side_base[(side, base)]
                elif rec["system"] == "Skeletal" and base in muscular_bases:
                    row["reason"] = "muscle_footprint_on_bone"
                else:
                    row["reason"] = "not_shipped_unexplained"
                    row["namemap_status"] = nm_status.get(o["name"])
        row["status"] = "in_viewer" if row["reason"] in ("shipped", "shipped_merged") else "absent"
    return rows


# ------------------------------------------------------------------ built page decoding
def load_page(html_path: Path):
    """(manifest, {id: (v, f)}) decoded exactly as viewer/zan_atlas.template.html's loader does."""
    html = Path(html_path).read_text(encoding="utf-8")
    man = json.loads(re.search(r"window\.__ANATOMY_MANIFEST__=(\{.*?\});\n", html, re.S).group(1))
    files = json.loads(re.search(r"window\.__ANATOMY_BIN_FILES__=(\[.*?\]);", html, re.S).group(1))
    if files:
        blob = b"".join(base64.b64decode((Path(html_path).parent / f["path"]).read_text()) for f in files)
    else:
        blob = base64.b64decode(re.search(r'window\.__ANATOMY_BIN__="([^"]*)"', html).group(1))
    meshes = {}
    for m in man["meshes"]:
        q = np.frombuffer(blob, "<u2", m["vc"] * 3, m["vo"]).reshape(-1, 3).astype(np.float64)
        v = np.asarray(m["min"]) + q / 65535.0 * np.asarray(m["span"])
        f = np.frombuffer(blob, "<u2", m["ic"] * 3, m["io"]).reshape(-1, 3).astype(np.int64)
        meshes[m["id"]] = (v, f)
    return man, meshes


def signed_volume(v, f) -> float:
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)


def is_closed(f) -> bool:
    e = np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1)
    _, c = np.unique(e, axis=0, return_counts=True)
    return bool(len(c)) and bool((c == 2).all())


SIDE_WORDS = {"r": ("left",), "l": ("right",)}


def defects(man: dict, meshes: dict, isolated_mm: float = 20.0) -> dict:
    """Per-viewer sweep of what actually ships (see module docstring)."""
    from scipy.spatial import cKDTree
    recs = {m["id"]: m for m in man["meshes"]}
    out: dict = defaultdict(list)
    for mid, m in recs.items():
        if m["ic"] == 0 or m["vc"] < 3:
            out["zero_triangles"].append(mid)
        if m.get("sys") not in TEMPLATE_LAYERS:
            out["unknown_layer"].append({"id": mid, "sys": m.get("sys")})
        if re.search(r"\.(l|r|el|er|ol|or|\d{3})$", m["name"]):
            out["raw_suffix_in_label"].append({"id": mid, "name": m["name"]})
        low = m["name"].lower()
        if any(re.search(r"\b" + w + r"\b", low) for w in SIDE_WORDS.get(m.get("side"), ())):
            out["label_side_word_contradicts_side"].append({"id": mid, "name": m["name"], "side": m.get("side")})
    for mid in recs:
        for a, b in (("_l", "_r"), ("_r", "_l")):
            if mid.endswith(a) and mid[:-2] + b not in recs:
                out["missing_counterpart"].append({"id": mid, "missing": mid[:-2] + b})
    # side vs position: atlas frame +X = subject's right
    for mid, (v, f) in meshes.items():
        sd = recs[mid].get("side")
        if sd in ("r", "l") and len(v):
            cx = float(v[:, 0].mean())
            if (sd == "r" and cx < -5) or (sd == "l" and cx > 5):
                out["side_contradicts_position"].append({"id": mid, "side": sd, "centroid_x_mm": round(cx, 1)})
        if len(f) and is_closed(f) and signed_volume(v, f) < 0:
            out["inside_out_closed"].append(mid)
    # isolated: nearest vertex of ANY other structure farther than isolated_mm
    ids = list(meshes)
    samp, lab = [], []
    rng = np.random.default_rng(0)
    for i, mid in enumerate(ids):
        v = meshes[mid][0]
        s = v if len(v) <= 400 else v[rng.choice(len(v), 400, replace=False)]
        samp.append(s); lab.append(np.full(len(s), i))
    P, L = np.vstack(samp), np.concatenate(lab)
    tree = cKDTree(P)
    for i, mid in enumerate(ids):
        s = P[L == i][:40]
        d, j = tree.query(s, k=min(96, len(P)))
        other = L[j] != i
        dm = np.where(other, d, np.inf).min()
        if dm > isolated_mm:
            out["isolated_from_every_other_structure"].append({"id": mid, "nearest_other_mm": round(float(dm), 1)
                                                               if np.isfinite(dm) else None})
    # duplicate geometry: same centroid (1 mm) and bbox (1 mm), then mean nearest distance < 0.5 mm
    key = defaultdict(list)
    for mid, (v, f) in meshes.items():
        if len(v):
            key[tuple(np.round(np.r_[v.mean(0), v.min(0), v.max(0)] / 2.0).astype(int))].append(mid)
    for grp in key.values():
        for a_i in range(len(grp)):
            for b_i in range(a_i + 1, len(grp)):
                A, B = meshes[grp[a_i]][0], meshes[grp[b_i]][0]
                d = cKDTree(B).query(A)[0].mean()
                if d < 0.5:
                    out["duplicate_geometry"].append({"ids": [grp[a_i], grp[b_i]], "mean_dist_mm": round(float(d), 2)})
    # two ids sharing one label (name + side) -> indistinguishable in the list
    lab_ids = defaultdict(list)
    for mid, m in recs.items():
        lab_ids[(m["name"], m.get("side"))].append(mid)
    out["same_label_two_ids"] = [{"label": k[0], "side": k[1], "ids": v} for k, v in lab_ids.items() if len(v) > 1]
    return {k: v for k, v in out.items()}


# ------------------------------------------------------------------ skin view
def skin_group(name: str, parents: dict) -> list[str]:
    """Parent chain (top first) of a Regions-of-human-body object, from the FBX hierarchy."""
    chain, p = [], parents.get(name)
    while p:
        chain.append(re.sub(r"\.(g|t|[lr])$", "", p))
        p = parents.get(p)
    return chain[::-1]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--source-objects", default=str(SOURCE_OBJECTS))
    ap.add_argument("--out", default=str(DERIVED / "Q186_zan_inventory.json"))
    ap.add_argument("--no-defects", action="store_true")
    a = ap.parse_args(argv)

    src = json.loads(Path(a.source_objects).read_text())
    inv_main = json.loads((DERIVED / "zanatomy_inventory.json").read_text())
    inv_skin = json.loads((DERIVED / "zanatomy_integument_inventory.json").read_text())
    inventory = {o["name"]: o for o in inv_main["objects"] + inv_skin["objects"]}
    namemap = json.loads((DERIVED / "zanatomy_name_map.json").read_text())
    parents = {o["name"]: o["parent"] for o in src["objects"] if o["file"].startswith("Regions")}

    per_viewer, defect_rep, totals = {}, {}, {}
    for vname, (html, report) in VIEWERS.items():
        rep = json.loads(Path(report).read_text())
        prov = rep.get("provenance") or {}
        if not prov:
            raise SystemExit(f"{report} has no provenance -- rebuild with the Q186 build script")
        man, meshes = load_page(html)
        shipped = {m["id"] for m in man["meshes"]}
        missing_from_page = sorted(set(prov) - shipped)
        dropped = set((rep.get("fit_to_vhf") or {}).get("male_only_dropped") or [])
        prov_all = dict(prov)
        if dropped:  # the female report's provenance lists only what shipped; take the male-only sources
            male_prov = json.loads(VIEWERS["male"][1].read_text()).get("provenance", {})
            prov_all.update({k: male_prov[k] for k in dropped if k in male_prov})
        per_viewer[vname] = classify_objects(src["objects"], inventory, namemap, prov_all, shipped, dropped)
        totals[vname] = {"structures": len(man["meshes"]), "by_layer": dict(Counter(m["sys"] for m in man["meshes"])),
                         "triangles": int(sum(m["ic"] for m in man["meshes"])),
                         "skin_structures": sum(1 for m in man["meshes"] if m["id"].startswith("zan_skin_")),
                         "provenance_ids_missing_from_page": missing_from_page}
        if not a.no_defects:
            defect_rep[vname] = defects(man, meshes)
        del meshes

    rows = []
    for i, o in enumerate(src["objects"]):
        m, f = per_viewer["male"][i], per_viewer["female"][i]
        row = {k: m[k] for k in ("file", "system", "name", "type") if k in m}
        for k in ("vertex_count", "face_count"):
            if k in m:
                row[k] = m[k]
        rec = inventory.get(o["name"])
        if rec is not None and rec["system"] == o["system"]:
            row["side"] = rec.get("side")
            row["licence"] = rec.get("license")
        row["male"] = {k: m[k] for k in ("status", "reason", "mesh_id", "merged_with", "ships_from") if k in m}
        row["female"] = {k: f[k] for k in ("status", "reason", "mesh_id", "merged_with", "ships_from") if k in f}
        if o["file"].startswith("Regions"):
            row["skin_region_path"] = skin_group(o["name"], parents)
        rows.append(row)

    def table(view):
        t = defaultdict(Counter)
        for r in rows:
            t[r["system"]][r[view]["reason"]] += 1
        return {s: dict(c) for s, c in sorted(t.items())}

    nc = [{"name": r["name"], "system": r["system"],
           "why_nc": ("Kidney (CC BY-NC 4.0, lissiecowley)" if re.search(r"kidney|renal", r["name"], re.I)
                      else "Inner Ear (CC BY-NC-SA 4.0, Univ. of Dundee) -- name pattern; cochlear/vestibular "
                           "nerve items may belong to the CC BY Cranial Nerves package, held conservatively")}
          for r in rows if r["male"]["reason"] == "excluded_nc_licensed"]
    skin_rows = [r for r in rows if r["file"].startswith("Regions") and r["type"] == "MESH"]
    skin_by_top = defaultdict(lambda: defaultdict(Counter))
    for r in skin_rows:
        top = (r.get("skin_region_path") or ["(top level)"])[0] if r.get("skin_region_path") else "(top level)"
        for v in ("male", "female"):
            skin_by_top[top][v][r[v]["reason"]] += 1
    out = {
        "source": ("Q186 (2026-10-01): scripts/zanatomy/zan_inventory_audit.py -- every object of the pinned "
                   "Z-Anatomy release (commit %s, 9 FBX files listed by scripts/zanatomy/list_fbx_objects.py) "
                   "against the built Z-Anatomy viewers (male build/viewer_zan_atlas, female-fitted "
                   "build/viewer_zan_female), using each build report's provenance (shipped id -> source "
                   "objects)." % src.get("commit")),
        "reasons": REASONS,
        "viewer_totals": totals,
        "counts_by_reason": {v: dict(Counter(r[v]["reason"] for r in rows)) for v in ("male", "female")},
        "table_by_system_and_reason": {v: table(v) for v in ("male", "female")},
        "nc_excluded": nc,
        "skin_by_region_group": {k: {v: dict(c) for v, c in d.items()} for k, d in sorted(skin_by_top.items())},
        "defects": defect_rep,
        "rows": rows,
    }
    Path(a.out).write_text(json.dumps(out, indent=0, default=str))
    for v in ("male", "female"):
        print(v, totals[v]["structures"], "structures,", totals[v]["skin_structures"], "skin;",
              out["counts_by_reason"][v])
    for v, d in defect_rep.items():
        print(v, "defects:", {k: len(x) for k, x in d.items()})
    print("wrote", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
