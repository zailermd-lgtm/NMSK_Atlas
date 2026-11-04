#!/usr/bin/env python3
"""Q219 phase 1 geometry: derive part positions ONLY where a documented rule on the body's own meshes allows it.
    python3 scripts/anatomy/q219/build_geometry.py [--bodies vhm,vhf,zan_m,zan_f]
Reads data/anatomy/structure_parts.json + the published bodies (own bundles / fitted Z pages).  Writes data/derived/Q219_parts_<body>.json
and data/derived/Q219_rule_validation.json.  All coordinates are points of (or on the surface of) the body's own meshes; atlas mm.
Source classes: rule_based (rule applied to the person's own mesh), z_fill (a dedicated Z-Anatomy part mesh as fitted), transferred (not used here).
Never 'measured'."""
from __future__ import annotations
import argparse, datetime as dt, json, re, sys
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import geomlib as G
REPO = G.REPO
sys.path.insert(0, str(REPO))
from scripts.audit_q189_model_separation import classify  # noqa: E402  (Q189 source classes of the own structures)

TABLE = REPO / "data/anatomy/structure_parts.json"
FRAME = "atlas mm (+X right, +Y superior, +Z anterior)"
R = lambda x, n=2: [round(float(v), n) for v in x]


# ------------------------------------------------------------------ mesh access
class Body:
    def __init__(self, key):
        self.key = key
        self.kind = G.BODIES[key]["kind"]
        self.m = G.load_body(key)
        self._tree = {}

    def ids_for(self, base, s):
        """Mesh ids of one structure on side s (own: base_s + its zfill pieces; Z: base_s / zan_base_s / midline base)."""
        out = []
        for c in (f"{base}_{s}", f"zan_{base}_{s}", base, f"zan_{base}"):
            if c in self.m:
                out.append(c)
                break
        return out

    def mesh(self, ids):
        ids = [i for i in ids if i in self.m]
        if not ids:
            return None
        vs, fs, o = [], [], 0
        pieces = []
        for i in ids:
            pieces.append(i)
            if self.kind == "own":
                pieces += sorted(j for j in self.m if j.startswith(i + "_zfill") and self.m[j]["cat"] == self.m[i]["cat"])
        for i in dict.fromkeys(pieces):
            vs.append(self.m[i]["v"]); fs.append(self.m[i]["f"] + o); o += len(self.m[i]["v"])
        return np.vstack(vs), np.vstack(fs)

    def tree(self, key, V, F):
        if key not in self._tree:
            self._tree[key] = cKDTree(np.vstack([V, V[F].mean(axis=1)]))
        return self._tree[key]

    def parent_class(self, ids):
        if self.kind == "zan":
            return "z_fill"
        i = ids[0]
        return classify(self.m[i].get("subject") or "", self.m[i].get("badge"))[0]

    def z_error(self, ids):
        """Per-structure fit error of a Z mesh from its own procedural badge (Q168 / Q195): (median, max, text) or (None, None, why)."""
        if self.kind != "zan":
            return None, None, None
        b = self.m[ids[0]].get("badge") or ""
        m = re.search(r"surface error median ([\d.]+) mm, max ([\d.]+) mm", b)
        if m:
            return float(m.group(1)), float(m.group(2)), "region estimate in the structure's badge (surface error median/max)"
        m = re.search(r"centroid ([\d.]+) mm, surface ([\d.]+) mm", b)
        if m:
            return float(m.group(2)), float(m.group(1)), "measured against the person's own mesh (surface / centroid) in the badge"
        return None, None, "no error figure in the badge"


def pca_axis(V):
    c = V.mean(axis=0)
    return c, np.linalg.svd(V - c, full_matrices=False)[2][0]


