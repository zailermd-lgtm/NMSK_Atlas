#!/usr/bin/env python3
"""Q292: Base · Female gets HER OWN breasts, her own chest skin contour and her own pelvic organs (the Visible Human female's CT /
cryosections), registered onto the Base body, and the HRA / CVH female set made consistent with them.

    python3 scripts/anatomy/q292/build_q292.py geometry [--work /dev/shm/q292/work]     # all geometry + data/derived/Q292_base_f_report.json
    python3 scripts/anatomy/q292/build_q292.py page [--work ...] [--out /dev/shm/q292/pre] # page dir viewer_base_female (from the live geometry)
    python3 scripts/anatomy/q292/build_q292.py rig --fresh FILE                            # splice new + replaced entries into data/anatomy/pose_rig_base_f.json
    python3 scripts/anatomy/q292/build_q292.py measure --page DIR                          # literature dimensions + mesh realness -> data/derived/Q292_validation.json

What was wrong (Phase 0, data/derived/Q292_diagnosis.json): the breasts were the HRA mammary set, which the HRA records as "sculpted from
scratch" (Krstic 1991; Gilroy 2008), squeezed by Q234 into the male Z chest skin and then given a skin bump by Q250 (a column-maximum lift of
the coarse Z skin patches: spikes / shards); the nipple sat 65 mm behind the breast apex on its lateral rim. The pelvic organs mixed three
bodies: a male Z-Anatomy bladder (450 triangles) and sigmoid / rectum, HRA reference organs of the VHF frame and CVH perineal structures of
another woman: the vagina ran 17 % inside the bladder, the uterus 13 %, the CVH urethra 38 % inside the vagina.

Method (one registration for everything): her atlas frame -> Base F by the bone correspondences of the two Z-Anatomy skeletons (Combined F =
Z bones fitted to HER skeleton; Base F = the same Z bones deformed onto her skeleton): identical-topology bones vertex to vertex, the others by
similarity ICP, a thin-plate spline through ~3,500 control points (lib292.Map). Pelvis: that spline. Breasts: the spline compresses the
supine breast (left 875 -> 598 cm3), so each breast takes a rigid fit of its own chest wall (ribs 2-7, cartilages, half sternum) at the global
scale, a depth correction (her breast-to-rib-cage height kept on the Base rib cage, smoothed 20 mm), a rule-based lateral squash of her supine
lateral spread (beyond 145 mm from the midline the lateral offset x 0.35: her arm lies against it in the CT, the Base arm hangs there) and
guarded pushes out of the arm / rib cage (keeping 4 mm for the pectoral layer). Skin: the Z chest patches (positions before the Q250 lift),
subdivided to 4 mm edges and fitted onto her own skin mapped with the same transform, tapering to nothing 30-80 mm from the breast and at the
borders with the patches that do not move; pushed out over the breast where her CT has no skin of her own there (lateral, against her arm).
"""
from __future__ import annotations

import argparse
import json
import pickle
import re
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import cKDTree
from trimesh.remesh import subdivide_to_size

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts/anatomy/q219")); sys.path.insert(0, str(Path(__file__).resolve().parent))
import geomlib as GL  # noqa: E402
import lib292 as L  # noqa: E402

LIVE_BASE_F = REPO / "build/q265/viewer_base_female"            # live Base · Female geometry (Q265; Q266-Q291 changed templates / sidecars only)
STEM = "atlas_viewer_base_female"
COMB_F = REPO / "build/q288/viewer_zan_female/atlas_viewer_zan_female.html"   # Z bones fitted to HER skeleton, her frame
OWN_F = REPO / "build/q288_pre/bundle_own_f"                    # her own meshes (Imaging-based Female bundle)
ZONLY = REPO / "build/q250_pre/viewer_base_zonly/atlas_viewer_base_female.html"   # Base F skin BEFORE the Q250 chest lift
REPORT = REPO / "data/derived/Q292_base_f_report.json"
DEFAULT_WORK = "/dev/shm/q292/work"

