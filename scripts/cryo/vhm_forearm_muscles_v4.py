"""Male RIGHT forearm muscles v4 (Q166): inter-muscle boundaries FROM his photographed pale septa by construction,
names from the Q165 rule labels by majority overlap. Rule-assisted naming; every structure badged.

    python3 scripts/cryo/vhm_forearm_muscles_v4.py --q164-work SCRATCH/q164_m_forearm/work \
        --rgb SCRATCH/q165_m_forearm/rgb_frame.npy --work SCRATCH/q166_m_forearm
    python3 scripts/cryo/vhm_forearm_muscles_v4.py --stamp build/vh/ct_vhm_forearm_v4      # after the converter

Q165 (vhm_forearm_muscles_v3.py, imported, not edited) got the tissue classes right but its label lines came from rule
seeds and crossed the visible septa (contact-on-septum 0.21-0.53). Here the order is reversed:
 1. REGIONS FROM SEPTA, per resliced slice. Paleness residual P (Q165: g/r minus its 5.5 mm local median) is smoothed
    (sigma 0.5 mm) and flooded (watershed from its h-minima, h 0.01) inside the muscle class, so every basin boundary
    runs along a paleness crest. Adjacent basins are then merged, weakest first (region-adjacency graph, merged
    boundaries pooled), while less than --support (0.5) of their shared boundary lies within 1 px in-plane / 1 slice of
    a pale pixel (P >= --pale, 0.10). What survives = septum LINES: thinned (1 px), gap-bridged within the slice only,
    each supported by pale pixels on >= half its length. Septum mask = those lines + fat + pale/other tissue + bone +
    outside; muscle regions = 4-connected components of (muscle class AND NOT septum mask), >= 4 mm2.
 2. LINKING into 3-D bellies: region a (slice i) and b (slice i+1) are one belly when IoU(a, b) >= --iou (0.5). IoU
    >= 0.5 is one-to-one, so a slice where a septum is missed (two bellies fused) never chains two bellies together;
    the track just breaks there. One-slice gaps are bridged (i -> i+2) for regions left unmatched.
 3. NAMING: each belly takes the Q165 rule label it overlaps most (data/ct_sources/task_outputs/
    vhm_forearm_muscles_v3.nii.gz sampled at every frame voxel); purity = share of the belly's voxels in that label;
    purity < --min-purity (0.6) stays unnamed (reported). Several bellies may form one muscle, so every boundary between
    two named muscles lies on a septum line / non-muscle in-plane, or between two bellies along the axis.
 4. EXPECTATIONS exactly as Q165: repo architecture volume (data/muscles/upper_limb/<id>_r.json) x ONE factor = his own
    upper-arm (biceps + brachialis + triceps meshes, build/vh) / their architecture volumes (2.698 on the Q165 run).
 5. SHIP GATE: volume 0.5-2.0x expectation; main 26-connected component >= 0.98; CONTACT-on-septum >= 0.7 = median over
    slices of the share of its contact pixels (4-neighbour boundary pixels with another named muscle within 2 px)
    lying within 1 px of PHOTOGRAPHED septum evidence in that same slice (a pale pixel P >= --pale, or a non-muscle
    tissue pixel) -- the watershed lines themselves do not count; PT/BR/ECRL/anconeus out of range (arise above his
    radial-head plane). STABILITY: rerun at --pale 0.08 and 0.12; ship only muscles passing at all three.

Outputs (passing muscles only get an atlas_id): data/ct_sources/task_outputs/vhm_forearm_muscles_v4.nii.gz,
mappings/vhm_forearm_muscles_v4_labels.json, mappings/subjects/ct_vhm_forearm_v4_volume_mapping.json,
data/derived/Q166_vhm_forearm_v4.json, montage PNG in --work.
"""
from __future__ import annotations

import argparse
import heapq
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "4"); os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
import numpy as np  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(Path(__file__).resolve().parent))
import vhm_forearm_muscles_fullres as Q  # noqa: E402  (Q164: frame, RAS volume, gate helpers, stamping)
import vhm_forearm_muscles_v3 as V  # noqa: E402       (Q165: tissue classes, paleness, expectations factor)

BADGE = "rule-assisted naming; boundaries from his photographed septa"
SUBJECT = "ct_vhm_forearm_v4"
LABEL_MAP = "vhm_forearm_muscles_v4"
RULE_VOLUME = REPO / "data/ct_sources/task_outputs/vhm_forearm_muscles_v3.nii.gz"
RULE_LABELS = REPO / "mappings/vhm_forearm_muscles_v3_labels.json"
SOURCE = ("U.S. National Library of Medicine, The Visible Human Project (public domain): male cryosection photographs at "
          "full resolution (0.33 mm, IDC series 4aaf9181-fb6a-4a4c-bf49-d1eb9ed4a385, instances 1575-1819) and his CT "
          "radius/ulna labels (data/ct_sources/task_outputs/vhm_arm_bones_cryo_completed.nii.gz) for registration. "
          "Derived data (scripts/cryo/vhm_forearm_muscles_v4.py): muscle regions enclosed by the pale fascial septa "
          "seen in the photographs, linked across sections, NAMED by majority overlap with the Q165 rule-based labels "
          "(data/ct_sources/task_outputs/vhm_forearm_muscles_v3.nii.gz); not traced by an anatomist. Expectations: "
          "repository architecture volumes (Holzbaur, Murray & Delp 2005 Ann Biomed Eng 33:829) scaled by his own "
          "upper-arm muscle volumes.")
