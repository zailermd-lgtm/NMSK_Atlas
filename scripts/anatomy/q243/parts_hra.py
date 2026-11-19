#!/usr/bin/env python3
"""Q243 (2): sub-part nodes of the uterus and the uterine tubes of the HRA United Female v1.10 (CC BY 4.0) as selectable PARTS (parts layer, Q219 / Q220) of the structures that are already on the pages
(the HRA uterus and tubes registered in Q233): no new geometry, each part is a named, sourced row with a marker at the area centroid of its registered sub-part surface.
 - table      data/anatomy/structure_parts_hra_q243.json   (rows in the schema of structure_parts.json, part_type `organ part`; references: the HRA objects)
 - geometry   data/derived/Q243_parts_hra.json             (per body: marker xyz, error bound, the distance to the carrier mesh, extent)
 - inject     python3 scripts/anatomy/q243/parts_hra.py --inject PAGE_DIR --body vhf|zan_f|zbase_f    (adds the rows + markers to the page's parts_data.json; idempotent)
The bladder sub-parts (dome, base, neck muscle, trigone, ureteral orifices) are NOT added: the bladder of every page is a CT segmentation (own) or a Z-Anatomy fit, not the HRA bladder, so the HRA sub-parts are not
parts of any shipped bladder geometry."""
from __future__ import annotations
import argparse, csv, json, sys
from pathlib import Path
import numpy as np, trimesh

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
from scripts.anatomy.q243 import hra, badges as BD  # noqa: E402
from scripts.transfer.q233_own_f import mask_of  # noqa: E402

TABLE = REPO / "data/anatomy/structure_parts_hra_q243.json"
GEO = REPO / "data/derived/Q243_parts_hra.json"
CROSSWALK = "united-female"
REF = "hra_united_female_v110"
# part id suffix, display name, HRA node (side placeholder {S} = L / R), structure id (side-agnostic)
UTERUS = [("fundus", "Fundus of the uterus", "VH_F_fundus_of_uterus"), ("body", "Body of the uterus", "VH_F_body_of_uterus"), ("cervix", "Cervix of the uterus", "VH_F_cervix"),
          ("external_os", "External cervical os", "VH_F_external_cervical_os"), ("internal_os", "Internal cervical os", "VH_F_internal_cervical_os"),
          ("anterior_wall", "Anterior wall of the uterus", "VH_F_anterior_wall_of_uterus"), ("posterior_wall", "Posterior wall of the uterus", "VH_F_posterior_wall_of_uterus"),
          ("lower_segment", "Lower uterine segment", "VH_F_lower_uterine_segment"), ("cornua", "Uterine cornua", "VH_F_cornua"),
          ("tubal_ostium", "Abdominal ostium of the uterine tube", "VH_F_abdominal_ostium_of_uterine_tube")]
TUBE = [("ampulla", "Ampulla of the uterine tube", "VH_F_ampulla_of_uterine_tube_{S}"), ("isthmus", "Isthmus of the uterine tube", "VH_F_isthmus_of_fallopian_tube_{S}"),
        ("infundibulum", "Infundibulum of the uterine tube", "VH_F_uterine_tube_infundibulum_{S}"), ("fimbriae", "Fimbriae of the uterine tube", "VH_F_fibria_of_uterine_tube_{S}")]
CARRIERS = {"uterus": {"vhf": ["uterus"], "zan_f": ["uterus"], "zbase_f": ["uterus"]},
            "uterine_tube": {"vhf": ["uterine_tube_l", "uterine_tube_r"], "zan_f": ["uterine_tube_l", "uterine_tube_r"], "zbase_f": ["uterine_tube_l", "uterine_tube_r"]}}
ERR_MM = 3.53       # p90 of the Q233 bone registration (own_f / comb_f); a soft sub-part also depends on HRA's own registration


def crosswalk():
    p = hra.glb_path(CROSSWALK).parent / "crosswalk.csv"
    return {r["node_name"]: (r["OntologyID"], r["label"]) for r in csv.DictReader(open(p, encoding="utf-8"))}


