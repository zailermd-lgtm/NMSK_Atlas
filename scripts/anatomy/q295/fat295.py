"""Q295 fat build, step 1 (voxels): for every 1 mm axial level of a page, the space inside the page's skin (minus the skin layer) that no
visible structure covers, classified by the body's own imaging at that point (her CT HU / his cryosection colour; Base pages through the
Base -> Combined registration), split subcutaneous / deep and by body part (nearest bone in the slice).

    python3 fat295.py masks KEY [--src DIR]          -> /dev/shm/q295/fat/KEY_vox.npz
    python3 fat295.py mesh KEY [--budget 250000]     -> /dev/shm/q295/fat/KEY_fat.npz (+ report json)
"""
from __future__ import annotations
import argparse, json, re, sys, time
from pathlib import Path
import numpy as np
from scipy import ndimage as ndi

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sl295 as S  # noqa: E402
import audit295 as A  # noqa: E402

OUT = Path("/dev/shm/q295/fat")
RES = 1.0
PROPAGATE_MM = 20.0
# part ids: 1.. ; (name, region)
TRUNK_PARTS = ["head", "neck", "thorax", "abdomen", "pelvis"]
LIMB_PARTS = ["upper_arm", "forearm", "hand", "thigh", "leg", "foot"]
PARTS = TRUNK_PARTS + [f"{p}_{s}" for p in LIMB_PARTS for s in "rl"]
PIDX = {p: i + 1 for i, p in enumerate(PARTS)}
HUM = re.compile(r'humer'); FORE = re.compile(r'radius|ulna'); THI = re.compile(r'femur|patella')
LEGB = re.compile(r'tibia|fibul')


def bone_part(bid):
    side = "r" if re.search(r'_r(_|$)|_r_zfill', bid) or bid.endswith("_r") else ("l" if re.search(r'_l(_|$)|_l_zfill', bid) or bid.endswith("_l") else None)
    if side is None:
        return None
    if HUM.search(bid): return f"upper_arm_{side}"
    if FORE.search(bid): return f"forearm_{side}"
    if A.HAND.search(bid): return f"hand_{side}"
    if THI.search(bid): return f"thigh_{side}"
    if LEGB.search(bid): return f"leg_{side}"
    if A.FOOT.search(bid): return f"foot_{side}"
    return None


