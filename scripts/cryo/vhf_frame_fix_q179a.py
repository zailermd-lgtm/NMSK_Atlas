"""Q179a (owner decision (a) on the Q179 audit): her Q48 thigh muscles moved by the SAME per-level, per-side translation as her
photo-tracked outlines, so both land on her femur-registered photographs.

Her tracked outlines (Q53 sciatic, Q55 femoral, Q56 popliteal) AND her Q48 thigh muscles (the male's lower-limb muscles transferred
onto her bones, then refined to her photographed septa) were built in her 1 mm cryosection frame, which was lost with a container
reset. Q179 re-registered the photographs to her CT femur and reconstructed the lost frame's shift per level and side
(data/ct_sources/task_outputs/vhf_tracked_reg_q179.json "sides": atlas dx, dz per level). This script applies that translation to
the Q48 meshes (vertex by vertex at the vertex's own y, linearly interpolated between the 1 mm levels; full weight over the levels
the shift was measured on, y +14 .. -386, faded linearly to zero over 20 mm beyond so the hip / leg ends join the unmoved geometry),
then (optionally) a bounded Q177-style face snap where tracked structures still enter a muscle.

    python3 scripts/cryo/vhf_frame_fix_q179a.py shift                    # field + ids -> task_outputs/vhf_q48_frame_fix_q179a.json
    python3 scripts/cryo/vhf_frame_fix_q179a.py apply [--if-stale]       # -> build/vh/xfer_vhm2vhf_sep_q179a (byte-reproducible)
    python3 scripts/cryo/vhf_frame_fix_q179a.py measure --crops DIR      # photo share, overlaps, snap -> vhf_q48_snap_q179a.npz
    python3 scripts/cryo/vhf_frame_fix_q179a.py badge-tracked            # badges on ct_vhf_nerve / ct_vhf_femoral / ct_vhf_popliteal*
    python3 scripts/cryo/vhf_frame_fix_q179a.py verify --crops DIR --old-bundle OLD.json   # after the rebuild

No photographs are needed for shift / apply / badge-tracked (the rebuild runs only those).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import trimesh

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.cryo import vhf_tracked_q179 as Q  # noqa: E402
from scripts.cryo import vhm_thigh_fat_plane_snap as SNAP  # noqa: E402

T = REPO / "data/ct_sources/task_outputs"
VH = REPO / "build/vh"
OUT_SUBJ = "xfer_vhm2vhf_sep_q179a"
STORE = T / "vhf_q48_frame_fix_q179a.json"
STORE_NPZ = T / "vhf_q48_snap_q179a.npz"
REPORT = REPO / "data/derived/Q179a_vhf_frame_fix.json"
# the Q48 subjects in vhf_rebuild_bundle.sh's --subject order (the first that carries an id wins it in the bundle)
SOURCES = ("ct_vhf_xfersepta_fix_contfix", "ct_vhf_xfersepta_fix", "xfer_vhm2vhf_sep_contfix_mesh", "xfer_vhm2vhf_sep_contfix",
           "xfer_vhm2vhf_sep")
RAMP_MM = 20.0
SNAP_MAX_DVOL_PCT = 5.0
SOURCE = ("U.S. National Library of Medicine, The Visible Human Project (public domain): her colour cryosections at full resolution (0.33 mm, "
          "NCI Imaging Data Commons) re-streamed by scripts/cryo/vhm_stream_leg_crops.py --body vhf and registered to her CT femur (Q179); "
          "her thigh muscles = the male's (DU lower-extremity release, Andreassen TE et al., Sci Data 10:34 (2023), CC BY 4.0) transferred "
          "onto her and refined to her septa (Q48); her tracked outlines Q53/Q55/Q56. Derived data (scripts/cryo/vhf_frame_fix_q179a.py).")
TRACK_SUBJ = {"sciatic_n": "ct_vhf_nerve", "femoral_a_r": "ct_vhf_femoral", "femoral_v_r": "ct_vhf_femoral", "femoral_n": "ct_vhf_femoral",
              "popliteal_a_r": "ct_vhf_popliteal_q179", "popliteal_v_r": "ct_vhf_popliteal_q179", "tibial_n": "ct_vhf_popliteal"}


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def side_of(aid):
    return "right" if aid.endswith("_r") else "left"


# ------------------------------------------------------------------------------------------------ the field
def build_field():
    """per side: the Q179 lost-frame translation (atlas dx, dz per 1 mm level) times the weight (1 on the measured levels, linear
    to 0 over RAMP_MM beyond them -- the table's own padding rows, which only repeat its end values)."""
    d = json.loads(Q.REG_JSON.read_text()); lo, hi = min(d["levels_with_features"]), max(d["levels_with_features"]); out = {}
    for side, rows in d["sides"].items():
        ys = np.array(sorted(int(y) for y in rows)); w = np.clip(1 - np.maximum(np.maximum(ys - hi, lo - ys), 0) / RAMP_MM, 0, 1)
        dx = np.array([rows[str(y)]["atlas_dx_dz_mm"][0] for y in ys]) * w; dz = np.array([rows[str(y)]["atlas_dx_dz_mm"][1] for y in ys]) * w
        out[side] = {"y": ys.tolist(), "dx": np.round(dx, 4).tolist(), "dz": np.round(dz, 4).tolist(), "weight": np.round(w, 4).tolist()}
    return out, [lo, hi]


def disp(v, fs):
    y = np.asarray(fs["y"], float)
    return np.c_[np.interp(v[:, 1], y, fs["dx"]), np.zeros(len(v)), np.interp(v[:, 1], y, fs["dz"])]


def winners():
    """{aid: (subject, [(structure, v, f), ...])} for every Q48 id, from the first SOURCES subject carrying it."""
    out = {}
    for sub in SOURCES:
        d = VH / sub
        if not (d / "manifest.json").exists():
            continue
        m, V, F = SNAP.load_subject(d); here = {}
        for s in m["structures"]:
            if s["atlas_id"] in out:
                continue
            v = V[s["vertex_offset"]:s["vertex_offset"] + s["vertex_count"]].astype(np.float64)
            f = F[s["face_offset"]:s["face_offset"] + s["triangle_count"]].astype(np.int64) - s["vertex_offset"]
            here.setdefault(s["atlas_id"], []).append((s, v, f))
        for aid, p in here.items():
            out[aid] = (sub, p)
    return out


def edge_stats(v0, v1, f):
    e = np.unique(np.sort(np.r_[f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]], 1), axis=0)
    l0 = np.linalg.norm(v0[e[:, 0]] - v0[e[:, 1]], axis=1); l1 = np.linalg.norm(v1[e[:, 0]] - v1[e[:, 1]], axis=1); ok = l0 > 1e-6
    r = l1[ok] / l0[ok]
    return {"edge_stretch_max": round(float(r.max()), 4), "edge_shrink_min": round(float(r.min()), 4),
            "edge_length_change_max_mm": round(float(np.abs(l1 - l0).max()), 3)}


