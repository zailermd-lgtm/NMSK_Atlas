"""Is the shipped perineal closure still the discrete minimal surface its badge claims?
Method: split the closed slab into its two sheets at the welded rim, take the OUTER sheet,
fix its boundary loop, re-run the Pinkall-Polthier cotangent-weight iteration to convergence,
and measure how far the shipped sheet sits from that minimal surface."""
import sys, numpy as np, collections
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
import geo
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve

def cot_laplacian(v, f, n):
    I=[];J=[];W=[]
    for tri in f:
        for a,b,c in ((0,1,2),(1,2,0),(2,0,1)):
            i,j,kk = tri[a],tri[b],tri[c]
            u=v[i]-v[kk]; w=v[j]-v[kk]
            cr=np.linalg.norm(np.cross(u,w))
            if cr<1e-12: continue
            ct=np.dot(u,w)/cr
            I += [i,j,i,j]; J += [j,i,i,j]; W += [-ct/2,-ct/2, ct/2, ct/2]
    return coo_matrix((W,(I,J)), shape=(n,n)).tocsr()

def sheets(v, f):
    """connected components of the mesh with rim vertices removed -> the two sheets."""
    # rim = vertices on the 'crease': find them as vertices whose one-ring normals split.
    # simpler: the two sheets are offset copies; cluster by vertex normal direction vs. slab mid-plane.
    vn = np.zeros_like(v)
    tn = np.cross(v[f[:,1]]-v[f[:,0]], v[f[:,2]]-v[f[:,0]])
    for k in range(3): np.add.at(vn, f[:,k], tn)
    nrm = np.linalg.norm(vn,axis=1, keepdims=True); nrm[nrm==0]=1
    return vn/nrm

def run(key, sid='zan_skin_perineal_closure'):
    v,f,r = geo.get(key, sid)
    n=len(v)
    # face adjacency graph over faces, split by dihedral: find the rim as the sharp crease
    # Instead: classify faces by their normal's dot with the slab's dominant plane normal.
    tn = np.cross(v[f[:,1]]-v[f[:,0]], v[f[:,2]]-v[f[:,0]])
    a = np.linalg.norm(tn,axis=1)
    tnh = tn/np.maximum(a,1e-12)[:,None]
    # dominant slab normal from area-weighted |normal| PCA
    C = (tnh*a[:,None]).T@tnh
    w,V = np.linalg.eigh(C)
    nd = V[:,np.argmax(w)]
    s = tnh@nd
    outer = s>0.3; inner = s<-0.3
    print(f'{key}: faces {len(f)}  outer {outer.sum()}  inner {inner.sum()}  rim {len(f)-outer.sum()-inner.sum()}')
    fo = f[outer]
    used = np.unique(fo)
    remap = -np.ones(n,int); remap[used]=np.arange(len(used))
    vo = v[used]; fo2 = remap[fo]
    # boundary of the outer sheet
    E=collections.Counter()
    for t in fo2:
        for e in ((t[0],t[1]),(t[1],t[2]),(t[2],t[0])): E[tuple(sorted(e))]+=1
    bnd = sorted({x for e,c in E.items() if c==1 for x in e})
    print(f'  outer sheet: {len(vo)} verts, {len(fo2)} tris, boundary verts {len(bnd)}')
    if len(bnd)<3 or len(bnd)>=len(vo)-2:
        print('  cannot isolate an interior -> test not applicable'); return None
    free = np.setdiff1d(np.arange(len(vo)), bnd)
    # Pinkall-Polthier: iterate x_free = solve(L_ff, -L_fb x_b) with cotangents recomputed
    cur = vo.copy()
    for it in range(80):
        L = cot_laplacian(cur, fo2, len(vo))
        Lff = L[free][:,free]; Lfb = L[free][:,bnd]
        try: nx = spsolve(Lff.tocsc(), -Lfb@cur[bnd])
        except Exception as e: print('  solve failed',e); return None
        nx = np.asarray(nx).reshape(len(free),3)
        d = np.linalg.norm(nx-cur[free],axis=1).max()
        cur[free]=nx
        if d<1e-4: break
    dev = np.linalg.norm(cur[free]-vo[free],axis=1)
    print(f'  iterations {it+1}; deviation of the SHIPPED outer sheet from the minimal surface of its own rim:')
    print(f'    mean {dev.mean():.2f} mm  median {np.median(dev):.2f} mm  p95 {np.percentile(dev,95):.2f} mm  max {dev.max():.2f} mm')
    # also the rim loop's own span, for scale
    bl = vo[bnd]
    print(f'    rim loop bbox span {np.round(bl.max(0)-bl.min(0),1)} mm; outer-sheet area {0.5*np.linalg.norm(np.cross(vo[fo2[:,1]]-vo[fo2[:,0]],vo[fo2[:,2]]-vo[fo2[:,0]]),axis=1).sum():.1f} mm2')
    return dict(mean=float(dev.mean()), median=float(np.median(dev)), p95=float(np.percentile(dev,95)), max=float(dev.max()), nfree=int(len(free)), nbnd=int(len(bnd)))

if __name__=='__main__':
    out={}
    for k in ('base_f','comb_f'):
        out[k]=run(k)
    import json; print(json.dumps(out,indent=1))