LAT_X0, LAT_K, WALL_GAP, SKIN_EDGE = 145.0, 0.35, 4.0, 4.0
WALL_RE = re.compile(r'_rib_[lr]$|costal_cartilage|^sternum$|^zan_xiphoid|intercostal_(muscles|membrane)|lobe_of_.*lung|^zan_pleura$|transversus_thoracis')
HRA_BREAST_RE = re.compile(r'^(breast_fat|mammary_gland|lactiferous|areola|nipple|breast_suspensory)')
ARM_RE = re.compile('biceps|brachial|brachialis|coracobrach|deltoid|triceps|cephalic|basilic|_arm')
SKIN_PATCH_RE = re.compile(r'mammary|pectoral_region|presternal|lateral_region_of_thorax|epigastric|infraclavicular|deltopectoral|hypochondriac')
HERWALL = ['ribs_l', 'ribs_r', 'costal_cartilage_l', 'costal_cartilage_r', 'sternum', 'external_intercostals_l', 'external_intercostals_r']
ORG = ['urinary_bladder', 'rectum', 'sigmoid_colon', 'uterus_cryo_vhf']
HIDE_PELVIS = ['zan_urinary_bladder', 'zan_sigmoid_colon', 'uterus', 'external_anal_sphincter']
FEMALE_SUBJ = re.compile(r'(xfer_hra2vhf_q23[34]|xfer_hra2vhf_q243|xfer_cvh2vhf_q235|xfer_cvh2vhf_q248)$')
UG = ['urethra_female_lumen', 'urethra_female_submucous_layer', 'urethral_sphincter_cvh', 'urethral_sphincter_raphe_cvh', 'urethral_compressor_cvh', 'urethrovaginal_sphincter_cvh']
LEV_RE = re.compile(r'zan_(pubococcygeus|pubo_analis|iliococcygeus)_muscle|^levator_ani_[lr]$|^coccygeus_[lr]$')
HOLD_PCT = 20.0


def sstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def load_inputs():
    B = {k: (d["v"], d["f"], d["cat"]) for k, d in GL.load_zan(LIVE_BASE_F / f"{STEM}.html").items()}
    C = {k: (d["v"], d["f"], d["cat"]) for k, d in GL.load_zan(COMB_F).items()}
    O = {k: (d["v"], d["f"], d["cat"], d["subject"]) for k, d in GL.load_own(OWN_F).items()}
    Z = {k: (d["v"], d["f"], d["cat"]) for k, d in GL.load_zan(ZONLY).items() if d["cat"] == "skin"}
    return B, C, O, Z


class Union:
    """max of several SDFs (inside any of them)"""
    def __init__(self, *f): self.f = f
    def at(self, P): return np.max([x.at(P) for x in self.f], 0)
    def grad(self, P):
        vals = np.stack([x.at(P) for x in self.f]); i = vals.argmax(0); g = np.stack([x.grad(P) for x in self.f])
        return g[i, np.arange(len(P))]