def do_shift(a):
    field, full = build_field(); W = winners(); ids = {}; stats = {}
    for aid in sorted(W):
        sub, pieces = W[aid]; fs = field[side_of(aid)]
        allv = np.concatenate([v for _, v, _ in pieces]); D = disp(allv, fs); mag = np.linalg.norm(D, axis=1)
        if not (mag > 1e-6).any():
            continue
        ids[aid] = {"subject": sub, "pieces": len(pieces), "source_md5": {k: md5(VH / sub / k) for k in ("manifest.json", "vertices.f32", "faces.u32")}}
        es = [edge_stats(v, v + disp(v, fs), f) for _, v, f in pieces]
        vol0 = sum(SNAP.vol_cm3(v, f) for _, v, f in pieces); vol1 = sum(SNAP.vol_cm3(v + disp(v, fs), f) for _, v, f in pieces)
        mv = mag[mag > 1e-6]
        stats[aid] = {"subject": sub, "side": side_of(aid), "vertices": int(len(allv)), "moved_vertices": int(len(mv)),
                      "y_range": [round(float(allv[:, 1].min()), 1), round(float(allv[:, 1].max()), 1)],
                      "shift_mm": {"median": round(float(np.median(mv)), 2), "max": round(float(mv.max()), 2), "min": round(float(mv.min()), 3)},
                      "volume_cm3": [round(vol0, 2), round(vol1, 2)], "volume_change_pct": round(100 * (vol1 - vol0) / vol0, 3),
                      "edge_stretch_max": max(e["edge_stretch_max"] for e in es), "edge_shrink_min": min(e["edge_shrink_min"] for e in es),
                      "edge_length_change_max_mm": max(e["edge_length_change_max_mm"] for e in es)}
        print(aid, stats[aid], flush=True)
    grad = {}
    for side, fs in field.items():
        y = np.array(fs["y"], float); g = np.hypot(np.diff(fs["dx"]), np.diff(fs["dz"])) / np.abs(np.diff(y)); grad[side] = round(float(g.max()), 3)
    old = json.loads(STORE.read_text()) if STORE.exists() else {}
    store = {"source": SOURCE, "_README": "Q179a: the translation applied to her Q48 thigh-muscle meshes (vhf_frame_fix_q179a.py apply). field[side]: "
             "atlas y (1 mm levels) -> dx, dz (atlas mm) = vhf_tracked_reg_q179.json 'sides' atlas_dx_dz_mm x weight (1 on the measured "
             f"levels y {full[1]}..{full[0]}, linear to 0 over {RAMP_MM:.0f} mm beyond); a vertex takes np.interp of it at its own y. ids: "
             "the moved ids, each from the first Q48 subject (rebuild order) that carries it; badges: the text apply stamps.",
             "reg_json_md5": md5(Q.REG_JSON), "full_weight_levels": full, "ramp_mm": RAMP_MM, "field": field, "ids": ids,
             "max_shift_gradient_mm_per_mm": grad, "stats": stats, "badges": old.get("badges", {})}
    STORE.write_text(json.dumps(store, indent=1))
    print("wrote", STORE.name, len(ids), "ids; max shift gradient (mm per mm of y)", grad)


