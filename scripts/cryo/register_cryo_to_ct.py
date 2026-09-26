"""Register the 1 mm cryosection volume to the CT (torso frame, RAS): per CT anchor slice, search
cryo slices +-60 around the expected index under 4 flip hypotheses, aligning in-plane by phase
correlation of the body silhouettes; report IoU. Output: anchors.json (ct_z, cryo_z, flip, dx, dy, iou)."""
import numpy as np, json, sys
from skimage.registration import phase_cross_correlation
from scipy import ndimage as ndi
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/vh_cryo/"
cls=np.load(S+"cryo_1mm_classes.npy",mmap_mode="r"); Z=cls.shape[0]
def cryo_mask(z): 
    m=np.asarray(cls[z])>0; return ndi.binary_fill_holes(ndi.binary_opening(m,iterations=2))
ct={n:np.load(S+f"ct_{n}_body.npy",mmap_mode="r") for n in ("torso","legs")}
ctz0={"torso":-863.0,"legs":-978.0-693.0}  # RAS z of slice 0
FLIPS={"id":lambda a:a,"fy":lambda a:a[::-1,:],"fx":lambda a:a[:,::-1],"fxy":lambda a:a[::-1,::-1]}
def pad(a,shape):
    out=np.zeros(shape,bool); h=min(a.shape[0],shape[0]); w=min(a.shape[1],shape[1]); out[:h,:w]=a[:h,:w]; return out
def score(a,b):
    a=pad(a,(480,700)); b=pad(b,(480,700))
    sh,_,_=phase_cross_correlation(a.astype(np.float32),b.astype(np.float32),upsample_factor=1)
    bs=np.roll(np.roll(b,int(sh[0]),0),int(sh[1]),1); inter=(a&bs).sum(); return inter/((a|bs).sum()+1), sh
# expected cryo index for CT RAS z: vertex at cryo 0 <-> CT torso top z=-20 (slice 843): cryo_idx ~ (-20 - z_ras)
res=[]
for name in ("torso","legs"):
    vol=ct[name]; n=vol.shape[0]
    for k in range(20,n-20,60):
        zr=ctz0[name]+k; guess=int(round(-20-zr)); a=np.asarray(vol[k]); 
        if a.sum()<2000: continue
        best=None
        for cz in range(max(0,guess-70),min(Z,guess+71),2):
            b=cryo_mask(cz)
            for fn,f in FLIPS.items():
                s,sh=score(a,f(b))
                if best is None or s>best[0]: best=(s,cz,fn,sh)
        res.append(dict(block=name,ct_k=k,ct_z=zr,cryo_z=best[1],flip=best[2],shift=[float(v) for v in best[3]],iou=float(best[0])))
        print(res[-1],flush=True); json.dump(res,open(S+"anchors.json","w"),indent=1)
print("REG_DONE",flush=True)