# Variants measured with this script on 2026-09-29 (pale 0.10; flags beyond the defaults), kept in the report.
TUNING_TRIED = [
    {"flags": "--link iou --sigma-u 0 (IoU 0.5 tracking, no axial smoothing)", "regions_per_slice": 19, "bellies": 3497, "bellies_ge_0p1cm3": 508,
     "median_slices_ge_0p1cm3": 2, "unnamed_cm3": 602.2, "named_cm3": 331.0, "pass": ["supinator", "extensor_indicis"], "stable_0.08_0.12": ["extensor_indicis"]},
    {"flags": "--link mutual --sigma-u 0", "regions_per_slice": 19, "bellies": 1952, "bellies_ge_0p1cm3": 379, "median_slices_ge_0p1cm3": 6,
     "unnamed_cm3": 575.1, "named_cm3": 358.1, "pass": []},
    {"flags": "--link iou (sigma-u 1.5)", "regions_per_slice": 17, "bellies": 2502, "bellies_ge_0p1cm3": 493, "median_slices_ge_0p1cm3": 3,
     "unnamed_cm3": 636.6, "named_cm3": 299.4, "pass": ["flexor_pollicis_longus"]},
    {"flags": "--support 0.4", "regions_per_slice": 21, "bellies": 1700, "bellies_ge_0p1cm3": 465, "median_slices_ge_0p1cm3": 6,
     "unnamed_cm3": 588.6, "named_cm3": 339.1, "pass": ["pronator_quadratus", "extensor_indicis"]},
    {"flags": "3-D watershed of the axially smoothed paleness + 3-D pooled-boundary merge (scratch prototype, not in this script)",
     "bellies": 820, "bellies_ge_0p1cm3": 109, "note": "two bellies of 512 and 371 cm3 (purity 0.24 / 0.21) swallow the forearm; named 50.7 cm3"},
    {"flags": "per-slice only, no merge support (closing/dilation of pale >= thr, components of muscle minus ridge)", "regions_per_slice": 3,
     "note": "one region holds most of each section: the pale ridge alone never closes"},
]
OUT_OF_RANGE = V.OUT_OF_RANGE
T = V.TISSUE


# ----------------------------------------------------------------------------------------------- pure functions
def pair_stats(L, E):
    """{(a, b): [sum, n]} (a < b) over face-neighbour pixel/voxel pairs (any dimension) of different nonzero labels;
    value = max(E[p], E[q])."""
    L = np.asarray(L); E = np.asarray(E, float); st = {}
    for ax in range(L.ndim):
        lo = tuple(slice(None, -1) if d == ax else slice(None) for d in range(L.ndim))
        hi = tuple(slice(1, None) if d == ax else slice(None) for d in range(L.ndim))
        A, B, EA, EB = L[lo], L[hi], E[lo], E[hi]
        k = (A != B) & (A > 0) & (B > 0)
        if not k.any():
            continue
        a = np.minimum(A[k], B[k]).astype(np.int64); b = np.maximum(A[k], B[k]).astype(np.int64)
        u, inv = np.unique(a * (1 << 32) + b, return_inverse=True)
        s = np.bincount(inv, weights=np.maximum(EA[k], EB[k])); n = np.bincount(inv)
        for kk, ss, nn in zip(u.tolist(), s.tolist(), n.tolist()):
            t = (kk >> 32, kk & 0xFFFFFFFF); o = st.get(t)
            if o:
                o[0] += ss; o[1] += nn
            else:
                st[t] = [ss, nn]
    return st


def merge_weak(L, E, thr):
    """Hierarchical region-adjacency merge: repeatedly merge the adjacent pair whose shared-boundary mean of E is
    lowest, pooling boundaries, while that mean < thr. Returns the merged label image (ids = surviving roots)."""
    L = np.asarray(L); nb = {}
    for (a, b), (s, n) in pair_stats(L, E).items():
        e = [s, n]; nb.setdefault(a, {})[b] = e; nb.setdefault(b, {})[a] = e
    h = [(e[0] / e[1], a, b) for a in nb for b, e in nb[a].items() if a < b]; heapq.heapify(h); parent = {}
    while h:
        m, a, b = heapq.heappop(h)
        if m >= thr:
            break
        if a in parent or b in parent or b not in nb.get(a, {}):
            continue
        e = nb[a][b]
        if abs(e[0] / e[1] - m) > 1e-12:
            continue                                  # stale heap entry
        parent[b] = a; del nb[a][b]; del nb[b][a]
        for c, e2 in nb.pop(b).items():
            del nb[c][b]; e1 = nb[a].get(c)
            if e1 is not None:
                e1[0] += e2[0]; e1[1] += e2[1]; e = e1
            else:
                e = e2; nb[a][c] = e; nb[c][a] = e
            heapq.heappush(h, (e[0] / e[1], min(a, c), max(a, c)))
    lut = np.arange(int(L.max()) + 1)
    for x in range(1, len(lut)):
        r = x
        while r in parent:
            r = parent[r]
        lut[x] = r
    return lut[L]