# ------------------------------------------------------------------------------------------------ apply
BADGE_SHIFT = ("Moved {med:.1f} mm (median; max {mx:.1f} mm) with the frame it was built in (Q179a): its septa were fitted (Q48) on her "
               "cryosections in the same 1 mm frame her tracked nerves and vessels were traced in, and that frame was lost; re-registering her "
               "photographs to her CT femur (femur contour on the photographed bone edge, per level and side) measured the offset, and this "
               "muscle was translated level by level by it (faded to zero over 20 mm above y +14 / below y -386 where it was not measured). "
               "Volume unchanged ({v0:.1f} cm3).")
BADGE_SNAP = (" Then its {face} face, where her tracked {what} still entered it, moved inward onto the fat plane photographed in her 0.33 mm "
              "cryosections (Q177 rule, her muscle colour; median {med:.2f} / max {mx:.2f} mm, volume {dv:+.1f} %).")


def stamp():
    h = hashlib.md5(STORE.read_bytes() + (STORE_NPZ.read_bytes() if STORE_NPZ.exists() else b"")).hexdigest()
    return f"q179a-store-{h}"


def build_pieces(store=None, npz=None, W=None):
    store = store or json.loads(STORE.read_text()); W = W or winners(); out = {}
    D = dict(np.load(STORE_NPZ)) if npz is None and STORE_NPZ.exists() else (npz or {})
    for aid, info in store["ids"].items():
        sub, pieces = W[aid]
        assert sub == info["subject"] and len(pieces) == info["pieces"], (aid, sub, info["subject"])
        fs = store["field"][side_of(aid)]; out[aid] = []
        for i, (s, v, f) in enumerate(pieces):
            v1 = v + disp(v, fs); key = f"{aid}#{i}"
            if key in D:
                assert len(D[key]) == len(v1), key
                v1 = v1 - D[key][:, None] * SNAP.outward_normals(v1, f)
            out[aid].append((s, v1, f))
    return out


def do_apply(a):
    if not STORE.exists():
        print("no", STORE.name); return
    d = VH / OUT_SUBJ; st = stamp()
    if a.if_stale and (d / "manifest.json").exists() and st in (d / "manifest.json").read_text():
        print("have", OUT_SUBJ); return
    store = json.loads(STORE.read_text()); W = winners()
    for aid, info in store["ids"].items():
        for k, h in info["source_md5"].items():
            if md5(VH / info["subject"] / k) != h:
                print(f"WARNING: {info['subject']}/{k} changed since the shift was stored (Q179a)", file=sys.stderr); break
    pcs = build_pieces(store, W=W); vs, fs_, structs = [], [], []; vo = fo = 0
    for aid in sorted(pcs):
        for s, v, f in pcs[aid]:
            e = {k: s[k] for k in ("atlas_id", "side", "source_structure") if k in s}
            e.update(source_file=f"{store['ids'][aid]['subject']}#{s.get('source_file', aid)} + Q179a frame fix", vertex_offset=vo, face_offset=fo,
                     vertex_count=int(len(v)), triangle_count=int(len(f)), bbox_min_mm=[round(float(x), 4) for x in v.min(0)],
                     bbox_max_mm=[round(float(x), 4) for x in v.max(0)])
            b = store["badges"].get(aid)
            if b:
                e["procedural_badge"] = ((s["procedural_badge"] + " ") if s.get("procedural_badge") else "") + b
            elif s.get("procedural_badge"):
                e["procedural_badge"] = s["procedural_badge"]
            structs.append(e); vs.append(v.astype(np.float32)); fs_.append((f + vo).astype(np.uint32)); vo += len(v); fo += len(f)
    Vall = np.concatenate(vs); Fall = np.concatenate(fs_); d.mkdir(parents=True, exist_ok=True)
    (d / "vertices.f32").write_bytes(Vall.tobytes()); (d / "faces.u32").write_bytes(Fall.tobytes())
    srcm = json.loads((VH / "xfer_vhm2vhf_sep" / "manifest.json").read_text())
    man = {"subject": OUT_SUBJ, "frame": srcm["frame"], "source_volume": None,
           "source_kind": "Q48 meshes (xfer_vhm2vhf_sep and its Q115/Q152 fixes) translated by her photographs' lost-frame offset (Q179a)",
           "vertex_count": int(len(Vall)), "triangle_count": int(len(Fall)),
           "bbox_min_mm": [round(float(x), 4) for x in Vall.min(0)], "bbox_max_mm": [round(float(x), 4) for x in Vall.max(0)],
           "attribution": srcm.get("attribution", []), "note": f"scripts/cryo/vhf_frame_fix_q179a.py apply; {st}", "structures": structs}
    (d / "manifest.json").write_text(json.dumps(man, indent=1))
    print("wrote", d, len(structs), "pieces,", len(pcs), "ids,", len(Vall), "vertices")