# ------------------------------------------------------------------------------------------------------------------- breasts + skin
def breasts(B, C, O, Z, M, rep):
    s0 = M.s
    RIBS = ['second', 'third', 'fourth', 'fifth', 'sixth', 'seventh']
    T = {}
    for s, sg in (('l', -1), ('r', 1)):
        keys = set([f'zan_{r}_rib_{s}' for r in RIBS] + [k for k in C if 'costal_cartilage' in k and k.endswith('_' + s)])
        X, Y, _ = L.correspondences(C, B, keys=keys, step=3)
        half = C['sternum'][0][C['sternum'][0][:, 0] * sg >= -5]
        X = np.vstack([X, half]); Y = np.vstack([Y, M(half)]); a = X[:, 2] > -20
        mx, my = X[a].mean(0), Y[a].mean(0); A_ = (X[a] - mx) * s0; B_ = Y[a] - my
        U, S, Vt = np.linalg.svd(A_.T @ B_); dd = np.sign(np.linalg.det(U @ Vt)); Rm = (U @ np.diag([1, 1, dd]) @ Vt).T
        t = my - s0 * Rm @ mx
        r = np.linalg.norm(s0 * X[a] @ Rm.T + t - Y[a], axis=1)
        T[s] = (Rm, t, dict(rot_deg=round(float(np.degrees(np.arccos(np.clip((np.trace(Rm) - 1) / 2, -1, 1)))), 2),
                             wall_fit_resid_med_mm=round(float(np.median(r)), 1), wall_fit_resid_p95_mm=round(float(np.percentile(r, 95)), 1)))
    # the chest-wall correction of the spline at the breast footprint (one constant per side)
    cw = np.vstack([trimesh.Trimesh(*O[k][:2], process=False).sample(40000) for k in ['ribs_l', 'ribs_r', 'costal_cartilage_l', 'costal_cartilage_r', 'sternum']])
    cw = cw[cw[:, 2] > -40]

    def W(X): return sstep((np.asarray(X)[:, 0] + 30) / 60)

    def rig(X):
        w = W(X)[:, None]
        return (1 - w) * (s0 * X @ T['l'][0].T + T['l'][1]) + w * (s0 * X @ T['r'][0].T + T['r'][1])
    dcw = M(cw) - rig(cw); tc = cKDTree(cw); cc = {}
    for s in 'lr':
        _, idx = tc.query(O['breast_ct_' + s][0], k=8); cc[s] = np.median(dcw[idx.ravel()], axis=0)

    def xf(X):
        X = np.asarray(X, float); w = W(X)[:, None]
        return (1 - w) * (s0 * X @ T['l'][0].T + T['l'][1] + cc['l']) + w * (s0 * X @ T['r'][0].T + T['r'][1] + cc['r'])
    rep['breast_transform'] = {s: dict(T[s][2], scale=round(float(s0), 4), translation_mm=np.round(T[s][1] + cc[s], 1).tolist()) for s in 'lr'}
    WALL = [k for k in B if WALL_RE.search(k)]
    BR = {}
    for s in 'lr':
        v, F = O['breast_ct_' + s][:2]; fv, ff = O['breast_fgt_ct_' + s][:2]
        R = {'her_volume_cm3': round(L.mesh_volume(v, F), 1), 'her_fgt_volume_cm3': round(L.mesh_volume(fv, ff), 1)}
        V = xf(v); FV = xf(fv); V0 = V.copy(); R['after_rigid_map_cm3'] = round(L.mesh_volume(V, F), 1)
        lo = V.min(0) - 45; hi = V.max(0) + 45
        sw = L.SDF([B[k][:2] for k in WALL if (B[k][0].max(0) > lo).all() and (B[k][0].min(0) < hi).all()], lo, hi, fill=True)
        sh = L.SDF([(xf(O[k][0]), O[k][1]) for k in HERWALL], lo, hi)
        hb = -sw.at(V); hh = -sh.at(V); n = -sw.grad(V); c = (hh - hb)[:, None] * n
        dd, ii = cKDTree(V).query(V, k=96); ww = np.exp(-0.5 * (dd / 20.0) ** 2); ww /= ww.sum(1, keepdims=True)
        V1 = V + (c[ii] * ww[..., None]).sum(1); FV = L.carry(V, V1, FV)
        R['depth_correction'] = dict(her_height_above_rib_cage_med_mm=round(float(np.median(hh)), 1), base_height_before_med_mm=round(float(np.median(hb)), 1),
                                     correction_p95_mm=round(float(np.percentile(np.linalg.norm((c[ii] * ww[..., None]).sum(1), axis=1), 95)), 1), volume_cm3=round(L.mesh_volume(V1, F), 1))
        V = V1
        sg = 1.0 if s == 'l' else -1.0

        def squash(X, X0=LAT_X0, k=LAT_K, wk=10.0):
            X = X.copy(); u = -sg * X[:, 0]; e = u - X0; sp = wk * np.logaddexp(0, e / wk); X[:, 0] = -sg * (u - (1 - k) * sp); return X
        V1 = squash(V); FV = squash(FV)
        R['lateral_squash'] = dict(rule=f"beyond {LAT_X0:.0f} mm from the midline the lateral offset is multiplied by {LAT_K} (smooth knee 10 mm)",
                                   vertices_moved_gt1mm=int((np.linalg.norm(V1 - V, axis=1) > 1).sum()), max_mm=round(float(np.abs(V1 - V)[:, 0].max()), 1), volume_cm3=round(L.mesh_volume(V1, F), 1))
        V = V1
        sa = L.SDF([B[k][:2] for k in B if k.endswith('_' + s) and ARM_RE.search(k) and B[k][2] != 'skin'], lo, hi)
        V1, R['out_of_arm'] = L.push_dir(V, F, sa, lambda Q, sg=sg: np.tile([sg, 0, 0], (len(Q), 1)), margin=0.5, max_disp=8, rounds=6)
        FV = L.carry(V, V1, FV); V = V1
        V1, R['out_of_rib_cage'] = L.push_dir(V, F, sw, lambda Q: -sw.grad(Q), margin=WALL_GAP, max_disp=15)
        FV = L.carry(V, V1, FV); V = V1
        BR[s] = dict(V=V, F=F, FV=FV, FF=ff, V0=V0, sw=sw, R=R)
    # ---- skin
    BV0 = np.vstack([BR[s]['V0'] for s in 'lr']); BV = np.vstack([BR[s]['V'] for s in 'lr'])
    sv, sf = O['skin'][:2]
    arm = np.vstack([O[k][0] for k in O if re.match(r'(humerus|radius|ulna)_[lr]$', k)])
    trunk = np.vstack([O[k][0] for k in ['ribs_l', 'ribs_r', 'sternum', 'costal_cartilage_l', 'costal_cartilage_r', 'clavicle_l', 'clavicle_r', 'scapula_l', 'scapula_r'] if k in O])
    da, _ = cKDTree(arm).query(sv); dt, _ = cKDTree(trunk).query(sv); keepv = (dt < da) & (sv[:, 1] > 250) & (sv[:, 1] < 640)
    hsk = trimesh.Trimesh(sv, sf, process=False); hn = hsk.vertex_normals
    for s in 'lr':
        bm = trimesh.Trimesh(*O['breast_ct_' + s][:2], process=False); bdist, bi = cKDTree(bm.vertices).query(sv)
        keepv |= (bdist < 15) & (np.einsum('ij,ij->i', hn, bm.vertex_normals[bi]) > 0.3)
    SV = xf(sv); dd, ii = cKDTree(BV0).query(SV, k=8); wgt = np.exp(-0.5 * (dd / 12.0) ** 2); fall = sstep(1 - (dd[:, 0] - 20) / 40.0)
    SV = SV + fall[:, None] * ((BV - BV0)[ii] * (wgt / (wgt.sum(1, keepdims=True) + 1e-12))[..., None]).sum(1)
    her = trimesh.Trimesh(SV, sf[keepv[sf].all(1)], process=False)
    PAT = sorted(k for k in Z if SKIN_PATCH_RE.search(k))
    vs, fs, lab, o = [], [], [], 0
    for i, k in enumerate(PAT):
        v, f, _ = Z[k]; vs.append(v); fs.append(f + o); lab.append(np.full(len(f), i)); o += len(v)
    m = trimesh.Trimesh(np.vstack(vs), np.vstack(fs), process=False); LAB = np.concatenate(lab); m.merge_vertices(digits_vertex=3)
    V2, F2, idx = subdivide_to_size(m.vertices, m.faces, max_edge=SKIN_EDGE, max_iter=12, return_index=True); LAB2 = LAB[idx]
    db, _ = cKDTree(BV).query(V2); w = sstep(1 - (db - 30) / 50.0)
    EXV = np.vstack([v for k, (v, f, c) in Z.items() if k not in PAT and v[:, 1].max() > 200 and v[:, 1].min() < 700]); dex, _ = cKDTree(EXV).query(V2)
    w *= sstep(dex / 25.0)
    cp, dist, tri = trimesh.proximity.closest_point(her, V2); nh = her.face_normals[tri]
    vn = trimesh.Trimesh(V2, F2, process=False).vertex_normals; outer = np.einsum('ij,ij->i', vn, nh) > 0.3
    D = (cp - V2) * w[:, None]; _, j = cKDTree(V2[outer]).query(V2[~outer]); D[~outer] = D[outer][j]
    A, deg = L.neighbour_matrix(len(V2), F2); lockb = dex < 0.05
    for _ in range(10):
        D = 0.5 * D + 0.5 * (A @ D) / deg[:, None]; D[lockb] = 0
    SK = V2 + D; skm = trimesh.Trimesh(SK, F2, process=False)
    fc = skm.triangles_center; _, _, tri2 = trimesh.proximity.closest_point(her, fc)
    outer_face = np.einsum('ij,ij->i', skm.face_normals, her.face_normals[tri2]) > 0
    rep['skin'] = dict(patches=PAT, faces_before=int(len(m.faces)), faces_after=int(len(F2)), max_edge_mm=SKIN_EDGE,
                       vertices_moved_gt1mm=int((np.linalg.norm(D, axis=1) > 1).sum()), fit_disp_max_mm=round(float(np.linalg.norm(D, axis=1).max()), 1),
                       her_skin_vertices_used=int(keepv.sum()))
    for s in 'lr':
        b = BR[s]; V = b['V']; F = b['F']
        for _ in range(2):
            V1, ri = L.push_inside_skin(V, F, skm, outer_face, margin=0.5, max_disp=4); b['FV'] = L.carry(V, V1, b['FV']); V = V1
            V1, rw = L.push_dir(V, F, b['sw'], lambda Q, sw=b['sw']: -sw.grad(Q), margin=WALL_GAP, max_disp=10); b['FV'] = L.carry(V, V1, b['FV']); V = V1
        sbi = L.SDF([(V, F)], V.min(0) - 25, V.max(0) + 25); sbi.d = -sbi.d; sbi.g = -sbi.g
        b['FV'], b['R']['fgt_kept_inside'] = L.push_out(b['FV'], b['FF'], sbi, margin=0.5, max_disp=20)
        b['V'] = V; b['R']['inside_skin_push'] = ri; b['R']['out_of_rib_cage_2'] = rw
    # skin envelope pushed out over the breasts where her own skin gave no target
    allV = np.vstack([BR[s]['V'] for s in 'lr'])
    sbb = L.SDF([(BR[s]['V'], BR[s]['F']) for s in 'lr'], allV.min(0) - 30, allV.max(0) + 30)
    vmask = np.zeros(len(SK), bool); vmask[np.unique(F2[outer_face])] = True
    D = np.zeros_like(SK); viol = vmask & (sbb.at(SK) > -1.5)
    if viol.any():
        need = np.zeros(viol.sum()); dv = -sbb.grad(SK[viol])
        for _ in range(50):
            q = SK[viol] + dv * need[:, None]; go = sbb.at(q) > -1.5
            if not go.any():
                break
            need[go] += 0.5; dv = -sbb.grad(q)
        D[viol] = dv * need[:, None]
        _, j = cKDTree(SK[vmask]).query(SK[~vmask]); D[~vmask] = D[vmask][j]
        D = L.diffuse(D, A, deg, viol.copy(), D.copy(), iters=10); D[dex < 0.05] = 0
    SK = SK + D; skm = trimesh.Trimesh(SK, F2, process=False)
    rep['skin'].update(pushed_out_over_breast_vertices=int(viol.sum()), pushed_out_max_mm=round(float(np.linalg.norm(D, axis=1).max()), 1))
    for s in 'lr':
        b = BR[s]; V = b['V']
        rs, *_ = L.surface_side(V, skm, outer_face)
        b['R'].update(final_volume_cm3=round(L.mesh_volume(V, b['F']), 1), final_fgt_volume_cm3=round(L.mesh_volume(b['FV'], b['FF']), 1),
                      volume_kept_pct=round(100 * L.mesh_volume(V, b['F']) / b['R']['her_volume_cm3'], 1),
                      vertices_outside_skin_gt0_5mm_pct=round(100 * float((rs > 0.5).mean()), 2),
                      vertices_in_rib_cage_gt0_5mm_pct=round(100 * float((b['sw'].at(V) > 0.5).mean()), 2),
                      fgt_vertices_outside_breast_pct=round(100 * float((L.SDF([(V, b['F'])], V.min(0) - 5, V.max(0) + 5).at(b['FV']) < -0.5).mean()), 2))
    # Base F soft structures entered by a breast: thinned toward the rib cage under it (Z pectoralis major etc.)
    MOV = {}
    for s in 'lr':
        V, F = BR[s]['V'], BR[s]['F']; lo = V.min(0) - 30; hi = V.max(0) + 30; sb = L.SDF([(V, F)], lo - 40, hi + 40)
        sw = L.SDF([B[k][:2] for k in WALL if (B[k][0].max(0) > lo - 40).all() and (B[k][0].min(0) < hi + 40).all()], lo - 40, hi + 40, fill=True)
        for k, (v, f, c) in B.items():
            if c in ('skin', 'bone', 'cartilage') or k in WALL or HRA_BREAST_RE.match(k) or ARM_RE.search(k):
                continue
            v0 = MOV[k][0] if k in MOV else v
            mm = ((v0 > lo) & (v0 < hi)).all(1)
            if not mm.any() or (sb.at(v0[mm]) > -1.0).sum() < 3:
                continue
            v1, info = L.compress_under(v0, f, sb, sw)
            info['inside_breast_before'] = int((sb.at(v0) > 0.5).sum()); info['inside_breast_after'] = int((sb.at(v1) > 0.5).sum())
            try:
                info['volume_before_cm3'] = round(L.mesh_volume(v, f), 2); info['volume_after_cm3'] = round(L.mesh_volume(v1, f), 2)
            except Exception:
                pass
            MOV[k] = (v1, f); rep.setdefault('thinned_under_breast', {})[k] = info
    rep['breasts'] = {s: BR[s]['R'] for s in 'lr'}
    NEW = {'breast_ct_' + s: (BR[s]['V'], BR[s]['F']) for s in 'lr'}
    NEW.update({'breast_fgt_ct_' + s: (BR[s]['FV'], BR[s]['FF']) for s in 'lr'})
    # split the fitted skin back into its patches
    SKP = {}
    for i, k in enumerate(PAT):
        fi = F2[LAB2 == i]; u, inv = np.unique(fi, return_inverse=True)
        SKP[k] = (SK[u], inv.reshape(-1, 3))
    return NEW, MOV, SKP