# ------------------------------------------------------------------ rules
def rule_z_part_mesh(body, part, s):
    pats = part["_zpats"]
    ids = [p.replace("{s}", s) for p in pats if p.replace("{s}", s) in body.m]
    if not ids:
        return None, "no dedicated Z part mesh for this part/side"
    V, F = body.mesh(ids)
    cen = V.mean(axis=0)
    closed = len(F) > 0
    # representative point: centroid if inside the (closed) mesh, else the mesh vertex nearest to the centroid
    pos = cen
    try:
        if not G.inside(cen[None], V, F)[0]:
            pos = V[np.argmin(np.linalg.norm(V - cen, axis=1))]
    except Exception:
        pos = V[np.argmin(np.linalg.norm(V - cen, axis=1))]
    med, mx, basis = body.z_error(ids)
    return dict(position_mm=R(pos), method="z_part_mesh: position of the dedicated Z-Anatomy part mesh as fitted to this body (inside-mesh centroid, else nearest vertex to the centroid)",
                source_class="z_fill", parent_source_class="z_fill", mesh_ids=ids, bbox_mm=[R(V.min(0)), R(V.max(0))], n_vertices=int(len(V)),
                error_bound_mm=mx, error_median_mm=med, error_basis=basis), None


def muscle_union(body, structure, s, part):
    ids = body.ids_for(structure, s)
    if ids:
        return ids
    # Z bodies carry some muscles only as part meshes (deltoid, pectoralis major, triceps heads)
    return [p.replace("{s}", s) for p in part["_structure_zpats"] if p.replace("{s}", s) in body.m]


def rule_end_snap_bone(body, part, s):
    g = part["geometry"]; st = part["structure_id"]
    ids = muscle_union(body, st, s, part)
    if g.get("muscle_part"):
        if body.kind == "own":
            return None, "single muscle mesh on this body: the part cannot be separated (the sector rule is not validated)"
        key = {"clavicular": "clavicular_part", "acromial": "acromial_part", "spinal": "scapular_spinal_part"}[g["muscle_part"]]
        ids = [i for i in ids if key in i]
    if not ids:
        return None, f"structure {st} absent on side {s}"
    bone = None
    for c in (f"{g['bone']}_{s}", g["bone"]):
        if c in body.m:
            bone = c; break
    if bone is None:
        return None, f"bone mesh {g['bone']} absent"
    V, F = body.mesh(ids); BV, BF = body.mesh([bone])
    c, u = pca_axis(V)
    t = (V - c) @ u
    lo, hi = t.min(), t.max(); rng = hi - lo
    ends = [V[t <= lo + 0.12 * rng], V[t >= hi - 0.12 * rng]]
    bt = body.tree(bone, BV, BF)
    dists = [bt.query(e)[0] for e in ends]
    k = int(np.argmin([d.min() for d in dists]))
    E, d = ends[k], dists[k]
    other = ends[1 - k]
    gap = float(d.min())
    tol = float(g.get("tol_mm", 8))
    if gap > tol:
        return None, f"the structure's mesh end is {gap:.1f} mm from the {g['bone']} surface (> tolerance {tol:g} mm); tendon/continuation not modelled"
    # limb muscles: the end touching the bone must be the expected end (proximal = higher y)
    expect = g.get("end")
    long_vertical = abs(u[1]) > 0.75 and rng > 120.0     # the proximal/distal check is only meaningful for long, vertical limb muscles
    if long_vertical and expect in ("proximal", "distal"):
        higher = E[:, 1].mean() > other[:, 1].mean()
        if (expect == "proximal") != higher and abs(E[:, 1].mean() - other[:, 1].mean()) > 20:
            # arm/leg muscles only; horizontal muscles are excluded above
            return None, f"the mesh end nearest the {g['bone']} is the {'distal' if expect == 'proximal' else 'proximal'} end, not the expected {expect} end"
    patch = E[d <= tol]
    pc = patch.mean(axis=0)
    dist, q = G.tri_nearest(pc[None], BV, BF)
    rad = float(np.linalg.norm(patch - pc, axis=1).max())
    err = float(max(rad, np.median(d[d <= tol])) + 1.0)   # footprint radius or gap (+1 mm vertex-grid slack)
    return dict(position_mm=R(q[0]), method=f"end_snap_bone: the {expect} end of the structure's own mesh (axis PCA, 12 % cap) touches the {g['bone']} mesh within {tol:g} mm; point = nearest bone-surface point to the centroid of the contact patch",
                source_class="rule_based", parent_source_class=body.parent_class(ids), mesh_ids=ids + [bone], bone_mesh=bone, n_patch_vertices=int(len(patch)),
                gap_mm=round(gap, 2), patch_radius_mm=round(rad, 2), error_bound_mm=round(err, 2),
                error_basis="max(contact-patch radius, median gap) + 1 mm; footprints larger than the patch are not resolved"), None


