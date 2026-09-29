"""Q169: the Visible Human FEMALE's own pelvic viscera -- urinary bladder, rectum and the pelvic part of the
sigmoid colon -- from her TotalSegmentator `total` labels (vhf_total.nii.gz: 21 urinary_bladder, 20 colon).
Q170: the same for the MALE (`--body vhm`), plus his prostate (label 22).

    python3 scripts/vhf_pelvic_viscera.py --origin '7.769,-885.229,14.137' [--png OUT.png]
    python3 scripts/vhf_pelvic_viscera.py --audit-bundle build/viewer_f_hr/bundle.json
    python3 scripts/vhf_pelvic_viscera.py --body vhm --origin '-6.035,-895.476,4.787' [--png OUT.png]
    python3 scripts/vhf_pelvic_viscera.py --body vhm --audit-bundle build/viewer_m_hr/bundle.json
    python3 scripts/vhf_pelvic_viscera.py --anal-check      # Q170: rectum's lower end vs each body's pelvic floor

Male volume (Q170): his torso-block `total` run (vhm_total) ends at atlas Y +32.5 mm, above his pubic symphysis --
it holds 0.5 cm3 of "bladder" and no prostate. The organs below come from his legs-block `total` run on its pelvis
slab (vhm_legs_total, slices 540-808), placed with the fixed block offset legs->torso = (+2.72, -0.89, -693.0) mm
RAS (docs/GEOMETRY_SOURCES.md "Stage 2, the Visible Human male's own CT": the torso block's bottom slice IS the
legs block's top slice; that same offset carries the femoral-head origin -6.035,-895.476,4.787 used by every
ct_vhm torso subject). Both blocks go onto one grid in the torso block's own affine, extended downward; the shared
slice is taken from the torso block. The legs block's in-plane grid lands 2.90 / 0.05 voxels off the torso grid,
so its labels are placed by nearest voxel (residual reported, <= 0.1 mm).

Real data only; every surface is hers. Cut rules, all measured on HER own labels:
  * pelvic inlet plane: through the sacral promontory (anterior-superior edge of her S1 body, label 26, within
    5 mm of the midline) and the upper border of her pubic symphysis (highest hip-bone voxel within 6 mm of the
    midline, anterior half), containing the left-right axis. Colon voxels caudal to it, largest connected piece
    (the one holding the anal end) = rectum + pelvic sigmoid; smaller pieces < 1 % are dropped and reported.
    The sigmoid is taken to begin at the pelvic brim (Michael & Rabi 2015, doi:10.7860/JCDR/2015/13850.6364,
    measure it from the same landmark), so what is shipped is the sigmoid's PELVIC part, named as such.
  * rectum / sigmoid: the "sigmoid take-off" (D'Souza et al. 2019 Delphi consensus, doi:10.1097/SLA.0000000000003251):
    a centreline is traced from the anal end to where the bowel crosses the inlet, with a cost 1/(d+0.5)^2 on the
    distance d (mm) to the bowel wall, so it stays in the lumen and does not short-cut through the places where two
    loops touch (the label merges touching loops). The take-off is the first local maximum of height along it
    (after 60 mm, followed by a >= 5 mm descent): where the bowel stops ascending in the sacral hollow and sweeps
    forward. Voxels are split by a marker watershed on -d seeded by the two halves of the centreline, so the cut
    runs across the tube and touching loops separate at their contact neck.
Surfaces: engine.volume_ingest.mask_surface(step 1, smooth 1.0) -> voxels_to_atlas -> minus the same origin as
every other ct_vhf subject, i.e. exactly what `ingest_volume_geometry.py convert --smooth 1.0` does; this script
writes the subject itself only because these ids have no entity in data/ (the atlas index has no viscera
category, so convert refuses them) -- each structure carries its own category/name, which the exporter reads.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import nibabel as nib
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from engine import volume_ingest as vol  # noqa: E402
from engine import vh_ingest as vh  # noqa: E402

TO = REPO / "data/ct_sources/task_outputs"
LEGS_TO_TORSO_RAS_MM = (2.72, -0.89, -693.0)     # docs/GEOMETRY_SOURCES.md, Stage 2 (VH male): fixed, not fitted
BODIES = {
    "vhf": {"task": "Q169", "src": [TO / "vhf_total.nii.gz"], "out_nii": TO / "vhf_pelvic_viscera.nii.gz",
            "subject": "ct_vhf_pelvis", "report": REPO / "data/derived/Q169_vhf_pelvic_viscera.json",
            "bones": REPO / "build/vh/ct_vhf", "labels": {1: "urinary_bladder", 2: "rectum", 3: "sigmoid_colon"},
            "who": "her", "sex": "FEMALE", "pfloor": ["ct_vhf_pfloor"], "reviewed_non_speck_drops": {}},
    "vhm": {"task": "Q170", "src": [TO / "vhm_total.nii.gz", TO / "vhm_legs_total.nii.gz"],
            "out_nii": TO / "vhm_pelvic_viscera.nii.gz",
            "subject": "ct_vhm_pelvis", "report": REPO / "data/derived/Q170_vhm_pelvic_viscera.json",
            "bones": REPO / "build/vh/vhm_both",
            "labels": {1: "urinary_bladder", 2: "rectum", 3: "sigmoid_colon", 4: "prostate"},
            "who": "his", "sex": "MALE", "pfloor": ["ct_vhm_pfloor_fix", "ct_vhm_pfloor"],
            # inspected (Q170): two bladder-labelled pieces NOT joined to the sac, each just over 1 % of it --
            # 0.52 cm3 6 mm posterior to the sac (legs block) and 0.46 cm3 35 mm cranial, anterior, in the torso
            # block's bottom slices (label 21 there is only this piece). Not part of the organ's surface; dropped
            # and listed individually in the report. Pelvic colon: one 2.0 cm3 piece (1.6 %) in the presacral space,
            # 4 mm in front of his sacrum and 7 mm behind the rectum, surrounded by unlabelled tissue and not joined
            # to any other colon voxel -- a broken-off wall fragment or a mislabel; not attached to anything, dropped.
            "reviewed_non_speck_drops": {"urinary_bladder": 2, "pelvic_colon": 1}},
}
BODY = "vhf"
SRC = BODIES[BODY]["src"][0]
OUT_NII = BODIES[BODY]["out_nii"]
SUBJECT = BODIES[BODY]["subject"]
SUBJ_DIR = REPO / "build/vh" / SUBJECT
REPORT = BODIES[BODY]["report"]
BONES = BODIES[BODY]["bones"]

TS = {"colon": 20, "urinary_bladder": 21, "prostate": 22, "sacrum": 25, "vertebrae_S1": 26, "hip_left": 77,
      "hip_right": 78}
LABELS = BODIES[BODY]["labels"]
NAMES = {"urinary_bladder": "Urinary bladder", "rectum": "Rectum",
         "sigmoid_colon": "Sigmoid colon (pelvic part, below the pelvic inlet)", "prostate": "Prostate"}


def configure(body):
    """Point the module-level paths/labels at one body (default vhf keeps Q169 exactly as it was)."""
    global BODY, SRC, OUT_NII, SUBJECT, SUBJ_DIR, REPORT, BONES, LABELS
    c = BODIES[body]
    BODY, SRC, OUT_NII, SUBJECT, REPORT, BONES, LABELS = (body, c["src"][0], c["out_nii"], c["subject"],
                                                          c["report"], c["bones"], c["labels"])
    SUBJ_DIR = REPO / "build/vh" / SUBJECT
SPECK_FRAC = 0.01

# Reference ranges. Volumes of these organs depend on filling, so each gate is a plausibility window with its
# basis written out; the length checks are the sharper test of the cut rules.
REFERENCE = {
    "urinary_bladder": {
        "volume_cm3": [5.0, 600.0],
        "basis": "wall plus contents; lower bound a near-empty bladder, upper bound the top of normal adult female "
                 "functional bladder capacity (bladder-diary reference limits in 161 asymptomatic women: Amundsen "
                 "et al. 2007, Neurourol Urodyn 26:341, doi:10.1002/nau.20241). A post-mortem bladder is expected "
                 "near the low end.",
    },
    "rectum": {
        "volume_cm3": [40.0, 400.0],
        "length_mm": [100.0, 180.0],
        "basis": "length: rectum ~12-15 cm from the anorectal junction to the rectosigmoid (Gray's Anatomy, 42nd "
                 "ed.), upper end = sigmoid take-off (D'Souza et al. 2019, Ann Surg 270:955, "
                 "doi:10.1097/SLA.0000000000003251); volume window derived from that length and a 2.5-5.5 cm "
                 "lumen (NOT a published volume range -- no per-segment rectal volume norm was found).",
    },
    "sigmoid_colon": {
        "volume_cm3": [15.0, 300.0],
        "length_mm": [60.0, 280.0],
        "basis": "length of the sigmoid measured from the pelvic brim: 15.2 +- 4.4 cm (Michael & Rabi 2015, J Clin "
                 "Diagn Res 9:AC04, doi:10.7860/JCDR/2015/13850.6364); window = mean -2 SD .. whole-sigmoid "
                 "length (Alatise et al. 2013, Surg Radiol Anat 35:249, doi:10.1007/s00276-012-1037-5, 30.5-67.8 "
                 "cm whole sigmoid). Volume window is a plausibility bound for the pelvic part only.",
    },
    "colon_total": {
        "basis": "fasting MRI in 75 healthy volunteers: ascending 203+-75, transverse 198+-79, descending 160+-86 mL "
                 "(Pritchard et al. 2014, Neurogastroenterol Motil 26:124, doi:10.1111/nmo.12243); her colon above "
                 "the inlet is compared with the sum of those means.",
        "above_inlet_ml_sum_of_means": 561.0,
    },
}

# Q170: the male's own windows (his bladder, his prostate); rectum/sigmoid/colon windows are shared
REFERENCE_VHM = {
    "urinary_bladder": {
        "volume_cm3": [5.0, 600.0],
        "basis": "wall plus contents; same plausibility window as hers: lower bound a near-empty bladder, upper bound "
                 "near the top of adult functional bladder capacity (largest single voided volume on 3-day "
                 "frequency-volume charts in 1688 community men: Blanker et al. 2001, Urology 57:1093, "
                 "doi:10.1016/s0090-4295(01)00988-8). A post-mortem bladder is expected near the low end.",
    },
    "prostate": {
        "volume_cm3": [8.0, 32.0],
        "basis": "normal adult prostate 20 +- 6 g from age 21-30, essentially constant after unless BPH develops "
                 "(Berry et al. 1984, J Urol 132:474, doi:10.1016/s0022-5347(17)49698-4; >1000 autopsy prostates); "
                 "window = mean +- 2 SD, grams read as cm3 (tissue density ~1). He was 38.",
    },
}


def reference(name):
    return REFERENCE_VHM[name] if BODY == "vhm" and name in REFERENCE_VHM else REFERENCE[name]


def to_atlas(idx, affine, origin):
    return vol.voxels_to_atlas(np.asarray(idx, dtype=float), affine) - origin


def largest_component(mask):
    lab, n = ndi.label(mask)
    if n == 0:
        return mask, []
    sizes = np.bincount(lab.ravel())
    sizes[0] = 0
    keep = sizes.argmax()
    dropped = [int(s) for i, s in enumerate(sizes) if i and i != keep and s]
    return lab == keep, dropped


def landmarks(V, A, O):
    s1 = to_atlas(np.argwhere(V == TS["vertebrae_S1"]), A, O)
    mid = s1[np.abs(s1[:, 0]) < 5]
    ant = mid[mid[:, 2] > np.median(mid[:, 2])]
    top = ant[ant[:, 1] > ant[:, 1].max() - 8]
    prom = top[top[:, 2].argmax()]
    hip = to_atlas(np.argwhere((V == TS["hip_left"]) | (V == TS["hip_right"])), A, O)
    near = hip[(np.abs(hip[:, 0]) < 6) & (hip[:, 2] > 0)]
    sym = near[near[:, 1].argmax()]
    d = sym - prom
    n = np.array([0.0, -d[2], d[1]])
    n /= np.linalg.norm(n)
    if n[1] < 0:
        n = -n                                     # normal points cranially
    sac, _ = largest_component((V == TS["sacrum"]) | (V == TS["vertebrae_S1"]))
    sac_pts = to_atlas(np.argwhere(sac), A, O)
    return prom, sym, n, float(sac_pts[:, 1].min())


def colon_below_inlet(V, A, O, prom, n):
    colon = V == TS["colon"]
    idx = np.argwhere(colon)
    mb = np.zeros_like(colon)
    mb[tuple(idx[(to_atlas(idx, A, O) - prom) @ n < 0].T)] = True
    return mb


def split_colon(V, A, O, prom, n, sp):
    import skimage.graph as sg
    from skimage.segmentation import watershed
    colon = V == TS["colon"]
    idx = np.argwhere(colon)
    below = (to_atlas(idx, A, O) - prom) @ n < 0
    mb = np.zeros_like(colon)
    mb[tuple(idx[below].T)] = True
    pelvic, dropped = largest_component(mb)
    pidx = np.argwhere(pelvic)
    lo = pidx.min(0) - 2
    hi = pidx.max(0) + 3
    sl = tuple(slice(a, b) for a, b in zip(lo, hi))
    sub = pelvic[sl]
    dt = ndi.distance_transform_edt(sub, sampling=sp)
    cost = np.where(sub, 1.0 / (dt + 0.5) ** 2, np.inf)
    sidx = np.argwhere(sub)
    Q = to_atlas(sidx + lo, A, O)
    anus = tuple(sidx[Q[:, 1].argmin()])
    mcp = sg.MCP_Geometric(cost, sampling=sp)
    G, _ = mcp.find_costs([anus])
    g = G[tuple(sidx.T)]
    near_plane = (Q - prom) @ n > -3.0
    exit_ = tuple(sidx[near_plane][g[near_plane].argmax()])
    path = np.array(mcp.traceback(exit_))                      # anus -> exit
    P = to_atlas(path + lo, A, O)
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    if P[0, 1] > P[-1, 1]:                                     # make sure s runs from the anal end
        path, P = path[::-1], P[::-1]
        s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    Ys = ndi.uniform_filter1d(P[:, 1], 9)
    take = None
    for i in range(len(s)):
        if s[i] < 60:
            continue
        fall = np.nonzero(Ys[i:] < Ys[i] - 5)[0]
        if len(fall) and Ys[i] >= Ys[max(0, i - 5):i + fall[0]].max():
            take = i
            break
    if take is None:
        raise SystemExit("no sigmoid take-off found on the centreline -- the rule does not apply; not splitting")
    # Q170: the pelvic colon can cross the inlet more than once (his does: a second, right-sided limb that rejoins
    # the sigmoid just above the brim). The centreline follows one exit; for every OTHER crossing band a second
    # lumen path is traced from the anal end. Where it leaves the first path (> 2 mm apart) the label branches: past
    # that point it cannot tell which limb continues the rectum (the label merges touching loops, and both limbs
    # have the same lumen, no neck), so the rectum ends at the take-off OR the first branch point, whichever comes
    # first, and everything beyond -- both limbs and the other crossing bands -- seeds the sigmoid. With a single
    # crossing (her) nothing changes.
    from scipy.spatial import cKDTree
    band = np.zeros(sub.shape, bool)
    band[tuple(sidx[near_plane].T)] = True
    band_l, nband = ndi.label(band, structure=np.ones((3, 3, 3)))
    cut, extra, branch_paths = take, [], []
    KP = cKDTree(P)
    for b in range(1, nband + 1):
        if band_l[exit_] == b:
            continue
        bm = band_l == b
        bi = np.argwhere(bm)
        e2 = tuple(bi[G[tuple(bi.T)].argmax()])
        p2 = np.array(mcp.traceback(e2))
        P2 = to_atlas(p2 + lo, A, O)
        if P2[0, 1] > P2[-1, 1]:
            p2, P2 = p2[::-1], P2[::-1]
        d2, j2 = KP.query(P2)
        away = np.nonzero(d2 > 2.0)[0]
        jdiv = int(j2[away[0] - 1]) if len(away) and away[0] > 0 else len(s) - 1
        cut = min(cut, jdiv)
        branch_paths.append((bm, p2[away[0]:] if len(away) else p2[:0]))
        s2 = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P2, axis=0), axis=1))]
        extra.append({"voxels": int(bm.sum()),
                      "centroid_atlas_mm": to_atlas(bi + lo, A, O).mean(0).round(1).tolist(),
                      "second_path_length_mm": round(float(s2[-1]), 1),
                      "branch_point_atlas_mm": P[jdiv].round(1).tolist(),
                      "branch_point_mm_from_anal_end": round(float(s[jdiv]), 1)})
    mk = np.zeros(sub.shape, np.int32)
    pp = path
    mk[tuple(pp[:cut + 1].T)] = 1
    mk[tuple(pp[cut + 1:].T)] = 2
    for bm, tail in branch_paths:
        mk[bm & (mk == 0)] = 2
        if len(tail):
            mk[tuple(tail.T)] = np.where(mk[tuple(tail.T)] == 1, 1, 2)
    ws = watershed(-dt, mk, mask=sub)
    out = np.zeros(V.shape, np.uint8)
    out[sl][ws == 1] = 2
    out[sl][ws == 2] = 3
    info = {
        "pelvic_colon_specks_dropped_voxels": dropped,
        "anal_end_atlas_mm": P[0].round(1).tolist(),
        "inlet_crossing_atlas_mm": P[-1].round(1).tolist(),
        "centreline_length_mm": round(float(s[-1]), 1),
        "take_off_atlas_mm": P[take].round(1).tolist(),
        "rectum_length_mm": round(float(s[cut]), 1),
        "sigmoid_pelvic_length_mm": round(float(s[-1] - s[cut]), 1),
        "centreline_atlas_mm": P[::4].round(1).tolist(),
    }
    if extra:
        info["extra_inlet_crossings_seeded_as_sigmoid"] = extra
        info["take_off_mm_from_anal_end"] = round(float(s[take]), 1)
        info["rectum_upper_end"] = {"rule": "take-off" if cut == take else "first branch point of the label (before "
                                    "the take-off: beyond it the label cannot say which limb continues the rectum)",
                                    "atlas_mm": P[cut].round(1).tolist()}
    return out, info


def load_body_volume():
    """Label volume + affine for the current body. Female: vhf_total as is. Male: his torso block (vhm_total) with
    his legs block's pelvis slab (vhm_legs_total) below it on one grid (see the module docstring)."""
    c = BODIES[BODY]
    if BODY == "vhf":
        img = nib.load(str(SRC))
        V, A, _codes = vol.load_labels(SRC)
        return V, A, img.header, {}
    Vt, At, _ = vol.load_labels(c["src"][0])
    Vl, Al, _ = vol.load_labels(c["src"][1])
    for M in (At, Al):
        assert np.allclose(M[:3, :3], np.diag(np.diag(M[:3, :3]))), "blocks must be axis-aligned"
    Al = Al.copy()
    Al[:3, 3] += np.array(LEGS_TO_TORSO_RAS_MM)
    kl = np.nonzero(Vl.reshape(-1, Vl.shape[2]).any(0))[0]
    k0 = int(kl.min())                                         # first labelled legs slice (pelvis slab start)
    # legs slice k sits at torso slice kt = (Al z(k) - At z(0)) / dz; the top legs slice is the torso's slice 0
    kt = lambda k: (Al[2, 2] * k + Al[2, 3] - At[2, 3]) / At[2, 2]
    top = kt(Vl.shape[2] - 1)
    assert abs(top) < 1e-6, f"legs top slice should coincide with torso slice 0, got {top}"
    ext = int(round(-kt(k0)))
    Ac = At.copy()
    Ac[2, 3] = At[2, 3] - ext * At[2, 2]
    V = np.zeros(Vt.shape[:2] + (Vt.shape[2] + ext,), np.uint8)
    V[:, :, ext:] = Vt.astype(np.uint8)
    # in-plane: legs (i, j) -> torso grid, nearest voxel
    Ainv = np.linalg.inv(Ac)
    ii = np.arange(Vl.shape[0]); jj = np.arange(Vl.shape[1])
    fi = (Ainv[0, 0] * (Al[0, 0] * ii + Al[0, 3]) + Ainv[0, 3])
    fj = (Ainv[1, 1] * (Al[1, 1] * jj + Al[1, 3]) + Ainv[1, 3])
    ri, rj = np.rint(fi).astype(int), np.rint(fj).astype(int)
    resid = float(max(np.abs(fi - ri).max() * abs(At[0, 0]), np.abs(fj - rj).max() * abs(At[1, 1])))
    oki, okj = (ri >= 0) & (ri < V.shape[0]), (rj >= 0) & (rj < V.shape[1])
    for k in range(k0, Vl.shape[2] - 1):                        # the shared top slice comes from the torso block
        kc = int(round(kt(k))) + ext
        sl = np.zeros(V.shape[:2], np.uint8)
        sl[np.ix_(ri[oki], rj[okj])] = Vl[np.ix_(ii[oki], jj[okj], [k])][:, :, 0]
        V[:, :, kc] = sl
    hdr = nib.Nifti1Header(); hdr.set_data_dtype(np.uint8)
    return V, Ac, hdr, {
        "blocks": {"torso": str(c["src"][0].relative_to(REPO)), "legs": str(c["src"][1].relative_to(REPO))},
        "legs_to_torso_ras_mm": list(LEGS_TO_TORSO_RAS_MM),
        "legs_to_torso_basis": "docs/GEOMETRY_SOURCES.md, Stage 2 (VH male): the torso block's bottom slice is the "
                               "legs block's top slice (image correlation 0.945); in-plane part by phase correlation; "
                               "the same offset carries his femoral-head origin to every ct_vhm torso subject",
        "legs_slices_used": [k0, int(Vl.shape[2] - 2)], "grid_slices_added_below_torso": ext,
        "in_plane_nearest_voxel_residual_mm": round(resid, 3),
        "torso_block_lowest_atlas_y_mm": None,                  # filled by main (needs the origin)
    }


