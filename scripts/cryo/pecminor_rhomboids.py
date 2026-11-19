"""Pectoralis minor and the rhomboids from the photographs (rule-based).
pectoralis minor: unlabelled muscle deep to the pectoralis major label (hybrid CT), anterior to ribs 2-6,
20-130 mm lateral of the midline, from the clavicle level down to rib 6, not touching the skin.
rhomboids: unlabelled muscle between the scapula's medial border and the midline (20-95 mm lateral),
posterior to the ribs, from C7 to T6, deep to the trapezius label (neck run); major and minor are not
separated (one mass, shown under rhomboid_major with a note)."""
import numpy as np, nibabel as nib, json
from scipy import ndimage as ndi
from PIL import Image
from totalsegmentator.map_to_binary import class_map
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"
cls=np.load(S+"vh_cryo/cryo_torso_frame_cls.npy",mmap_mode="r"); rgb=np.load(S+"vh_cryo/cryo_torso_frame_rgb.npy",mmap_mode="r"); n,H,W=cls.shape; OFF=110
tot=np.asarray(nib.load(S+"vhm_ts/total.nii.gz").dataobj); hyb=np.asarray(nib.load(S+"vhm_hyb/abdominal_muscles.nii.gz").dataobj); neck=np.asarray(nib.load(S+"vhm_ts/headneck_muscles_merged.nii.gz").dataobj)
cuff=np.load(S+"vh_cryo/cuff_frame.npy",mmap_mode="r"); delt=np.load(S+"vh_cryo/deltoid_frame.npy",mmap_mode="r"); arm=np.load(S+"vh_cryo/arm_muscles_frame.npy",mmap_mode="r"); es=np.asarray(nib.load(S+"vhm_ts/erector_columns.nii.gz").dataobj)
inv={v:k for k,v in class_map['total'].items()}; ha={v:k for k,v in class_map['abdominal_muscles'].items()}; hn={v:k for k,v in class_map['headneck_muscles'].items()}
vert=[k for k,v in class_map['total'].items() if v.startswith('vertebrae_')]; ribs=[k for k,v in class_map['total'].items() if v.startswith('rib_')]
def frame(vol,k): z=ndi.zoom(vol[:,:,k],480/512,order=0).T; f=np.zeros((H,W),z.dtype); f[:,OFF:OFF+480]=z; return f
def zr(vol,ids): z=np.where(np.isin(vol,ids).any(axis=(0,1)))[0]; return int(z.min()),int(z.max())
zC7=zr(tot,[inv['vertebrae_C7']]); zT6=zr(tot,[inv['vertebrae_T6']]); zclav=zr(tot,[inv['clavicula_right'],inv['clavicula_left']]); zrib6=zr(tot,[inv['rib_right_6'],inv['rib_left_6']])
out=np.zeros((n,H,W),np.uint8); OUT={"pecminor_right":1,"pecminor_left":2,"rhomboid_right":3,"rhomboid_left":4}
for k in range(zrib6[0],zclav[1]+1):
    t=frame(tot,k); hb=frame(hyb,k); nk=frame(neck,k); e=frame(es,k); c=np.asarray(cls[k])
    vb=np.isin(t,vert)
    if not vb.any(): continue
    ys,xs=np.where(vb); mid=xs.mean(); vrow=ys.mean()
    tissue=ndi.binary_fill_holes(c>0); dskin=ndi.distance_transform_edt(tissue); yy,xx=np.mgrid[0:H,0:W]
    labelled=(t>0)|(hb>0)|(nk>0)|(e>0)|(np.asarray(cuff[k])>0)|(np.asarray(delt[k])>0)|(np.asarray(arm[k])>0)
    free=(c==3)&~labelled&(dskin>6)
    # pectoralis minor: deep to pec major, anterior to the ribs
    for side,sgn,lid in (("right",-1,1),("left",1,2)):   # frame col increases towards the patient's LEFT (x = 350 - col)
        pm=hb==ha[f"pectoralis_major_{side}"]
        if not pm.any(): continue
        deep=ndi.binary_dilation(pm,iterations=10)&~pm&(yy>np.where(pm)[0].mean())   # a thin sheet directly behind the pec major (<=10 mm)
        rb=np.isin(t,ribs); ant=(yy<vrow-40)
        lat=(sgn*(xx-mid)>20)&(sgn*(xx-mid)<130)
        m=free&deep&ant&lat&~ndi.binary_dilation(rb,iterations=8)   # anything hugging the ribs is intercostal / serratus, not pec minor
        if m.any():
            cl,mm=ndi.label(m); sizes=ndi.sum(np.ones_like(cl),cl,np.arange(1,mm+1)); m=cl==(np.argmax(sizes)+1)
            if sizes.max()>=40: out[k][m]=lid
    # rhomboids: between scapula medial border and midline, deep to trapezius, posterior
    if zT6[0]<=k<=zC7[1]:
        for side,sgn,lid in (("right",-1,3),("left",1,4)):
            sc=t==inv[f"scapula_{side}"]; tr=nk==hn[f"trapezius_{side}"]
            if not sc.any() or not tr.any(): continue
            xs_=np.where(sc)[1]; medial=xs_.min() if side=="left" else xs_.max()   # medial border (towards mid): left scapula at larger cols
            band=(sgn*(xx-mid)>20)&(sgn*(xx-mid)<95)&(yy>vrow) if False else None
            band=((xx<medial+5) if side=="left" else (xx>medial-5))&(sgn*(xx-mid)>15)&(yy>vrow)
            deep=ndi.binary_dilation(tr,iterations=25)&~tr&(yy<np.where(tr)[0].max())
            m=free&band&deep&~ndi.binary_dilation(np.isin(t,ribs),iterations=3)
            if m.any():
                cl,mm=ndi.label(m); sizes=ndi.sum(np.ones_like(cl),cl,np.arange(1,mm+1)); m=cl==(np.argmax(sizes)+1)
                if sizes.max()>=40: out[k][m]=lid
rep={kk:round(float((out==v).sum())/1000,1) for kk,v in OUT.items()}; print("volumes cm3",rep)
np.save(S+"vh_cryo/pecminor_rhomboids_frame.npy",out)
aff=np.array([[-1,0,0,350],[0,-1,0,240],[0,0,1,-863],[0,0,0,1]],float); nib.save(nib.Nifti1Image(np.ascontiguousarray(out.transpose(2,1,0)),aff),S+"vhm_ts/pecminor_rhomboids_cryo.nii.gz")
lut=np.zeros((5,3),np.uint8); lut[1]=lut[2]=(255,120,60); lut[3]=lut[4]=(80,200,255)
ks=np.where((out>0).any(axis=(1,2)))[0]; ts=[]
for k in np.linspace(ks.min()+3,ks.max()-3,5).astype(int):
    im=np.asarray(rgb[k]).copy(); m=out[k]; im[m>0]=(0.5*im[m>0]+0.5*lut[m[m>0]]).astype(np.uint8); ts.append(im[:,60:640])
Image.fromarray(np.concatenate(ts,axis=1)).save(S+"vh_cryo/pecminor_rhomboids.png"); print("done")