def rule_cc_ligament_ratio(body, part, s):
    g = part["geometry"]
    cid = body.ids_for("clavicle", s)
    if not cid:
        return None, "clavicle mesh absent"
    V, F = body.mesh(cid)
    sx = 1 if s == "r" else -1
    a = V[np.argmin(sx * V[:, 0])]; b = V[np.argmax(sx * V[:, 0])]     # medial end -> lateral end
    u = G.unit(b - a)
    t = (V - a) @ u
    L = float(t.max() - t.min())
    f = g["ratio"]
    t0 = t.max() - f * L
    sel = np.abs(t - t0) <= 2.0
    if sel.sum() < 3:
        return None, "no clavicle vertices at the ratio position"
    S = V[sel]
    p = S[np.argmin(S[:, 1])]            # inferior surface (conoid tubercle / trapezoid line are on the inferior surface)
    sd = float(g.get("ratio_sd_mm", 5.0))
    err = float(np.sqrt(sd ** 2 + 3.0 ** 2))
    return dict(position_mm=R(p), method=f"cc_ligament_ratio: {g['component']} clavicular attachment at {f:.2f} of the clavicle length from the lateral end (Rios 2007), inferior-most clavicle vertex in a 4 mm slab",
                source_class="rule_based", parent_source_class=body.parent_class(cid), mesh_ids=cid, clavicle_length_mm=round(L, 1), error_bound_mm=round(err, 2),
                error_basis=f"sqrt(published SD {sd:g} mm ^2 + 3 mm landmark^2); Rios 2007 SD of the position along the clavicle"), None


def rule_mtj_by_distance(body, part, s):
    g = part["geometry"]; st = part["structure_id"]
    ids = body.ids_for(st, s)
    if not ids:
        return None, f"structure {st} absent"
    V, F = body.mesh(ids)
    hip = body.ids_for(g["origin_bone"], s)
    if not hip:
        return None, "hip bone absent"
    HV, _ = body.mesh(hip)
    it = HV[np.argmin(HV[:, 1])]            # ischial tuberosity (lowest hip-bone point; same landmark as Q187)
    c, u = pca_axis(V)
    if u[1] < 0: u = -u                      # towards proximal
    dmm = g["distance_mm"]
    # walk along the muscle axis from the tuberosity: distal direction = -u ; plane at distance dmm along -u
    t_it = (it - c) @ u
    t_target = t_it - dmm
    sel = np.abs((V - c) @ u - t_target) <= 3.0
    if sel.sum() < 5:
        return None, f"the muscle mesh does not reach {dmm:g} mm from the ischial tuberosity along its axis"
    S = V[sel]; cen = S.mean(axis=0)
    if not G.inside(cen[None], V, F)[0]:
        return None, "the section centroid at that distance lies outside the muscle mesh"
    return dict(position_mm=R(cen), method=f"mtj_by_distance_from_origin: centroid of the muscle cross-section {dmm:g} mm from the ischial tuberosity along the muscle axis (Miller 2007: ST/BF MTJs separate at 99 +/- 15 mm)",
                source_class="rule_based", parent_source_class=body.parent_class(ids), mesh_ids=ids, error_bound_mm=float(g["sd_mm"]) + 3.0,
                error_basis=f"published SD {g['sd_mm']:g} mm (Miller 2007, n=14) + 3 mm landmark/axis error"), None