def ct_bone_field(V, labels, A, organs, margin=30):
    """The same Gaussian(1 voxel) field mask_surface puts its 0.5 iso-surface on, for the CT bone labels, cropped
    to the organs' box + margin. Returns (field, affine of the crop)."""
    idx = np.argwhere(organs)
    lo = np.maximum(idx.min(0) - margin, 0)
    hi = np.minimum(idx.max(0) + margin + 1, V.shape)
    m = np.isin(V[tuple(slice(a, b) for a, b in zip(lo, hi))], labels)
    Ac = A.copy()
    Ac[:3, 3] = A[:3, :3] @ lo + A[:3, 3]
    return ndi.gaussian_filter(m.astype(np.float32), 1.0), Ac


def inside_ct_bone(v, field, A, O):
    """Vertices (atlas mm) whose position lies inside the CT bone surface (field > 0.5, trilinear)."""
    ras = np.c_[v[:, 0] + O[0], v[:, 2] + O[2], v[:, 1] + O[1]]
    idx = (np.linalg.inv(A) @ np.c_[ras, np.ones(len(ras))].T)[:3]
    val = ndi.map_coordinates(field, idx, order=1, mode="constant", cval=0.0)
    return int((val > 0.5).sum())


def mesh_mask(mask, A, O, smooth=1.0):
    idx = np.argwhere(mask)
    lo = np.maximum(idx.min(0) - 8, 0)
    hi = np.minimum(idx.max(0) + 9, mask.shape)
    crop = mask[tuple(slice(a, b) for a, b in zip(lo, hi))]
    v, f = vol.mask_surface(crop, step=1, smooth=smooth)
    return to_atlas(v + lo, A, O), f


