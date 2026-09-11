"""Named arm muscles from the photograph compartments (first pass, position rules from standard anatomy):
posterior compartment -> triceps brachii (one muscle, three heads).
anterior compartment: pixels within 12 mm of the humerus surface in the distal 60 % of the arm segment ->
brachialis; in the proximal 40 %, pixels medial to the humerus centre and within 15 mm of it ->
coracobrachialis; everything else anterior -> biceps brachii. Boundaries are rule-based, not traced."""
import numpy as np, nibabel as nib, json
from scipy import ndimage as ndi
from PIL import Image
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"
comp=np.load(S+"vh_cryo/arm_compartments_frame.npy",mmap_mode="r"); lab=np.load(S+"vh_cryo/arm_bones_completed_frame.npy",mmap_mode="r"); rgb=np.load(S+"vh_cryo/cryo_torso_frame_rgb.npy",mmap_mode="r")
n,H,W=comp.shape; out=np.zeros((n,H,W),np.uint8)
OUT={"biceps_right":1,"brachialis_right":2,"coracobrachialis_right":3,"triceps_right":4,"biceps_left":5,"brachialis_left":6,"coracobrachialis_left":7,"triceps_left":8}
for side,(cols,ant,post,hum,base,medial_sign) in {"right":(slice(0,300),1,2,1,0,+1),"left":(slice(400,700),5,6,5,4,-1)}.items():
    C=np.asarray(comp)[:,:,cols]; ks=np.where((C==ant).any(axis=(1,2)))[0]; k0,k1=ks.min(),ks.max(); L=k1-k0
    print(side,"arm segment",k0,k1,flush=True)
    for k in ks:
        a=C[k]==ant; p=C[k]==post; h=np.asarray(lab[k])[:,cols]==hum
        if not h.any(): continue
        d=ndi.distance_transform_edt(~h); frac=(k-k0)/L   # 0 = elbow, 1 = top
        ys,xs=np.where(h); cx=xs.mean()
        yy,xx=np.mgrid[0:H,0:cols.stop-cols.start]
        o=out[k][:,cols]; o[p]=base+4
        brach=a&(d<=22)&(frac<0.65); o[brach]=base+2
        cor=a&(frac>=0.6)&(d<=15)&(medial_sign*(xx-cx)>0); o[cor]=base+3   # medial = towards the trunk: +x cols for the right arm (cols 0-300, trunk to the right), -x for the left
        o[a&~brach&~cor]=base+1
vols={k:round(float((out==v).sum())/1000,1) for k,v in OUT.items()}; print("volumes cm3",vols)
np.save(S+"vh_cryo/arm_muscles_frame.npy",out)
aff=np.array([[-1,0,0,350],[0,-1,0,240],[0,0,1,-863],[0,0,0,1]],float); nib.save(nib.Nifti1Image(np.ascontiguousarray(out.transpose(2,1,0)),aff),S+"vhm_ts/arm_muscles_cryo.nii.gz")
lut=np.array([[0,0,0],[255,90,90],[255,200,90],[200,120,255],[90,120,255],[255,90,90],[255,200,90],[200,120,255],[90,120,255]],np.uint8)
for side,cols in (("right",slice(0,300)),("left",slice(400,700))):
    sh=np.load(S+f"vh_cryo/arm_shift_{side}.npy"); ts=[]
    for k in (480,440,400,360,320,280,250):
        im=np.asarray(rgb[k])[:,cols].copy(); im=np.roll(np.roll(im,-int(round(sh[k,0])),0),-int(round(sh[k,1])),1); m=out[k][:,cols]; ys,xs=np.where(m>0)
        if len(ys)==0: continue
        r0,r1,c0,c1=max(ys.min()-15,0),min(ys.max()+15,H),max(xs.min()-15,0),min(xs.max()+15,m.shape[1]); im=im[r0:r1,c0:c1]; mm=m[r0:r1,c0:c1]
        im[mm>0]=(0.5*im[mm>0]+0.5*lut[mm[mm>0]]).astype(np.uint8); ts.append(im)
    h=max(t.shape[0] for t in ts); w=max(t.shape[1] for t in ts)
    Image.fromarray(np.concatenate([np.pad(t,((0,h-t.shape[0]),(0,w-t.shape[1]),(0,0))) for t in ts],axis=1)).save(S+f"vh_cryo/arm_muscles_{side}.png")
print("done")