# ------------------------------------------------------------------------------------------------------------------- pelvis
def pelvis(B, O, M, rep):
    NEW, MOD, CH = {}, {}, {}
    subj = lambda k: O[k][3] or ''
    SET = sorted(k for k in O if FEMALE_SUBJ.match(subj(k)) and O[k][0][:, 1].max() < 200)
    BONES = [k for k in B if B[k][2] == 'bone' and B[k][0][:, 1].min() < 150 and B[k][0][:, 1].max() > -160 and np.abs(B[k][0][:, 0]).min() < 160]
    lo = np.array([-170, -170, -130]); hi = np.array([170, 200, 170])
    SB = L.SDF([B[k][:2] for k in BONES], lo, hi)
    for k in ORG:
        V = M(O[k][0]); F = O[k][1]; v1, info = L.push_out(V, F, SB, margin=0.5, max_disp=6)
        info.update(her_volume_cm3=round(L.mesh_volume(*O[k][:2]), 1), volume_cm3=round(L.mesh_volume(v1, F), 1)); NEW[k] = (v1, F); rep.setdefault('organs', {})[k] = info
    SO = L.SDF([NEW[k] for k in ORG], lo, hi)
    SP_ = L.SDF([B[k][:2] for k in B if re.search('psoas_major|iliacus_muscle', k)], lo, hi)
    BLOCK = Union(SB, SO, SP_)
    stay = [k for k in B if k not in SET and k not in HIDE_PELVIS and B[k][2] in ('bone', 'muscle', 'viscera', 'cartilage') and B[k][0][:, 1].min() < 130
            and B[k][0][:, 1].max() > -140 and np.abs(B[k][0][:, 0]).min() < 90]
    OS = {k: L.occ_scan(*B[k][:2]) for k in stay}; OS.update({k: L.occ_scan(*NEW[k]) for k in ORG})

    def conflicts(vf, self_k):
        o = L.occ_scan(*vf); n = max(o[1].sum(), 1); out = {}
        for s, os_ in OS.items():
            if s != self_k:
                ov = L.overlap(o, os_)
                if ov / n >= 0.01:
                    out[s] = round(100 * ov / n, 1)
        return out, round(100 * float((BLOCK.at(vf[0]) > 0.5).mean()), 1)
    for k in SET:
        cand = {}
        if k in B:
            cand['live'] = B[k][:2]
        cand['mapped'] = (M(O[k][0]), O[k][1])
        best = None
        for nm, vf in cand.items():
            v1, info = L.push_out(vf[0], vf[1], BLOCK, margin=0.5, max_disp=8)
            c, vin = conflicts((v1, vf[1]), k); score = vin + 0.2 * sum(c.values())
            if best is None or score < best[0]:
                best = (score, nm, v1, vf[1], info, c, vin)
        score, nm, v1, F, info, c, vin = best
        CH[k] = dict(placement=nm, push=info, vertices_in_bone_her_organs_or_psoas_pct=vin, overlap_pct_of_volume=dict(sorted(c.items(), key=lambda x: -x[1])[:6]),
                     centroid_shift_from_live_mm=round(float(np.linalg.norm(v1.mean(0) - B[k][0].mean(0))), 1) if k in B else None,
                     hidden_default=bool(vin > HOLD_PCT), new_on_page=k not in B)
        NEW[k] = (v1, F)
    vag = L.occ_scan(*NEW['vagina']); shift = 0.0
    for dz in np.arange(0, 14.5, 0.5):
        if sum(L.overlap(L.occ_scan(NEW[k][0] + [0, 0, dz], NEW[k][1]), vag) for k in UG[:2]) <= 10:
            shift = float(dz); break
    for k in UG:
        NEW[k] = (NEW[k][0] + [0, 0, shift], NEW[k][1]); CH[k]['urethral_group_anterior_shift_mm'] = shift
    rep['urethral_group_anterior_shift_mm'] = shift
    eas = M(O['external_anal_sphincter'][0]); F = O['external_anal_sphincter'][1]; eas = L.push_out(eas, F, SB, margin=0.5, max_disp=6)[0]
    NEW['external_anal_sphincter_ct_vhf'] = (eas, F); oe = L.occ_scan(eas, F)
    rep['her_external_anal_sphincter'] = dict(volume_cm3=round(L.mesh_volume(eas, F), 1), her_volume_cm3=round(L.mesh_volume(*O['external_anal_sphincter'][:2]), 1),
                                              overlap_pct_of_volume={k: round(100 * L.overlap(oe, L.occ_scan(*NEW[k])) / oe[1].sum(), 1) for k in ('rectum', 'vagina', 'perineal_body')})
    SOR = L.SDF([NEW[k] for k in ('rectum', 'vagina', 'urinary_bladder', 'uterus_cryo_vhf')], lo, hi)
    for k in [k for k in B if LEV_RE.search(k)]:
        v1, info = L.push_out(B[k][0], B[k][1], SOR, margin=0.5, max_disp=5)
        info.update(volume_before_cm3=round(L.mesh_volume(*B[k][:2]), 2), volume_after_cm3=round(L.mesh_volume(v1, B[k][1]), 2))
        if info['moved_gt1mm']:
            MOD[k] = (v1, B[k][1]); rep.setdefault('levator_fitted_to_her_organs', {})[k] = info
    rep['female_set'] = CH
    rep['map'] = dict(scale=round(float(M.s), 4), control_points=int(len(M.cp)), tps_resid_med_mm=round(float(np.median(M.resid)), 2),
                      tps_resid_p95_mm=round(float(np.percentile(M.resid, 95)), 2))
    return NEW, MOD