def septum_lines(M):
    """1-px lines separating different nonzero labels: pixels whose label is larger than a nonzero 4-neighbour's."""
    M = np.asarray(M); out = np.zeros(M.shape, bool)
    for A, B, oa in ((M[:, :-1], M[:, 1:], (slice(None), slice(None, -1))), (M[:-1], M[1:], (slice(None, -1), slice(None))),
                     (M[:, 1:], M[:, :-1], (slice(None), slice(1, None))), (M[1:], M[:-1], (slice(1, None), slice(None)))):
        out[oa] |= (A > B) & (B > 0)
    return out


def regions(muscle, lines, min_px):
    """4-connected components of muscle AND NOT lines, components < min_px dropped (0). Returns (labels, n)."""
    from scipy import ndimage as ndi
    lab, n = ndi.label(np.asarray(muscle, bool) & ~np.asarray(lines, bool), structure=ndi.generate_binary_structure(2, 1))
    if n:
        sz = np.bincount(lab.ravel()); keep = sz >= min_px; keep[0] = False
        lut = np.zeros(n + 1, np.int32); lut[keep] = np.arange(1, int(keep.sum()) + 1); lab = lut[lab]; n = int(keep.sum())
    return lab.astype(np.int32), n


def iou_links(A, B, iou_min):
    """[(a, b, iou)] for label pairs of two slices with IoU >= iou_min (one-to-one when iou_min >= 0.5)."""
    A = np.asarray(A, np.int64); B = np.asarray(B, np.int64)
    na = np.bincount(A.ravel()); nbb = np.bincount(B.ravel()); k = (A > 0) & (B > 0)
    if not k.any():
        return []
    u, c = np.unique(A[k] * (1 << 32) + B[k], return_counts=True)
    out = []
    for key, n in zip(u.tolist(), c.tolist()):
        a, b = key >> 32, key & 0xFFFFFFFF; iou = n / (na[a] + nbb[b] - n)
        if iou >= iou_min:
            out.append((int(a), int(b), float(iou)))
    return out


def mutual_links(A, B, min_frac):
    """[(a, b, frac)]: a and b are each other's largest-overlap partner and the overlap is >= min_frac of the smaller
    region (one-to-one by construction)."""
    A = np.asarray(A, np.int64); B = np.asarray(B, np.int64)
    na = np.bincount(A.ravel()); nbb = np.bincount(B.ravel()); k = (A > 0) & (B > 0)
    if not k.any():
        return []
    u, c = np.unique(A[k] * (1 << 32) + B[k], return_counts=True); a_ = u >> 32; b_ = u & 0xFFFFFFFF
    best_a, best_b = {}, {}
    for a, b, n in zip(a_.tolist(), b_.tolist(), c.tolist()):
        if n > best_a.get(a, (0, 0))[1]:
            best_a[a] = (b, n)
        if n > best_b.get(b, (0, 0))[1]:
            best_b[b] = (a, n)
    out = []
    for a, (b, n) in best_a.items():
        if best_b[b][0] == a and n >= min_frac * min(na[a], nbb[b]):
            out.append((int(a), int(b), float(n / min(na[a], nbb[b]))))
    return out


def track(R, iou_min=0.5, skip=True, mode="iou"):
    """R: (n_slices, H, W) per-slice region labels (0 = none). Links regions across slices by IoU (and over one
    missing slice for unmatched regions when skip) with union-find. Returns (belly volume int32, number of bellies)."""
    R = np.asarray(R); offs = np.zeros(len(R) + 1, np.int64)
    for i in range(len(R)):
        offs[i + 1] = offs[i] + int(R[i].max())
    parent = np.arange(int(offs[-1]) + 1)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[max(rx, ry)] = min(rx, ry)

    has_next = [set() for _ in range(len(R))]; has_prev = [set() for _ in range(len(R))]
    for i in range(len(R) - 1):
        for a, b, _ in (iou_links if mode == "iou" else mutual_links)(R[i], R[i + 1], iou_min):
            union(offs[i] + a, offs[i + 1] + b); has_next[i].add(a); has_prev[i + 1].add(b)
    if skip:
        for i in range(len(R) - 2):
            A = np.where(np.isin(R[i], list(has_next[i])), 0, R[i]); B = np.where(np.isin(R[i + 2], list(has_prev[i + 2])), 0, R[i + 2])
            for a, b, _ in (iou_links if mode == "iou" else mutual_links)(A, B, iou_min):
                union(offs[i] + a, offs[i + 2] + b)
    roots = np.array([find(x) for x in range(len(parent))]); uniq = np.unique(roots[1:])
    lut = np.zeros(len(parent), np.int32); lut[1:] = np.searchsorted(uniq, roots[1:]) + 1
    out = np.zeros(R.shape, np.int32)
    for i in range(len(R)):
        m = R[i] > 0; out[i][m] = lut[offs[i] + R[i][m]]
    return out, len(uniq)


def name_bellies(belly, rule, min_purity=0.6):
    """{belly: (rule label, purity, n voxels)}; purity = share of the belly's voxels carrying its majority nonzero rule
    label; label 0 when purity < min_purity or the belly lies outside every rule label."""
    b = np.asarray(belly).ravel(); r = np.asarray(rule).ravel().astype(np.int64); k = b > 0
    nb = int(b.max()) if b.size else 0; nr = int(r.max()) + 1 if r.size else 1
    tab = np.bincount(b[k].astype(np.int64) * nr + r[k], minlength=(nb + 1) * nr).reshape(nb + 1, nr)
    out = {}
    for j in range(1, nb + 1):
        n = int(tab[j].sum())
        if not n:
            continue
        lab = int(np.argmax(tab[j, 1:])) + 1 if nr > 1 else 0; pur = float(tab[j, lab] / n) if lab else 0.0
        out[j] = (lab if (lab and pur >= min_purity) else 0, pur, n) if lab else (0, 0.0, n)
    return out


