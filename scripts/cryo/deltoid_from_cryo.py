"""Deltoid from the photographs (rule-based): muscle-class voxels that are (a) within 45 mm of the proximal
humerus (head + upper shaft, from 20 mm above the head to 150 mm below), (b) superficial -- within 28 mm of
the skin surface (the deltoid is the only muscle between skin and proximal humerus laterally), (c) not
already labelled by the hybrid-CT trunk run (pectoralis major, latissimus, serratus, trapezius) or the
arm compartments (biceps, triceps), (d) lateral to the glenoid (x beyond the scapula's lateral edge)."""
import numpy as np, nibabel as nib, json
from scipy import ndimage as ndi
from PIL import Image
from totalsegmentator.map_to_binary import class_map
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"
cls=np.load(S+"vh_cryo/cryo_torso_frame_cls.npy",mmap_mode="r"); rgb=np.load(S+"vh_cryo/cryo_torso_frame_rgb.npy",mmap_mode="r")
lab=np.load(S+"vh_cryo/arm_bones_completed_frame.npy",mmap_mode="r"); arm=np.load(S+"vh_cryo/arm_muscles_frame.npy",mmap_mode="r")
n,H,W=lab.shape; OFF=110
tot=nib.load(S+"vhm_ts/total.nii.gz").dataobj; hyb=nib.load(S+"vhm_hyb/abdominal_muscles.nii.gz").dataobj
inv={v:k for k,v in class_map['total'].items()}; scap={"right":inv["scapula_right"],"left":inv["scapula_left"]}
out=np.zeros((n,H,W),np.uint8); rep={}
for side,(cols,hum,lid,sgn) in {"right":(slice(0,300),1,1,+1),"left":(slice(400,700),5,2,-1)}.items():
    sh=np.load(S+f"vh_cryo/arm_shift_{side}.npy"); L=np.asarray(lab)[:,:,cols]; ks=np.where((L==hum).any(axis=(1,2)))[0]; ktop=ks.max()
    for k in range(max(0,ktop-150),min(n,ktop+21)):
        h=L[k]==hum
        c=np.asarray(cls[k])[:,cols]; c=np.roll(np.roll(c,-int(round(sh[k,0])),0),-int(round(sh[k,1])),1)
        t=np.asarray(tot[:,:,k]); t480=ndi.zoom(t,480/512,order=0).T; full=np.zeros((H,W),np.int32); full[:,OFF:OFF+480]=t480; t_=full[:,cols]
        hb=np.asarray(hyb[:,:,k]); hb480=ndi.zoom(hb,480/512,order=0).T; fullh=np.zeros((H,W),np.uint8); fullh[:,OFF:OFF+480]=hb480; hb_=fullh[:,cols]
        tissue=ndi.binary_fill_holes(c>0); dskin=ndi.distance_transform_edt(tissue)
        ref=h|(t_==scap[side])
        if not h.any() and not (t_==scap[side]).any(): continue
        dhum=ndi.distance_transform_edt(~h) if h.any() else np.full((H,cols.stop-cols.start),999.0)
        sc=t_==scap[side]; xs=np.where(sc)[1]; lat_edge=(xs.min() if sgn>0 else xs.max()) if xs.size else None
        m=(c==3)&(dhum<=55)&(dskin<=40)&(hb_==0)&(np.asarray(arm[k])[:,cols]==0)&(t_==0)
        if lat_edge is not None:
            xx=np.arange(cols.stop-cols.start)[None,:]; m&=(xx<=lat_edge+8) if sgn>0 else (xx>=lat_edge-8)   # lateral to the scapula's lateral edge
        m=ndi.binary_opening(m,iterations=1)
        if m.any():
            cl,mm=ndi.label(m); sizes=ndi.sum(np.ones_like(cl),cl,np.arange(1,mm+1)); m=cl==(np.argmax(sizes)+1)   # one muscle: largest piece
        out[k][:,cols][m]=lid
    rep[side]=round(float((out==lid).sum())/1000,1)
print("deltoid volumes cm3",rep)
np.save(S+"vh_cryo/deltoid_frame.npy",out)
aff=np.array([[-1,0,0,350],[0,-1,0,240],[0,0,1,-863],[0,0,0,1]],float); nib.save(nib.Nifti1Image(np.ascontiguousarray(out.transpose(2,1,0)),aff),S+"vhm_ts/deltoid_cryo.nii.gz")
for side,cols in (("right",slice(0,300)),("left",slice(400,700))):
    sh=np.load(S+f"vh_cryo/arm_shift_{side}.npy"); ts=[]; ks=np.where((out[:,:,cols]>0).any(axis=(1,2)))[0]
    for k in np.linspace(ks.min(),ks.max(),7).astype(int):
        im=np.asarray(rgb[k])[:,cols].copy(); im=np.roll(np.roll(im,-int(round(sh[k,0])),0),-int(round(sh[k,1])),1); m=out[k][:,cols]; ys,xs=np.where(m>0)
        if len(ys)==0: continue
        r0,r1,c0,c1=max(ys.min()-25,0),min(ys.max()+25,H),max(xs.min()-25,0),min(xs.max()+25,m.shape[1]); im=im[r0:r1,c0:c1]; mm=m[r0:r1,c0:c1]
        im[mm>0]=(0.5*im[mm>0]+np.array([120,40,127])).astype(np.uint8); ts.append(im)
    h=max(t.shape[0] for t in ts); w=max(t.shape[1] for t in ts)
    Image.fromarray(np.concatenate([np.pad(t,((0,h-t.shape[0]),(0,w-t.shape[1]),(0,0))) for t in ts],axis=1)).save(S+f"vh_cryo/deltoid_{side}.png")
print("done")