# ------------------------------------------------------------------------------------------------ measurement helpers
def all_muscles(bundle_json, moved=None):
    """full-res meshes of every thigh-region muscle, from the subject that wins it in the bundle (moved ids replaced)."""
    b = json.loads(Path(bundle_json).read_text()); cache = {}; M = {}
    for e in b["structures"]:
        aid = e["id"]
        if not any(w in aid for w in Q.MUSCLE_WORDS) or "tendon" in aid:
            continue
        if moved is not None and aid in moved:
            v, f = moved[aid]
        else:
            sub = e["subject"]
            if sub not in cache:
                cache[sub] = Q.subject_meshes(VH / sub)
            v, f = cache[sub][aid]
        M[aid] = {"v": v, "f": f}
    return M


def cat(pieces):
    vs, fs, o = [], [], 0
    for _, v, f in pieces:
        vs.append(v); fs.append(f + o); o += len(v)
    return np.concatenate(vs), np.concatenate(fs)


def photo_muscle_share(crops, v, f, side, skip, ys):
    """area share of the mesh section on her photographed muscle (her rule, 3 x 3 majority), 1 mm grid, per level."""
    from PIL import Image, ImageDraw
    ph = Q.HerMusclePhoto(crops, side, skip); tm = trimesh.Trimesh(v, f, process=False); rows = []
    for y in ys:
        k = ph.mask(y)
        if k is None or tm.bounds[0, 1] > y or tm.bounds[1, 1] < y:
            continue
        s = tm.section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0])
        if s is None:
            continue
        img = Image.new("L", (k.shape[1], k.shape[0]), 0); dr = ImageDraw.Draw(img); n = 0
        for e in s.entities:
            p = s.vertices[e.points]; pr, pc = ph.c.atlas_to_px(y, p[:, 0], p[:, 2])
            if len(p) >= 3:
                dr.polygon(list(zip(pc.tolist(), pr.tolist())), fill=1, outline=None); n += 1
        m = np.asarray(img, bool)
        if m.sum() < 50:
            continue
        rows.append({"y": int(y), "area_px": int(m.sum()), "on_muscle": float(k[m].mean())})
    if not rows:
        return None
    w = np.array([r["area_px"] for r in rows], float)
    return {"levels": len(rows), "on_photographed_muscle": round(float(np.average([r["on_muscle"] for r in rows], weights=w)), 4)}


class HerPhoto:
    """SNAP.snap's photo sampler on her crops: 3 = photographed muscle (her rule), 1 = not, 255 = unknown/unusable."""
    def __init__(self, crops, skip):
        self.ph = {s: Q.HerMusclePhoto(crops, s, skip[s]) for s in ("right", "left")}

    def sample(self, P):
        P = np.asarray(P, float); out = np.full(len(P), 255, np.uint8); ys = np.rint(P[:, 1]).astype(int)
        for side, sel in (("right", P[:, 0] > 0), ("left", P[:, 0] <= 0)):
            for y in np.unique(ys[sel]):
                k = self.ph[side].mask(y)
                if k is None:
                    continue
                s = sel & (ys == y); pr, pc = self.ph[side].c.atlas_to_px(y, P[s, 0], P[s, 2]); pr = np.rint(pr).astype(int); pc = np.rint(pc).astype(int)
                ok = (pr >= 0) & (pc >= 0) & (pr < k.shape[0]) & (pc < k.shape[1]); o = np.full(s.sum(), 255, np.uint8)
                o[ok] = np.where(k[pr[ok], pc[ok]], 3, 1); out[s] = o
        return out


