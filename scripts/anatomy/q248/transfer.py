"""Q248 (a): Z-Anatomy ligament -> own page, carried by LOCAL carrier-bone fits.

For a Z ligament L of the Combined page (Z-Anatomy structure already fitted to the same donor body) and the own page of that donor:
  1. carrier groups = the Z bone groups within CARRIER_MM of L (fit.group_map pairs each with the own bone mesh(es));
  2. per group a LOCAL rigid fit (scale fixed to the group's global scale): the Z bone surface within PATCH_MM of the L vertices near that bone is fitted by trimmed ICP onto the own bone, started from the
     group's global bidirectional ICP; the local residual (median / p90) is the fit error of the card;
  3. every vertex is carried by the inverse-distance blend of the group transforms (weight 1 / (d + 1)^3, d = distance to the Z bone of that group);
  4. ATTACHMENT vertices (<= ATT_MM from a Z bone) are snapped to the nearest point of the own bone (kept only if the snap moves <= SNAP_MAX_MM), the snap displacement is spread over the mesh with a Gaussian
     kernel (sigma SIGMA_MM) so the mesh stays smooth; the attachment vertices end ON the bone surface (error 0 by construction; reported as the distance before the snap);
  5. guards: no vertex deeper than 1 mm inside any own bone except attachment vertices (pushed out, bounded), inside the skin, overlap with muscles / organs, edge stretch, left / right by x.
The result is an ESTIMATE of the ligament position on the own body (Z-Anatomy shape, CC BY-SA 4.0), not a measurement."""
from __future__ import annotations
import json, re, sys, time
from pathlib import Path
import numpy as np, trimesh
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lig_pages as PG, lig_fit as FT  # noqa: E402
import checklist as CL  # noqa: E402

CARRIER_MM, PATCH_MM, ATT_MM, SNAP_MAX_MM, SIGMA_MM = 6.0, 28.0, 1.5, 7.0, 8.0
USE_BASE_PAGE = False     # tried in Q248: attachment vertices / carriers from the Base page (same Z meshes at their original positions) -> fewer structures pass (own F 76 vs 79, own M 62 vs 75); kept off
BASE_OF = {"comb_f": "base_f", "comb_m": "base_m"}
PUSH_MAX_MM, MAX_PUSH_FRAC = 8.0, 0.35
MUSCLE_DEEP_MM, ORGAN_DEEP_MM, MAX_MUSCLE_FRAC, MAX_ORGAN_FRAC = 6.0, 3.0, 0.25, 0.10
EDGE_P95, EDGE_P05 = 3.0, 0.2
CAT = {"joint": "ligament", "cartilage": "cartilage", "fascia": "ligament", "ligament": "ligament"}


