"""Q217: re-tile the muscles of HIS forearm inside HIS photographed muscle mass.

`tile()` takes the current muscle meshes (the position prior) and returns a disjoint voxel label volume (0.5 mm):
  1. every muscle's filled solid S_i is clipped to the container (his photographed muscle / tendon voxels, inside his skin, minus his bones, minus the fixed neighbours = the measured arm muscles);
  2. a voxel claimed by several muscles goes to the one that is DEEPEST inside its own solid there (depth = Euclidean distance to its own surface) = the equidistant interface between the two surfaces;
  3. every label gives up the voxel layer that touches another label: two neighbouring muscles end up FASCIA_MM = 1.0 mm apart (Q162 muscle | muscle interface rule), nothing is shrunk beyond that;
  4. the volume a muscle lost to its neighbours or to the container is given back inside the free container voxels nearest to its own prior solid (never within 1 voxel of another label), up to its
     prior volume x REGROW_MAX: the muscle slides into the free photographed muscle next to it instead of being dented.
The label volume is the TARGET of the non-rigid fit of the existing meshes (q217_fit.py); no mesh is rebuilt from voxels."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.q216_common import VoxGrid  # noqa: E402

H = 0.5
FASCIA_MM = 1.0
REGROW_MAX = 1.0           # a muscle gets back at most its prior volume (in the window) - the volumes are conserved, not inflated
GROW_REACH_MM = 14.0


def local_solid(g, v, f, pad=2.0):
    """-> (slices, bool array) of the filled solid of a closed (or nearly closed) mesh on the grid g"""
    v = np.asarray(v, float)
    a = np.maximum(g.idx(v.min(0) - pad), 0)
    b = np.minimum(g.idx(v.max(0) + pad) + 1, np.asarray(g.shape))
    if (b <= a).any():
        return None
    sub = VoxGrid(g.pos(a), g.pos(b - 1), g.h)
    s = sub.solid(v, np.asarray(f, np.int64))
    sl = tuple(slice(int(a[k]), min(int(a[k]) + s.shape[k], g.shape[k])) for k in range(3))
    return sl, s[tuple(slice(0, sl[k].stop - sl[k].start) for k in range(3))]


def edt_half(mask, h):
    """Euclidean distance (mm) from a True voxel to the nearest False voxel, computed on the 2x-coarser lattice and expanded (about 8x cheaper; 1 mm accuracy)"""
    m2 = mask[::2, ::2, ::2]
    d2 = ndi.distance_transform_edt(m2, sampling=2 * h).astype(np.float32)
    d = np.repeat(np.repeat(np.repeat(d2, 2, 0), 2, 1), 2, 2)[: mask.shape[0], : mask.shape[1], : mask.shape[2]]
    return d


def tile(g, priors, container, blocked, log=print, regrow_max=REGROW_MAX):
    """priors = {id: (v, f)}; container = bool volume (allowed voxels); blocked = bool volume (bones, fixed muscles).  -> labels int16 volume (0 = none, k = 1 + index in `ids`), ids, report"""
    import time
    t0 = time.time()
    ids = list(priors)
    allowed = container & ~blocked
    shape = g.shape
    best = np.full(shape, -1.0, np.float16)
    owner = np.zeros(shape, np.int16)
    cnt = np.zeros(shape, np.uint8)
    prior_vol = {}
    sols = {}
    for k, i in enumerate(ids):
        r = local_solid(g, *priors[i])
        if r is None:
            continue
        sl, s = r
        sols[i] = (sl, s)
        cnt[sl] += s.astype(np.uint8)
        prior_vol[i] = int(s.sum())
        d = edt_half(s, g.h).astype(np.float16)
        sub_best = best[sl]
        upd = s & (d > sub_best)
        sub_best[upd] = d[upd]
        owner[sl][upd] = k + 1
        del d
    log(f"  tile: solids + depth argmax {time.time() - t0:.0f} s")
    lab = np.where(allowed & (owner > 0), owner, 0).astype(np.int16)
    rep = {i: dict(prior_cm3=round(prior_vol[i] * g.h ** 3 / 1000.0, 2)) for i in sols}
    for k, i in enumerate(ids):
        if i in sols:
            sl, s = sols[i]
            rep[i]["contested_pct"] = round(100.0 * float((s & (cnt[sl] > 1)).sum()) / max(s.sum(), 1), 1)
            rep[i]["released_pct"] = round(100.0 * float((s & ~allowed[sl]).sum()) / max(s.sum(), 1), 1)
    # interface gap: every label gives up the voxels that touch another label (6-neighbourhood): two labels end up 2 voxels = FASCIA_MM apart
    lab = carve_gap(lab)
    for k, i in enumerate(ids):
        rep[i]["after_cut_cm3"] = round(float((lab == k + 1).sum()) * g.h ** 3 / 1000.0, 2)
    # regrowth into free container voxels nearest to the prior solid
    log(f"  tile: gap carved {time.time() - t0:.0f} s")
    lab = regrow(g, lab, sols, ids, allowed, prior_vol, regrow_max, rep, log)
    log(f"  tile: regrown {time.time() - t0:.0f} s")
    for k, i in enumerate(ids):
        rep[i]["final_cm3"] = round(float((lab == k + 1).sum()) * g.h ** 3 / 1000.0, 2)
    return lab, ids, rep


def carve_gap(lab):
    """remove from every label the voxels that have a 6-neighbour with a different non-zero label"""
    out = lab.copy()
    touch = np.zeros(lab.shape, bool)
    for ax in range(3):
        for sh in (1, -1):
            nb = np.roll(lab, sh, axis=ax)
            if sh == 1:
                sl = [slice(None)] * 3
                sl[ax] = slice(0, 1)
                nb[tuple(sl)] = 0
            else:
                sl = [slice(None)] * 3
                sl[ax] = slice(-1, None)
                nb[tuple(sl)] = 0
            touch |= (lab > 0) & (nb > 0) & (nb != lab)
    out[touch] = 0
    return out


def regrow(g, lab, sols, ids, allowed, prior_vol, regrow_max, rep, log):
    """give lost volume back: free container voxels are offered to each deficient label in order of their distance to the muscle's PRIOR solid (sweep r = 0.5 mm ... GROW_REACH_MM); a voxel is taken when it is
    free, allowed and not adjacent to another label (keeps the 1.0 mm interface); every candidate is looked at once.  A label keeps its largest connected component, the rest is given back to the free pool."""
    shape = lab.shape
    n = len(ids)
    deficit = {}
    cand = {}
    for k, i in enumerate(ids):
        if i not in sols:
            continue
        have = int((lab == k + 1).sum())
        d = max(int(prior_vol[i] * regrow_max) - have, 0)
        if d == 0:
            continue
        deficit[k + 1] = d
        reach = int(np.ceil(GROW_REACH_MM / g.h)) + 1
        sl, s = sols[i]
        lo = [max(sl[a].start - reach, 0) for a in range(3)]
        hi = [min(sl[a].stop + reach, shape[a]) for a in range(3)]
        box = tuple(slice(lo[a], hi[a]) for a in range(3))
        inside = np.zeros(tuple(hi[a] - lo[a] for a in range(3)), bool)
        inside[tuple(slice(sl[a].start - lo[a], sl[a].stop - lo[a]) for a in range(3))] = s
        dk = edt_half(~inside, g.h)
        m = (dk <= GROW_REACH_MM) & allowed[box] & (lab[box] == 0)
        ii = np.argwhere(m)
        dd = dk[tuple(ii.T)]
        o = np.argsort(dd, kind="stable")
        ii = ii[o] + np.array(lo)
        cand[k + 1] = (np.ravel_multi_index(tuple(ii.T), shape), dd[o])
        del dk, inside
    labf = lab.reshape(-1)
    adj = np.zeros(lab.size, np.int16)            # label of a neighbour (0 none), -1 several different
    def mark(flat_idx, k):
        ijk = np.array(np.unravel_index(flat_idx, shape)).T
        for ax in range(3):
            for sh in (-1, 1):
                nb = ijk.copy()
                nb[:, ax] += sh
                ok = (nb[:, ax] >= 0) & (nb[:, ax] < shape[ax])
                f2 = np.ravel_multi_index(tuple(nb[ok].T), shape)
                a = adj[f2]
                adj[f2] = np.where((a == 0) | (a == k), k, -1)
    # initial adjacency from the carved labels
    nz = np.flatnonzero(labf > 0)
    for k in np.unique(labf[nz]):
        mark(nz[labf[nz] == k], int(k))
    ptr = {k: 0 for k in deficit}
    r = 0.0
    while any(d > 0 for d in deficit.values()) and r < GROW_REACH_MM:
        r += g.h
        for k in list(deficit):
            if deficit[k] <= 0:
                continue
            fl, dd = cand[k]
            hi_ = int(np.searchsorted(dd, r, side="right"))
            sel = fl[ptr[k]:hi_]
            ptr[k] = hi_
            if not len(sel):
                continue
            ok = (labf[sel] == 0) & ((adj[sel] == 0) | (adj[sel] == k))
            sel = sel[ok]
            if not len(sel):
                continue
            if len(sel) > deficit[k]:
                sel = sel[: deficit[k]]
            labf[sel] = k
            deficit[k] -= len(sel)
            mark(sel, k)
    lab = labf.reshape(shape)
    # one connected piece per label
    for k, i in enumerate(ids):
        if i not in sols:
            continue
        m = lab == k + 1
        if not m.any():
            continue
        lb, nc = ndi.label(m, structure=np.ones((3, 3, 3)))
        if nc > 1:
            cnt = np.bincount(lb.ravel())[1:]
            keep = int(np.argmax(cnt)) + 1
            lab[m & (lb != keep)] = 0
        rep[i]["regrow_deficit_left_cm3"] = round(max(deficit.get(k + 1, 0), 0) * g.h ** 3 / 1000.0, 2)
    return lab
