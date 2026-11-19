import numpy as np, collections
def stats(v,f):
    vv=v[f]
    n=np.cross(vv[:,1]-vv[:,0],vv[:,2]-vv[:,0])
    a=np.linalg.norm(n,axis=1)
    area=0.5*a.sum()
    vol=np.einsum('ij,ij->i',vv[:,0],np.cross(vv[:,1],vv[:,2])).sum()/6.0
    E=collections.defaultdict(list)
    for i,(x,y,z) in enumerate(f):
        for e in ((x,y),(y,z),(z,x)):
            E[tuple(sorted(e))].append(i)
    nman=[e for e,l in E.items() if len(l)!=2]
    # mean dihedral over manifold edges
    nh=n/np.maximum(a,1e-12)[:,None]
    ang=[]
    for e,l in E.items():
        if len(l)==2:
            c=np.clip(np.dot(nh[l[0]],nh[l[1]]),-1,1)
            ang.append(np.degrees(np.arccos(c)))
    ang=np.array(ang) if ang else np.array([0.0])
    # spikes: vertex whose distance from the centroid of its one-ring is large vs local edge length
    ring=collections.defaultdict(set)
    for x,y,z in f:
        ring[x].update((y,z)); ring[y].update((x,z)); ring[z].update((x,y))
    sp=[]
    for i,nb in ring.items():
        if len(nb)<3: continue
        p=v[list(nb)]
        c=p.mean(0); el=np.linalg.norm(p-v[i],axis=1).mean()
        if el>1e-9: sp.append(np.linalg.norm(v[i]-c)/el)
    sp=np.array(sp) if sp else np.array([0.0])
    # degenerate triangles
    deg=int((a<1e-9).sum())
    return dict(nv=len(v), nf=len(f), area_mm2=float(area), vol_cm3=float(vol/1000.0),
                nonmanifold_edges=len(nman), defect_pct=float(100.0*len(nman)/max(len(E),1)),
                mean_dihedral_deg=float(ang.mean()), p95_dihedral_deg=float(np.percentile(ang,95)),
                spike_max=float(sp.max()), spike_p999=float(np.percentile(sp,99.9)), spikes_gt2=int((sp>2).sum()),
                degenerate_tris=deg)

def normals_consistent(v,f):
    """fraction of manifold edges whose two faces agree in winding"""
    seen={}; good=0; tot=0
    for x,y,z in f:
        for a,b in ((x,y),(y,z),(z,x)):
            k=(b,a)
            if k in seen: good+=1; tot+=1; seen.pop(k)
            elif (a,b) in seen: tot+=1
            else: seen[(a,b)]=1
    return good, tot