def rule_mtj_interface(body, part, s):
    g = part["geometry"]
    tid = body.ids_for(g["tendon"], s)
    if not tid:
        return None, f"tendon mesh {g['tendon']} absent in this body"
    TV, TF = body.mesh(tid); tt = body.tree(tid[0], TV, TF)
    res = []
    for mname in ([g["muscle"]] if "muscle" in g else g["muscles"]):
        mid = body.ids_for(mname, s)
        if not mid:
            continue
        V, F = body.mesh(mid)
        d, _ = tt.query(V)
        near = V[d <= 3.0]
        if len(near) < 3:
            res.append(dict(muscle=mname, placed=False, why=f"no muscle vertex within 3 mm of the tendon (min {d.min():.1f} mm)"))
            continue
        cen = near.mean(axis=0)
        pos = near[np.argmin(np.linalg.norm(near - cen, axis=1))]
        res.append(dict(muscle=mname, placed=True, position_mm=R(pos), n_contact_vertices=int(len(near)), contact_radius_mm=round(float(np.linalg.norm(near - cen, axis=1).max()), 1), parent_source_class=body.parent_class(mid)))
    ok = [r for r in res if r["placed"]]
    if not ok:
        return None, "; ".join(r.get("why", "") for r in res) or "muscle meshes absent"
    return dict(position_mm=ok[0]["position_mm"], method="mtj_interface: muscle-mesh vertices within 3 mm of the tendon mesh (the junction is where the two meshes meet); one point per muscle in `per_muscle`",
                source_class="rule_based", parent_source_class=ok[0]["parent_source_class"], mesh_ids=tid, per_muscle=ok,
                error_bound_mm=round(max(r["contact_radius_mm"] for r in ok) + 3.0, 1), error_basis="contact-patch radius + 3 mm contact threshold"), None


def nerve_ids(body, nerve, s):
    out = [i for i in body.m if (i == f"{nerve}_{s}" or i == nerve or i.startswith(f"{nerve}_") and i.endswith(f"_{s}")) and body.m[i]["cat"] in ("nerve",)]
    exact = [i for i in out if i in (f"{nerve}_{s}", nerve)]
    return exact or out


def rule_passage_contact(body, part, s):
    g = part["geometry"]
    nid = nerve_ids(body, g["nerve"], s)
    if not nid:
        return None, f"nerve mesh {g['nerve']} absent"
    fid = body.ids_for(g["fascia"], s)
    if not fid:
        return None, f"structure {g['fascia']} absent"
    NV, NF = body.mesh(nid[:1]); FV, FF = body.mesh(fid)
    ft = body.tree(fid[0] + "_c", FV, FF)
    d, i = ft.query(NV)
    k = int(np.argmin(d))
    if d[k] > 3.0:
        return None, f"closest approach of nerve and {g['fascia']} meshes is {d[k]:.1f} mm (> 3 mm): meshes do not meet, passage not located"
    near = NV[d <= 3.0]
    pos = near.mean(axis=0)
    return dict(position_mm=R(pos), method="passage_contact: nerve-mesh vertices within 3 mm of the fascia/retinaculum mesh; point = their centroid",
                source_class="rule_based" if body.kind == "own" else "z_fill", parent_source_class=body.parent_class(nid), mesh_ids=nid[:1] + fid, gap_mm=round(float(d[k]), 2),
                n_contact_vertices=int(len(near)), contact_extent_mm=round(float(np.ptp((near - near.mean(0)) @ pca_axis(near)[1])) if len(near) > 2 else 0.0, 1),
                error_bound_mm=round(float(near.std(axis=0).max() * 2 + 3.0), 1), error_basis="2 x contact spread + 3 mm threshold (a nerve running in contact along a muscle has an extended contact, the point is its centroid)"), None


RULES = dict(z_part_mesh=rule_z_part_mesh, end_snap_bone=rule_end_snap_bone, cc_ligament_ratio=rule_cc_ligament_ratio, mtj_by_distance_from_origin=rule_mtj_by_distance,
             mtj_interface=rule_mtj_interface, passage_contact=rule_passage_contact)


