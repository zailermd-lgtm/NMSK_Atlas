"""Q200: continue a structure that was cut flat at a data-block seam with its Z-Anatomy counterpart.

A measured (or transferred) structure M ends in a planar cap (axis-aligned plane, e.g. the CT block edge). Its fitted Z-Anatomy
counterpart Zf is clipped at the same plane (keeping the side beyond it), the clipped end is warped so that its cross-section
equals M's cap outline (polar radius ratio about the section centroids, decaying along the axis), the far end can be pulled to the
bone it attaches to (smooth, bounded), and the two outlines are bridged by a thin strip. M itself is never edited."""
from __future__ import annotations
import numpy as np
import trimesh
from scipy.spatial import cKDTree
from shapely.geometry import Polygon, LineString, Point

AX = {"x": 0, "y": 1, "z": 2}


def ordered_loops(v, f):
    """boundary of a triangle soup as ORDERED vertex-index loops (chained through shared boundary edges)"""
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    es = np.sort(e, 1)
    u, inv, cnt = np.unique(es, axis=0, return_inverse=True, return_counts=True)
    inv = inv.reshape(-1)
    b = cnt[inv] == 1
    be = e[b]                                   # directed boundary edges
    nxt = {}
    for a, c in be:
        nxt.setdefault(int(a), []).append(int(c))
    loops, seen = [], set()
    for a0 in list(nxt):
        if a0 in seen:
            continue
        loop = [a0]; seen.add(a0)
        cur = a0
        while True:
            cands = [c for c in nxt.get(cur, []) if c not in seen or c == a0]
            if not cands:
                break
            c = cands[0]
            if c == a0:
                break
            loop.append(c); seen.add(c); cur = c
        if len(loop) >= 3:
            loops.append(np.array(loop))
    return loops