def centroid_area(v, f):
    m = trimesh.Trimesh(v, f, process=False)
    tri = m.triangles_center; a = m.area_faces
    return (tri * a[:, None]).sum(0) / a.sum(), m


def build_table():
    """-> rows, registered markers per node (HRA frame -> atlas axis, before the page transform)"""
    nodes = hra.load_nodes(CROSSWALK, "|".join(f"^{n.format(S=s)}$" for _, _, n in UTERUS + TUBE for s in ("L", "R")))
    cw = crosswalk()
    rows, hra_geo = [], {}
    ref = {REF: dict(kind="database", t="HuBMAP Human Reference Atlas 3D Reference Object Library, 3D Reference Organ Set for United Female v1.10 (2026-06-09), Browne K, Schlehlein H; CC BY 4.0", doi="10.48539/HBM637.DWBM.744", pmid=None)}

    def add(struct, suf, name, node, side):
        v, f = nodes[node]
        c, m = centroid_area(v, f)
        onto, label = cw.get(node, (None, None))
        ext = (m.bounds[1] - m.bounds[0])
        sd = {"left": "left ", "right": "right ", None: ""}[side]
        d = (f"HRA node `{node}`" + (f" ({onto}, '{label}')" if onto else " (no ontology id in the library)") + f": a named sub-part of the {struct.replace('_', ' ')} in the HRA 3D Reference Object Library "
             f"(united-female v1.10); {'closed' if m.is_watertight else 'open'} surface of {len(f)} triangles, spans about {ext[0]:.0f} x {ext[1]:.0f} x {ext[2]:.0f} mm in the HRA frame. "
             f"The {sd}{struct.replace('_', ' ')} of this page is the HRA one (Q233), so the part is a region of shipped geometry; no new surface is drawn, the marker is the point of the registered sub-part surface nearest to its area centroid.")
        rows.append(dict(id=f"{struct}.{suf}" + (f"_{side[0]}" if side else ""), structure_id=struct, structure_class="organ", part_type="organ part", name=name + (f" ({side})" if side else ""), description=d,
                         ontology=onto, hra_node=node, hra_triangles=int(len(f)), hra_closed=bool(m.is_watertight), side=side, refs=[REF], verification="verified",
                         note="Verified against the library itself (node name, ontology id, geometry read from the GLB on 2026-10-15); the library gives no description of how the sub-parts were delineated."))
        anchor = v[int(np.linalg.norm(v - c, axis=1).argmin())]              # the sub-part surface vertex nearest to the area centroid: a marker ON the sub-part, not in the lumen of a curved tube
        hra_geo[rows[-1]["id"]] = dict(centroid=c, anchor=anchor, extent=ext, node=node, centroid_to_anchor_mm=float(np.linalg.norm(anchor - c)))

    for suf, name, node in UTERUS:
        add("uterus", suf, name, node, None)
    for suf, name, node in TUBE:
        for side, S in (("left", "L"), ("right", "R")):
            add("uterine_tube", suf, name, node.format(S=S), side)
    return rows, hra_geo, ref


def main():
    rows, hra_geo, ref = build_table()
    doc = dict(schema="nmsk.structure_parts.hra.v1", generated="2026-10-15", license="CC BY 4.0 (HRA 3D Reference Object Library) -> anatomy layer, CC BY-SA 4.0 compatible",
               about=(__doc__.split("\n")[0]), part_types={"organ part": "a named sub-part (region) of an organ in a reference atlas (not a muscle head / attachment): wall, segment, os, ostium, fimbriae ..."}, references=ref, parts=rows,
               not_added={"urinary_bladder": "dome, base, neck muscle, trigone, ureteral orifices (HRA): the bladder on every page is a CT segmentation (own pages) or a Z-Anatomy fit, not the HRA bladder (HRA 13 cm3 vs 44 cm3 on her CT, Q233), so these sub-parts are not parts of shipped geometry"},
               counts=dict(parts=len(rows), structures=len({r["structure_id"] for r in rows})))
    TABLE.write_text(json.dumps(doc, indent=1) + "\n")
    print("table", len(rows), "parts ->", TABLE.name)


