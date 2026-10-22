"""Q241 skinning weights: every structure of a page -> rigid attachment to ONE segment, or per-vertex weights over <= 4 segments.
Bones: rigid with their segment (ribs: per-vertex by height, they are skinned between the vertebra segments and the sternum segment).
Soft tissue: weights from the distance of every vertex to the surface of each segment's bones, w_s ~ exp(-(d_s - d_min)/lambda) (smooth falloff near joints, lambda per tissue class),
top-4 influences, smoothed over the mesh edges.  Nothing is simulated (no collision, no volume preservation)."""
from __future__ import annotations
import numpy as np
from scipy.spatial import cKDTree
from scipy import sparse
import model as MD
import rig as RG
from geom import *  # noqa

LAMBDA = {"cartilage": 3.0, "joint": 4.0, "insertion": 3.0, "ligament": 4.0, "tendon": 5.0, "muscle": 6.0, "fascia": 6.0, "bursa": 6.0, "nerve": 6.0, "vessel": 6.0, "lymph": 8.0,
          "cns": 12.0, "viscera": 15.0, "organ": 15.0, "skin": 16.0, "bone": 3.0}
TOPK = 4
SNAP = 0.015       # a structure whose weight outside its dominant segment is below this at (almost) every vertex is attached rigidly


def bone_samples(M, RB, per_mm2=1 / 12.0, nmin=300, nmax=6000):
    """surface samples of the rigid bones labelled with their segment index -> (pts, labels)"""
    pts, lab = [], []
    rng = np.random.default_rng(1)
    sid = RB.sid
    th = [(v_["c"][1], sid["v" + v_["label"]]) for v_ in RB.K.spine if v_["region"] == "thoracic"]
    ys = np.array([t[0] for t in th]); sgs = np.array([t[1] for t in th], np.int32)
    for k, sg in RB.bone_seg.items():
        if sg is None:
            continue
        b = M.bones()[k]
        v, f = b["v"], b["f"]
        from_ = C_area(v, f)
        n = int(np.clip(from_ * per_mm2, nmin, nmax))
        p = C_samples(v, f, n, rng)
        pts.append(p); lab.append(np.full(len(p), sid[sg], np.int32))
    for k in RB.soft_bones:                    # ribs: every sample takes the segment of the thoracic vertebra nearest in height (same rule as the per-vertex rib weights)
        b = M.bones()[k]
        v, f = b["v"], b["f"]
        n = int(np.clip(C_area(v, f) * per_mm2, nmin, 12000))
        p = C_samples(v, f, n, rng)
        pts.append(p); lab.append(sgs[np.abs(p[:, 1:2] - ys[None, :]).argmin(1)].astype(np.int32))
    return np.vstack(pts), np.concatenate(lab)


def C_area(v, f):
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return float(0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1).sum())


def C_samples(v, f, n, rng):
    import core as C
    return C.area_samples(v, f, n, rng)


def laplacian_adj(f, nv):
    e = np.r_[f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]
    A = sparse.coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(nv, nv)).tocsr()
    return ((A + A.T) > 0).astype(np.int8).tocsr()


def laplacian(f, nv):
    e = np.r_[f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]
    A = sparse.coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(nv, nv)).tocsr()
    A = ((A + A.T) > 0).astype(float)
    d = np.asarray(A.sum(1)).ravel()
    d[d == 0] = 1
    return sparse.diags(1.0 / d) @ A


import re as _re
SKIN_LIMB = _re.compile(r"(arm|elbow|cubital|wrist|palm|hand|digit|nail|perionyx|radial_foveola|thigh|knee|popliteal|leg|ankle|malleol|foot|heel|sole|hallucial|metatarsal|dorsum)")
SKIN_JUNCTION = _re.compile(r"(hip|gluteal|inguinal|femoral_triangle|deltoid|deltopectoral|lateral_bicipital|medial_bicipital)")


def skin_kind(x):
    """'limb' / 'trunk' / None (junction or not a Z skin patch -> decided by the data) from the Z skin patch name"""
    if x["sys"] != "skin":
        return None
    i = x["id"].lower()
    if not i.startswith("zan_skin_") or SKIN_JUNCTION.search(i):
        return None
    return "limb" if SKIN_LIMB.search(i) else "trunk"