def geometry(work):
    t0 = time.time(); work = Path(work); work.mkdir(parents=True, exist_ok=True)
    B, C, O, Z = load_inputs()
    X, Y, crep = L.correspondences(C, B); M = L.Map(X, Y, smoothing=10.0)
    rep = {"_README": ["Q292: Base · Female -- her own breasts / chest skin / pelvic organs; scripts/anatomy/q292/build_q292.py geometry"],
           "inputs": {"base_f_live": str(LIVE_BASE_F.relative_to(REPO)), "her_frame_bundle": str(OWN_F.relative_to(REPO)), "combined_f": str(COMB_F.relative_to(REPO)),
                      "base_f_skin_before_q250_lift": str(ZONLY.relative_to(REPO))},
           "correspondences": {"pairs": int(len(X)), "bones_vertex_to_vertex": sum(1 for v in crep.values() if v[0] == 'vertex'), "bones_icp": sum(1 for v in crep.values() if v[0] == 'icp')}}
    from scipy.spatial import cKDTree as KD
    val = {}
    for k in ['hip_bone_l', 'hip_bone_r', 'sacrum', 'sternum', 'ribs_l', 'ribs_r']:
        bk = [b for b in B if (b == k) or (k.startswith('ribs_') and re.search(r'_rib_' + k[-1] + '$', b))]
        if k in O and bk:
            d, _ = KD(np.vstack([B[b][0] for b in bk])).query(M(O[k][0][::3])); val[k] = dict(med_mm=round(float(np.median(d)), 1), p95_mm=round(float(np.percentile(d, 95)), 1))
    rep['her_ct_bones_mapped_to_base_f_bones'] = val
    NEWp, MODp = pelvis(B, O, M, rep); print('pelvis', round(time.time() - t0), flush=True)
    NEWb, MOVb, SKP = breasts(B, C, O, Z, M, rep); print('breasts', round(time.time() - t0), flush=True)
    rep['seconds'] = round(time.time() - t0)
    pickle.dump(dict(NEW={**NEWp, **NEWb}, MOD={**MODp, **MOVb}, SKIN=SKP, rep=rep), open(work / "geometry.pkl", "wb"))
    REPORT.write_text(json.dumps(rep, indent=1, default=float), encoding="utf-8")
    print(json.dumps({k: rep[k] for k in ('map', 'breasts', 'organs', 'urethral_group_anterior_shift_mm')}, indent=1, default=float)[:4000])


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["geometry", "page", "rig", "measure"])
    ap.add_argument("--work", default=DEFAULT_WORK); ap.add_argument("--out", default="/dev/shm/q292/pre"); ap.add_argument("--fresh"); ap.add_argument("--page")
    a = ap.parse_args()
    if a.cmd == "geometry":
        geometry(a.work)
    elif a.cmd == "page":
        import page_q292
        page_q292.build(a.work, a.out)
    elif a.cmd == "rig":
        import page_q292
        page_q292.splice_rig(a.fresh)
    else:
        import measure_q292
        measure_q292.run(a.page)


if __name__ == "__main__":
    main()
