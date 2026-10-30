"""Q292 geometry library: her-frame -> Base F registration, voxel occupancy, signed-distance fields and guarded pushes.

Used by scripts/anatomy/q292/build_q292.py (Base · Female: her own breasts / chest skin contour / pelvic organs). Plain numpy / scipy / trimesh;
every push reports what it moved (count, max / p95 displacement, what is still violating) so the cards and the report can state it.
"""
from __future__ import annotations

import re

import numpy as np
import trimesh
from scipy import ndimage as ndi
from scipy.interpolate import RBFInterpolator
from scipy.sparse import coo_matrix
from scipy.spatial import cKDTree


# ---------------------------------------------------------------- occupancy (1 mm voxels on the global grid)
def occ_scan(v,f,pitch=1.0):
    """solid occupancy by z-ray parity on columns at voxel centres (global grid i*pitch). returns (i0, bool array)"""
    i0=np.floor(v.min(0)/pitch).astype(int)-1; i1=np.ceil(v.max(0)/pitch).astype(int)+1
    sh=i1-i0+1
    T=v[f]  # (n,3,3)
    xs=(i0[0]+np.arange(sh[0]))*pitch; ys=(i0[1]+np.arange(sh[1]))*pitch
    hits=[[] for _ in range(sh[0]*sh[1])]
    # per triangle: columns inside its xy bbox
    mn=T[:,:,:2].min(1); mx=T[:,:,:2].max(1)
    ia=np.ceil(mn[:,0]/pitch).astype(int)-i0[0]; ib=np.floor(mx[:,0]/pitch).astype(int)-i0[0]
    ja=np.ceil(mn[:,1]/pitch).astype(int)-i0[1]; jb=np.floor(mx[:,1]/pitch).astype(int)-i0[1]
    cols_i=[];cols_j=[];tri=[]
    for t in range(len(T)):
        if ib[t]<ia[t] or jb[t]<ja[t]: continue
        I,J=np.meshgrid(np.arange(ia[t],ib[t]+1),np.arange(ja[t],jb[t]+1),indexing='ij')
        cols_i.append(I.ravel());cols_j.append(J.ravel());tri.append(np.full(I.size,t))
    if not tri: return i0,np.zeros(sh,bool)
    ci=np.concatenate(cols_i);cj=np.concatenate(cols_j);tr=np.concatenate(tri)
    px=xs[ci];py=ys[cj]; A=T[tr,0];B=T[tr,1];C=T[tr,2]
    # barycentric in xy (jitter to avoid edge double counting)
    px=px+1e-4;py=py+2e-4
    d=(B[:,1]-C[:,1])*(A[:,0]-C[:,0])+(C[:,0]-B[:,0])*(A[:,1]-C[:,1])
    ok=np.abs(d)>1e-12
    l1=((B[:,1]-C[:,1])*(px-C[:,0])+(C[:,0]-B[:,0])*(py-C[:,1]))/np.where(ok,d,1)
    l2=((C[:,1]-A[:,1])*(px-C[:,0])+(A[:,0]-C[:,0])*(py-C[:,1]))/np.where(ok,d,1)
    l3=1-l1-l2
    ins=ok&(l1>=0)&(l2>=0)&(l3>=0)
    z=l1*A[:,2]+l2*B[:,2]+l3*C[:,2]
    ci,cj,z=ci[ins],cj[ins],z[ins]
    occ=np.zeros(sh,bool)
    key=ci*sh[1]+cj; o=np.lexsort((z,key)); key,z=key[o],z[o]
    starts=np.r_[0,np.nonzero(np.diff(key))[0]+1]; ends=np.r_[starts[1:],len(key)]
    zs=(i0[2]+np.arange(sh[2]))*pitch
    for s,e in zip(starts,ends):
        n=e-s
        if n<2: continue
        zz=z[s:e]
        if n%2: zz=zz[:-1]
        k=key[s]; a,b=divmod(k,sh[1])
        for p in range(0,len(zz)-1,2):
            m=(zs>=zz[p])&(zs<=zz[p+1]); occ[a,b,m]=True
    return i0,occ
def overlap(oa,ob):
    (ia,a),(ib,b)=oa,ob
    lo=np.maximum(ia,ib); hi=np.minimum(ia+np.array(a.shape),ib+np.array(b.shape))
    if (hi<=lo).any(): return 0
    sa=tuple(slice(lo[k]-ia[k],hi[k]-ia[k]) for k in range(3)); sb=tuple(slice(lo[k]-ib[k],hi[k]-ib[k]) for k in range(3))
    return int((a[sa]&b[sb]).sum())


