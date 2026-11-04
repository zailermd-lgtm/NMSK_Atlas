"""Upper-arm muscle compartments from the photographs (first approximation).
Within each arm's cross-section (tissue connected component containing the humerus), muscle-class pixels
are split by the coronal plane through the humerus centre in the arm's local frame: anterior = flexor
compartment (biceps, brachialis, coracobrachialis), posterior = extensor compartment (triceps).
Forearm likewise about the radius-ulna line: anterior = flexor-pronator group, posterior = extensor group.
The intermuscular septa run roughly in that plane; where they do not, the boundary is off by the septum's
obliquity. This is compartment-level geometry, not individual muscles."""
import numpy as np, nibabel as nib, json
from scipy import ndimage as ndi
from PIL import Image
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"
cls=np.load(S+"vh_cryo/cryo_torso_frame_cls.npy",mmap_mode="r"); rgb=np.load(S+"vh_cryo/cryo_torso_frame_rgb.npy",mmap_mode="r")
lab=np.load(S+"vh_cryo/arm_bones_completed_frame.npy",mmap_mode="r"); n,H,W=lab.shape
OUT={"arm_ant_r":1,"arm_post_r":2,"fore_ant_r":3,"fore_post_r":4,"arm_ant_l":5,"arm_post_l":6,"fore_ant_l":7,"fore_post_l":8}
out=np.zeros((n,H,W),np.uint8); rep={k:0 for k in OUT}
SIDES={"right":(slice(0,300),(1,2,3,4),0),"left":(slice(400,700),(5,6,7,8),4)}
for side,(cols,ids,o) in SIDES.items():
    sh=np.load(S+f"vh_cryo/arm_shift_{side}.npy")
    L3=np.asarray(lab)[:,:,cols]; ktop=int(np.where((L3==ids[0]).any(axis=(1,2)))[0].max()); elbow=ktop-340
    kw=int(np.where(((L3==ids[1])|(L3==ids[2])).any(axis=(1,2)))[0].min())
    print(side,"arm segment k",elbow,"..",ktop-70,"forearm k",kw,"..",elbow,flush=True)
    for k in range(n):
        l=np.asarray(lab[k])[:,cols]
        if not (l>0).any(): continue
        c=np.asarray(cls[k])[:,cols]; c=np.roll(np.roll(c,-int(round(sh[k,0])),0),-int(round(sh[k,1])),1)
        tissue=ndi.binary_fill_holes(c>0); tl,tn=ndi.label(tissue)
        hum=l==ids[0]; fore=(l==ids[1])|(l==ids[2])
        for seg,bone,base in (("arm",hum,0),("fore",fore,2)):
            if bone.sum()<30: continue
            if seg=="arm" and not (elbow<=k<=ktop-70): continue
            if seg=="fore" and not (kw<=k<elbow): continue
            u=np.unique(tl[bone]); comp=np.isin(tl,u[u>0])  # the arm's own cross-section
            # exclude the trunk if the arm touches it: keep the component but drop pixels farther than 90 mm from the bone centroid
            ys,xs=np.where(bone); cy,cx=ys.mean(),xs.mean(); yy,xx=np.mgrid[0:H,0:cols.stop-cols.start]
            comp&=((yy-cy)**2+(xx-cx)**2)<70**2
            # the arm's muscle mass only: erode the muscle class to break the thin skin/fat contact with the trunk,
            # keep the pieces next to the bone, grow back within the muscle class
            mall=comp&(c==3)&(l==0); er=ndi.binary_erosion(mall,iterations=3); el,en=ndi.label(er)
            near=np.unique(el[ndi.binary_dilation(bone,iterations=12)]); near=near[near>0]
            if len(near)==0: continue
            musc=np.isin(el,near); musc=ndi.binary_dilation(musc,iterations=3)&mall
            if seg=="arm": ant=yy<cy   # row index increases posteriorly (row = 240 - y_RAS)
            else:
                # forearm: split by the line through radius and ulna centroids
                r=l==ids[1]; u=l==ids[2]
                if r.sum()<20 or u.sum()<20: ant=yy<cy
                else:
                    ry,rx=np.where(r); uy,ux=np.where(u); p=np.array([ry.mean(),rx.mean()]); q=np.array([uy.mean(),ux.mean()]); d=q-p; nrm=np.array([-d[1],d[0]])
                    if nrm[0]>0: nrm=-nrm   # normal pointing anteriorly (decreasing row)
                    ant=((yy-p[0])*nrm[0]+(xx-p[1])*nrm[1])>0
            sub=out[k][:,cols]; sub[musc&ant]=ids[base]+0; sub[musc&~ant]=ids[base]+1
for name,v in OUT.items(): rep[name]=round(float((out==v).sum())/1000,1)
print("volumes cm3",rep)
np.save(S+"vh_cryo/arm_compartments_frame.npy",out)
aff=np.array([[-1,0,0,350],[0,-1,0,240],[0,0,1,-863],[0,0,0,1]],float); nib.save(nib.Nifti1Image(np.ascontiguousarray(out.transpose(2,1,0)),aff),S+"vhm_ts/arm_compartments_cryo.nii.gz")
lut=np.array([[0,0,0],[255,90,90],[90,120,255],[255,200,90],[120,255,140],[255,90,90],[90,120,255],[255,200,90],[120,255,140]],np.uint8)
for side,(cols,ids,o) in SIDES.items():
    sh=np.load(S+f"vh_cryo/arm_shift_{side}.npy"); ts=[]
    for k in (450,380,300,240,180,120):
        im=np.asarray(rgb[k])[:,cols].copy(); im=np.roll(np.roll(im,-int(round(sh[k,0])),0),-int(round(sh[k,1])),1); m=out[k][:,cols]
        ys,xs=np.where(m>0)
        if len(ys)==0: continue
        r0,r1,c0,c1=max(ys.min()-20,0),min(ys.max()+20,H),max(xs.min()-20,0),min(xs.max()+20,m.shape[1]); im=im[r0:r1,c0:c1]; mm=m[r0:r1,c0:c1]
        im[mm>0]=(0.45*im[mm>0]+0.55*lut[mm[mm>0]]).astype(np.uint8); ts.append(im)
    h=max(t.shape[0] for t in ts); w=max(t.shape[1] for t in ts)
    Image.fromarray(np.concatenate([np.pad(t,((0,h-t.shape[0]),(0,w-t.shape[1]),(0,0))) for t in ts],axis=1)).save(S+f"vh_cryo/compartments_{side}.png")
print("done")