def validate_rules(bodies, parts):
    """Validation of rules against Z-Anatomy's own parts (the only truth available): cc ratio vs the Z conoid / trapezoid ligament meshes;
    deltoid azimuth sector rule vs the Z deltoid part meshes (reported, rule NOT used for placement because its centroid error is too large)."""
    out = {}
    cc = []
    for key in ("zan_m", "zan_f"):
        b = bodies.get(key)
        if not b: continue
        for s in "rl":
            for comp, ratio in (("conoid", 0.24), ("trapezoid", 0.17)):
                part = dict(geometry=dict(component=comp, ratio=ratio, ratio_sd_mm=4.6), structure_id="coracoclavicular_ligament")
                r, why = rule_cc_ligament_ratio(b, part, s)
                zid = f"zan_{comp}_ligament_{s}"
                if r and zid in b.m:
                    ZV = b.m[zid]["v"]
                    d = float(np.linalg.norm(ZV - np.array(r["position_mm"]), axis=1).min())
                    cc.append(dict(body=key, side=s, component=comp, distance_to_Z_ligament_mesh_mm=round(d, 1)))
    out["cc_ligament_ratio_vs_Z_ligament_mesh"] = dict(note="distance from the rule's clavicle point to the nearest vertex of the Z-Anatomy conoid/trapezoid ligament mesh fitted to the same clavicle (Z is not truth; a consistency check)", cases=cc,
                                                       median_mm=round(float(np.median([c["distance_to_Z_ligament_mesh_mm"] for c in cc])), 1) if cc else None)
    # deltoid azimuth rule vs Z parts
    from scipy.optimize import least_squares
    def head_center(hum):
        top = hum[hum[:, 1] > hum[:, 1].max() - 35]; c0 = top.mean(0)
        return least_squares(lambda p: np.linalg.norm(top - p[:3], axis=1) - p[3], [*c0, 22]).x[:3]
    data = []
    for key in ("zan_m", "zan_f"):
        b = bodies.get(key)
        if not b: continue
        for s in "rl":
            sx = 1 if s == "r" else -1
            c = head_center(b.m[f"humerus_{s}"]["v"])
            V = []; L = []
            for k, p in enumerate(("clavicular", "acromial", "scapular_spinal")):
                v = b.m[f"zan_{p}_part_of_deltoid_muscle_{s}"]["v"]; V.append(v); L += [k] * len(v)
            data.append((f"{key}_{s}", np.vstack(V), np.array(L), c, sx))
    az = lambda V, c, sx: np.degrees(np.arctan2(V[:, 2] - c[2], (V[:, 0] - c[0]) * sx))
    def fit(sub):
        grid = np.arange(-60, 90, 2.0); best = (0, None)
        for t1 in grid:
            for t2 in grid:
                if t2 >= t1: continue
                acc = np.mean([(np.where(az(V, c, sx) > t1, 0, np.where(az(V, c, sx) > t2, 1, 2)) == L).mean() for _, V, L, c, sx in sub])
                if acc > best[0]: best = (acc, (t1, t2))
        return best[1]
    cases = []
    for i, (nm, V, L, c, sx) in enumerate(data):
        thr = fit([d for j, d in enumerate(data) if j != i])
        a = az(V, c, sx); pred = np.where(a > thr[0], 0, np.where(a > thr[1], 1, 2))
        errs = [float(np.linalg.norm(V[L == k].mean(0) - V[pred == k].mean(0))) for k in range(3)]
        cases.append(dict(body_side=nm, leave_one_out_thresholds_deg=[float(thr[0]), float(thr[1])], vertex_accuracy=round(float((pred == L).mean()), 3),
                          centroid_error_mm=dict(zip(["clavicular", "acromial", "spinal"], [round(e, 1) for e in errs]))))
    out["deltoid_sector_azimuth_rule_vs_Z_parts"] = dict(
        note="Rule: azimuth about the vertical axis through the humeral head centre, two thresholds. Leave-one-body-out against the Z-Anatomy deltoid part meshes. Centroid errors of 6-40 mm are larger than the parts are thick -> the rule is NOT used to place deltoid parts on the two own bodies (single mesh) -> text only.",
        cases=cases, max_centroid_error_mm=round(max(max(c["centroid_error_mm"].values()) for c in cases), 1) if cases else None)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bodies", default="vhm,vhf,zan_m,zan_f")
    ap.add_argument("--out", default="data/derived/Q219_parts_{k}.json", help="output path template (Q220 runs the same rules on the unfitted Z bodies: data/derived/Q220_parts_{k}.json)")
    ap.add_argument("--skip-validation", action="store_true", help="do not rewrite Q219_rule_validation.json (needs the fitted Z bodies)")
    a = ap.parse_args()
    table = json.loads(TABLE.read_text())
    parts = table["parts"]
    # attach the Z part-mesh patterns (rows carry them in maps_to only as resolved ids -> re-derive the patterns from the module rows)
    sys.path.insert(0, str(HERE))
    import rows_common, rows_upper, rows_lower, rows_trunk_hand, rows_hand_passages  # noqa: F401
    import rows_q256_attachments  # noqa: F401  (Q256: origin/insertion rows for tendons/ligaments/fascia)
    import importlib, pkgutil
    for _m in sorted(m.name for m in pkgutil.iter_modules([str(HERE)]) if m.name.startswith('rows_q222_')):
        importlib.import_module(_m)   # Q222 rows (z_part_ids / geometry requests)
    pats = {r["id"]: r["z_part_ids"] for r in rows_common.ROWS}
    struct_pats = defaultdict(list)
    for r in rows_common.ROWS:
        for p in r["z_part_ids"]:
            struct_pats[r["structure_id"]].append(p)
    for p in parts:
        p["_zpats"] = pats[p["id"]]
        p["_structure_zpats"] = sorted(set(struct_pats[p["structure_id"]]))
    keys = a.bodies.split(",")
    bodies = {k: Body(k) for k in keys}
    if not a.skip_validation:
        val = validate_rules(bodies, parts)
        (REPO / "data/derived/Q219_rule_validation.json").write_text(json.dumps(val, indent=1) + "\n")
    for k in keys:
        body = bodies[k]
        placed, text_only = [], []
        for p in parts:
            g = p["geometry"]
            rule = (g or {}).get("rule")
            sides = ("r", "l")
            if rule == "deltoid_sector":
                # own bodies: single mesh, rule fails validation -> text only; Z bodies: the part meshes are placed through z_part_mesh below
                if body.kind == "zan":
                    rule = "z_part_mesh"
                else:
                    text_only.append(dict(part_id=p["id"], reason="single deltoid mesh on this body; the azimuth sector rule has 6-40 mm centroid error against the Z parts (Q219_rule_validation.json) -> not placed"))
                    continue
            if rule == "gastrocnemius_sector":
                text_only.append(dict(part_id=p["id"], reason="no validated sector rule (Z-Anatomy has no separate gastrocnemius head meshes to validate against)"))
                continue
            if not rule:
                text_only.append(dict(part_id=p["id"], reason="no geometry rule defined for this part (text-only part)" if True else ""))
                continue
            if rule == "z_part_mesh" and body.kind == "own":
                text_only.append(dict(part_id=p["id"], reason="Z-Anatomy part mesh rule; this body is an own reconstruction without a separate mesh for this part"))
                continue
            fn = RULES[rule]
            any_ok = False; whys = []
            for s in sides:
                try:
                    r, why = fn(body, p, s)
                except Exception as e:  # keep the run going; the reason is recorded
                    r, why = None, f"error: {type(e).__name__}: {e}"
                if r:
                    r.update(dict(part_id=p["id"], structure_id=p["structure_id"], side=s, rule=rule, part_type=p["part_type"], verification=p["verification"]))
                    placed.append(r); any_ok = True
                else:
                    whys.append(f"{s}: {why}")
            if not any_ok:
                text_only.append(dict(part_id=p["id"], reason="; ".join(whys), rule_tried=rule))
            elif whys:
                text_only.append(dict(part_id=p["id"], reason="one side only: " + "; ".join(whys), rule_tried=rule, partial=True))
        out = dict(schema="nmsk.parts_geometry.v1", body=k, label=G.BODIES[k]["label"], generated=dt.date.today().isoformat(), frame=FRAME,
                   source=str(Path(G.BODIES[k]["path"]).relative_to(REPO)),
                   source_classes=dict(rule_based="rule applied to this body's own mesh by a documented rule with a published or measured error",
                                       z_fill="position of a dedicated Z-Anatomy part mesh as fitted to this body (not segmented from the person)",
                                       transferred="not used in phase 1", measured="never used: no part boundary is measured from the person's own labelled evidence"),
                   counts=dict(placed=len(placed), parts_with_a_placement=len({x["part_id"] for x in placed}), text_only=len([t for t in text_only if not t.get("partial")]),
                               placed_by_rule=dict(Counter(x["rule"] for x in placed)), placed_by_class=dict(Counter(x["source_class"] for x in placed))),
                   placed=placed, text_only=text_only)
        (REPO / a.out.format(k=k)).write_text(json.dumps(out, indent=1) + "\n")
        print(k, out["counts"])


if __name__ == "__main__":
    main()