# ---------------------------------------------------------------- registration: her atlas frame (Imaging F / Combined F) -> Base F
TRUNK = re.compile(r'(vertebra|sacrum|coccyx|hip_bone|_rib_|stern|xiph|clavic|scapul|costal|atlas_c1|axis_c2|intervertebral_disc)')
def sim(X, Y):
    mx, my = X.mean(0), Y.mean(0); A = X - mx; B = Y - my
    U, S, Vt = np.linalg.svd(A.T @ B); d = np.sign(np.linalg.det(U @ Vt)); D = np.diag([1, 1, d])
    R = (U @ D @ Vt).T; s = (S * np.diag(D)).sum() / (A ** 2).sum(); t = my - s * R @ mx
    return s, R, t
def icp_pairs(X, Y, iters=30):
    """similarity ICP of X onto Y; returns pairs (X subset, matched Y points) after convergence, symmetric-rejection"""
    tY = cKDTree(Y); s, R, t = sim(X, Y) if len(X) == len(Y) else (1.0, np.eye(3), Y.mean(0) - X.mean(0))
    for _ in range(iters):
        Z = s * X @ R.T + t; d, i = tY.query(Z)
        keep = d < np.percentile(d, 90) + 1e-9
        s, R, t = sim(X[keep], Y[i[keep]])
    Z = s * X @ R.T + t; d, i = tY.query(Z)
    keep = d < 3.0
    return X[keep], Y[i[keep]], float(np.median(d))
def correspondences(C, B, keys=None, step=6):
    Xs, Ys, rep = [], [], {}
    for k in sorted(B):
        v, f, c = B[k][:3]
        if c not in ('bone', 'cartilage') or not TRUNK.search(k) or k not in C: continue
        if keys and k not in keys: continue
        cv, cf = C[k][0], C[k][1]
        if np.array_equal(cf, f):
            X, Y = cv[::step], v[::step]; mode = 'vertex'
            r = None
        else:
            X, Y, r = icp_pairs(cv[::2], v); X, Y = X[::max(1, step // 2)], Y[::max(1, step // 2)]; mode = 'icp'
        Xs.append(X); Ys.append(Y); rep[k] = (mode, len(X), r)
    return np.vstack(Xs), np.vstack(Ys), rep
class Map:
    def __init__(self, X, Y, smoothing=50.0, ncp=3500, seed=0):
        s, R, t = sim(X, Y); self.s, self.R, self.t = s, R, t
        Z = s * X @ R.T + t
        rng = np.random.default_rng(seed)
        # spatially uniform subsample of control points (voxel 8 mm)
        key = np.floor(Z / 8.0).astype(int); _, first = np.unique(key, axis=0, return_index=True)
        idx = first if len(first) <= ncp else rng.choice(first, ncp, replace=False)
        self.cp = Z[idx]; self.rbf = RBFInterpolator(Z[idx], (Y - Z)[idx], kernel='thin_plate_spline', smoothing=smoothing, degree=1)
        self.resid_rigid = np.linalg.norm(Y - Z, axis=1)
        self.resid = np.linalg.norm(self(X) - Y, axis=1)
    def lin(self, P): return self.s * np.asarray(P) @ self.R.T + self.t
    def __call__(self, P):
        Z = self.lin(P); out = np.empty_like(Z)
        for a in range(0, len(Z), 20000): out[a:a + 20000] = Z[a:a + 20000] + self.rbf(Z[a:a + 20000])
        return out


# ---------------------------------------------------------------- signed distance + pushes
class SDF:
    """signed distance (mm, + inside) of the union of closed meshes on a 1 mm grid covering lo..hi"""
    def __init__(self, meshes, lo, hi, pitch=1.0, fill=False):
        self.p = pitch; self.lo = np.floor(np.asarray(lo) / pitch).astype(int); hi = np.ceil(np.asarray(hi) / pitch).astype(int)
        sh = hi - self.lo + 1; occ = np.zeros(sh, bool)
        for v, f in meshes:
            i0, o = occ_scan(v, f, pitch)
            a = np.maximum(i0, self.lo); b = np.minimum(i0 + np.array(o.shape), self.lo + sh)
            if (b <= a).any(): continue
            occ[tuple(slice(a[k] - self.lo[k], b[k] - self.lo[k]) for k in range(3))] |= o[tuple(slice(a[k] - i0[k], b[k] - i0[k]) for k in range(3))]
        if fill:   # solid chest wall: close the intercostal gaps and fill the cavity slice by slice (axial = y)
            occ = ndi.binary_closing(occ, iterations=3)
            for j in range(occ.shape[1]): occ[:, j, :] = ndi.binary_fill_holes(occ[:, j, :])
        self.occ = occ
        self.d = (ndi.distance_transform_edt(occ) - ndi.distance_transform_edt(~occ)) * pitch
        self.g = np.stack(np.gradient(ndi.gaussian_filter(self.d, 1.0)), 0)
    def _c(self, P): return (np.asarray(P) / self.p - self.lo).T
    def at(self, P): return ndi.map_coordinates(self.d, self._c(P), order=1, mode='nearest')
    def grad(self, P):
        c = self._c(P); g = np.stack([ndi.map_coordinates(self.g[k], c, order=1, mode='nearest') for k in range(3)], 1)
        return g / (np.linalg.norm(g, axis=1, keepdims=True) + 1e-9)
def neighbour_matrix(nv, f):
    e = np.vstack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]); e = np.vstack([e, e[:, ::-1]])
    A = coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(nv, nv)).tocsr(); A.data[:] = 1
    deg = np.asarray(A.sum(1)).ravel(); deg[deg == 0] = 1
    return A, deg