def depth_inside(tm, P):
    ins = tm.contains(P); d = np.zeros(len(P))
    if ins.any():
        d[ins] = trimesh.proximity.closest_point(tm, P[ins])[1]
    return d


# ------------------------------------------------------------------------------------------------ measure (+ snap)
def do_measure(a):
    """before/after on the full-res meshes: tracked-in-muscle, muscle-in-bone, muscle share on photographed muscle; then the bounded
    Q177 face snap of every moved muscle a tracked structure still enters > 1 mm (> 5 % volume change = not stored for that muscle)."""
    from scripts.cryo.vhm_tracked_clip import overlap
    store = json.loads(STORE.read_text()); W = winners(); skip = Q.unusable(a.crops)
    pcs0 = {aid: W[aid][1] for aid in store["ids"]}; pcs1 = build_pieces(store, npz={}, W=W)
    moved1 = {aid: cat(p) for aid, p in pcs1.items()}
    bj = str(REPO / "build/viewer_f_hr/bundle.json")
    M0 = all_muscles(bj); M1 = all_muscles(bj, moved1)
    tr_old = {}; tr_new = {}
    for sub in ("ct_vhf_nerve", "ct_vhf_femoral", "ct_vhf_popliteal"):
        tr_old.update(Q.subject_meshes(Path(a.old_subjects) / sub))
    for aid, sub in TRACK_SUBJ.items():
        tr_new[aid] = Q.subject_meshes(VH / sub)[aid]
    rep = json.loads(REPORT.read_text()) if REPORT.exists() else {}
    res = {"tracked_in_muscle_fullres": {}, "muscle_in_bone_fullres": {}, "muscle_share": {}}
    for aid in Q.TRACKED:
        r0 = overlap(tr_old[aid][0], M0, Q.MUSCLE_WORDS); r1 = overlap(tr_new[aid][0], M1, Q.MUSCLE_WORDS)
        res["tracked_in_muscle_fullres"][aid] = {"before": r0, "after": r1}
        print(aid, "full-res >1mm in muscle", r0["beyond_1mm_any"], "->", r1["beyond_1mm_any"], "of", r0["vertices"], "/", r1["vertices"],
              "max", r0["max_depth_mm"], "->", r1["max_depth_mm"], {k: v["beyond_1mm"] for k, v in r1["per_mesh"].items() if v["beyond_1mm"]}, flush=True)
    from scripts.transfer.bundle_io import read_bundle_dir, meshes_by_id
    bf, blob = read_bundle_dir(str(REPO / "build/viewer_f_hr")); B = meshes_by_id(bf, blob)
    bones = {k: trimesh.Trimesh(np.asarray(B[k]["v"], float), np.asarray(B[k]["f"]), process=False) for k in Q.BONES if k in B}
    for aid in store["ids"]:
        v0, f0 = cat(pcs0[aid]); v1, _ = moved1[aid]; row = {}
        for bn, tm in bones.items():
            if (tm.bounds[1] < v0.min(0) - 15).any() or (tm.bounds[0] > v0.max(0) + 15).any():
                continue
            d0 = depth_inside(tm, v0); d1 = depth_inside(tm, v1)
            if (d0 > 0).any() or (d1 > 0).any():
                row[bn] = {"beyond_1mm": [int((d0 > 1).sum()), int((d1 > 1).sum())], "max_depth_mm": [round(float(d0.max()), 2), round(float(d1.max()), 2)]}
        res["muscle_in_bone_fullres"][aid] = row
        sh = {}
        for nm, (v, f) in (("before", (v0, f0)), ("after", moved1[aid])):
            ys = range(min(40, int(v[:, 1].max())), max(-420, int(v[:, 1].min())) - 1, -10)
            sh[nm] = photo_muscle_share(a.crops, v, f, side_of(aid), skip[side_of(aid)], ys)
        res["muscle_share"][aid] = sh
        print(aid, "bone", row, "share", sh, flush=True)
    # bounded Q177 snap where a tracked structure still enters a moved muscle > 1 mm
    snap = {}; D_store = {}
    if not a.no_snap:
        P_all = {aid: tr_new[aid][0] for aid in Q.TRACKED if aid != "tibial_n" or a.tibial_moved}
        for mid in sorted(store["ids"]):
            v, f = moved1[mid]; tm = trimesh.Trimesh(v, f, process=False); ent = []
            for tid, P in P_all.items():
                P = P[(P[:, 0] > 0) == (side_of(mid) == "right")]; lo, hi = v.min(0) - 2, v.max(0) + 2; P = P[((P > lo) & (P < hi)).all(1)]
                if len(P) and (depth_inside(tm, P) > 1.0).any():
                    ent.append(tid)
            if not ent:
                continue
            P = np.concatenate([tr_new[t][0] for t in ent]); P = P[(P[:, 0] > 0) == (side_of(mid) == "right")]
            lo, hi = v.min(0) - 2, v.max(0) + 2; P = P[((P > lo) & (P < hi)).all(1)]; d = depth_inside(tm, P); keep = d > 0.5
            cp, _, fi = trimesh.proximity.closest_point(tm, P[keep]); n = tm.face_normals[fi] * (1 if tm.volume > 0 else -1)
            dirv = n.mean(0); dirv[1] = 0; dirv /= np.linalg.norm(dirv); yl, yh = P[keep, 1].min() - 2, P[keep, 1].max() + 2
            row = {"entered_by": ent, "dir_xz": [round(float(dirv[0]), 3), round(float(dirv[2]), 3)], "y_range": [round(float(yl), 1), round(float(yh), 1)],
                   "tracked_beyond_1mm_before": int((d > 1).sum()), "max_before": round(float(d.max()), 2), "pieces": {}}
            o = 0; Ds = []
            for i, (s, pv, pf) in enumerate(pcs1[mid]):
                Dp, info = SNAP.snap(pv, pf, HerPhoto(a.crops, skip), tuple(dirv), nz_min=0.5, y_range=(yl, yh), prefix_known=True)
                Ds.append(Dp); row["pieces"][str(i)] = {"move": SNAP.surface_move_stats(Dp, info["surface_vertices"]), "info": info}
            v2 = np.concatenate([pv - Dp[:, None] * SNAP.outward_normals(pv, pf) for (s, pv, pf), Dp in zip(pcs1[mid], Ds)])
            v0_, v1_ = SNAP.vol_cm3(v, f), SNAP.vol_cm3(v2, f); row["volume_cm3"] = [round(v0_, 2), round(v1_, 2)]
            row["dvol_pct"] = round(100 * (v1_ - v0_) / v0_, 2); d2 = depth_inside(trimesh.Trimesh(v2, f, process=False), P)
            row["tracked_beyond_1mm_after"] = int((d2 > 1).sum()); row["max_after"] = round(float(d2.max()), 2)
            allD = np.concatenate(Ds); row["move"] = SNAP.surface_move_stats(allD, int(sum(p["info"]["surface_vertices"] for p in row["pieces"].values())))
            if abs(row["dvol_pct"]) > SNAP_MAX_DVOL_PCT:
                row["status"] = f"STOP: volume change > {SNAP_MAX_DVOL_PCT:.0f} % -- not stored, translation only"
            elif row["move"]["moved_vertices"] == 0:
                row["status"] = "nothing moved"
            else:
                row["status"] = "stored"
                for i, Dp in enumerate(Ds):
                    D_store[f"{mid}#{i}"] = Dp.astype(np.float64)
            snap[mid] = row; print(mid, {k: v for k, v in row.items() if k != "pieces"}, flush=True)
        if D_store:
            np.savez_compressed(STORE_NPZ, **D_store)
        elif STORE_NPZ.exists():
            STORE_NPZ.unlink()
    res["snap"] = snap
    # badges
    badges = {}
    words = {"sciatic_n": "sciatic nerve", "femoral_a_r": "femoral artery", "femoral_v_r": "femoral vein", "femoral_n": "femoral nerve",
             "popliteal_a_r": "popliteal artery", "popliteal_v_r": "popliteal vein", "tibial_n": "tibial nerve"}
    for aid, st in store["stats"].items():
        if aid not in store["ids"]:
            continue
        b = BADGE_SHIFT.format(med=st["shift_mm"]["median"], mx=st["shift_mm"]["max"], v0=st["volume_cm3"][0])
        sr = snap.get(aid)
        if sr and sr["status"] == "stored":
            ang = np.degrees(np.arctan2(sr["dir_xz"][1], sr["dir_xz"][0] if aid.endswith("_r") else -sr["dir_xz"][0])) % 360
            b += BADGE_SNAP.format(face=SNAP.dir_name(ang), what=" / ".join(words[t] for t in sr["entered_by"]), med=sr["move"]["median_mm"],
                                   mx=sr["move"]["max_mm"], dv=sr["dvol_pct"])
        badges[aid] = b
    store["badges"] = badges; STORE.write_text(json.dumps(store, indent=1))
    rep.update({"source": SOURCE, "task": "Q179a: her Q48 thigh muscles moved with her tracked outlines onto the femur-registered photographs",
                "measure_fullres": res})
    REPORT.write_text(json.dumps(rep, indent=1))


