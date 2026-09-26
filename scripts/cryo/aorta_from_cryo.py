"""Aorta tracked through the photographs (Q6). Seed: the largest `total` aorta fragment of the frozen CT
(descending thoracic), mapped into the cryo torso frame. Walk up and down: the next slice's lumen = the
dark-red component (blood: class 3 but darker than muscle, value < 110) inside the previous cross-section
dilated by 4 mm, area 250-900 mm2, roughly round (solidity > 0.8); stops when nothing round remains
(arch: turns; bifurcation: two smaller lumina -> stop at the common iliacs). Rule-based, badged."""
import numpy as np, nibabel as nib, json
from scipy import ndimage as ndi
from PIL import Image
from totalsegmentator.map_to_binary import class_map
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"
rgb=np.load(S+"vh_cryo/cryo_torso_frame_rgb.npy",mmap_mode="r"); cls=np.load(S+"vh_cryo/cryo_torso_frame_cls.npy",mmap_mode="r"); n,H,W=cls.shape; OFF=110
tot=np.asarray(nib.load(S+"vhm_ts/total.nii.gz").dataobj); inv={v:k for k,v in class_map['total'].items()}
ao=tot==inv['aorta']; cl,m=ndi.label(ao); sizes=ndi.sum(np.ones_like(cl),cl,np.arange(1,m+1)); big=cl==(np.argmax(sizes)+1)
ks=np.where(big.any(axis=(0,1)))[0]; k0=int(np.median(ks)); print("seed slice k",k0,"fragment z-range",ks.min(),ks.max(),flush=True)
def frame(vol2d): z=ndi.zoom(vol2d,480/512,order=0).T; f=np.zeros((H,W),z.dtype); f[:,OFF:OFF+480]=z; return f
seed=frame(big[:,:,k0].astype(np.uint8))>0
def blood(k):
    im=np.asarray(rgb[k]).astype(np.float32); v=im.max(-1); r,g,b=im[...,0],im[...,1],im[...,2]
    tissue=ndi.binary_fill_holes(np.asarray(cls[k])>0)
    return tissue&(v<85)&(b<r+10)                 # the clotted lumen photographs near-black; exclude the blue gelatin
def solidity(mask):
    from skimage.morphology import convex_hull_image
    h=convex_hull_image(mask); return mask.sum()/max(h.sum(),1)
out=np.zeros((n,H,W),np.uint8)
def walk(k,prev,direction):
    steps=0
    while 0<=k<n:
        out[k][prev]=1; k+=direction; steps+=1
        if not (0<=k<n): break
        cand=blood(k)&ndi.binary_dilation(prev,iterations=4); cl,mm=ndi.label(cand)
        if mm==0: break
        sizes=ndi.sum(np.ones_like(cl),cl,np.arange(1,mm+1)); best=None
        for i in np.argsort(-sizes)[:3]:
            c=cl==i+1; a=c.sum()
            if 250<=a<=900 and solidity(c)>0.8: best=c; break
        if best is None: break
        prev=ndi.binary_fill_holes(best)
    return steps
# refine the seed to the blood component overlapping it
cand=blood(k0)&ndi.binary_dilation(seed,iterations=3); cl,mm=ndi.label(cand)
if mm==0: print("no blood component at seed"); raise SystemExit
sizes=ndi.sum(np.ones_like(cl),cl,np.arange(1,mm+1)); seed=ndi.binary_fill_holes(cl==(np.argmax(sizes)+1)); print("seed area mm2",int(seed.sum()),flush=True)
up=walk(k0,seed,+1); down=walk(k0,seed,-1); print("walked up",up,"down",down,"total length mm",up+down,flush=True)
zs=np.where(out.any(axis=(1,2)))[0]; print("aorta z-range k",zs.min(),zs.max(),"volume cm3",round(float(out.sum())/1000,1))
np.save(S+"vh_cryo/aorta_frame.npy",out)
aff=np.array([[-1,0,0,350],[0,-1,0,240],[0,0,1,-863],[0,0,0,1]],float); nib.save(nib.Nifti1Image(np.ascontiguousarray(out.transpose(2,1,0)),aff),S+"vhm_ts/aorta_cryo.nii.gz")
ts=[]
for k in np.linspace(zs.min()+3,zs.max()-3,6).astype(int):
    im=np.asarray(rgb[k]).copy(); mm_=out[k]>0; ys,xs=np.where(mm_); r0,r1,c0,c1=max(ys.min()-40,0),min(ys.max()+40,H),max(xs.min()-40,0),min(xs.max()+40,W); im=im[r0:r1,c0:c1]; e=mm_[r0:r1,c0:c1]&~ndi.binary_erosion(mm_[r0:r1,c0:c1]); im[e]=(0,255,0); ts.append(im)
h=max(t.shape[0] for t in ts); w=max(t.shape[1] for t in ts); Image.fromarray(np.concatenate([np.pad(t,((0,h-t.shape[0]),(0,w-t.shape[1]),(0,0))) for t in ts],axis=1)).resize((w*len(ts)*2,h*2)).save(S+"vh_cryo/aorta.png"); print("done")
