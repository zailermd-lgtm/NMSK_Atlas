"""Rotator cuff from the photographs (rule-based): muscle-class voxels within 25 mm of the scapula and not
already labelled (deltoid, pec, lat, serratus, trapezius, arm), assigned by which scapular surface is nearest:
ventral (anterior of the nearest scapula voxel) -> subscapularis; dorsal -> supraspinatus if above the
scapular spine level (top 22 % of the scapula's height) else infraspinatus (teres minor merged into it).
Voxels within 25 mm of the humeral head are kept (the cuff tendons), those further than 25 mm from the
scapula are not. Boundaries are rules, not traced fascia."""
import numpy as np, nibabel as nib, json
from scipy import ndimage as ndi
from PIL import Image
from totalsegmentator.map_to_binary import class_map
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"
cls=np.load(S+"vh_cryo/cryo_torso_frame_cls.npy",mmap_mode="r"); rgb=np.load(S+"vh_cryo/cryo_torso_frame_rgb.npy",mmap_mode="r")
arm=np.load(S+"vh_cryo/arm_muscles_frame.npy",mmap_mode="r"); delt=np.load(S+"vh_cryo/deltoid_frame.npy",mmap_mode="r")
n,H,W=arm.shape; OFF=110
tot=np.asarray(nib.load(S+"vhm_ts/total.nii.gz").dataobj); hyb=np.asarray(nib.load(S+"vhm_hyb/abdominal_muscles.nii.gz").dataobj)
inv={v:k for k,v in class_map['total'].items()}; rib_ids=[k for k,v in class_map['total'].items() if v.startswith('rib_') or v=='costal_cartilages']
def frame(vol,k,order=0):
    z=ndi.zoom(vol[:,:,k],480/512,order=order).T; f=np.zeros((H,W),z.dtype); f[:,OFF:OFF+480]=z; return f
out=np.zeros((n,H,W),np.uint8); rep={}
LAB={"right":(1,2,3),"left":(4,5,6)}   # supraspinatus, infraspinatus, subscapularis
for side,(cols,ids) in {"right":(slice(0,360),LAB["right"]),"left":(slice(340,700),LAB["left"])}.items():
    sc=inv[f"scapula_{side}"]; zs=np.where((tot==sc).any(axis=(0,1)))[0]; z0,z1=zs.min(),zs.max(); zspine=z0+0.78*(z1-z0)
    # local shift from the arm registration (nearest available); scapula region is close to the arm so it is reused
    sh=np.load(S+f"vh_cryo/arm_shift_{side}.npy")
    for k in range(z0,z1+1):
        t=frame(tot,k)[:,cols]; scap=t==sc
        if not scap.any(): continue
        c=np.asarray(cls[k])[:,cols]; c=np.roll(np.roll(c,-int(round(sh[k,0])),0),-int(round(sh[k,1])),1)
        hb=frame(hyb,k)[:,cols]; a=np.asarray(arm[k])[:,cols]; d=np.asarray(delt[k])[:,cols]
        dist,ind=ndi.distance_transform_edt(~scap,return_indices=True)
        m=(c==3)&(dist<=25)&(hb==0)&(a==0)&(d==0)&(t==0)
        ribs=np.isin(t,rib_ids)
        if ribs.any(): m&=ndi.distance_transform_edt(~ribs)>8     # serratus / intercostals hug the ribs; the cuff does not
        xs_=np.where(scap)[1]; lat=xs_.min() if side=="right" else xs_.max()
        xx=np.arange(cols.stop-cols.start)[None,:]*np.ones((H,1),int); fossa=(xx>=lat+15) if side=="right" else (xx<=lat-15)   # medial to the glenoid
        if not m.any(): continue
        yy=np.arange(H)[:,None]*np.ones((1,cols.stop-cols.start),int); ny=ind[0]   # row of the nearest scapula voxel
        ventral=yy<ny    # smaller row = more anterior
        o=out[k][:,cols]
        o[m&ventral]=ids[2]
        dors=m&~ventral; o[dors&(k>=zspine)&fossa]=ids[0]; o[dors&((k<zspine)|~fossa)]=ids[1]
    for i,name in enumerate(("supraspinatus","infraspinatus","subscapularis")): rep[f"{name}_{side}"]=round(float((out==ids[i]).sum())/1000,1)
print("volumes cm3",rep)
np.save(S+"vh_cryo/cuff_frame.npy",out)
aff=np.array([[-1,0,0,350],[0,-1,0,240],[0,0,1,-863],[0,0,0,1]],float); nib.save(nib.Nifti1Image(np.ascontiguousarray(out.transpose(2,1,0)),aff),S+"vhm_ts/rotator_cuff_cryo.nii.gz")
lut=np.zeros((7,3),np.uint8); lut[1]=lut[4]=(255,120,60); lut[2]=lut[5]=(80,200,255); lut[3]=lut[6]=(200,120,255)
for side,cols in (("right",slice(0,360)),("left",slice(340,700))):
    sh=np.load(S+f"vh_cryo/arm_shift_{side}.npy"); ks=np.where((out[:,:,cols]>0).any(axis=(1,2)))[0]; ts=[]
    for k in np.linspace(ks.min(),ks.max(),6).astype(int):
        im=np.asarray(rgb[k])[:,cols].copy(); im=np.roll(np.roll(im,-int(round(sh[k,0])),0),-int(round(sh[k,1])),1); m=out[k][:,cols]; ys,xs=np.where(m>0)
        if len(ys)==0: continue
        r0,r1,c0,c1=max(ys.min()-25,0),min(ys.max()+25,H),max(xs.min()-25,0),min(xs.max()+25,m.shape[1]); im=im[r0:r1,c0:c1]; mm=m[r0:r1,c0:c1]
        im[mm>0]=(0.5*im[mm>0]+0.5*lut[mm[mm>0]]).astype(np.uint8); ts.append(im)
    h=max(t.shape[0] for t in ts); w=max(t.shape[1] for t in ts)
    Image.fromarray(np.concatenate([np.pad(t,((0,h-t.shape[0]),(0,w-t.shape[1]),(0,0))) for t in ts],axis=1)).save(S+f"vh_cryo/cuff_{side}.png")
print("done")