def drop_mesh_specks(v, f, frac=SPECK_FRAC):
    """Q170: marching cubes on the smoothed field can pinch a thin voxel neck into a separate shell. Shells under
    `frac` of the structure's enclosed volume are dropped (same 1 % speck rule as the voxels); returns their cm3."""
    import trimesh
    t = trimesh.Trimesh(v, f, process=False)
    lab = trimesh.graph.connected_component_labels(t.face_adjacency, node_count=len(f))
    if lab.max() == 0:
        return v, f, []
    vols = np.array([abs(trimesh.Trimesh(v, f[lab == i], process=False).volume) for i in range(lab.max() + 1)])
    keep = vols >= frac * vols.sum()
    f2 = f[keep[lab]]
    used = np.unique(f2)
    remap = np.full(len(v), -1, np.int64)
    remap[used] = np.arange(len(used))
    return v[used], remap[f2], [round(float(x) / 1000, 3) for x in vols[~keep]]


def mesh_stats(v, f):
    import trimesh
    m = trimesh.Trimesh(v, f, process=False)
    parts = m.split(only_watertight=False)
    return {"triangles": int(len(f)), "mesh_volume_cm3": round(abs(float(m.volume)) / 1000, 2),
            "mesh_components": int(len(parts)), "watertight": bool(m.is_watertight),
            "bbox_min_mm": v.min(0).round(2).tolist(), "bbox_max_mm": v.max(0).round(2).tolist()}