def loop_area_2d(P2):
    x, y = P2[:, 0], P2[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def plane_2d(P, axis):
    k = [i for i in range(3) if i != AX[axis]]
    return P[:, k], k


def face_components(f):
    """connected components of a face subset (by shared vertices) -> list of index arrays into f"""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    uv, inv = np.unique(f, return_inverse=True)
    inv = inv.reshape(f.shape)
    n = len(uv)
    A = coo_matrix((np.ones(len(f) * 3), (np.r_[inv[:, 0], inv[:, 1], inv[:, 2]], np.r_[inv[:, 1], inv[:, 2], inv[:, 0]])), shape=(n, n))
    _, lab = connected_components(A, directed=False)
    fl = lab[inv[:, 0]]
    return [np.where(fl == l)[0] for l in np.unique(fl)]


def find_caps(v, f, minarea=40.0, tol=0.35, at_end=2.0, group_mm=0.7):
    """flat caps of M grouped by plane: faces (nearly) in an axis-aligned plane at an extreme of the structure ->
    [{axis,pos,sign,faces,area,comps:[ordered outer loop per connected component],polys:[shapely],n_comp}]"""
    from shapely.ops import unary_union
    vf = v[f]
    nrm = np.cross(vf[:, 1] - vf[:, 0], vf[:, 2] - vf[:, 0])
    ar = 0.5 * np.linalg.norm(nrm, axis=1)
    nrm = nrm / np.maximum(2 * ar[:, None], 1e-12)
    out = []
    for kn, k in AX.items():
        fk = (np.abs(nrm[:, k]) > 0.95) & ((vf[:, :, k].max(1) - vf[:, :, k].min(1)) < tol)
        if not fk.any():
            continue
        pc = vf[:, :, k].mean(1)
        lo, hi = v[:, k].min(), v[:, k].max()
        idx = np.where(fk)[0]
        key = np.round(pc[idx] / group_mm).astype(int)
        binarea = {}
        for kk_, a_ in zip(key, ar[idx]):
            binarea[kk_] = binarea.get(kk_, 0.0) + a_
        taken, groups = set(), []
        for kb in sorted(binarea, key=lambda x: -binarea[x]):
            if binarea[kb] < minarea or kb in taken:
                continue
            g = [kb] + [n for n in (kb - 1, kb + 1) if n in binarea and n not in taken and binarea[n] >= 0.25 * binarea[kb]]
            taken.update(g); groups.append(g)
        groups = [idx[np.isin(key, g)] for g in groups]
        for g in groups:
            g = np.asarray(g)
            area = float(ar[g].sum()); pos = float(np.average(pc[g], weights=ar[g]))
            if kn == "x" and abs(pos) < 15:
                continue
            if area < minarea:
                continue
            if not (abs(pos - lo) < at_end or abs(pos - hi) < at_end):
                continue
            sign = 1 if abs(pos - hi) < abs(pos - lo) else -1
            comps, polys = [], []
            for comp in face_components(f[g]):
                fc = g[comp]
                if ar[fc].sum() < 8.0:
                    continue
                loops = ordered_loops(v, f[fc])
                if not loops:
                    continue
                areas = [abs(loop_area_2d(plane_2d(v[l], kn)[0])) for l in loops]
                lp = loops[int(np.argmax(areas))]
                pg = Polygon(plane_2d(v[lp], kn)[0]).buffer(0)
                if pg.is_empty:
                    continue
                comps.append(lp); polys.append(pg)
            if not polys:
                continue
            out.append(dict(axis=kn, pos=pos, sign=sign, faces=g, area=area, comps=comps, polys=polys, n_comp=len(polys)))
    return sorted(out, key=lambda c: -c["area"])


def cap_outline(cap, close_mm=4.0):
    """single outer outline (n,2) of the cap group: the loop itself for one component, else the closed union (convex hull
    if the fragments stay apart)"""
    from shapely.ops import unary_union
    polys = cap["polys"]
    if len(polys) == 1:
        u = polys[0]
    else:
        u = unary_union([p.buffer(close_mm) for p in polys]).buffer(-close_mm)
        if u.geom_type != "Polygon":
            u = unary_union(polys).convex_hull
    if u.geom_type != "Polygon":
        u = max(list(u.geoms), key=lambda g: g.area)
    xy = np.asarray(u.exterior.coords)[:-1]
    return xy, u


def clip_side(v, f, axis, pos, sign):
    """keep the part of the mesh with sign*(x[axis]-pos) >= 0; returns v2, f2 (new vertices exactly on the plane)"""
    n = np.zeros(3); n[AX[axis]] = sign
    o = np.zeros(3); o[AX[axis]] = pos
    m = trimesh.Trimesh(v, f, process=False)
    r = trimesh.intersections.slice_mesh_plane(m, n, o, cap=False)
    v2, f2 = np.asarray(r.vertices, float), np.asarray(r.faces, np.int64)
    key = np.round(v2 / 1e-4).astype(np.int64)
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    v2, f2 = v2[first], inv.reshape(-1)[f2]
    ok = (f2[:, 0] != f2[:, 1]) & (f2[:, 1] != f2[:, 2]) & (f2[:, 0] != f2[:, 2])
    return v2, f2[ok]


def polar_radius(loop_xy, c, nb=72):
    """farthest boundary radius per angular bin about c (smoothed circularly)"""
    d = loop_xy - c
    th = np.arctan2(d[:, 1], d[:, 0]); r = np.linalg.norm(d, axis=1)
    # densify the polyline so bins are filled
    pts = []
    for i in range(len(loop_xy)):
        a, b = loop_xy[i], loop_xy[(i + 1) % len(loop_xy)]
        for t in np.linspace(0, 1, 6, endpoint=False):
            pts.append(a + t * (b - a))
    pts = np.asarray(pts) - c
    th = np.arctan2(pts[:, 1], pts[:, 0]); r = np.linalg.norm(pts, axis=1)
    bins = ((th + np.pi) / (2 * np.pi) * nb).astype(int) % nb
    R = np.zeros(nb)
    for b_ in range(nb):
        s = r[bins == b_]
        R[b_] = s.max() if len(s) else np.nan
    ok = ~np.isnan(R)
    if ok.sum() < 4:
        return None
    idx = np.arange(nb)
    R = np.interp(idx, idx[ok], R[ok], period=nb)
    k = np.array([1, 2, 3, 2, 1], float); k /= k.sum()
    Rp = np.concatenate([R[-2:], R, R[:2]])
    return np.convolve(Rp, k, mode="valid")


def smooth_w(s, L):
    t = np.clip(1.0 - s / max(L, 1e-6), 0, 1)
    return t * t * (3 - 2 * t)


def warp_section(cv, axis, pos, sign, cz, cm, Rz, Rm, L, rmin=0.45, rmax=2.2):
    """in-plane polar map: Zf section (centre cz, radius Rz(th)) -> M cap outline (centre cm, Rm(th)), decaying with the
    distance s beyond the plane over L mm. Returns the new vertices."""
    k = [i for i in range(3) if i != AX[axis]]
    s = sign * (cv[:, AX[axis]] - pos)
    w = smooth_w(np.maximum(s, 0), L)
    xy = cv[:, k]
    d = xy - cz
    th = np.arctan2(d[:, 1], d[:, 0]); nb = len(Rz)
    fb = (th + np.pi) / (2 * np.pi) * nb
    i0 = np.floor(fb).astype(int) % nb; i1 = (i0 + 1) % nb; a = fb - np.floor(fb)
    rz = Rz[i0] * (1 - a) + Rz[i1] * a
    rm = Rm[i0] * (1 - a) + Rm[i1] * a
    ratio = np.clip(rm / np.maximum(rz, 1e-6), rmin, rmax)
    scale = 1.0 + w * (ratio - 1.0)
    new = cm + (cz - cz) + d * scale[:, None] + (cm - cz) * 0  # placeholder replaced below
    shift = (cm - cz)
    new = cz + d * scale[:, None] + shift * w[:, None]
    out = cv.copy()
    out[:, k] = new
    return out


def strip_faces(vA, la, vB, lb):
    """triangle strip between two ordered loops (vertex arrays indexed globally in one vertex array: la, lb are index
    arrays into the SAME array V); both loops are parameterised by arclength from the closest pair, same orientation."""
    A, B = np.asarray(la), np.asarray(lb)
    pa, pb = vA[A], vB[B]
    # orient both counter-clockwise about the common centroid in their plane (use 3D: sign of area w.r.t. the loop normal)
    def ccw_sign(P):
        c = P.mean(0)
        n = np.zeros(3)
        for i in range(len(P)):
            n += np.cross(P[i] - c, P[(i + 1) % len(P)] - c)
        return n
    na, nb_ = ccw_sign(pa), ccw_sign(pb)
    if np.dot(na, nb_) < 0:
        B = B[::-1]; pb = pb[::-1]
    # start B at the vertex closest to A[0]
    j0 = int(np.argmin(np.linalg.norm(pb - pa[0], axis=1)))
    B = np.roll(B, -j0); pb = np.roll(pb, -j0)

    def par(P):
        seg = np.linalg.norm(np.roll(P, -1, 0) - P, axis=1)
        t = np.concatenate([[0], np.cumsum(seg)[:-1]]) / max(seg.sum(), 1e-9)
        return t
    ta, tb = par(pa), par(pb)
    i = j = 0
    faces = []
    na_, nb2 = len(A), len(B)
    while i < na_ or j < nb2:
        ta_next = ta[i + 1] if i + 1 < na_ else 1.0
        tb_next = tb[j + 1] if j + 1 < nb2 else 1.0
        if i >= na_:
            adv_a = False
        elif j >= nb2:
            adv_a = True
        else:
            adv_a = ta_next <= tb_next
        if adv_a:
            faces.append([A[i % na_], A[(i + 1) % na_], B[j % nb2]]); i += 1
        else:
            faces.append([B[j % nb2], A[i % na_], B[(j + 1) % nb2]]); j += 1
    return np.asarray(faces, np.int64)


def section_area_inside(Mv, Mf, axis, pos, sign, depth=3.0):
    """area of M's cross-section 'depth' mm inside the cap plane (shapely union of the section loops)"""
    from shapely.ops import unary_union
    n = np.zeros(3); n[AX[axis]] = 1.0
    o = np.zeros(3); o[AX[axis]] = pos - sign * depth
    seg = trimesh.intersections.mesh_plane(trimesh.Trimesh(Mv, Mf, process=False), n, o, return_faces=False)
    if len(seg) == 0:
        return 0.0
    kk = [i for i in range(3) if i != AX[axis]]
    from shapely.geometry import LineString as LS
    from shapely.ops import polygonize
    lines = unary_union([LS(x[:, kk]) for x in seg if np.linalg.norm(x[0] - x[1]) > 1e-6])
    polys = list(polygonize(lines))
    return float(sum(p.area for p in polys))


def projected_area(v, f, axis, cell=1.0):
    """area of M's silhouette projected onto the plane normal to `axis` (rasterised, mm^2)"""
    from skimage.draw import polygon as skpoly
    kk = [i for i in range(3) if i != AX[axis]]
    P = v[:, kk]
    lo = P.min(0) - 1
    G = np.zeros(tuple(np.ceil((P.max(0) - lo) / cell).astype(int) + 3), bool)
    T = (P[f] - lo) / cell
    for t in T:
        rr, cc = skpoly(t[:, 0], t[:, 1], G.shape)
        G[rr, cc] = True
    return float(G.sum() * cell * cell)


def cap_union_area(cap, close_mm=0.0):
    from shapely.ops import unary_union
    return float(unary_union(cap["polys"]).area)


def continue_cap(Mv, cap, Zv, Zf_faces, min_beyond=6.0, L_min=20.0, L_max=70.0, rmax=6.0):
    """Z continuation beyond the cap plane of M (M not edited): clipped Zf, section warped onto the cap outline, closed by a planar face."""
    import mapbox_earcut as earcut
    axis, pos, sign = cap["axis"], cap["pos"], cap["sign"]
    k = AX[axis]; kk = [i for i in range(3) if i != k]
    beyond = sign * (Zv[:, k] - pos)
    if beyond.max() < min_beyond:
        return dict(reason=f"Z counterpart ends {beyond.max():.1f} mm beyond the plane (< {min_beyond:g} mm): no Z material to add")
    cv, cf = clip_side(Zv, Zf_faces, axis, pos, sign)
    if len(cf) < 8:
        return dict(reason="clip left <8 faces")
    loops = [l for l in ordered_loops(cv, cf) if np.abs(cv[l, k] - pos).max() < 1e-4]
    if not loops:
        return dict(reason="Z mesh has no closed section at the plane")
    xyZ = [plane_2d(cv[l], axis)[0] for l in loops]
    areasZ = [abs(loop_area_2d(p)) for p in xyZ]
    amax = max(areasZ)
    keep = [i for i, a in enumerate(areasZ) if a > 0.12 * amax]
    # keep only the faces connected to a kept section loop
    comps = face_components(cf)
    kv = set(int(x) for i in keep for x in loops[i])
    cfk = np.concatenate([cf[c] for c in comps if kv & set(cf[c].ravel().tolist())])
    used = np.unique(cfk)
    remap = -np.ones(len(cv), int); remap[used] = np.arange(len(used))
    cv, cf = cv[used], remap[cfk]
    loops = [remap[loops[i]] for i in keep]
    xyZ = [plane_2d(cv[l], axis)[0] for l in loops]
    xm, um = cap_outline(cap)
    from shapely.ops import unary_union
    zpoly = unary_union([Polygon(p).buffer(0) for p in xyZ])
    if zpoly.geom_type != "Polygon":
        zpoly = zpoly.convex_hull
    xz = np.asarray(zpoly.exterior.coords)[:-1]
    cz = np.asarray(zpoly.centroid.coords[0]); cm = np.asarray(um.centroid.coords[0])
    Rz = polar_radius(xz, cz); Rm = polar_radius(xm, cm)
    if Rz is None or Rm is None:
        return dict(reason="degenerate section")
    dR = abs(float(Rm.mean() - Rz.mean()))
    L = float(np.clip(L_min + 4.0 * dR, L_min, L_max))
    cv2 = warp_section(cv, axis, pos, sign, cz, cm, Rz, Rm, L, rmax=rmax)
    snapped = False
    if len(loops) == 1:
        ring = LineString(np.vstack([xm, xm[:1]]))
        for idx in loops[0]:
            q = ring.interpolate(ring.project(Point(cv2[idx, kk])))
            cv2[idx, kk[0]], cv2[idx, kk[1]] = q.x, q.y
        snapped = True
    for l in loops:
        cv2[l, k] = pos
    faces = [cf]
    for l in loops:
        P2 = cv2[l][:, kk]
        tri = earcut.triangulate_float64(P2.astype(np.float64), np.array([len(P2)], np.uint32)).reshape(-1, 3)
        faces.append(l[tri])
    F = np.vstack(faces)
    return dict(v=cv2, f=F, loops=loops, n_loops_z=len(loops), area_ratio=float(zpoly.area / max(um.area, 1e-6)), beyond_mm=float(beyond.max()), L=L,
                cz=cz, cm=cm, n_frag=cap["n_comp"], snapped=snapped)


def _ease(t):
    return t * t * (3 - 2 * t)


def _local_continuation(s0, cap, capA, axis, pos, sign, kk, k, beyond, shift_decay):
    """The Z counterpart's section at the seam is much smaller than the measured cap face (the measured mass is wider than the Z muscle):
    no loft over the whole face. The Z structure is clipped at the seam plane, its section closed by a planar face, and shifted in-plane
    (fading over `shift_decay` mm) so that the section lies on the measured cap face; the rest of the flat face stays as it is (reported)."""
    import mapbox_earcut as earcut
    from shapely.geometry import Point as _P
    from shapely.ops import nearest_points
    v1, f1, loops1, keep1, poly0 = s0
    comps = face_components(f1)
    kv = set(int(x) for i in keep1 for x in loops1[i])
    fk = np.concatenate([f1[c] for c in comps if kv & set(f1[c].ravel().tolist())])
    used = np.unique(fk)
    remap = -np.ones(len(v1), int); remap[used] = np.arange(len(used))
    zv, zf = v1[used].copy(), remap[fk]
    zloops = [remap[loops1[i]] for i in keep1]
    c = _P(poly0.centroid.coords[0])
    if capA.contains(c):
        sh = np.zeros(2)
    else:
        q = nearest_points(capA, c)[0]
        sh = np.array([q.x - c.x, q.y - c.y])
        # move far enough that the section's own extent starts to overlap the face
    s = np.maximum(sign * (zv[:, k] - pos), 0)
    w = 1.0 - _ease(np.clip(s / shift_decay, 0, 1))
    zv[:, kk[0]] += w * sh[0]; zv[:, kk[1]] += w * sh[1]
    faces = [zf]
    for l in zloops:
        zv[l, k] = pos
        P2 = zv[l][:, kk]
        tri = earcut.triangulate_float64(P2.astype(np.float64), np.array([len(P2)], np.uint32)).reshape(-1, 3)
        faces.append(l[tri])
    from shapely.geometry import Polygon as _Pg
    zpoly = _uu_polys([_Pg(zv[l][:, kk]).buffer(0) for l in zloops])
    cover = float(zpoly.intersection(capA).area / max(capA.area, 1e-9))
    ring0 = np.unique(np.concatenate(zloops))
    return dict(v=zv, f=np.vstack(faces), ring0=ring0, n=len(ring0), n_loops_z=len(zloops), Lt=0.0, beyond_mm=float(beyond.max()), sh=float(np.linalg.norm(sh)),
                area_ratio=float(poly0.area / max(capA.area, 1e-6)), n_frag=cap["n_comp"], mode="local", cap_covered=cover)


def _uu_polys(ps):
    from shapely.ops import unary_union
    return unary_union(ps)


def continue_cap2(Mv, cap, Zv, Zf_faces, min_beyond=10.0, shift_decay=30.0, nstep=4, nang=64, local_ratio=0.35):
    """Z continuation beyond the cap plane P0 of M, as a loft + Z piece (M is not edited):
      ring 0   = outline of M's cap (the loop itself for a one-piece cap, the closed union of the fragments otherwise) at P0;
      ring K   = outline of the fitted Z counterpart's section at the plane P1, Lt mm beyond P0 (Lt grows with the size mismatch);
      the loft joins the two (smooth interpolation), a planar face closes P1; the Z counterpart beyond P1 is kept as it is, shifted
      in-plane by (cap centroid - Z section centroid at P0) with the shift fading to 0 over `shift_decay` mm."""
    import mapbox_earcut as earcut
    axis, pos, sign = cap["axis"], cap["pos"], cap["sign"]
    k = AX[axis]; kk = [i for i in range(3) if i != k]
    beyond = sign * (Zv[:, k] - pos)
    if beyond.max() < min_beyond:
        return dict(reason=f"Z counterpart ends {beyond.max():.1f} mm beyond the plane (< {min_beyond:g} mm): no Z material to add")
    xm, um = cap_outline(cap)
    cm = np.asarray(um.centroid.coords[0])
    # Z section at P0 -> centroid and size
    def section(p):
        v2, f2 = clip_side(Zv, Zf_faces, axis, p, sign)
        if len(f2) < 8:
            return None
        loops = [l for l in ordered_loops(v2, f2) if np.abs(v2[l, k] - p).max() < 1e-4]
        if not loops:
            return None
        xy = [plane_2d(v2[l], axis)[0] for l in loops]
        ar = [abs(loop_area_2d(q)) for q in xy]
        keep = [i for i, a in enumerate(ar) if a > 0.12 * max(ar)]
        from shapely.ops import unary_union
        poly = unary_union([Polygon(xy[i]).buffer(0) for i in keep])
        if poly.geom_type != "Polygon":
            poly = poly.convex_hull
        return v2, f2, loops, keep, poly
    s0 = section(pos)
    if s0 is None:
        return dict(reason="Z mesh has no closed section at the plane")
    poly0 = s0[4]
    cz0 = np.asarray(poly0.centroid.coords[0])
    from shapely.ops import unary_union as _uu
    capA = _uu(cap["polys"])
    if poly0.area < local_ratio * capA.area:
        return _local_continuation(s0, cap, capA, axis, pos, sign, kk, k, beyond, shift_decay)
    Rm = polar_radius(xm, cm); Rz0 = polar_radius(np.asarray(poly0.exterior.coords)[:-1], cz0)
    if Rm is None or Rz0 is None:
        return dict(reason="degenerate section")
    dR = abs(float(Rm.mean() - Rz0.mean()))
    Lt0 = float(np.clip(6.0 + 0.8 * dR, 6.0, 35.0))
    s1 = None
    for Lt in (Lt0, 0.7 * Lt0, 0.5 * Lt0, 4.0, 2.5):
        Lt = float(min(Lt, max(beyond.max() - 1.0, 1.5)))
        p1 = pos + sign * Lt
        s1 = section(p1)
        if s1 is not None:
            break
    if s1 is None:
        return dict(reason="Z mesh has no closed section at the loft end")
    v1, f1, loops1, keep1, poly1 = s1
    # keep faces connected to the kept loops, then shift
    comps = face_components(f1)
    kv = set(int(x) for i in keep1 for x in loops1[i])
    f1k = np.concatenate([f1[c] for c in comps if kv & set(f1[c].ravel().tolist())])
    used = np.unique(f1k)
    remap = -np.ones(len(v1), int); remap[used] = np.arange(len(used))
    zv, zf = v1[used].copy(), remap[f1k]
    zloops = [remap[loops1[i]] for i in keep1]
    sh = cm - cz0
    s = np.maximum(sign * (zv[:, k] - p1), 0)
    w = 1.0 - _ease(np.clip(s / shift_decay, 0, 1))
    zv[:, kk[0]] += w * sh[0]; zv[:, kk[1]] += w * sh[1]
    for l in zloops:
        zv[l, k] = p1
    # Z outline at P1 after the shift
    poly1s = []
    from shapely.ops import unary_union
    poly1s = unary_union([Polygon(plane_2d(zv[l], axis)[0]).buffer(0) for l in zloops])
    if poly1s.geom_type != "Polygon":
        poly1s = poly1s.convex_hull
    xz1 = np.asarray(poly1s.exterior.coords)[:-1]
    cz1 = np.asarray(poly1s.centroid.coords[0])
    Rz1 = polar_radius(xz1, cz1)
    if Rz1 is None:
        return dict(reason="degenerate section at the loft end")
    # ring 0: M's outline itself (ordered, counter-clockwise about cm), ring K: Z outline at the same angles
    xm_o = xm if loop_area_2d(xm) > 0 else xm[::-1]
    ang = np.arctan2(xm_o[:, 1] - cm[1], xm_o[:, 0] - cm[0])
    nb = len(Rz1)
    fb = (ang + np.pi) / (2 * np.pi) * nb
    i0 = np.floor(fb).astype(int) % nb; i1 = (i0 + 1) % nb; a = fb - np.floor(fb)
    rr = Rz1[i0] * (1 - a) + Rz1[i1] * a
    ringK2 = cz1 + np.stack([np.cos(ang), np.sin(ang)], 1) * rr[:, None]
    n = len(xm_o)
    rings = []
    for j in range(nstep + 1):
        t = _ease(j / nstep)
        xy = xm_o + t * (ringK2 - xm_o)
        P = np.zeros((n, 3)); P[:, kk[0]] = xy[:, 0]; P[:, kk[1]] = xy[:, 1]; P[:, k] = pos + sign * Lt * (j / nstep)
        rings.append(P)
    LV = np.vstack(rings)
    lf = []
    for j in range(nstep):
        for i in range(n):
            a_, b_ = j * n + i, j * n + (i + 1) % n
            c_, d_ = (j + 1) * n + i, (j + 1) * n + (i + 1) % n
            lf += [[a_, b_, d_], [a_, d_, c_]]
    lf = np.asarray(lf, np.int64)
    # planar cap at P1 over ring K
    tri = earcut.triangulate_float64(rings[-1][:, kk].astype(np.float64), np.array([n], np.uint32)).reshape(-1, 3) + nstep * n
    V = np.vstack([LV, zv])
    F = np.vstack([lf, tri, zf + len(LV)])
    return dict(v=V, f=F, ring0=np.arange(n), n=n, mode="loft", cap_covered=1.0, n_loops_z=len(zloops), Lt=Lt, beyond_mm=float(beyond.max()), sh=float(np.linalg.norm(sh)),
                area_ratio=float(poly0.area / max(um.area, 1e-6)), n_frag=cap["n_comp"])