def push_out(V, F, sdf, margin=1.0, max_disp=15.0, iters=60, smooth=0.5, lock=None):
    """move vertices so that sdf(V+D) <= -margin; displacement diffused over the mesh (shape kept), capped at max_disp"""
    A, deg = neighbour_matrix(len(V), F); D = np.zeros_like(V)
    for it in range(iters):
        P = V + D; s = sdf.at(P); viol = s > -margin
        if not viol.any(): break
        g = sdf.grad(P[viol]); D[viol] -= (s[viol] + margin + 0.05)[:, None] * g
        Dn = (A @ D) / deg[:, None]; D = (1 - smooth) * D + smooth * Dn
        if lock is not None: D[lock] = 0
        n = np.linalg.norm(D, axis=1); big = n > max_disp; D[big] *= (max_disp / n[big])[:, None]
    P = V + D; s = sdf.at(P)
    return P, dict(iters=it + 1, still_violating=int((s > -margin + 0.2).sum()), max_inside_mm=round(float(max(s.max(), -99)), 2),
                   moved_gt1mm=int((np.linalg.norm(D, axis=1) > 1).sum()), disp_max_mm=round(float(np.linalg.norm(D, axis=1).max()), 2),
                   disp_p95_mm=round(float(np.percentile(np.linalg.norm(D, axis=1), 95)), 2))
def mesh_volume(V, F): return float(trimesh.Trimesh(V, F, process=False).volume) / 1000.0
def push_dir(V, F, sdf, dirfn, margin=1.0, max_disp=20.0, rounds=6, smooth_iters=8, lock=None, step=0.5, stop=None, decay=0.85):
    """move violating vertices along dirfn(P) (unit vectors) until sdf <= -margin (line search), then diffuse the
    displacement over the mesh (smooth_iters Jacobi passes, violators re-imposed each round)"""
    A, deg = neighbour_matrix(len(V), F); D = np.zeros_like(V)
    for r in range(rounds):
        P = V + D; s = sdf.at(P); viol = np.nonzero(s > -margin)[0]
        if not len(viol): break
        dv = dirfn(P[viol]); need = np.zeros(len(viol))
        for k in range(int(max_disp / step) + 1):
            q = P[viol] + dv * (need[:, None]); sq = sdf.at(q); go = sq > -margin
            if stop is not None: go &= stop.at(q + dv * step) < -0.2
            if not go.any(): break
            need[go] += step
        D[viol] += dv * need[:, None]
        req = D.copy(); fixed = np.zeros(len(V), bool); fixed[viol] = True
        for _ in range(smooth_iters):
            Dn = (A @ D) / deg[:, None]; D = np.where(fixed[:, None], np.where((np.linalg.norm(Dn, axis=1) > np.linalg.norm(req, axis=1))[:, None], Dn, req), decay * Dn + (1 - decay) * 0.0)
        if lock is not None: D[lock] = 0
        n = np.linalg.norm(D, axis=1); big = n > max_disp; D[big] *= (max_disp / n[big])[:, None]
    P = V + D; s = sdf.at(P); n = np.linalg.norm(D, axis=1)
    return P, dict(rounds=r + 1, still_violating=int((s > -margin + 0.25).sum()), max_inside_mm=round(float(s.max()), 2),
                   moved_gt1mm=int((n > 1).sum()), disp_max_mm=round(float(n.max()), 2), disp_p95_mm=round(float(np.percentile(n, 95)), 2))