# ------------------------------------------------------------------------------------------------------------------------------------- placement on a page
def place(body, T0, page_meshes):
    """body vhf|zan_f|zbase_f; T0 = (s, R, t) HRA -> page; page_meshes = {mesh id: (V, F)} -> list of marker dicts (checked against the carrier meshes)"""
    rows, hra_geo, _ = build_table()
    out = []
    s, R, t = T0
    for r in rows:
        g = hra_geo[r["id"]]
        xyz = hra.to_world(T0, g["anchor"][None])[0]
        carriers = [c for c in CARRIERS[r["structure_id"]][body]]
        side = {"left": "l", "right": "r", None: "m"}[r["side"]]
        if r["structure_id"] == "uterine_tube":
            carriers = [c for c in carriers if c.endswith("_" + side)]
        best = None
        for c in carriers:
            if c not in page_meshes:
                continue
            V, F = page_meshes[c]
            m = trimesh.Trimesh(V, F, process=True)
            d = float(trimesh.proximity.closest_point(m, xyz[None])[1][0])
            inside = inside_vote(m, xyz)
            if best is None or (inside, -d) > (best["inside"], -best["d"]):
                best = dict(carrier=c, d=round(d, 2), inside=inside, watertight=bool(m.is_watertight))
        ext = (np.asarray(g["extent"]) * s)
        ok = bool(best is not None and (best["inside"] or best["d"] <= ERR_MM))
        out.append(dict(part=r["id"], side=side, xyz=[round(float(x), 2) for x in xyz], e=ERR_MM, carrier=best, centroid_to_marker_mm=round(g["centroid_to_anchor_mm"] * s, 1), extent_mm=[round(float(x), 1) for x in ext], ok=ok, node=g["node"]))
    return out