# ------------------------------------------------------------------------------------------------ tracked-structure badges
BADGE_TRACKED = ("Placed (Q179a) on her photographs as re-registered to her CT femur: it was traced in her 1 mm cryosection frame, which was "
                 "lost; the frame's offset was reconstructed from the traced outlines of both legs against their photographed features "
                 "(femur registration taken out) and the outline moved by it ({how}); then clipped to her photographed non-muscle (Q176 rule, "
                 "her calibrated muscle colour){interp}. Her thigh muscles were moved by the same offset.")
BADGE_TIBIAL = ("Kept as traced (Q56) in her lost 1 mm frame: moving it with that frame's offset does not put it on the photographed tibial "
                "nerve -- the traced outline follows a structure ~12 mm lateral of the nerve seen in her photographs (a tracking error, not "
                "the frame); her thigh muscles around it were moved (Q179a), so it may sit partly inside them.")


def do_badge_tracked(a):
    reg = json.loads(Q.REG_JSON.read_text()); rep = json.loads(Q.REPORT.read_text())
    howr = lambda s: {"sciatic": "per level and side, median {:.1f} mm".format(np.median([np.hypot(*v["atlas_dx_dz_mm"]) for v in reg["sides"][s].values()]))}
    txt = {"sciatic_n": BADGE_TRACKED.format(how="per level and side: right median {:.1f} mm, left {:.1f} mm".format(
               np.median([np.hypot(*v["atlas_dx_dz_mm"]) for y, v in reg["sides"]["right"].items() if -386 <= int(y) <= 14]),
               np.median([np.hypot(*v["atlas_dx_dz_mm"]) for y, v in reg["sides"]["left"].items() if -386 <= int(y) <= 14])),
               interp="; her photographs at y -127..-131 (right) / -127..-132 (left) are unusable (blank, gel spill, frost) and the nerve there "
                      "is interpolated between the neighbouring traced levels")}
    for g, ids in (("femoral", ("femoral_a_r", "femoral_v_r", "femoral_n")), ("popliteal", ("popliteal_a_r", "popliteal_v_r"))):
        dx, dz = reg["groups"][g]["atlas_dx_dz_mm"]
        for aid in ids:
            clip = " (arteries are not clipped: their wall photographs as muscle)" if aid.endswith("_a_r") else ""
            txt[aid] = BADGE_TRACKED.format(how=f"one translation for the {g} group, {np.hypot(dx, dz):.1f} mm", interp=clip)
    txt["tibial_n"] = BADGE_TIBIAL
    done = []
    for sub in sorted(set(TRACK_SUBJ.values())):
        p = VH / sub / "manifest.json"
        if not p.exists():
            continue
        m = json.loads(p.read_text()); ch = False
        for st in m["structures"]:
            b = txt.get(st["atlas_id"])
            if b and st.get("procedural_badge") != b and TRACK_SUBJ.get(st["atlas_id"]) == sub:
                st["procedural_badge"] = b; ch = True; done.append(st["atlas_id"])
        if ch:
            p.write_text(json.dumps(m, indent=1))
    print("badged", sorted(set(done)))