def contact_on_septum(L, evidence, reach=2, min_px=10):
    """One slice. L: named labels; evidence: bool photographed septum (pale pixel or non-muscle). Contact pixels of a
    label = its 4-neighbour boundary pixels with another nonzero label within `reach` px (Chebyshev). Returns
    {label: (share of contact pixels within 1 px of evidence, n contact px)} for labels with >= min_px contact px."""
    from scipy import ndimage as ndi
    L = np.asarray(L).astype(np.int32); cross = ndi.generate_binary_structure(2, 1); big = 1 << 20
    bnd = (L > 0) & ((ndi.maximum_filter(L, footprint=cross, mode="constant") != L) |
                     (ndi.minimum_filter(L, footprint=cross, mode="constant") != L))
    w = 2 * reach + 1
    mx = ndi.maximum_filter(L, size=w, mode="constant"); mn = ndi.minimum_filter(np.where(L > 0, L, big), size=w, mode="constant", cval=big)
    contact = bnd & (((mx != L) & (mx > 0)) | ((mn != L) & (mn < big)))
    onsep = ndi.binary_dilation(np.asarray(evidence, bool), structure=np.ones((3, 3), bool))
    n = int(L.max()) + 1; nc = np.bincount(L[contact], minlength=n); ns = np.bincount(L[contact & onsep], minlength=n)
    return {l: (float(ns[l] / nc[l]), int(nc[l])) for l in range(1, n) if nc[l] >= min_px}


def gate_v4(v, expected, main_frac, contact_median, lo=0.5, hi=2.0, min_main=0.98, min_contact=0.7, out_of_range=False):
    """(ship, reason): repo gate (volume ratio, main component) + contact-on-septum median >= min_contact."""
    if out_of_range:
        return False, "OUT OF RANGE: arises above his radial-head plane; only the part below it is segmented"
    if v <= 0:
        return False, "no belly named for it"
    ok, why = Q.gate(v, expected, main_frac, lo, hi, min_main)
    if not ok:
        return False, why
    if contact_median is None:
        return False, "no contact with another named muscle measured"
    if contact_median < min_contact:
        return False, f"contact-on-septum {contact_median:.2f} (median over slices) < {min_contact}"
    return True, f"{why}, contact-on-septum {contact_median:.2f}"


def stable_set(passes):
    """Muscles passing in every run: passes = [set(names) per run]."""
    return set.intersection(*map(set, passes)) if passes else set()


def badge_text(v, exp, factor, contact, purity, nbellies):
    return (f"Muscle regions enclosed by the pale fascial septa photographed in his own cryosections (Visible Human male, "
            f"0.33 mm, instances 1575-1819), linked into {nbellies} belly piece(s) across sections; not traced anatomy. "
            f"Boundaries come from his photographed septa: median {round(100 * contact)} % of its outline where it meets "
            f"another muscle lies on a photographed pale septum or non-muscle tissue. The NAME is rule-assisted: the "
            f"pieces were named by majority overlap with a position-rule segmentation ({round(100 * purity)} % "
            f"agreement). Measured volume {v:.1f} cm3 vs expectation {exp:.1f} cm3 (repository architecture volume x "
            f"{factor:.2f}, the ratio of his own upper-arm muscle volumes to theirs). Only the part between his "
            f"radial-head and distal-radius planes is segmented.")


# ----------------------------------------------------------------------------------------------- stages
def sample_rule_labels(path, shape, us, ss, ts, c, a):
    """The Q165 RAS label volume sampled (nearest) at every frame voxel."""
    import nibabel as nib
    img = nib.load(str(path)); L3 = np.asarray(img.dataobj); inv = np.linalg.inv(img.affine)
    v1, v2 = Q.frame_basis(a); S, Tt = np.meshgrid(ss, ts, indexing="ij"); out = np.zeros(shape, np.uint8)
    for i, u in enumerate(us):
        P = c[None, None] + u * a + S[..., None] * v1 + Tt[..., None] * v2
        ijk = np.rint(P @ inv[:3, :3].T + inv[:3, 3]).astype(int); ok = np.all((ijk >= 0) & (ijk < np.array(L3.shape)), -1)
        out[i][ok] = L3[ijk[ok][:, 0], ijk[ok][:, 1], ijk[ok][:, 2]]
    return out


def slice_septa(m, P, support_map, support, sigma_px, h):
    """One slice: watershed of the smoothed paleness from its h-minima inside muscle m, weak boundaries merged.
    Returns (septum lines bool, number of watershed basins)."""
    from scipy import ndimage as ndi
    from skimage.morphology import h_minima
    from skimage.segmentation import watershed
    if not m.any():
        return np.zeros(m.shape, bool), 0
    Ps = ndi.gaussian_filter(np.where(m, P, 0.3).astype(np.float32), sigma_px)
    mk, nb = ndi.label(h_minima(Ps, h) & m)
    W = watershed(Ps, mk, mask=m)
    return septum_lines(merge_weak(W, support_map.astype(np.float32), support)), nb


