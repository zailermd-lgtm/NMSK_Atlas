"""Translation legs-block -> torso-block by maximising the fraction of the legs block's
hip+sacrum voxels that land on the torso block's hip+sacrum label (the torso holds the whole
pelvis, the legs block only its lower part, so centroids do not match and plain ICP fails).
Coarse-to-fine grid search, then ICP polish on surface points, then Dice/residual report and
origin transfer.  usage: register_blocks2.py torso_total legs_total --origin x,y,z"""
import nibabel as nib, numpy as np, sys
from scipy import ndimage as ndi
from scipy.spatial import cKDTree
from totalsegmentator.map_to_binary import class_map
inv={v:k for k,v in class_map['total'].items()}; ids=[inv[n] for n in ('hip_left','hip_right','sacrum')]
imT=nib.load(sys.argv[1]); mT=np.isin(np.asarray(imT.dataobj),ids); imL=nib.load(sys.argv[2]); mL=np.isin(np.asarray(imL.dataobj),ids)
wL=nib.affines.apply_affine(imL.affine,np.argwhere(mL)); rng=np.random.default_rng(0); sub=wL[rng.choice(len(wL),40000,replace=False)]
inv_aff=np.linalg.inv(imT.affine); shape=np.array(mT.shape)
def cover(t):
    v=np.round(nib.affines.apply_affine(inv_aff,sub+t)).astype(int); ok=np.all((v>=0)&(v<shape),axis=1)
    return mT[v[ok,0],v[ok,1],v[ok,2]].sum()/len(sub)
c0=wL.mean(0); cT=nib.affines.apply_affine(imT.affine,np.argwhere(mT)).mean(0); g=cT-c0
best=None
for dz in np.arange(-120,121,4):
    for dx in np.arange(-24,25,4):
        for dy in np.arange(-24,25,4):
            t=g+np.array([dx,dy,dz]); s=cover(t)
            if best is None or s>best[0]: best=(s,t)
print("coarse: coverage %.3f at"%best[0],best[1].round(1),flush=True)
for step in (2,1):
    b=best
    for dz in np.arange(-6,7,step):
        for dx in np.arange(-6,7,step):
            for dy in np.arange(-6,7,step):
                t=b[1]+np.array([dx,dy,dz]); s=cover(t)
                if s>best[0]: best=(s,t)
    print("refine step",step,": coverage %.3f at"%best[0],best[1].round(1),flush=True)
t=best[1]
# ICP polish on surfaces
sT=nib.affines.apply_affine(imT.affine,np.argwhere(mT&~ndi.binary_erosion(mT))); sL=nib.affines.apply_affine(imL.affine,np.argwhere(mL&~ndi.binary_erosion(mL)))
tree=cKDTree(sT); subL=sL[rng.choice(len(sL),min(80000,len(sL)),replace=False)]
for it in range(20):
    d,i=tree.query(subL+t); keep=d<4; tn=(sT[i[keep]]-subL[keep]).mean(0)
    if np.linalg.norm(tn-t)<0.01: t=tn; break
    t=tn
d,_=tree.query(subL+t); print("ICP translation (RAS mm)",t.round(2),"| surface residual median %.2f mm, 90%% %.2f mm, frac<2mm %.2f"%(np.median(d),np.percentile(d,90),(d<2).mean()),"| coverage %.3f"%cover(t))
if "--origin" in sys.argv:
    o=np.array([float(v) for v in sys.argv[sys.argv.index("--origin")+1].split(",")]); ras=np.array([o[0],o[2],o[1]])+t
    print("origin in torso frame (atlas mm): --origin '%.3f,%.3f,%.3f'"%(ras[0],ras[2],ras[1]))