def load_bone(atlas_ids):
    man = json.loads((BONES / "manifest.json").read_text())
    V = np.fromfile(BONES / "vertices.f32", np.float32).reshape(-1, 3)
    F = np.fromfile(BONES / "faces.u32", np.uint32).reshape(-1, 3)
    vs, fs, base = [], [], 0
    for s in man["structures"]:
        if s["atlas_id"] in atlas_ids:
            v = V[s["vertex_offset"]:s["vertex_offset"] + s["vertex_count"]].astype(float)
            f = F[s["face_offset"]:s["face_offset"] + s["triangle_count"]].astype(np.int64) - s["vertex_offset"]
            vs.append(v); fs.append(f + base); base += len(v)
    return np.concatenate(vs), np.concatenate(fs)


def containment(v, bones, prom, n, ct_bone=None):
    """Where a structure sits relative to the body's own hip bones and sacrum (mesh space, atlas mm)."""
    import trimesh
    from scipy.spatial import cKDTree
    hv = np.concatenate([bones["hip_bone_l"][0], bones["hip_bone_r"][0]])
    sv = bones["sacrum"][0]
    out = {}
    # pelvic box: hip bones laterally/inferiorly, sacrum posteriorly, symphysis anteriorly, inlet superiorly
    box_lo = np.array([hv[:, 0].min(), hv[:, 1].min(), sv[:, 2].min()])
    box_hi = np.array([hv[:, 0].max(), hv[:, 1].max(), hv[:, 2].max()])
    out["margin_to_pelvic_box_mm"] = {
        "right(+X)": round(float(box_hi[0] - v[:, 0].max()), 1), "left(-X)": round(float(v[:, 0].min() - box_lo[0]), 1),
        "superior(+Y, iliac crests)": round(float(box_hi[1] - v[:, 1].max()), 1),
        "inferior(-Y, ischial tuberosities)": round(float(v[:, 1].min() - box_lo[1]), 1),
        "anterior(+Z, pubis)": round(float(box_hi[2] - v[:, 2].max()), 1),
        "posterior(-Z, sacrum)": round(float(v[:, 2].min() - box_lo[2]), 1)}
    out["inside_pelvic_box"] = bool(all(x >= 0 for x in out["margin_to_pelvic_box_mm"].values()))
    sd = (v - prom) @ n
    out["fraction_of_vertices_below_inlet"] = round(float((sd < 0).mean()), 4)
    out["max_height_above_inlet_mm"] = round(float(max(0.0, sd.max())), 1)
    for name, (bv, bf) in bones.items():
        d, _ = cKDTree(bv).query(v)
        m = trimesh.Trimesh(bv, bf, process=False)
        inside = int(m.contains(v[::7]).sum()) if m.is_watertight else None
        out[f"min_surface_distance_to_{name}_mm"] = round(float(d.min()), 1)
        out[f"sampled_vertices_inside_{name}"] = inside
    if ct_bone is not None:                                    # Q170: his bone meshes are not watertight
        out["vertices_inside_ct_bone_surface_hip_sacrum"] = inside_ct_bone(v, *ct_bone)
    return out