def masks(key, src=None):
    import oracle295 as O
    t0 = time.time()
    pg = S.Page(key, src); orc = O.make(A.BODY[key]); reg = None
    if A.BODY[key] == "vhm" and key.startswith("base"):
        orc.precompute()
    if key.startswith("base"):
        import reg295 as RG
        reg = RG.fast(key, pg, RG.build(key, pg, S.Page(RG.PAIR[key])))
    skin = pg.sid_where(lambda k, c, n: c == 'skin')
    cnt = pg.sid_where(lambda k, c, n: c != 'skin'); cnt = cnt[~pg.hidden[cnt]]
    bones = pg.sid_where(lambda k, c, n: c == 'bone')
    bpart = np.zeros(len(pg.ids) + 1, np.int16)            # 0 = trunk
    for s in bones:
        p = bone_part(pg.ids[s]); bpart[s] = PIDX[p] if p else 0
    R = A.regions(pg)
    yb = {"head": R["head"][0] - 5, "neck": R["neck"][0] - 8, "thorax": R["thorax"][0] - 5, "abdomen": R["abdomen"][0] - 3}
    lo, hi = pg.bbox(skin)
    u0, v0 = lo[0] - 3, lo[2] - 3; W = int((hi[0] - lo[0] + 6) / RES); H = int((hi[2] - lo[2] + 6) / RES)
    ys = np.arange(np.ceil(lo[1]) + 0.5, hi[1], RES)
    grid = (u0, v0, RES, W, H)
    lab = np.zeros((len(ys), H, W), np.uint8)
    own_lookup = None; ident = {}
    if not key.startswith("own"):
        import ownvol295 as OV
        own_lookup = OV.Lookup(A.BODY[key])              # 0 none; part id (1..) | 64 if deep; 128 bit = soft-tissue void (not fat)
    jj, ii = np.mgrid[0:H, 0:W]
    stats = {"fat": 0, "soft": 0, "gas": 0, "unknown": 0, "propagated": 0, "void": 0, "body": 0}
    for li, y0 in enumerate(ys):
        body, cov, sl, bad = S.slice_page(pg, y0, grid, skin, cnt)
        body &= ~ndi.binary_dilation(~body, iterations=int(round(A.SKIN_MM / RES)))
        void = body & (cov == 0)
        stats["body"] += int(body.sum()); stats["void"] += int(void.sum())
        if not void.any():
            continue
        full, sh = O.slice_classes(orc, reg, grid, y0, body)
        cl = np.zeros((H, W), np.uint8); cl[void] = full[void]
        nsh = sum(1 for d in sh if d[0] or d[1]); stats["shifted_parts"] = stats.get("shifted_parts", 0) + nsh
        cl[void & (cl == 1)] = 9                           # 'air' inside the page body: registered point outside the VH body (or gas for her)
        valid = void & ((cl == 2) | (cl == 3))
        need = void & ~valid & (cl != 5)
        if need.any() and valid.any():
            d, (ai, aj) = ndi.distance_transform_edt(~valid, return_indices=True)
            ok = need & (d * RES <= PROPAGATE_MM)
            cl[ok] = cl[ai[ok], aj[ok]]; stats["propagated"] += int(ok.sum())
        if A.BODY[key] == "vhf" and not key.startswith("base"):
            cl[void & (cl == 9)] = 5                       # her CT: < -400 HU inside the body = gas / lung
        stats["fat"] += int((void & (cl == 2)).sum()); stats["soft"] += int((void & (cl == 3)).sum())
        stats["gas"] += int((void & (cl == 5)).sum()); stats["unknown"] += int((void & ~np.isin(cl, [2, 3, 5])).sum())
        # body part per pixel: nearest bone in the slice; trunk by level
        bl = np.where(np.isin(sl, bones), sl, -1)
        if (bl >= 0).any():
            _, (ni, nj) = ndi.distance_transform_edt(bl < 0, return_indices=True)
            part = bpart[bl[ni, nj]]
        else:
            part = np.zeros((H, W), np.int16)
        tr = "head" if y0 >= yb["head"] else "neck" if y0 >= yb["neck"] else "thorax" if y0 >= yb["thorax"] else "abdomen" if y0 >= yb["abdomen"] else "pelvis"
        part = np.where(part == 0, PIDX[tr], part)
        solid = (cov > 0) & body
        env = ndi.binary_fill_holes(ndi.binary_closing(solid, iterations=5))
        deep = env & void
        fat = void & (cl == 2); soft = void & (cl == 3)
        if own_lookup is not None and soft.any():
            Pm = O.slice_classes.last_P.reshape(H, W, 3)[soft]
            ids_ = own_lookup(Pm); pp = part[soft]
            key2 = pp.astype(np.int64) * 100000 + (ids_ + 1)
            u_, c_ = np.unique(key2, return_counts=True)
            for kk, cc in zip(u_.tolist(), c_.tolist()):
                ident[kk] = ident.get(kk, 0) + cc
        L = np.zeros((H, W), np.uint8)
        L[fat] = part[fat]; L[fat & deep] |= 64
        L[soft] = part[soft] | 128; L[soft & deep] |= 64
        lab[li] = L
        if li % 200 == 0:
            print(key, li, len(ys), round(time.time() - t0), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(OUT / f"{key}_vox.npz", lab=lab, origin=np.array([u0, ys[0], v0]), res=RES, parts=np.array(PARTS))
    if own_lookup is not None:
        idn = {}
        for kk, cc in ident.items():
            pi, sid = divmod(kk, 100000); sid -= 1
            nm = "(nothing segmented there either)" if sid < 0 else f"{own_lookup.names[sid]} [{own_lookup.cats[sid]}]"
            idn.setdefault(PARTS[pi - 1], {}); idn[PARTS[pi - 1]][nm] = idn[PARTS[pi - 1]].get(nm, 0) + cc
        stats["soft_void_identified_by_imaging_page_cm3"] = {p_: {k: round(v / 1000, 1) for k, v in sorted(d.items(), key=lambda x: -x[1])[:15]} for p_, d in idn.items()}
    stats["seconds"] = round(time.time() - t0)
    (OUT / f"{key}_vox.json").write_text(json.dumps(stats, indent=1))
    print(key, stats, flush=True)


# ------------------------------------------------------------------------------------------------ step 2: meshes
PRETTY = {"head": "head", "neck": "neck", "thorax": "thorax", "abdomen": "abdomen", "pelvis": "pelvis and perineum",
          "upper_arm": "arm", "forearm": "forearm", "hand": "hand", "thigh": "thigh", "leg": "leg", "foot": "foot"}
DEEP_NAME = {"head": "Deep fat of the head (orbital, buccal, deep facial)", "neck": "Deep cervical fat",
             "thorax": "Deep thoracic fat (mediastinal, paravertebral, axillary)", "abdomen": "Visceral and retroperitoneal fat (abdomen)",
             "pelvis": "Deep pelvic fat (ischioanal fossa, pelvic visceral, gluteal)", "upper_arm": "Intermuscular fat of the arm",
             "forearm": "Intermuscular fat of the forearm", "hand": "Deep fat of the hand (palmar, digital)",
             "thigh": "Intermuscular fat of the thigh and popliteal fossa", "leg": "Intermuscular fat of the leg (incl. popliteal, pre-Achilles)",
             "foot": "Deep fat of the foot (plantar, heel pad, sinus tarsi)"}


def units(lab):
    """(unit id, kind, part, voxel-value predicate) for every non-empty unit"""
    out = []
    vals = np.unique(lab); vals = vals[vals > 0]
    for p, pi in PIDX.items():
        if pi not in (vals & 63):
            continue
        base, side = (p[:-2], p[-1]) if p[-2:] in ("_r", "_l") else (p, None)
        sfx = f"_{side}" if side else ""
        lr = {"r": " (right)", "l": " (left)"}.get(side, "")
        out.append((f"fat_subcut_{base}{sfx}", "fat_sub", p, f"Subcutaneous fat, {PRETTY[base]}{lr}", [pi]))
        out.append((f"fat_deep_{base}{sfx}", "fat_deep", p, DEEP_NAME[base] + lr, [pi | 64]))
        out.append((f"soft_unlabelled_{base}{sfx}", "soft", p, f"Unlabelled soft tissue, {PRETTY[base]}{lr}", [pi | 128, pi | 128 | 64]))
    return out


def mc(mask, origin, res, y0, step=1, sigma=1.0):
    from skimage import measure
    m = np.pad(mask, 2).astype(np.float32)
    m = ndi.gaussian_filter(m, sigma)
    if m.max() < 0.5:
        return None
    V, F, _, _ = measure.marching_cubes(m, 0.5, step_size=step)
    V = V - 2
    P = np.c_[origin[0] + (V[:, 2] + 0.5) * res, y0 + V[:, 0] * res, origin[2] + (V[:, 1] + 0.5) * res]
    return P, F.astype(np.int64)


def signed_volume(V, F):
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)