def inject(page_dir, body, markers):
    """add the rows + markers to the page's parts_data.json (idempotent: an earlier Q243 addition is removed first)"""
    p = Path(page_dir) / "parts_data.json"
    D = json.loads(p.read_text(encoding="utf-8"))
    tab = json.loads(TABLE.read_text(encoding="utf-8"))
    # remove an earlier Q243 addition
    keep = [i for i, r in enumerate(D["parts"]) if not str(r.get("q")) == "q243"]
    if len(keep) != len(D["parts"]):
        remap = {old: new for new, old in enumerate(keep)}
        D["parts"] = [D["parts"][i] for i in keep]
        D["placed"] = [dict(x, p=remap[x["p"]]) for x in D["placed"] if x["p"] in remap]
        D["mesh_parts"] = {k: dict(v, p=[remap[i] for i in v["p"] if i in remap]) for k, v in D["mesh_parts"].items() if any(i in remap for i in v["p"])}
    D["refs"] = {k: v for k, v in D["refs"].items() if k != REF}
    base = len(D["parts"])
    ok = {m["part"]: m for m in markers if m["ok"]}
    idx = {}
    for r in tab["parts"]:
        if r["id"] not in ok:
            continue
        idx[r["id"]] = base + len(idx)
        D["parts"].append({"id": r["id"], "st": r["structure_id"], "ty": "organ part", "n": r["name"], "d": r["description"], "r": r["refs"], "ev": "HRA 3D Reference Object Library v1.10 (united-female), read from the GLB",
                           "note": r["note"], "q": "q243"})
    D["refs"][REF] = {"t": tab["references"][REF]["t"], "pmid": None, "doi": tab["references"][REF]["doi"], "k": "database"}
    D["types"] = dict(D.get("types") or {}, **{"organ part": "organ part"})
    for pid, m in ok.items():
        D["placed"].append({"p": idx[pid], "s": m["side"], "xyz": m["xyz"], "c": "hra_reference", "e": m["e"], "rule": "hra_subnode_centroid", "m": "hra_subnode_centroid",
                            "mt": (f"HRA node `{m['node']}`: the sub-part surface vertex nearest to its area centroid (offset {m['centroid_to_marker_mm']} mm), registered with the Q233 pelvis transform onto this page; the sub-part spans about "
                                   f"{m['extent_mm'][0]} x {m['extent_mm'][1]} x {m['extent_mm'][2]} mm; the marker is {'inside' if m['carrier']['inside'] else 'within ' + str(m['carrier']['d']) + ' mm of'} the shipped mesh `{m['carrier']['carrier']}`"),
                            "eb": "p90 of the bone registration (3.53 mm); the sub-part's own extent is larger than the marker", "car": [m["carrier"]["carrier"]]})
    by_carrier = {}
    for pid, m in ok.items():
        by_carrier.setdefault(m["carrier"]["carrier"], [m["side"], []])[1].append(idx[pid])
    for c, (side, lst) in by_carrier.items():
        cur = D["mesh_parts"].get(c, {"s": side, "p": []})
        cur["p"] = sorted(set(cur["p"]) | set(lst)); D["mesh_parts"][c] = cur
    D["source_classes"] = dict(D.get("source_classes") or {}, hra_reference="Reference: the HRA 3D Reference Object Library's own sub-part, registered onto this body by its bones (not measured on this body)")
    c = D["counts"]
    c["parts"] = len(D["parts"]); c["structures"] = len({x["st"] for x in D["parts"]}); c["meshes_with_parts"] = len(D["mesh_parts"]); c["placements"] = len(D["placed"]); c["parts_placed"] = len({x["p"] for x in D["placed"]})
    c["hra_organ_parts_q243"] = len(ok)
    p.write_text(json.dumps(D, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    return len(ok)


def inside_vote(m, p):
    """inside the (possibly leaky) closed envelope: ray parity along the six axis directions, majority (the page meshes are decimated envelopes that are not always watertight)"""
    votes = 0
    for ax in range(3):
        for sg in (1.0, -1.0):
            d = np.zeros(3); d[ax] = sg
            hits = m.ray.intersects_location(p[None], d[None])[0]
            votes += int(len(hits) % 2 == 1)
    return bool(votes >= 4)


def page_meshes(body):
    ids = ["uterus", "uterine_tube_l", "uterine_tube_r"]
    if body == "vhf":
        from scripts.transfer.q200_bundle import Bundle
        B = Bundle(REPO / "build/viewer_f_hr_q243" if (REPO / "build/viewer_f_hr_q243").exists() else REPO / "build/viewer_f_hr_q237")
        return {it["e"]["id"]: B.mesh(it) for it in B.items if it["e"]["id"] in ids}
    from scripts.zanatomy import q205_pages as P5
    d, stem = {"zan_f": ("build/q239/viewer_zan_female", "atlas_viewer_zan_female"), "zbase_f": ("build/q239/viewer_base_female", "atlas_viewer_base_female")}[body]
    man, blob = P5.load_page(REPO / d, stem)
    S = P5.decode(man, blob)
    return {i: (S[i]["v"], S[i]["f"]) for i in ids if i in S}


def transform(body):
    if body == "zbase_f":
        r = json.loads((REPO / "data/derived/Q233_report_base_f.json").read_text())["registration"]
    else:
        r = json.loads((REPO / "data/derived/Q233_hra_to_vhf_transform.json").read_text())
    return (r["scale"], np.array(r["rotation"]), np.array(r["translation_mm"])), r


def markers():
    out = {}
    for body in ("vhf", "zan_f", "zbase_f"):
        T0, r = transform(body)
        mk = place(body, T0, page_meshes(body))
        out[body] = dict(registration=dict(scale=r["scale"], residual_mm=r["residual_mm"]), markers=mk, ok=sum(1 for m in mk if m["ok"]), total=len(mk))
        print(body, out[body]["ok"], "/", out[body]["total"], "markers pass (inside or within", ERR_MM, "mm of the shipped mesh)")
    GEO.write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--table", action="store_true"); ap.add_argument("--markers", action="store_true"); ap.add_argument("--inject"); ap.add_argument("--body")
    a = ap.parse_args()
    if a.table:
        main()
    if a.markers:
        markers()
    if a.inject:
        n = inject(a.inject, a.body, json.loads(GEO.read_text())[a.body]["markers"])
        print(f"parts: {a.inject}: {n} HRA organ parts added ({a.body})")