def run(pale_thr, tis, pres, seg_rng, rule, a, ds, du):
    """The whole v4 pipeline at one paleness threshold. Returns a dict of arrays and stats."""
    from scipy import ndimage as ndi
    it, ib = seg_rng; n = tis.shape[0]
    musc = np.zeros(tis.shape, bool); musc[it:ib + 1] = tis[it:ib + 1] == T["muscle"]
    min_px = int(round(a.min_region_mm2 / (ds * ds)))
    pale = (pres >= pale_thr) & (tis > 0)
    sup = ndi.maximum_filter(pale, size=(2 * a.support_slices + 1, 3, 3))
    pflood = ndi.gaussian_filter1d(pres, a.sigma_u, axis=0) if a.sigma_u > 0 else pres   # septa are sheets along the axis
    R = np.zeros(tis.shape, np.int32); lines = np.zeros(tis.shape, bool); nreg, basins, sizes = [], [], []
    for i in range(it, ib + 1):
        lines[i], nbs = slice_septa(musc[i], pflood[i], sup[i], a.support, a.sigma_mm / ds, a.h)
        R[i], k = regions(musc[i], lines[i], min_px); basins.append(nbs); nreg.append(k)
        if k:
            sizes += (np.bincount(R[i].ravel())[1:] * ds * ds).tolist()
    Bv, nbel = track(R[it:ib + 1], a.iou, skip=True, mode=a.link); belly = np.zeros(tis.shape, np.int32); belly[it:ib + 1] = Bv
    names = name_bellies(belly, rule, a.min_purity)
    lut = np.zeros(nbel + 1, np.uint8)
    for j, (l, _p, _n) in names.items():
        lut[j] = l
    lab = lut[belly]
    vox = ds * ds * du / 1000.0
    span = np.zeros(nbel + 1, int)
    for i in range(it, ib + 1):
        span[np.unique(belly[i][belly[i] > 0])] += 1
    sizes = np.array(sizes) if sizes else np.zeros(1)
    largest = [float(np.bincount(R[i].ravel())[1:].max() / max((R[i] > 0).sum(), 1)) for i in range(it, ib + 1) if R[i].any()]
    bstat = {"regions_per_slice": {"median": float(np.median(nreg)), "p10": float(np.percentile(nreg, 10)), "p90": float(np.percentile(nreg, 90)),
                                   "min": int(min(nreg)), "max": int(max(nreg))},
             "watershed_basins_per_slice_median": float(np.median(basins)),
             "region_size_mm2": {"p10": round(float(np.percentile(sizes, 10)), 1), "median": round(float(np.median(sizes)), 1),
                                 "p90": round(float(np.percentile(sizes, 90)), 1), "max": round(float(sizes.max()), 1)},
             "largest_region_share_of_slice_muscle_median": round(float(np.median(largest)), 3),
             "muscle_in_regions_share": round(float((R > 0).sum() / max(musc.sum(), 1)), 4),
             "septum_line_px_share_of_muscle": round(float((lines & musc).sum() / max(musc.sum(), 1)), 4)}
    vols = np.array([names[j][2] * vox if j in names else 0 for j in range(nbel + 1)])
    sp = span[1:]; big = vols[1:] >= 0.1
    bstat.update(n_bellies=int(nbel), n_bellies_ge_0p1cm3=int(big.sum()),
                 slices_spanned={"median_all": float(np.median(sp)), "median_ge_0p1cm3": float(np.median(sp[big])) if big.any() else 0,
                                 "p90_ge_0p1cm3": float(np.percentile(sp[big], 90)) if big.any() else 0, "max": int(sp.max()),
                                 "n_spanning_ge_20": int((sp >= 20).sum()), "n_spanning_ge_50": int((sp >= 50).sum())},
                 volume_in_bellies_ge_0p1cm3_share=round(float(vols[1:][big].sum() / max(vols.sum(), 1e-9)), 3))
    unnamed = [(j, names[j]) for j in names if names[j][0] == 0]
    bstat["unnamed"] = {"n": len(unnamed), "volume_cm3": round(sum(v[2] for _, v in unnamed) * vox, 1),
                        "n_ge_0p1cm3": int(sum(1 for _, v in unnamed if v[2] * vox >= 0.1)),
                        "largest": [{"belly": int(j), "volume_cm3": round(v[2] * vox, 2), "slices": int(span[j]), "best_purity": round(v[1], 3)}
                                    for j, v in sorted(unnamed, key=lambda t: -t[1][2])[:8]]}
    bstat["named_volume_cm3"] = round(float((lab > 0).sum() * vox), 1)
    # contact on photographed septum evidence (in-plane; the watershed lines themselves are not evidence)
    evid = pale | (tis != T["muscle"])
    per, perall = {}, {}
    for i in range(it, ib + 1):
        for l, (f, _n) in contact_on_septum(lab[i], evid[i], a.reach).items():
            per.setdefault(l, []).append(f)
        onsep = ndi.binary_dilation(evid[i], structure=np.ones((3, 3), bool))
        for l, (fa, _fc, _n) in V.boundary_septum_fractions(lab[i], onsep).items():
            perall.setdefault(l, []).append(fa)
    chance = float(np.median([ndi.binary_dilation(evid[i], structure=np.ones((3, 3), bool))[musc[i]].mean()
                              for i in range(it, ib + 1) if musc[i].any()]))
    return {"R": R, "lines": lines, "belly": belly, "lab": lab, "names": names, "span": span, "stats": bstat,
            "contact": per, "boundary": perall, "chance_evidence_near_muscle_px": round(chance, 3)}