def render_png(path, meshes, bones):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    import fast_simplification as fs
    col = {"urinary_bladder": "#e0b030", "rectum": "#8b4a2b", "sigmoid_colon": "#3f8f4f", "prostate": "#b03a8a"}
    who = BODIES[BODY]["who"]
    fig = plt.figure(figsize=(16, 9))
    for k, (elev, azim, title) in enumerate(((0, 90, f"front, from anterior ({who} right on the viewer's left)"), (0, 180, f"from {who} left side (anterior to the left)"))):
        ax = fig.add_subplot(1, 2, k + 1, projection="3d")
        for name, (v, f) in list(bones.items()) + list(meshes.items()):
            if len(f) > 20000:
                v, f = fs.simplify(v.astype(np.float32), f.astype(np.int32), 1 - 20000 / len(f))
            # atlas (X right, Y up, Z anterior) -> plot (x, y=depth, z=up)
            P = np.c_[v[:, 0], v[:, 2], v[:, 1]]
            bone = name in bones
            pc = Poly3DCollection(P[f], facecolor="#d9d4c7" if bone else col[name], edgecolor="none",
                                  alpha=0.18 if bone else 0.95, linewidth=0)
            pc.set_zsort("average")
            ax.add_collection3d(pc)
        ax.set_xlim(-150, 150); ax.set_ylim(-150, 150); ax.set_zlim(-100, 200)
        ax.set_box_aspect((300, 300, 300)); ax.view_init(elev=elev, azim=azim)
        ax.set_xlabel("X right (mm)"); ax.set_ylabel("Z anterior"); ax.set_zlabel("Y superior")
        ax.set_title(title)
    c = BODIES[BODY]
    fig.suptitle(f"{c['task']} VH {c['sex'].lower()}: urinary bladder (yellow), rectum (brown), pelvic sigmoid (green)"
                 + (", prostate (magenta)" if "prostate" in meshes else "") + f" with {who} hip bones + sacrum")
    plt.tight_layout(); plt.savefig(path, dpi=80); plt.close(fig)


def audit_bundle(bundle_path):
    import trimesh
    b = json.loads(Path(bundle_path).read_text())
    blob = (Path(bundle_path).parent / "bundle.bin").read_bytes()
    q = b.get("quantum_mm", 0.25)
    off, rows = 0, {}
    for e in b["structures"]:
        nv, nf = e["nv"], e["nf"]
        v = np.frombuffer(blob, np.int16, nv * 3, off).reshape(-1, 3) * q; off += nv * 6
        f = np.frombuffer(blob, np.uint16, nf * 3, off).reshape(-1, 3); off += nf * 6
        if e["id"] in LABELS.values():
            m = trimesh.Trimesh(v.astype(float), f.astype(np.int64), process=False)
            parts = m.split(only_watertight=False)
            rows[e["id"]] = {"cat": e["cat"], "subject": e["subject"], "triangles": nf,
                             "pieces": len(parts), "name": e.get("rec", {}).get("name")}
    rep = json.loads(REPORT.read_text())
    rep["bundle_audit"] = {"bundle": str(Path(bundle_path).resolve().relative_to(REPO)), "structures": rows,
                           "bundle_triangles": int(b.get("triangles", 0)), "bundle_structures": len(b["structures"])}
    REPORT.write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep["bundle_audit"], indent=1))