class Carrier:
    def __init__(self, own_key, comb_key, root=None):
        self.own_key, self.comb_key = own_key, comb_key
        self.O = PG.load(own_key, root); self.C = PG.load(comb_key, root)
        self.G = FT.group_map(self.O, self.C)
        self.zgroup = {zi: g for g, (oi, ci) in self.G.items() for zi in ci}
        self.obf, self.zbf = PG.BoneField(self.O), PG.BoneField(self.C)
        # the Base page holds the SAME Z-Anatomy meshes (same vertex order) at their original Z positions: it tells which vertices of a ligament are attachment vertices (<= ATT_MM from a Z bone) even where the
        # Combined fit left the ligament several mm off its bones
        self.B = PG.load(BASE_OF[comb_key], root) if (comb_key in BASE_OF and USE_BASE_PAGE) else {}
        self.bbf = PG.BoneField(self.B) if self.B else None
        self.glob = {}
        self._soft = {}; self._closed = {}
        self.skin = self.O.get("skin")
        hips = [self.O[f"hip_bone_{s}"]["v"].mean(0) for s in "lr"]
        self.xmid = float(np.mean([h[0] for h in hips])); self.hip = {s: self.O[f"hip_bone_{s}"]["v"].mean(0) for s in "lr"}

    # ---- group fits (global, lazy)
    def global_fit(self, g):
        if g not in self.glob:
            oi, ci = self.G[g]
            dst = FT.surf_samples([PG.mesh(self.O[i]) for i in oi], 15000); src = FT.surf_samples([PG.mesh(self.C[i]) for i in ci], 3000)
            T, st = FT.icp(src, dst)
            T2, st2 = FT.icp(src, dst, init=(1.0, np.eye(3), dst.mean(0) - src.mean(0)))
            if st2["median_mm"] < st["median_mm"] - 0.1:
                T, st = T2, st2
            kd = cKDTree(dst)
            self.glob[g] = dict(T=T, stats=st, kd=kd, dst=dst, src_pts=src)
        return self.glob[g]

    def local_fit(self, g, Xnear, zpts_all):
        """rigid local ICP (scale = global scale) of the Z bone patch around Xnear onto the own bone group"""
        gf = self.global_fit(g)
        s0, R0, t0 = gf["T"]
        kd_all = cKDTree(Xnear)
        sel = zpts_all[kd_all.query(zpts_all)[0] <= PATCH_MM]
        if len(sel) < 50:
            return gf["T"], dict(mode="global", n=0, **gf["stats"])
        R, t = R0, t0
        for _ in range(25):
            Y = s0 * sel @ R.T + t
            d, i = gf["kd"].query(Y)
            k = d <= np.quantile(d, 0.9)
            X, Yt = sel[k], gf["dst"][i[k]]
            mx, my = X.mean(0), Yt.mean(0)
            C = (Yt - my).T @ (X - mx)
            U, S, Vt = np.linalg.svd(C)
            D = np.eye(3); D[2, 2] = np.sign(np.linalg.det(U @ Vt))
            Rn = U @ D @ Vt; tn = my - s0 * Rn @ mx
            if np.abs(tn - t).max() < 1e-4 and np.abs(Rn - R).max() < 1e-6:
                R, t = Rn, tn; break
            R, t = Rn, tn
        Y = s0 * sel @ R.T + t
        d = gf["kd"].query(Y)[0]
        # a local fit may not move the patch centroid by more than 12 mm from the global fit (else: global)
        c = sel.mean(0)
        if np.linalg.norm((s0 * R @ c + t) - FT.apply(gf["T"], c[None])[0]) > 12.0:
            return gf["T"], dict(mode="global(local rejected)", n=int(len(sel)), **gf["stats"])
        return (s0, R, t), dict(mode="local", n=int(len(sel)), median_mm=round(float(np.median(d)), 2), p90_mm=round(float(np.quantile(d, .9)), 2), scale=round(float(s0), 4),
                                global_median_mm=gf["stats"]["median_mm"])

    # ---- soft structures for the overlap guard
    def soft_field(self, ids):
        for i in ids:
            if i not in self._soft:
                m = PG.mesh(self.O[i]); n = int(min(40000, max(4000, m.area / 0.5)))
                np.random.seed(0)
                pts, fi = trimesh.sample.sample_surface(m, n, seed=0)
                self._soft[i] = (cKDTree(pts), PG.outward_normals(m)[fi])
        return [self._soft[i] for i in ids]

    def soft_overlap(self, V, exclude=()):
        """fraction of the vertices deeper than MUSCLE_DEEP_MM inside a (closed) muscle, and deeper than ORGAN_DEEP_MM inside a closed organ. Open meshes (seam sheets) have no inside and are skipped"""
        lo, hi = V.min(0) - 8, V.max(0) + 8
        ids = []
        for i, e in self.O.items():
            if e["sys"] in ("muscle", "organ") and i not in exclude and len(e["f"]) > 20 and i not in ("skin",):
                a, b = e["v"].min(0), e["v"].max(0)
                if (a <= hi).all() and (b >= lo).all():
                    if i not in self._closed:
                        self._closed[i] = bool(PG.mesh(e).is_watertight)
                    if self._closed[i]:
                        ids.append(i)
        dm = np.zeros(len(V), bool); do = np.zeros(len(V), bool); who = {}; zf = {}
        for i, (kd, nn) in zip(ids, self.soft_field(ids)):
            d, k = kd.query(V)
            ins = ((V - kd.data[k]) * nn[k]).sum(1) < 0
            org = self.O[i]["sys"] == "organ"
            deep = ins & (d > (ORGAN_DEEP_MM if org else MUSCLE_DEEP_MM))
            if deep.any():
                if "zfill" in i:                      # Z-filled seam muscles are estimates themselves: reported, not gated
                    zf[i] = int(deep.sum()); continue
                who[i] = int(deep.sum()); (do if org else dm).__ior__(deep)
        return float(dm.mean()), float(do.mean()), dict(sorted(who.items(), key=lambda x: -x[1])[:4]), dict(sorted(zf.items(), key=lambda x: -x[1])[:3])

    def skin_inside(self, V):
        if self.skin is None:
            return None
        kd, nn = self.soft_field(["skin"])[0]
        d, k = kd.query(V)
        s = ((V - kd.data[k]) * nn[k]).sum(1)
        return float(np.min(np.where(s < 0, d, -d)))     # smallest depth inside the skin (negative = outside)

    # ---- the transfer of one structure
    def transfer(self, zid):
        Z = self.C[zid]; X = Z["v"].astype(float); F = Z["f"]
        rep = dict(id=zid, name=Z["name"], n_vertices=int(len(X)))
        zids = self.zbf.near(X, [i for i in self.zgroup], margin=CARRIER_MM + 6)
        if not zids:
            rep.update(status="held", reason="no Z bone near the structure"); return None, rep
        sd, arg, nrm, pt = self.zbf.signed(X, zids)
        dabs = np.abs(sd)
        att_base = np.zeros(len(X), bool)
        if zid in self.B and len(self.B[zid]["v"]) == len(X):
            bz = self.B[zid]["v"].astype(float)
            bids = self.bbf.near(bz, [i for i in self.zgroup if i in self.B], margin=4.0)
            if bids:
                att_base = np.abs(self.bbf.signed(bz, bids)[0]) <= ATT_MM
        rep["attachment_vertices_from_base_page"] = int(att_base.sum())
        # per carrier group: distance of each vertex to the Z bones of the group
        groups = {}
        for g, (oi, ci) in self.G.items():
            cz = [zi for zi in ci if zi in zids]
            dg = np.abs(self.zbf.signed(X, cz)[0]) if cz else np.full(len(X), np.inf)
            if zid in self.B and len(self.B[zid]["v"]) == len(X):       # distance on the Base page (original Z positions) counts too
                bz = self.B[zid]["v"].astype(float)
                cb = self.bbf.near(bz, [zi for zi in ci if zi in self.B], margin=CARRIER_MM + 6)
                if cb:
                    dg = np.minimum(dg, np.abs(self.bbf.signed(bz, cb)[0]))
            if not np.isfinite(dg).any():
                continue
            if (dg <= CARRIER_MM).any():
                groups[g] = dg
        if not groups:
            rep.update(status="held", reason="no Z carrier bone within %g mm of the structure" % CARRIER_MM); return None, rep
        # LOCAL fits
        Ts, fits = {}, {}
        for g, dg in groups.items():
            oi, ci = self.G[g]
            zpts = FT.surf_samples([PG.mesh(self.C[i]) for i in ci], 6000)
            near = X[dg <= max(CARRIER_MM, 3.0)]
            T, st = self.local_fit(g, near, zpts)
            Ts[g] = T; fits[g] = st
        gl = list(groups)
        excluded = [g for g in gl if fits[g].get("median_mm", 0) > 2.5]
        if excluded and len(excluded) < len(gl):           # a carrier whose local fit is poor does not take part in the blend (its vertices follow the good neighbours)
            gl = [g for g in gl if g not in excluded]
        rep["carriers_excluded_from_blend"] = excluded if len(gl) < len(groups) else []
        W = np.stack([1.0 / (np.minimum(groups[g], 60) + 1.0) ** 3 for g in gl], 1)
        W /= W.sum(1, keepdims=True)
        Y = sum(W[:, k:k + 1] * FT.apply(Ts[g], X) for k, g in enumerate(gl))
        # ---- attachment snap
        att = (dabs <= ATT_MM) | att_base
        car_ids = sorted({i for g in gl for i in self.G[g][0]})
        own_ids = sorted(set(car_ids) | set(self.obf.near(Y, [i for i in self.O if self.O[i]["sys"] == "bone" and "zfill" not in i and not i.startswith("zan_")], margin=15.0)))
        sdo, ao, no, po = self.obf.signed(Y, car_ids)
        snap_d = np.zeros(len(X))
        rep["attachment_vertices"] = int(att.sum())
        if att.any():
            snap_d[att] = np.abs(sdo[att])
            disp = np.zeros_like(Y)
            ok_att = att & (np.abs(sdo) <= SNAP_MAX_MM)
            disp[ok_att] = po[ok_att] - Y[ok_att]
            rep["attachment_gap_before_snap_mm"] = dict(median=round(float(np.median(snap_d[att])), 2), p90=round(float(np.quantile(snap_d[att], .9)), 2), max=round(float(snap_d[att].max()), 2),
                                                       not_snappable=int((att & ~ok_att).sum()))
            if ok_att.any():
                ka = cKDTree(Y[ok_att]); D = disp[ok_att]
                idx = ka.query_ball_point(Y, r=3 * SIGMA_MM)
                delta = np.zeros_like(Y)
                for j, nb in enumerate(idx):
                    if nb:
                        r = np.linalg.norm(Y[ok_att][nb] - Y[j], axis=1); K = np.exp(-(r / SIGMA_MM) ** 2)
                        delta[j] = (K[:, None] * D[nb]).sum(0) / (K.sum() + 0.05)
                Y = Y + delta
                Y[ok_att] = Y[ok_att]                      # placeholder (set below)
                # attachment vertices exactly on the bone surface
                sd2, a2, n2, p2 = self.obf.signed(Y, car_ids)
                tgt = np.where(ok_att)[0]
                Y[tgt] = p2[tgt] + 0.0 * n2[tgt]
        # ---- push out of bones (non-attachment)
        sd3, a3, n3, p3 = self.obf.signed(Y, own_ids)
        inside = (sd3 < -1.0) & ~(att & (np.abs(sd3) <= 1.0))
        pushed = np.zeros(len(X)); moved = 0
        if inside.any():
            need = (-sd3[inside] + 0.2)
            Y[inside] = Y[inside] + n3[inside] * need[:, None]
            pushed[inside] = need; moved = int(inside.sum())
        sd4 = self.obf.signed(Y, own_ids)[0]
        rep.update(carriers={g: fits[g] for g in gl}, pushed_out_vertices=moved, pushed_fraction=round(moved / len(X), 3), max_push_mm=round(float(pushed.max()), 2),
                   min_signed_distance_to_bone_mm=round(float(sd4.min()), 2), vertices_deeper_1mm_in_bone=int((sd4 < -1.0).sum()))
        # ---- shape / size guards
        E = np.vstack([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]); E = np.unique(np.sort(E, 1), axis=0)
        l0 = np.linalg.norm(X[E[:, 0]] - X[E[:, 1]], axis=1); l1 = np.linalg.norm(Y[E[:, 0]] - Y[E[:, 1]], axis=1)
        ok = l0 > 0.05; ratio = l1[ok] / l0[ok]
        rep["edge_stretch"] = dict(p05=round(float(np.quantile(ratio, .05)), 2), median=round(float(np.median(ratio)), 2), p95=round(float(np.quantile(ratio, .95)), 2))
        ext0 = np.ptp(X @ np.linalg.svd(X - X.mean(0), full_matrices=False)[2].T, axis=0); ext1 = np.ptp(Y @ np.linalg.svd(Y - Y.mean(0), full_matrices=False)[2].T, axis=0)
        rep["length_mm"] = dict(z=round(float(ext0[0]), 1), own=round(float(ext1[0]), 1), ratio=round(float(ext1[0] / max(ext0[0], 1e-6)), 2))
        m0, m1 = trimesh.Trimesh(X, F, process=False), trimesh.Trimesh(Y, F, process=False)
        rep["volume_cm3"] = dict(z=round(float(abs(m0.volume)) / 1000, 3) if m0.is_watertight else None, own=round(float(abs(m1.volume)) / 1000, 3) if m1.is_watertight else None,
                                 area_ratio=round(float(m1.area / max(m0.area, 1e-6)), 2), watertight=bool(m0.is_watertight))
        # ---- soft overlap, skin, side
        fm, fo, who, zf = self.soft_overlap(Y)
        rep["soft_overlap"] = dict(muscle_fraction_deeper_6mm=round(fm, 3), organ_fraction_deeper_3mm=round(fo, 3), top=who, z_filled_estimates_not_gated=zf)
        rep["skin_min_depth_mm"] = self.skin_inside(Y)
        c = Y.mean(0); side = Z["side"]
        sc = (c[0] - self.xmid)
        side_ok = True if side not in ("l", "r") or abs(sc) < 8 else ((sc > 0) == (side == "r"))
        rep["side"] = dict(name_side=side, centroid_x_vs_midline_mm=round(float(sc), 1), ok=bool(side_ok))
        # ---- gates
        why = []
        if gl and max(fits[g].get("median_mm", 0) for g in gl) > 2.5: why.append("carrier local fit median > 2.5 mm")
        if rep["pushed_fraction"] > MAX_PUSH_FRAC or rep["max_push_mm"] > PUSH_MAX_MM: why.append("too much of the mesh pushed out of bone")
        if rep.get("attachment_gap_before_snap_mm", {}).get("not_snappable", 0) > 0.2 * max(1, att.sum()): why.append("attachment vertices not snappable")
        if rep["edge_stretch"]["p95"] > EDGE_P95 or rep["edge_stretch"]["p05"] < EDGE_P05: why.append("mesh distorted (edge stretch)")
        if not (0.6 <= rep["length_mm"]["ratio"] <= 1.6): why.append("length ratio outside 0.6-1.6")
        if fm > MAX_MUSCLE_FRAC: why.append("> 25 %% of the vertices deeper than %g mm inside a muscle" % MUSCLE_DEEP_MM)
        if fo > MAX_ORGAN_FRAC: why.append("> 10 %% of the vertices deeper than %g mm inside an organ" % ORGAN_DEEP_MM)
        if rep["skin_min_depth_mm"] is not None and rep["skin_min_depth_mm"] < 1.0: why.append("outside / within 1 mm of the skin")
        if not side_ok: why.append("left / right by x position fails")
        if rep["vertices_deeper_1mm_in_bone"]: why.append("vertices still > 1 mm in bone")
        rep["status"] = "ship" if not why else "held"
        rep["held_reasons"] = why
        return (Y, F), rep