BALL2 = (np.add.reduce(np.indices((5, 5, 5)) - 2) ** 0 * 0 + (((np.indices((5, 5, 5)) - 2) ** 2).sum(0) <= 4))
MINV = {"fat_sub": 100, "fat_deep": 100, "soft": 500}
SHARE = {"fat_sub": 0.30, "fat_deep": 0.35, "soft": 0.35}


def edge_defects(F):
    e = np.sort(np.r_[F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]], axis=1)
    _, c = np.unique(e, axis=0, return_counts=True)
    return int((c == 1).sum()), int((c > 2).sum()), int(len(c))


def mesh(key, budget=600000, min_vox=27):
    import fast_simplification as FS
    import trimesh
    z = np.load(OUT / f"{key}_vox.npz"); lab = z["lab"]; org = z["origin"]; res = float(z["res"])
    U = units(lab); masks_ = {}; f2 = {}
    objs = ndi.find_objects(lab)
    for uid, kind, part, name, vals in U:
        bb = [objs[v - 1] for v in vals if v - 1 < len(objs) and objs[v - 1] is not None]
        if not bb:
            continue
        a = np.array([[b_.start for b_ in o] for o in bb]).min(0) - 3; b = np.array([[b_.stop for b_ in o] for o in bb]).max(0) + 3
        a = np.maximum(a, 0); b = np.minimum(b, lab.shape)
        crop = lab[a[0]:b[0], a[1]:b[1], a[2]:b[2]]
        sub = np.isin(crop, vals)
        # close the seams between neighbouring body parts: grow 3 voxels into the same tissue kind of the adjacent parts
        same = (crop >= 128) if kind == "soft" else ((crop > 0) & (crop < 128))
        sub = sub | (ndi.binary_dilation(sub, iterations=3) & same)
        # slivers: fat thinner than ~2 mm (r = 1 opening) and unlabelled soft tissue thinner than ~4 mm (r = 2 ball) stay as the
        # few-mm seams between structures; chunks smaller than MINV (fat 0.1 cm3, soft 0.5 cm3) are dropped
        sub = ndi.binary_opening(sub, structure=BALL2 if kind == "soft" else ndi.generate_binary_structure(3, 1))
        mv = MINV[kind]
        if sub.sum() < mv:
            continue
        cl, n = ndi.label(sub)
        if n > 1:
            sz = np.bincount(cl.ravel()); keep = sz >= mv; keep[0] = False; sub = keep[cl]
        if not sub.any():
            continue
        r = mc(sub, (0, 0, 0), res, 0, step=2)
        if r is None:
            continue
        masks_[uid] = (kind, part, name, a, sub.shape, np.packbits(sub.ravel()), float(sub.sum() * res ** 3 / 1000.0))
        f2[uid] = len(r[1])
    tot = {k: sum(f2[u] for u in f2 if masks_[u][0] == k) for k in SHARE}
    res_ = {}
    for uid, (kind, part, name, a, shp, bits, vol) in masks_.items():
        tgt = max(300, int(budget * SHARE[kind] * f2[uid] / max(tot[kind], 1)))
        # marching-cubes step chosen to meet the budget without decimation where possible (decimation leaves non-manifold edges that the
        # cut-face fill has to repair); estimated faces at step s ~ f2 * (2 / s)^2
        step = next((s_ for s_ in range(1, 6) if f2[uid] * (2.0 / s_) ** 2 <= 1.25 * tgt), 5)
        sub = np.unpackbits(bits)[:int(np.prod(shp))].reshape(shp).astype(bool)
        V, F = mc(sub, (org[0] + a[2] * res, 0, org[2] + a[1] * res), res, org[1] + a[0] * res, step=step)
        if len(F) > 1.25 * tgt:
            V2, F2 = FS.simplify(V.astype(np.float32), F.astype(np.int32), target_reduction=1 - tgt / len(F), agg=7)
        else:
            V2, F2 = V, F
        tm = trimesh.Trimesh(np.asarray(V2, np.float64), np.asarray(F2, np.int64), process=True)
        tm.update_faces(tm.nondegenerate_faces()); tm.update_faces(tm.unique_faces()); tm.remove_unreferenced_vertices()
        V2, F2 = np.asarray(tm.vertices), np.asarray(tm.faces)
        if signed_volume(V2, F2) < 0:
            F2 = F2[:, [0, 2, 1]]; tm = trimesh.Trimesh(V2, F2, process=False)
        ang = np.degrees(tm.face_adjacency_angles) if len(tm.face_adjacency) else np.zeros(1)
        bd, nm, ne = edge_defects(F2)
        res_[uid] = dict(kind=kind, part=part, name=name, v=V2, f=F2, vox_cm3=round(vol, 1),
                         mesh_cm3=round(abs(signed_volume(V2, F2)) / 1000, 1), tris=int(len(F2)), nv=int(len(V2)), mc_step_mm=step,
                         watertight=bool(tm.is_watertight), boundary_edges=bd, nonmanifold_edges=nm, edges=ne,
                         dihedral_mean_deg=round(float(ang.mean()), 1))
        assert res_[uid]["nv"] < 65535, uid
        print(key, uid, res_[uid]["tris"], "tris", res_[uid]["mesh_cm3"], "cm3 step", step, "defects", bd, nm, flush=True)
    np.savez_compressed(OUT / f"{key}_fat.npz", **{f"{u}__v": d["v"] for u, d in res_.items()}, **{f"{u}__f": d["f"] for u, d in res_.items()})
    rep = {u: {k: v for k, v in d.items() if k not in ("v", "f")} for u, d in res_.items()}
    (OUT / f"{key}_fat.json").write_text(json.dumps(rep, indent=1))
    print(key, "units", len(rep), "tris", sum(d["tris"] for d in rep.values()))
    return rep


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd"); ap.add_argument("key"); ap.add_argument("--src"); ap.add_argument("--budget", type=int, default=600000)
    a = ap.parse_args()
    if a.cmd == "masks":
        masks(a.key, a.src)
    elif a.cmd == "mesh":
        mesh(a.key, a.budget)