SOURCE_VHM = ("U.S. National Library of Medicine, The Visible Human Project (public domain), MALE frozen CT via the "
              "NCI Imaging Data Commons (torso series 5d409385-d3e7-48a9-ae50-150b39e834da, legs series "
              "145c2668-7d2f-4d7e-b1c7-2cf2462bef60); TotalSegmentator v2 `total` task labels "
              "(data/ct_sources/task_outputs/vhm_total.nii.gz and, below his torso block, vhm_legs_total.nii.gz: "
              "21 urinary_bladder, 20 colon, 22 prostate). References: Berry 1984 doi:10.1016/s0022-5347(17)49698-4; "
              "Blanker 2001 doi:10.1016/s0090-4295(01)00988-8; D'Souza 2019 doi:10.1097/SLA.0000000000003251; "
              "Michael & Rabi 2015 doi:10.7860/JCDR/2015/13850.6364; Alatise 2013 doi:10.1007/s00276-012-1037-5; "
              "Pritchard 2014 doi:10.1111/nmo.12243.")


def describe_pieces(mask, kept, A, O, vox_cm3, min_cm3):
    """Every dropped piece >= min_cm3: size, centroid and gap to the kept piece (atlas mm)."""
    from scipy.spatial import cKDTree
    lab, n = ndi.label(mask & ~kept)
    K = cKDTree(to_atlas(np.argwhere(kept), A, O))
    out = []
    for i in range(1, n + 1):
        idx = np.argwhere(lab == i)
        if len(idx) * vox_cm3 < min_cm3:
            continue
        P = to_atlas(idx, A, O)
        out.append({"cm3": round(len(idx) * vox_cm3, 3), "centroid_atlas_mm": P.mean(0).round(1).tolist(),
                    "gap_to_kept_mm": round(float(K.query(P)[0].min()), 1)})
    return out


def subject_meshes(subjects, ids=None):
    """{atlas_id: (v, f)} from build/vh subjects; the first subject listed wins an id (as in the rebuild order)."""
    out = {}
    for sub in subjects:
        d = REPO / "build/vh" / sub
        if not (d / "manifest.json").exists():
            continue
        man = json.loads((d / "manifest.json").read_text())
        Vv = np.fromfile(d / "vertices.f32", np.float32).reshape(-1, 3)
        F = np.fromfile(d / "faces.u32", np.uint32).reshape(-1, 3)
        for st in man["structures"]:
            a = st["atlas_id"]
            if a in out or (ids and a not in ids):
                continue
            v = Vv[st["vertex_offset"]:st["vertex_offset"] + st["vertex_count"]].astype(float)
            f = F[st["face_offset"]:st["face_offset"] + st["triangle_count"]].astype(np.int64) - st["vertex_offset"]
            out[a] = (v, f)
    return out