def muscle_rows(res, ids, ex, factor, vol_ras, voxr):
    """Per-muscle metrics and gate from one run."""
    rows = {}
    for nm, l in ids.items():
        m = vol_ras == l; v = float(m.sum() * voxr / 1000.0)
        mf, ncomp = Q.main_component_fraction(m) if v > 0 else (0.0, 0)
        bl = [(j, t) for j, t in res["names"].items() if t[0] == l]
        nvox = sum(t[2] for _, t in bl); pur = sum(t[1] * t[2] for _, t in bl) / nvox if nvox else None
        cs = res["contact"].get(l, []); cm = float(np.median(cs)) if cs else None
        ba = res["boundary"].get(l, [])
        exp = ex[nm][0] * factor
        ok, why = gate_v4(v, exp, mf, cm, out_of_range=nm in OUT_OF_RANGE)
        rows[nm] = {"label": l, "volume_cm3": round(v, 1), "expected_cm3": round(exp, 1), "ratio": round(v / exp, 2) if exp else None,
                    "architecture_volume_cm3": ex[nm][0], "expectation_source": ex[nm][1],
                    "main_component_fraction": round(mf, 4), "components_26": ncomp,
                    "contact_on_septum_median": None if cm is None else round(cm, 3), "contact_slices": len(cs),
                    "boundary_on_septum_or_nonmuscle_median": round(float(np.median(ba)), 3) if ba else None,
                    "naming_purity": None if pur is None else round(float(pur), 3), "bellies": len(bl),
                    "belly_slices_max": int(max((res["span"][j] for j, _ in bl), default=0)),
                    "out_of_range": nm in OUT_OF_RANGE, "gate_pass": ok, "reason": why}
    return rows


def montage(rgb, lab, lines, B, us, it, ib, path, slices, ncol, up=2):
    """Row 1: the resliced photograph; row 2: named muscles (alpha 0.55) over it, septum lines thin white, CT
    radius/ulna outline grey."""
    from PIL import Image, ImageDraw
    from scipy import ndimage as ndi
    from vhf_forearm_muscles_from_cryo import palette
    p = palette(ncol); col = np.array([p[k] for k in range(ncol + 1)], np.uint8); tops, bots = [], []
    for i in slices:
        im = rgb[i].copy(); L = lab[i]; ov = im.copy(); m = L > 0
        ov[m] = (0.55 * col[L[m]] + 0.45 * im[m]).astype(np.uint8)
        for b in (2, 3):
            bm = B[i] == b; ov[bm & ~ndi.binary_erosion(bm)] = 160
        ov[lines[i]] = 255
        a_ = np.kron(im, np.ones((up, up, 1), np.uint8)); b_ = np.kron(ov, np.ones((up, up, 1), np.uint8))
        pa = Image.fromarray(a_); ImageDraw.Draw(pa).text((4, 4), f"u {us[i]:.0f} mm  f {(i - it) / max(ib - it, 1):.2f}", fill=(255, 255, 0))
        tops.append(np.asarray(pa)); bots.append(b_)
    Image.fromarray(np.concatenate([np.concatenate(tops, 1), np.concatenate(bots, 1)], 0)).save(path)
    return str(path)