# ------------------------------------------------------------------------------------------------ verify (after the rebuild)
def do_verify(a):
    from scripts.cryo.vhm_tracked_clip import overlap
    from scripts.transfer.bundle_io import read_bundle_dir, meshes_by_id
    bdir = REPO / (a.bundle or "build/viewer_f_hr"); bf, blob = read_bundle_dir(str(bdir)); B = meshes_by_id(bf, blob)
    ob = json.loads(Path(a.old_bundle).read_text()); oblob = Path(a.old_bundle).with_suffix(".bin").read_bytes(); O = meshes_by_id(ob, oblob)
    h = lambda m: hashlib.md5(np.ascontiguousarray(m["v"], np.float32).tobytes() + np.ascontiguousarray(m["f"], np.int64).tobytes()).hexdigest()
    new_ids = {e["id"] for e in bf["structures"]}; old_ids = {e["id"] for e in ob["structures"]}
    changed = sorted(i for i in new_ids & old_ids if h(B[i]) != h(O[i]))
    meta = {e["id"]: json.dumps(e.get("rec", {}), sort_keys=True) for e in bf["structures"]}
    ometa = {e["id"]: json.dumps(e.get("rec", {}), sort_keys=True) for e in ob["structures"]}
    rep = json.loads(REPORT.read_text()); store = json.loads(STORE.read_text())
    intended = set(store["ids"]) | {k for k, v in TRACK_SUBJ.items() if v != "ct_vhf_popliteal"}
    out = {"ids_added": sorted(new_ids - old_ids), "ids_removed": sorted(old_ids - new_ids), "geometry_changed": changed,
           "geometry_changed_unintended": sorted(set(changed) - intended), "intended_unchanged": sorted(intended - set(changed)),
           "metadata_changed": sorted(i for i in new_ids & old_ids if meta[i] != ometa.get(i)),
           "structures": [len(ob["structures"]), len(bf["structures"])], "triangles": [ob.get("triangles"), bf.get("triangles")]}
    Mo = {k: v for k, v in O.items() if any(w in k for w in Q.MUSCLE_WORDS)}; Mn = {k: v for k, v in B.items() if any(w in k for w in Q.MUSCLE_WORDS)}
    tb = {}
    for aid in Q.TRACKED:
        r0 = overlap(np.asarray(O[aid]["v"], float), Mo, Q.MUSCLE_WORDS); r1 = overlap(np.asarray(B[aid]["v"], float), Mn, Q.MUSCLE_WORDS)
        b0 = overlap(np.asarray(O[aid]["v"], float), O, Q.BONES, exact=True); b1 = overlap(np.asarray(B[aid]["v"], float), B, Q.BONES, exact=True)
        tb[aid] = {"muscle": {"before": r0, "after": r1}, "bone_beyond_1mm": [b0["beyond_1mm_any"], b1["beyond_1mm_any"]],
                   "bone_max_mm": [b0["max_depth_mm"], b1["max_depth_mm"]]}
        print(aid, "bundle >1mm in muscle", r0["beyond_1mm_any"], "->", r1["beyond_1mm_any"], "max", r0["max_depth_mm"], "->", r1["max_depth_mm"],
              "bone", tb[aid]["bone_beyond_1mm"], flush=True)
    mb = {}
    for aid in store["ids"]:
        row = {}
        for bn in Q.BONES:
            if bn not in B:
                continue
            r0 = overlap(np.asarray(O[aid]["v"], float), {bn: O[bn]}, (bn,), exact=True); r1 = overlap(np.asarray(B[aid]["v"], float), {bn: B[bn]}, (bn,), exact=True)
            if r0["inside_any"] or r1["inside_any"]:
                row[bn] = {"beyond_1mm": [r0["beyond_1mm_any"], r1["beyond_1mm_any"]], "max_depth_mm": [r0["max_depth_mm"], r1["max_depth_mm"]]}
        # unmoved neighbour muscles (her own CT glutei / iliopsoas, the unmoved Q48 leg muscles)
        nb = {}
        for k in Mn:
            if k in store["ids"] or k == aid:
                continue
            r0 = overlap(np.asarray(O[aid]["v"], float), {k: O[k]}, (k,), exact=True); r1 = overlap(np.asarray(B[aid]["v"], float), {k: B[k]}, (k,), exact=True)
            if r0["beyond_1mm_any"] or r1["beyond_1mm_any"]:
                nb[k] = {"beyond_1mm": [r0["beyond_1mm_any"], r1["beyond_1mm_any"]], "max_depth_mm": [r0["max_depth_mm"], r1["max_depth_mm"]]}
        mb[aid] = {"bone": row, "unmoved_muscles": nb}
    out["tracked_bundle"] = tb; out["moved_muscles_bundle"] = mb
    rep["verify_bundle"] = out; REPORT.write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k not in ("tracked_bundle", "moved_muscles_bundle")}, indent=0)[:3000])


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("shift")
    p = sub.add_parser("apply"); p.add_argument("--if-stale", action="store_true")
    p = sub.add_parser("measure"); p.add_argument("--crops", required=True); p.add_argument("--old-subjects", required=True)
    p.add_argument("--no-snap", action="store_true"); p.add_argument("--tibial-moved", action="store_true")
    sub.add_parser("badge-tracked")
    p = sub.add_parser("verify"); p.add_argument("--old-bundle", required=True); p.add_argument("--bundle", default=None)
    a = ap.parse_args()
    {"shift": do_shift, "apply": do_apply, "measure": do_measure, "badge-tracked": do_badge_tracked, "verify": do_verify}[a.cmd](a)


if __name__ == "__main__":
    main()