def diffuse(D, A, deg, fixed=None, req=None, iters=8, decay=0.85):
    for _ in range(iters):
        Dn = decay * (A @ D) / deg[:, None]
        if fixed is not None:
            keep = fixed & (np.linalg.norm(Dn, axis=1) < np.linalg.norm(req, axis=1))
            Dn[keep] = req[keep]
        D = Dn
    return D
def carry(Va, Vb, X, k=8):
    """move points X with the displacement Vb-Va of their k nearest source vertices (inverse distance)"""
    from scipy.spatial import cKDTree
    d, i = cKDTree(Va).query(X, k=k); w = 1 / (d + 1e-3); w /= w.sum(1, keepdims=True)
    return X + ((Vb - Va)[i] * w[..., None]).sum(1)
def surface_side(P, mesh, outer_face):
    """signed distance-like value: > 0 outside the body behind a thin skin slab (outer faces = slab faces whose normal points out of the body)"""
    c, d, tri = trimesh.proximity.closest_point(mesh, P); n = mesh.face_normals[tri]
    s = np.einsum('ij,ij->i', P - c, n)
    o = outer_face[tri]
    return np.where(o, s, -s - 2.3), c, n, o
def push_inside_skin(V, F, mesh, outer_face, margin=0.5, max_disp=25.0, rounds=8):
    A, deg = neighbour_matrix(len(V), F); D = np.zeros_like(V)
    for r in range(rounds):
        P = V + D; s, c, n, o = surface_side(P, mesh, outer_face)
        viol = s > -margin
        if not viol.any(): break
        out_n = np.where(o[:, None], n, -n)
        req = D.copy(); req[viol] = D[viol] - out_n[viol] * (s[viol] + margin + 0.1)[:, None]
        D = req.copy(); D = diffuse(D, A, deg, viol, req, iters=6)
        nn = np.linalg.norm(D, axis=1); big = nn > max_disp; D[big] *= (max_disp / nn[big])[:, None]
    P = V + D; s, *_ = surface_side(P, mesh, outer_face); nn = np.linalg.norm(D, axis=1)
    return P, dict(rounds=r + 1, outside_gt0_5mm_pct=round(100 * float((s > 0.5).mean()), 2), max_outside_mm=round(float(s.max()), 2),
                   disp_max_mm=round(float(nn.max()), 2), disp_p95_mm=round(float(np.percentile(nn, 95)), 2))
def compress_under(V, F, sb, sw, gap=1.0, floor=0.5, rounds=4, smooth_iters=10):
    """a layer lying on the chest wall (sw: wall SDF) and entered by the breast (sb: breast SDF): every vertex inside the breast is moved
    toward the wall to `gap` mm behind the breast surface (never closer than `floor` mm to the wall); the displacement is smoothed over
    the mesh (vertices that must move keep at least their required move), so the layer is thinned under the breast, not shifted."""
    A, deg = neighbour_matrix(len(V), F); D = np.zeros_like(V)
    for r in range(rounds):
        P = V + D; s = sb.at(P); viol = s > -gap
        if not viol.any(): break
        h = -sw.at(P[viol]); n = -sw.grad(P[viol])
        target = np.maximum(h - (s[viol] + gap), floor); mv = np.maximum(h - target, 0)
        req = D.copy(); req[viol] = D[viol] - n * mv[:, None]
        D = req.copy(); fixed = viol.copy()
        for _ in range(smooth_iters):
            Dn = (A @ D) / deg[:, None]
            keep = fixed & (np.linalg.norm(Dn, axis=1) < np.linalg.norm(req, axis=1)); Dn[keep] = req[keep]
            D = 0.5 * D + 0.5 * Dn
    P = V + D; s = sb.at(P); nn = np.linalg.norm(D, axis=1)
    return P, dict(rounds=r + 1, still_inside_breast=int((s > 0.5).sum()), max_inside_mm=round(float(s.max()), 2),
                   in_wall_gt0_5mm=int((sw.at(P) > 0.5).sum()), disp_max_mm=round(float(nn.max()), 2), disp_p95_mm=round(float(np.percentile(nn, 95)), 2))