ATTACH_MM = 12.0
ATTACH_SYS = ("muscle", "tendon", "ligament", "joint", "bursa", "insertion", "nerve", "vessel", "lymph", "cartilage")
LIMB_BIAS = 1.5      # skin / fascia distances to the distal limb segments are multiplied by this (see dist_weights)
KIN_MAX = 3          # a vertex may only be influenced by segments within this many joints of the segment it is nearest to (an arm hanging next to the hip must not drag the thigh skin)


def limb_bias(RB):
    """per segment: LIMB_BIAS for the distal limb segments (humerus, forearm, hand, fingers, femur, leg, foot, toes, patella), 1 otherwise"""
    import re
    b = np.ones(len(RB.segs), np.float32)
    for i, sg in enumerate(RB.segs):
        if re.match(r"(hum|uln|rad|hand|th_|f\d_|fem|tib|tal|foot|pat|t\d_)", sg["id"]):
            b[i] = LIMB_BIAS
    return b


def kin_dist(RB):
    """(nseg, nseg) number of joints between two segments in the kinematic tree"""
    n = len(RB.segs)
    par = [s["par"] for s in RB.segs]
    D = np.full((n, n), 99, np.int16)
    for a in range(n):
        # ancestors of a with depth
        anc = {}
        x, d = a, 0
        while x >= 0:
            anc[x] = d; x = par[x]; d += 1
        for b in range(n):
            x, d = b, 0
            while x >= 0 and x not in anc:
                x = par[x]; d += 1
            if x >= 0:
                D[a, b] = anc[x] + d
    return D



import re as _re2
_CANON = _re2.compile(r"_(zfill\w*|q\d+\w*)$")


def canon_id(i):
    """structure id without the Z prefix and without the gap-fill / re-segmentation suffixes (own pages: 'external_oblique_l_zfill203s' -> 'external_oblique_l')"""
    i = i.lower()
    if i.startswith("zan_"):
        i = i[4:]
    while True:
        j = _CANON.sub("", i)
        if j == i:
            return i
        i = j


def prior_from(M, RB, out):
    """canonical structure id -> set of segment ids (strings) the structure uses on a page whose limbs do not touch the trunk (the Base pages: A-pose); used as the candidate set on the pages
    where an arm rests on the abdomen (weights are still computed from THIS page's geometry)"""
    P = {}
    for x in M.S:
        o = out[x["idx"]]
        if o is None or x["sys"] == "bone":
            continue
        if o["kind"] == "rigid":
            used = {RB.segs[o["seg"]]["id"]}
        else:
            used = set()
            for j in range(o["idx"].shape[1]):
                for sg in np.unique(o["idx"][:, j]):
                    if float(o["w"][o["idx"][:, j] == sg, j].sum()) / len(o["idx"]) >= 0.03:
                        used.add(RB.segs[int(sg)]["id"])
        P.setdefault(canon_id(x["id"]), set()).update(used)
    return P


def map_prior_segment(RB, sid_name):
    """segment id string of the prior -> index on this page (fingers / toes of a page without them fall back to hand / foot)"""
    if sid_name in RB.sid:
        return RB.sid[sid_name]
    m = _re2.match(r"(th_\w+|f\d_\w)_(r|l)$", sid_name)
    if m:
        return RB.sid.get("hand_" + m.group(2))
    m = _re2.match(r"t\d_\w_(r|l)$", sid_name)
    if m:
        return RB.sid.get("foot_" + m.group(1))
    return None


TOUCH_MM = 4.0


def prune_islands(best, raw, A, kin, touch=TOUCH_MM, iters=3):
    """Contact islands: a connected region of vertices whose nearest allowed segment is s, whose neighbouring regions all belong to segments more than 2 joints from s, and that comes no closer than
    `touch` mm to s's bones is not attached to s - it is a part of the structure that merely lies against that segment (a forearm folded on the abdomen) - and loses s as a candidate.
    A region that touches the bone (<= touch) is a real attachment (latissimus dorsi on the humerus) and stays.  best / raw: (n, nseg) distances (inf = not allowed); A: vertex adjacency (csr)."""
    from scipy.sparse.csgraph import connected_components
    n = best.shape[0]
    for _ in range(iters):
        dom = best.argmin(1)
        changed = False
        for sg in np.unique(dom):
            idx = np.where(dom == sg)[0]
            if len(idx) == n:
                continue
            sub = A[idx][:, idx]
            nc, lb = connected_components(sub, directed=False)
            for c in range(nc):
                vs = idx[lb == c]
                if raw[vs, sg].min() <= touch:
                    continue
                nb = np.unique(A[vs].indices)
                nb = nb[dom[nb] != sg]
                if len(nb) == 0:
                    continue
                labs = np.unique(dom[nb])
                if (kin[sg, labs] > 2).all():
                    best[vs, sg] = np.inf; changed = True
        if not changed:
            break
    return best