def anal_check():
    """Q170 (open item from Q169): where each body's rectum mesh ends relative to that body's own external anal
    sphincter and levator ani meshes. Measures only -- no geometry is changed here."""
    import trimesh
    from scipy.spatial import cKDTree
    res = {}
    for body, c in BODIES.items():
        rect = subject_meshes([c["subject"]], {"rectum"}).get("rectum")
        pf = subject_meshes(c["pfloor"])
        if rect is None or "external_anal_sphincter" not in pf:
            res[body] = {"skipped": "rectum or external_anal_sphincter mesh absent"}
            continue
        rv, rf = rect
        ev, ef = pf["external_anal_sphincter"]
        low = rv[rv[:, 1].argmin()]
        cap = rv[rv[:, 1] < low[1] + 5.0]                                  # the rectum's lowest 5 mm
        E = trimesh.Trimesh(ev, ef, process=False)
        R = trimesh.Trimesh(rv, rf, process=False)
        d_re = cKDTree(ev).query(rv)[0]
        la = [pf[k][0] for k in ("levator_ani_l", "levator_ani_r") if k in pf]
        lav = np.concatenate(la) if la else None
        # horizontal offset of the rectum's lowest cap from the sphincter's axis (its centroid in the X-Z plane)
        e_c = ev.mean(0)
        e_r = np.linalg.norm((ev - e_c)[:, [0, 2]], axis=1)
        row = {
            "pelvic_floor_subjects": [s for s in c["pfloor"] if (REPO / "build/vh" / s / "manifest.json").exists()],
            "rectum_lowest_point_atlas_mm": low.round(1).tolist(),
            "rectum_lowest_5mm_cap_centroid_atlas_mm": cap.mean(0).round(1).tolist(),
            "external_anal_sphincter_y_range_mm": [round(float(ev[:, 1].min()), 1), round(float(ev[:, 1].max()), 1)],
            "external_anal_sphincter_centroid_atlas_mm": e_c.round(1).tolist(),
            "external_anal_sphincter_radius_about_its_axis_mm": [round(float(e_r.min()), 1), round(float(np.median(e_r)), 1),
                                                                round(float(e_r.max()), 1)],
            "external_anal_sphincter_watertight": bool(E.is_watertight),
            "gap_rectum_lowest_to_sphincter_top_mm": round(float(low[1] - ev[:, 1].max()), 1),
            "gap_rectum_lowest_to_sphincter_bottom_mm": round(float(low[1] - ev[:, 1].min()), 1),
            "rectum_vertices_within_sphincter_height": int(((rv[:, 1] >= ev[:, 1].min()) & (rv[:, 1] <= ev[:, 1].max())).sum()),
            "min_distance_rectum_to_sphincter_mm": round(float(d_re.min()), 1),
            "distance_rectum_lowest_point_to_sphincter_mm": round(float(cKDTree(ev).query(low)[0]), 1),
            "horizontal_offset_rectum_cap_to_sphincter_axis_mm": round(float(np.linalg.norm((cap.mean(0) - e_c)[[0, 2]])), 1),
            "rectum_vertices_inside_sphincter": int(E.contains(rv).sum()) if E.is_watertight else None,
            "sphincter_vertices_inside_rectum": int(R.contains(ev).sum()) if R.is_watertight else None,
        }
        if lav is not None:
            row["levator_ani_y_range_mm"] = [round(float(lav[:, 1].min()), 1), round(float(lav[:, 1].max()), 1)]
            row["gap_rectum_lowest_to_levator_lowest_mm"] = round(float(low[1] - lav[:, 1].min()), 1)
            row["min_distance_rectum_to_levator_ani_mm"] = round(float(cKDTree(lav).query(rv)[0].min()), 1)
        res[body] = row
    rep_path = BODIES["vhm"]["report"]
    rep = json.loads(rep_path.read_text()) if rep_path.exists() else {}
    rep["anal_canal_check"] = {
        "question": "does the rectum (the TotalSegmentator colon label's anal end) reach the body's own external anal "
                    "sphincter / pelvic floor meshes, stop well above them, or run through them? Measured only.",
        "sign": "gap > 0: the rectum's lowest point lies ABOVE that level; < 0: below it (atlas +Y superior)",
        **res}
    rep_path.write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep["anal_canal_check"], indent=1))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--origin")
    ap.add_argument("--png")
    ap.add_argument("--audit-bundle")
    ap.add_argument("--body", choices=sorted(BODIES), default="vhf")
    ap.add_argument("--anal-check", action="store_true", help="Q170: rectum's lower end vs each body's pelvic floor")
    args = ap.parse_args()
    if args.anal_check:
        return anal_check()
    configure(args.body)
    if args.audit_bundle:
        return audit_bundle(args.audit_bundle)
    if not args.origin:
        raise SystemExit("--origin is required (the same value the body's rebuild script passes its CT subjects)")
    O = vh.parse_origin(args.origin)
    V, A, hdr, vinfo = load_body_volume()
    cfg = BODIES[BODY]
    if vinfo:
        vinfo["torso_block_lowest_atlas_y_mm"] = round(float(
            to_atlas([[0, 0, vinfo["grid_slices_added_below_torso"]]], A, O)[0, 1]), 2)
    sp = tuple(float(x) for x in np.sqrt((A[:3, :3] ** 2).sum(0)))
    vox_cm3 = float(abs(np.linalg.det(A[:3, :3]))) / 1000
    prom, sym, n, sac_apex_y = landmarks(V, A, O)

    lab = np.zeros(V.shape, np.uint8)
    bladder, bl_drop = largest_component(V == TS["urinary_bladder"])
    lab[bladder] = 1
    colon_parts, cinfo = split_colon(V, A, O, prom, n, sp)
    lab[colon_parts > 0] = colon_parts[colon_parts > 0]
    drops = {"urinary_bladder": bl_drop}
    kept = {"urinary_bladder": bladder}
    if 4 in LABELS:
        prostate, pr_drop = largest_component(V == TS["prostate"])
        assert not (lab[prostate] > 0).any(), "prostate overlaps another organ label"
        lab[prostate] = 4
        drops["prostate"], kept["prostate"] = pr_drop, prostate
    del colon_parts
    out = nib.Nifti1Image(lab, A, header=hdr)
    out.set_data_dtype(np.uint8)
    nib.save(out, str(OUT_NII))

    bones = {"hip_bone_l": load_bone({"hip_bone_l"}), "hip_bone_r": load_bone({"hip_bone_r"}),
             "sacrum": load_bone({"sacrum"})}
    field, Af = ct_bone_field(V, [TS["hip_left"], TS["hip_right"], TS["sacrum"], TS["vertebrae_S1"]], A, lab > 0)
    ct_bone = (field, Af, O)
    SUBJ_DIR.mkdir(parents=True, exist_ok=True)
    vb, fb, structs, meshes = [], [], [], {}
    vbase = fbase = 0
    per = {}
    for k, name in LABELS.items():
        m = lab == k
        comps = ndi.label(m)[1]
        v, f = mesh_mask(m, A, O)
        v, f, mesh_specks = drop_mesh_specks(v, f)
        meshes[name] = (v, f)
        st = mesh_stats(v, f)
        vol_cm3 = round(float(m.sum()) * vox_cm3, 2)
        ref = reference(name)
        row = {"label": k, "voxel_volume_cm3": vol_cm3, "voxel_components": int(comps), **st,
               "reference_volume_cm3": ref["volume_cm3"],
               "volume_in_reference_range": bool(ref["volume_cm3"][0] <= vol_cm3 <= ref["volume_cm3"][1]),
               "reference_basis": ref["basis"]}
        if mesh_specks:
            row["mesh_specks_dropped_cm3"] = mesh_specks
        if name in drops:
            row["specks_dropped_cm3"] = [round(x * vox_cm3, 3) for x in drops[name] if x * vox_cm3 < SPECK_FRAC * vol_cm3]
            big = [x for x in drops[name] if x * vox_cm3 >= SPECK_FRAC * vol_cm3]
            if big:
                allowed = cfg["reviewed_non_speck_drops"].get(name, 0)
                if len(big) > allowed:
                    raise SystemExit(f"{name}: {len(big)} dropped piece(s) >= 1% of the structure ({big}) -- not "
                                     f"specks and not reviewed; stop")
                row["non_speck_pieces_dropped"] = describe_pieces(V == TS[name], kept[name], A, O, vox_cm3,
                                                                  SPECK_FRAC * vol_cm3)
        if name in ("rectum", "sigmoid_colon"):
            key = "rectum_length_mm" if name == "rectum" else "sigmoid_pelvic_length_mm"
            row["centreline_length_mm"] = cinfo[key]
            row["reference_length_mm"] = ref["length_mm"]
            row["length_in_reference_range"] = bool(ref["length_mm"][0] <= cinfo[key] <= ref["length_mm"][1])
        row["position"] = containment(v, bones, prom, n, ct_bone)
        per[name] = row
        structs.append({
            "atlas_id": name, "category": "organ", "name": NAMES[name], "region": "pelvis",
            "source_structure": {"urinary_bladder": "urinary_bladder", "prostate": "prostate"}.get(
                name, f"colon ({name} part)"),
            "side": None, "source_file": f"{OUT_NII.name}#{k}",
            "vertex_offset": vbase, "face_offset": fbase, "vertex_count": int(len(v)), "triangle_count": int(len(f)),
            "bbox_min_mm": st["bbox_min_mm"], "bbox_max_mm": st["bbox_max_mm"]})
        vb.append(v.astype(np.float32)); fb.append((f + vbase).astype(np.uint32))
        vbase += len(v); fbase += len(f)
    allv, allf = np.concatenate(vb), np.concatenate(fb)
    (SUBJ_DIR / "vertices.f32").write_bytes(allv.tobytes())
    (SUBJ_DIR / "faces.u32").write_bytes(allf.tobytes())
    (SUBJ_DIR / "manifest.json").write_text(json.dumps({
        "subject": SUBJECT, "frame": "atlas: +X right, +Y superior, +Z anterior, millimetres",
        "source_volume": str(OUT_NII.relative_to(REPO)), "source_kind": "labelled volume (NIfTI)",
        "label_map": f"{BODY}_pelvic_viscera (labels " + ", ".join(f"{k} {v}" for k, v in LABELS.items()) + ")",
        "marching_cubes_step": 1, "surface_smoothing_sigma_voxels": 1.0,
        "vertex_count": int(len(allv)), "triangle_count": int(len(allf)),
        "bbox_min_mm": allv.min(0).round(4).tolist(), "bbox_max_mm": allv.max(0).round(4).tolist(),
        "attribution": [f"Visible Human {cfg['sex'].lower()} CT (U.S. National Library of Medicine, public domain, "
                        "via the NCI Imaging Data Commons); TotalSegmentator v2 `total` labels; rectum/sigmoid split "
                        f"and pelvic cut by scripts/vhf_pelvic_viscera.py ({cfg['task']})."],
        "structures": structs}, indent=2))

    colon_all = float((V == TS["colon"]).sum()) * vox_cm3
    pelvic = per["rectum"]["voxel_volume_cm3"] + per["sigmoid_colon"]["voxel_volume_cm3"]
    report = {
        "source": SOURCE_VHM if BODY == "vhm" else
                  "U.S. National Library of Medicine, The Visible Human Project (public domain), FEMALE CT via the "
                  "NCI Imaging Data Commons; TotalSegmentator v2 `total` task labels "
                  "(data/ct_sources/task_outputs/vhf_total.nii.gz: 21 urinary_bladder, 20 colon). References: "
                  "D'Souza 2019 doi:10.1097/SLA.0000000000003251; Michael & Rabi 2015 doi:10.7860/JCDR/2015/13850.6364; "
                  "Alatise 2013 doi:10.1007/s00276-012-1037-5; Pritchard 2014 doi:10.1111/nmo.12243; Amundsen 2007 "
                  "doi:10.1002/nau.20241.",
        "task": cfg["task"], "subject": SUBJECT, "script": "scripts/vhf_pelvic_viscera.py",
        "label_volume": str(OUT_NII.relative_to(REPO)), "origin_atlas_mm": O.tolist(),
        "cut_rules": {
            "pelvic_inlet_plane": f"through {cfg['who']} sacral promontory and the upper border of {cfg['who']} pubic symphysis, "
                                  "containing the left-right axis; colon caudal to it = rectum + pelvic sigmoid",
            "rectum_sigmoid": "sigmoid take-off: first local height maximum along a lumen-seeking centreline from "
                              "the anal end (after 60 mm, then >= 5 mm descent); marker watershed on -distance",
        },
        "landmarks_atlas_mm": {"sacral_promontory": prom.round(1).tolist(), "symphysis_upper_border": sym.round(1).tolist(),
                               "inlet_normal": n.round(4).tolist(),
                               "inlet_angle_to_horizontal_deg": round(float(np.degrees(np.arctan2(abs(sym[1] - prom[1]), abs(sym[2] - prom[2])))), 1),
                               "obstetric_conjugate_mm": round(float(np.linalg.norm(sym - prom)), 1),
                               "sacral_apex_y_mm": round(sac_apex_y, 1),
                               "take_off_fraction_of_sacral_height_from_promontory":
                                   round(float((prom[1] - cinfo["take_off_atlas_mm"][1]) / (prom[1] - sac_apex_y)), 3),
                               **({"rectum_upper_end_fraction_of_sacral_height_from_promontory": round(float(
                                   (prom[1] - cinfo["rectum_upper_end"]["atlas_mm"][1]) / (prom[1] - sac_apex_y)), 3)}
                                  if "rectum_upper_end" in cinfo else {})},
        "colon": {**{k: v for k, v in cinfo.items() if k != "pelvic_colon_specks_dropped_voxels"},
                  "pelvic_colon_specks_dropped_cm3": [round(x * vox_cm3, 3) for x in cinfo["pelvic_colon_specks_dropped_voxels"]],
                  "speck_rule": f"pieces < {SPECK_FRAC:.0%} of the structure dropped",
                  "whole_colon_label_cm3": round(colon_all, 1), "pelvic_colon_cm3": round(pelvic, 1),
                  "colon_above_inlet_cm3": round(colon_all - pelvic, 1),
                  "above_inlet_vs_reference_sum_of_means_ml": REFERENCE["colon_total"]["above_inlet_ml_sum_of_means"],
                  "reference_basis": REFERENCE["colon_total"]["basis"]},
        "structures": per,
    }
    if vinfo:
        report["volume_assembly"] = vinfo
        report["origin_basis"] = ("his femoral-head origin, the constant scripts/vhm_rebuild_bundle.sh passes every "
                                  "torso-block ct_vhm subject (docs/GEOMETRY_SOURCES.md Stage 2)")
    for name, d in (("pelvic colon", cinfo["pelvic_colon_specks_dropped_voxels"]),):
        big = [x for x in d if x * vox_cm3 >= SPECK_FRAC * pelvic]
        if big and len(big) <= cfg["reviewed_non_speck_drops"].get("pelvic_colon", 0):
            report["colon"]["pelvic_colon_specks_dropped_cm3"] = [
                round(x * vox_cm3, 3) for x in d if x * vox_cm3 < SPECK_FRAC * pelvic]
            report["colon"]["non_speck_pieces_dropped"] = describe_pieces(
                colon_below_inlet(V, A, O, prom, n), (lab == 2) | (lab == 3), A, O, vox_cm3, SPECK_FRAC * pelvic)
        elif big:
            raise SystemExit(f"{name}: a dropped piece is >= 1% of the structure ({big}) -- not a speck; stop")
    if args.png:
        render_png(args.png, meshes, bones)
        report["check_png"] = "scratchpad (not committed)"
    if REPORT.exists():                                        # keep the separately run checks
        old = json.loads(REPORT.read_text())
        for key in ("anal_canal_check",):
            if key in old and old.get("task") == report["task"]:
                report[key] = old[key]
    REPORT.write_text(json.dumps(report, indent=1))
    for k, r in per.items():
        print(f"{k:16s} {r['voxel_volume_cm3']:7.1f} cm3  comps {r['voxel_components']}/{r['mesh_components']}  "
              f"tris {r['triangles']}  in_box {r['position']['inside_pelvic_box']}")
    print(f"wrote {SUBJ_DIR} {OUT_NII.relative_to(REPO)} {REPORT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