def plan(carrier, own_key):
    """Z structure ids to transfer: those matching a checklist item that the own page lacks (or has one side of) and that the Combined page has"""
    O, C = carrier.O, carrier.C
    from lig_audit import structs, match  # noqa: E402
    So = structs(own_key, PG.ROOT); Sc = structs(carrier.comb_key, PG.ROOT)
    mo, mc = match(CL.ITEMS, So, own_key), match(CL.ITEMS, Sc, carrier.comb_key)
    ids = {}
    for g, k, label, sex, sided, inc, exc in CL.ITEMS:
        if g in ("pelvic_floor",) and k not in ("pubococcygeal_puboperineal",):
            continue
        if k in ("pubococcygeal_puboperineal", "pubic_symphysis_disc", "menisci", "sacrococcygeal_symphysis"):
            continue
        if mo[k]["status"] in ("missing", "one side") and mc[k]["status"] == "present":
            for h in mc[k]["hits"]:
                if h not in O and C[h]["sys"] in ("joint", "cartilage", "fascia", "ligament"):
                    ids.setdefault(h, []).append(k)
    return ids


if __name__ == "__main__":
    own, comb = sys.argv[1], sys.argv[2]
    t0 = time.time()
    car = Carrier(own, comb)
    P = plan(car, own)
    print(len(P), "Z structures planned", flush=True)
    only = sys.argv[3:] or None
    out, reps = {}, {}
    for zid in sorted(P):
        if only and zid not in only: continue
        try:
            res, rep = car.transfer(zid)
        except Exception as ex:  # noqa: BLE001
            res, rep = None, dict(id=zid, status="error", reason=repr(ex))
        rep["items"] = P[zid]; reps[zid] = rep
        if res is not None and rep["status"] == "ship":
            out[zid] = res
        print(f"{zid:60s} {rep['status']:5s} {'; '.join(rep.get('held_reasons', [])) or rep.get('reason', '')}", flush=True)
    outdir = HERE.parents[2] / "data/derived"
    tag = own if comb.startswith("comb") else f"{own}_from_{comb}"
    np.savez_compressed(outdir / f"Q248_xfer_{tag}.npz", **{f"{k}__v": v[0] for k, v in out.items()}, **{f"{k}__f": v[1] for k, v in out.items()})
    (outdir / f"Q248_xfer_{tag}.json").write_text(json.dumps(dict(own=own, comb=comb, groups={g: dict(stats=car.glob[g]["stats"]) for g in car.glob}, structures=reps), indent=1, default=float) + "\n")
    print("shipped", len(out), "of", len(reps), "in", round(time.time() - t0), "s")