def dist_weights(P, tree, lab, nseg, lam, k=28, topk=TOPK, kin=None, share=0.03, bias=None, P_all=None, limb=None, kind=None, attach_mm=None, attach_share=0.02, A=None, prior=None):
    """P (n,3) -> (idx (n,topk) int, w (n,topk)); distances to the nearest sample of each segment among the k nearest samples.
    Candidate segments of the structure: those that are the nearest segment of >= `share` of its vertices, plus the segments one joint away from them (parent / children); a segment that is
    nearest only to a few vertices (an arm hanging beside the hip, a stray island of a broken mesh) is not a candidate, so it cannot drag them."""
    D, I = tree.query(P, k=k)
    L = lab[I]
    n = len(P)
    best = np.full((n, nseg), np.inf, np.float32)
    rows = np.arange(n)
    for j in range(k - 1, -1, -1):          # D ascending: later (smaller) distances overwrite
        best[rows, L[:, j]] = D[:, j]
    if bias is not None:                       # skin / fascia: where an arm lies against the trunk the trunk wins (distances to distal limb segments count more)
        best = best * bias[None, :]
    dom = best.argmin(1)
    cnt = np.bincount(dom, minlength=nseg) / n
    allowed = cnt >= share
    prior_on = prior is not None and prior.any()
    if prior_on and kin is not None:
        # the prior only applies when the structure sits where the Base page has it (its nearest segment is a prior segment or next to one); a structure that lies elsewhere (a muscle of the right foot
        # modelled at the left foot) is decided by its own geometry
        mj0 = int(cnt.argmax())
        if not (prior[mj0] or (kin[prior, mj0] <= 1).any()):
            prior_on = False
    if prior_on:
        allowed = prior.copy()
    majority_limb = None if limb is None else bool(limb[int(cnt.argmax())])
    if prior_on:
        pass
    elif kind in ("limb", "trunk"):                  # Z skin patches carry their region in the name: that decides, not the nearest bone (an arm folded onto the abdomen)
        mj = int(cnt.argmax())
        if kind == "limb":
            lm = np.where(limb & (cnt > 0))[0]
            mj = int(lm[cnt[lm].argmax()]) if len(lm) else mj
            majority_limb = True
            allowed = kin[mj] <= 1
        else:
            majority_limb = False
            tr = np.where(~limb & (cnt > 0))[0]
            mj = int(tr[cnt[tr].argmax()]) if len(tr) else mj
            allowed = (cnt >= share) & ~limb
            if not allowed.any():
                allowed = np.zeros(nseg, bool); allowed[mj] = True
    elif attach_mm is not None:
        # soft tissue that attaches to bone (muscle, tendon, ligament, vessel, nerve ...): a segment is a candidate only when the structure TOUCHES its bones (>= attach_share of the vertices within
        # attach_mm of them) or is its majority segment; a forearm resting on the abdomen is not touched by the abdominal wall muscles
        near = (best <= attach_mm).sum(0) / n
        allowed = (near >= attach_share) | (np.arange(nseg) == int(cnt.argmax()))
        majority_limb = None
    elif limb is not None and kin is not None and limb[int(cnt.argmax())]:
        # skin / fascia patch of a limb: only the patch's own segment and its neighbours (an arm lying against the trunk must not attach the arm skin to the ribs)
        allowed = kin[int(cnt.argmax())] <= 1
    trunk_patch = (not prior_on) and (kind == "trunk") or (not prior_on and kind is None and limb is not None and kin is not None and not limb[int(cnt.argmax())] and float(cnt[limb].sum()) < 0.15)     # a sheet spanning trunk and limb (fascia lata) keeps both
    if kin is not None:
        allowed = allowed | ((kin[allowed] <= 1).any(0) if allowed.any() else False)
        if trunk_patch:
            allowed = allowed & ~limb              # a trunk patch is never attached to an arm / leg lying against it
            if not allowed.any():
                allowed = np.zeros(nseg, bool); allowed[int(cnt.argmax())] = True
        best[:, ~allowed] = np.inf
        if A is not None and not prior_on:
            raw = best.copy()
            if bias is not None:
                raw = raw / bias[None, :]
            keep = best.copy()
            best = prune_islands(best, raw, A, kin)
            lost = ~np.isfinite(best).any(1)
            if lost.any():
                best[lost] = keep[lost]
        bad = ~np.isfinite(best).any(1)          # no candidate segment among the k nearest samples: distances to the candidate segments' own samples
        if bad.any():
            sel = np.isin(lab, np.where(allowed)[0])
            if sel.any():
                t2 = cKDTree(P_all[sel]); l2 = lab[sel]
                D2, I2 = t2.query(P[bad], k=min(12, int(sel.sum())))
                L2 = l2[I2.reshape(len(D2), -1)]; D2 = D2.reshape(len(D2), -1)
                bb = np.full((int(bad.sum()), nseg), np.inf, np.float32); r2 = np.arange(len(D2))
                for j in range(D2.shape[1] - 1, -1, -1):
                    bb[r2, L2[:, j]] = D2[:, j]
                if bias is not None:
                    bb = bb * bias[None, :]
                best[bad] = bb
            else:
                best[bad, int(cnt.argmax())] = 1.0
    dmin = best.min(1, keepdims=True)
    w = np.exp(-(best - dmin) / lam)
    w[~np.isfinite(best)] = 0
    top = np.argsort(-w, axis=1)[:, :topk]
    tw = np.take_along_axis(w, top, 1)
    tw = tw / tw.sum(1, keepdims=True)
    return top.astype(np.int32), tw.astype(np.float32)