# ----------------------------------------------------------------------------------------------- main
def main(argv=None):
    import nibabel as nib
    from scipy import ndimage as ndi
    from cryo_classes import classify as classify_m
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--q164-work", help="Q164 work dir holding frame.npz")
    ap.add_argument("--rgb", help="Q165 resliced photograph cache rgb_frame.npy")
    ap.add_argument("--work", help="scratch folder for the montage")
    ap.add_argument("--pale", type=float, default=0.10, help="paleness residual counted as a pale (septum) pixel")
    ap.add_argument("--stability", default="0.08,0.12", help="other --pale values the ship set must also pass at")
    ap.add_argument("--support", type=float, default=0.5, help="share of a boundary near pale pixels to keep it")
    ap.add_argument("--support-slices", type=int, default=1, help="pale support also from +-k neighbouring slices")
    ap.add_argument("--sigma-mm", type=float, default=0.5, help="in-plane smoothing of the paleness before flooding")
    ap.add_argument("--h", type=float, default=0.01, help="h-minima depth of the watershed markers")
    ap.add_argument("--min-region-mm2", type=float, default=4.0)
    ap.add_argument("--iou", type=float, default=0.5, help="IoU (link iou) or overlap share of the smaller region (link mutual)")
    ap.add_argument("--link", choices=("iou", "mutual"), default="mutual")
    ap.add_argument("--sigma-u", type=float, default=1.5, help="Gaussian sigma (slices) of the paleness along the axis before flooding")
    ap.add_argument("--min-purity", type=float, default=0.6)
    ap.add_argument("--reach", type=int, default=2, help="px within which another muscle counts as contact")
    ap.add_argument("--out", default=str(REPO / "data/ct_sources/task_outputs/vhm_forearm_muscles_v4.nii.gz"))
    ap.add_argument("--labels-out", default=str(REPO / f"mappings/{LABEL_MAP}_labels.json"))
    ap.add_argument("--mapping-out", default=str(REPO / f"mappings/subjects/{SUBJECT}_volume_mapping.json"))
    ap.add_argument("--report", default=str(REPO / "data/derived/Q166_vhm_forearm_v4.json"))
    ap.add_argument("--stamp", default=None, help="only stamp badges from --mapping-out onto this converted subject dir")
    a = ap.parse_args(argv)
    if a.stamp:
        print(f"stamped {Q.stamp_badges(a.stamp, a.mapping_out)} badges"); return 0
    if not (a.q164_work and a.rgb and a.work):
        ap.error("--q164-work, --rgb and --work are required unless --stamp")
    W = Path(a.work); W.mkdir(parents=True, exist_ok=True)
    F = dict(np.load(Path(a.q164_work) / "frame.npz")); us, ss, ts, c, ax = F["us"], F["ss"], F["ts"], F["c"], F["a"]
    ds = float(ss[1] - ss[0]); du = float(us[1] - us[0])
    rgb = np.load(a.rgb); isl3 = F["island"]; B = F["B"]
    cls = V.classify_frame(rgb, classify_m)
    bone = np.stack([ndi.binary_dilation(B[i] > 0, iterations=2) for i in range(len(us))])
    tis = V.tissue_map(cls, isl3, bone); del cls, bone
    q165 = json.load(open(REPO / "data/derived/Q165_vhm_forearm_v3.json"))
    u0, u1 = q165["segment"]["u_mm"]; it, ib = int(np.argmin(abs(us - u0))), int(np.argmin(abs(us - u1)))
    pres = np.zeros(tis.shape, np.float32)
    for i in range(it, ib + 1):
        pres[i] = V.paleness_residual(rgb[i], isl3[i])
    rule = sample_rule_labels(RULE_VOLUME, tis.shape, us, ss, ts, c, ax)
    ids = {nm: int(k) for k, nm in json.load(open(RULE_LABELS))["labels"].items()}; names = list(ids)
    ex = Q.expectations_from_repo(names); arch_arm = Q.expectations_from_repo(list(V.ARM_MUSCLES))
    his = V.his_arm_volumes()
    factor = V.scale_factor({k: v[0] for k, v in his.items()}, {k: arch_arm[k][0] for k in V.ARM_MUSCLES})
    thrs = [a.pale] + [float(x) for x in a.stability.split(",") if x.strip()]
    runs = {}
    for thr in thrs:
        res = run(thr, tis, pres, (it, ib), rule, a, ds, du)
        vol, aff = Q.frame_to_ras_volume(res["lab"], us, ss, ts, c, ax); voxr = float(abs(np.linalg.det(aff[:3, :3])))
        rows = muscle_rows(res, ids, ex, factor, vol, voxr); res["rows"] = rows
        st = res["stats"]
        print(f"pale {thr}: regions/slice {st['regions_per_slice']['median']:.0f} (p10-p90 {st['regions_per_slice']['p10']:.0f}-{st['regions_per_slice']['p90']:.0f}), "
              f"largest {st['largest_region_share_of_slice_muscle_median']}, bellies {st['n_bellies']} ({st['n_bellies_ge_0p1cm3']} >= 0.1 cm3), "
              f"unnamed {st['unnamed']['n']} / {st['unnamed']['volume_cm3']} cm3, named {st['named_volume_cm3']} cm3; "
              f"pass {[nm for nm, r in rows.items() if r['gate_pass']]}")
        if thr == a.pale:
            res["vol"], res["aff"] = vol, aff
        else:
            for k in ("R", "belly", "lab", "vol"):
                res.pop(k, None)
        runs[thr] = res
    P0 = runs[a.pale]; rows = P0["rows"]
    stable = stable_set([{nm for nm, r in runs[t]["rows"].items() if r["gate_pass"]} for t in thrs])
    for nm, r in rows.items():
        r["pass_at"] = {str(t): runs[t]["rows"][nm]["gate_pass"] for t in thrs}
        r["stable"] = nm in stable
        r["ship"] = bool(r["gate_pass"] and nm in stable)
        if r["gate_pass"] and nm not in stable:
            r["reason"] = "UNSTABLE: fails the gate at pale " + ", ".join(f"{t}: {runs[t]['rows'][nm]['reason']}" for t in thrs if not runs[t]["rows"][nm]["gate_pass"])
        print(f"  {nm:32s} {r['volume_cm3']:6.1f} exp {r['expected_cm3']:6.1f} x{r['ratio']} main {r['main_component_fraction']:.3f} "
              f"contact {r['contact_on_septum_median']} purity {r['naming_purity']} bellies {r['bellies']} stable {r['stable']}  "
              f"{'SHIP' if r['ship'] else 'no: ' + r['reason'][:70]}")
    # outputs
    q = [int(it + (ib - it) * f) for f in (0.1, 0.3, 0.5, 0.7, 0.9)]
    mont = montage(rgb, P0["lab"], P0["lines"], B, us, it, ib, W / "vhm_forearm_v4_montage.png", q, max(ids.values()))
    shipping = any(r["ship"] for r in rows.values())
    if not shipping:
        print("nothing passes at every threshold: no volume / label key / mapping written (report only)")
    else:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        nib.save(nib.Nifti1Image(P0["vol"], P0["aff"]), a.out)
    key = {"_README": [f"Label id -> structure for the Visible Human MALE right forearm muscle volume v4 ({Path(__file__).name}). A KEY, not data. {BADGE}."],
           "source": SOURCE, "task": LABEL_MAP, "version": "2026-09-29", "badge": BADGE, "labels": {str(l): nm for nm, l in ids.items()}}
    if shipping:
        Path(a.labels_out).write_text(json.dumps(key, indent=1))
    entries = []
    for nm, r in rows.items():
        e = {"label": r["label"], "source_structure": nm, "side": "right", "relationship": "exact", "candidates": [nm + "_r"]}
        if r["ship"]:
            e.update(status="curated", atlas_id=nm + "_r",
                     procedural_badge=badge_text(r["volume_cm3"], r["expected_cm3"], factor, r["contact_on_septum_median"], r["naming_purity"], r["bellies"]),
                     note=f"{BADGE}; SHIPPED: {r['reason']}; passes at pale {', '.join(map(str, thrs))}. Expectation source: {r['expectation_source']} x his upper-arm factor {factor:.3f}.")
        else:
            e.update(status="review", atlas_id=None, note=f"{BADGE}; NOT SHIPPED: {r['reason']}. Expectation source: {r['expectation_source']} x his upper-arm factor {factor:.3f}.")
        entries.append(e)
    if shipping:
        Path(a.mapping_out).write_text(json.dumps({"_README": ["Review every entry before running convert.", "Set 'atlas_id' to the correct entity, or null to skip the label.",
                                                            "'status' is advisory; convert reads 'atlas_id' only. 'procedural_badge' is stamped onto the converted manifest by this script's --stamp."],
                                                    "subject": SUBJECT, "source_volume": str(Path(a.out).resolve()), "label_map": LABEL_MAP, "entries": entries}, indent=2))
    report = {"source": SOURCE, "badge": BADGE, "script": "scripts/cryo/vhm_forearm_muscles_v4.py", "subject": SUBJECT,
              "reuses": "Q164 frame (frame.npz), Q165 resliced photograph cache (rgb_frame.npy), tissue classes, paleness residual and rule labels (vhm_forearm_muscles_v3.nii.gz)",
              "segment": {"u_mm": [float(us[it]), float(us[ib])], "slices": int(ib - it + 1)},
              "method": {"septum_lines": f"watershed of the paleness residual (smoothed {a.sigma_mm} mm) from its h-minima (h {a.h}) inside the muscle class; adjacent basins merged weakest-first while < {a.support} of their shared boundary lies within 1 px in-plane / {a.support_slices} slice of a pale pixel; surviving boundaries = 1 px septum lines",
                         "septum_mask": "septum lines + every non-muscle tissue class (fat, pale, other, bone, outside)",
                         "regions": f"4-connected components of muscle AND NOT septum mask, >= {a.min_region_mm2} mm2",
                         "linking": f"IoU >= {a.iou} between consecutive slices (one-to-one), one-slice gaps bridged for unmatched regions; union-find",
                         "naming": f"majority Q165 rule label per belly; purity < {a.min_purity} unnamed",
                         "contact_on_septum": f"per slice, share of a muscle's contact pixels (another named muscle within {a.reach} px) within 1 px of a photographed pale pixel (residual >= pale) or non-muscle pixel, same slice; median over slices"},
              "expectations": {"rule": "V = PCSA x optimal fascicle length / cos(pennation) (data/muscles/upper_limb/<id>_r.json) x ONE factor from his own upper arm (as Q165)",
                               "factor": round(factor, 4),
                               "his_upper_arm_cm3": {k: {"volume_cm3": v[0], "subject": f"build/vh/{v[1]}"} for k, v in his.items()},
                               "architecture_upper_arm_cm3": {k: arch_arm[k][0] for k in V.ARM_MUSCLES}},
              "gate": "0.5 <= volume/expected <= 2.0; main 26-connected component >= 0.98 (islands < 1 % dropped); contact-on-septum median >= 0.7; PT/BR/ECRL/anconeus out of range; pass at every pale threshold",
              "runs": {str(t): {"stats": runs[t]["stats"], "chance_evidence_near_muscle_px": runs[t]["chance_evidence_near_muscle_px"],
                                "pass": [nm for nm, r in runs[t]["rows"].items() if r["gate_pass"]],
                                "muscles": {nm: {k: r[k] for k in ("volume_cm3", "ratio", "main_component_fraction", "contact_on_septum_median", "naming_purity", "bellies", "gate_pass", "reason")}
                                            for nm, r in runs[t]["rows"].items()}} for t in thrs},
              "tuning_tried": TUNING_TRIED,
              "verdict": ("SHIPPED " + ", ".join(nm for nm, r in rows.items() if r["ship"])) if shipping else
                         ("STOPPED: the photographed pale septa do not close into muscle-sized regions consistently along the axis. "
                          "Per slice the regions are plausible, but linked in 3-D they are either short fragments or large bellies spanning "
                          "several rule muscles (purity < 0.6, left unnamed), so the named muscles are small and broken; nothing passes "
                          "the gate at every paleness threshold."),
              "muscles": rows, "stable": sorted(stable), "montage": mont,
              "shipped": [nm + "_r" for nm, r in rows.items() if r["ship"]],
              "shipped_label_ids": sorted(r["label"] for r in rows.values() if r["ship"])}
    Path(a.report).parent.mkdir(parents=True, exist_ok=True); Path(a.report).write_text(json.dumps(report, indent=1))
    print(f"factor {factor:.3f}; stable {sorted(stable)}; shipped {report['shipped']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