def smooth_weights(idx, w, f, nv, nseg, iters=3):
    """Laplacian smoothing of the per-vertex weights (dense over the segments used by this structure)"""
    segs = np.unique(idx[w > 0])
    if len(segs) <= 1:
        return idx, w
    col = {s: i for i, s in enumerate(segs)}
    W = np.zeros((nv, len(segs)), np.float32)
    for j in range(idx.shape[1]):
        m = w[:, j] > 0
        W[np.where(m)[0], [col[s] for s in idx[m, j]]] += w[m, j]
    Lp = laplacian(f, nv)
    for _ in range(iters):
        W = 0.5 * W + 0.5 * (Lp @ W)
    top = np.argsort(-W, axis=1)[:, :TOPK]
    tw = np.take_along_axis(W, top, 1)
    tw = tw / np.maximum(tw.sum(1, keepdims=True), 1e-9)
    out_idx = segs[top]
    tw[tw < 0.01] = 0
    tw = tw / np.maximum(tw.sum(1, keepdims=True), 1e-9)
    return out_idx.astype(np.int32), tw.astype(np.float32)


def compute(M, RB, verbose=True, only=None, prior=None):
    """-> list per structure index: dict(kind 'rigid', seg) | dict(kind 'skin', idx (nv,4), w (nv,4)) ; plus stats"""
    S = M.S
    sid = RB.sid
    nseg = len(RB.segs)
    P, lab = bone_samples(M, RB)
    tree = cKDTree(P)
    kin = kin_dist(RB)
    lbias = limb_bias(RB)
    bone_of = {}
    for k, b in M.bones().items():
        for i in b["idx"]:
            bone_of[i] = k
    out = [None] * len(S)
    thor = sid["v" + RB._thorax_vert()]
    vert_y = np.array([RB.K.spine[i]["c"][1] for i in range(len(RB.K.spine))])
    vert_seg = [sid["v" + v["label"]] for v in RB.K.spine]
    stats = dict(rigid=0, skin=0, skin_verts=0, rigid_verts=0)
    for x in S:
        i = x["idx"]
        if only is not None and i not in only:
            continue
        v, f = x["v"], x["f"]
        nv = len(v)
        k = bone_of.get(i)
        if k is not None and RB.bone_seg.get(k) is not None:
            out[i] = dict(kind="rigid", seg=sid[RB.bone_seg[k]]); stats["rigid"] += 1; stats["rigid_verts"] += nv
            continue
        if k is not None and k in RB.soft_bones:
            # ribs: per vertex by height among the thoracic vertebrae (nearest level in y), smoothed
            th = [(v_["c"][1], sid["v" + v_["label"]]) for v_ in RB.K.spine if v_["region"] == "thoracic"] or [(vert_y[0], vert_seg[0])]
            ys = np.array([t[0] for t in th]); sg = np.array([t[1] for t in th])
            # near the sternum (anterior) the rib follows the sternum's segment
            order = np.argsort(np.abs(v[:, 1:2] - ys[None, :]), axis=1)[:, :2]
            idx = sg[order]
            d = np.abs(v[:, 1:2] - ys[None, :]); d2 = np.take_along_axis(d, order, 1)
            ww = 1.0 / np.maximum(d2, 1.0); ww = ww / ww.sum(1, keepdims=True)
            idx = np.c_[idx, np.zeros((nv, 2), np.int32)]; ww = np.c_[ww, np.zeros((nv, 2))]
            idx, ww = smooth_weights(idx, ww.astype(np.float32), f, nv, nseg, 6)
            out[i] = dict(kind="skin", idx=idx, w=ww); stats["skin"] += 1; stats["skin_verts"] += nv
            continue
        if x["sys"] == "bone":                       # unmapped bone (cartilages of the larynx, ...): rigid with the segment of the nearest bone sample
            q = v[:: max(1, nv // 60)]
            _, I = tree.query(q, k=1)
            seg = int(np.bincount(lab[I]).argmax())
            out[i] = dict(kind="rigid", seg=seg); stats["rigid"] += 1; stats["rigid_verts"] += nv
            continue
        lam = LAMBDA.get(x["sys"], 6.0)
        pm = None
        if prior is not None:
            names = prior.get(canon_id(x["id"]))
            if names:
                pm = np.zeros(nseg, bool)
                for nme in names:
                    j_ = map_prior_segment(RB, nme)
                    if j_ is not None:
                        pm[j_] = True
                if pm.any():
                    pm = pm | (kin[pm] <= 1).any(0)          # + the neighbouring segments (smooth falloff at the joints)
                else:
                    pm = None
        idx, w = dist_weights(v, tree, lab, nseg, lam, prior=pm, kin=kin, bias=(lbias if x["sys"] == "skin" else None), P_all=P, limb=((lbias > 1) if x["sys"] in ("skin", "fascia") else None), kind=skin_kind(x), attach_mm=(ATTACH_MM if x["sys"] in ATTACH_SYS else None), A=(laplacian_adj(f, nv) if x["sys"] != "cns" else None))
        idx, w = smooth_weights(idx, w, f, nv, nseg, 3)
        # rigid when practically every vertex belongs to one segment
        am = idx[np.arange(nv), np.argmax(w, 1)]
        dom = np.bincount(am, minlength=nseg).argmax()
        # rigid only when (almost) every vertex belongs to ONE segment (stray islands of a broken mesh, e.g. a hand muscle with a foot fragment, must not travel with the dominant segment)
        if (((am == dom) & (w.max(1) >= 0.9)).mean() >= 0.98):
            out[i] = dict(kind="rigid", seg=int(dom)); stats["rigid"] += 1; stats["rigid_verts"] += nv
        else:
            out[i] = dict(kind="skin", idx=idx, w=w); stats["skin"] += 1; stats["skin_verts"] += nv
    return out, stats


if __name__ == "__main__":
    import sys, time
    M = MD.Model(sys.argv[1]); RB = RG.RigBuilder(M); RB.build()
    t = time.time()
    out, st = compute(M, RB)
    print(st, "seconds", round(time.time() - t, 1))


def apply_pose(S, skin_out, Ms, only=None):
    """posed vertex arrays for all structures: rigid -> M[seg] v ; skin -> sum w M[seg_k] v"""
    res = {}
    for x in S:
        i = x["idx"]
        if only is not None and i not in only:
            continue
        o = skin_out[i]
        v = x["v"]
        if o["kind"] == "rigid":
            M = Ms[o["seg"]]
            res[i] = v @ M[:3, :3].T + M[:3, 3]
        else:
            out = np.zeros_like(v)
            for j in range(o["idx"].shape[1]):
                w = o["w"][:, j]
                if not w.any():
                    continue
                for sg in np.unique(o["idx"][w > 0, j]):
                    m = (o["idx"][:, j] == sg) & (w > 0)
                    M = Ms[sg]
                    out[m] += w[m, None] * (v[m] @ M[:3, :3].T + M[:3, 3])
            res[i] = out
    return res
