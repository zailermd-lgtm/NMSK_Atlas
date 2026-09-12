"""Female pectoralis minor and rhomboids by the male's rules (pecminor_rhomboids.py v2) on her registered cryosection
photographs with her MODEL labels as anchors: pectoralis minor = unlabelled muscle in a sheet <= 10 mm deep to her
pectoralis major label, anterior to the vertebral level, 20-130 mm lateral of the midline, clavicle to rib 6, >= 8 mm
from the ribs, not touching the skin; rhomboids = unlabelled muscle between the scapula's medial border and the
midline, posterior, deep to her trapezius label (neck run), C7-T6 (major + minor as one mass under rhomboid_major).
Rule-based: badge it, record the volumes. Output vhf_ts/pecminor_rhomboids_cryo.nii.gz (torso RAS), report, render."""
import numpy as np, nibabel as nib, json
from scipy import ndimage as ndi
from PIL import Image
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"; D=S+"vh_cryo_f/"; R="/home/user/NMSK_Atlas/"; T=R+"data/ct_sources/task_outputs/"
cls=np.load(D+"cryo_frame_cls.npy",mmap_mode="r"); rgb=np.load(D+"cryo_frame_rgb.npy",mmap_mode="r"); z0=json.load(open(D+"frame.json"))["z0"]; n,H,W=cls.shape; OFF=110
def load(name): im=nib.load(T+name); return np.asarray(im.dataobj),float(im.affine[2,3])
tot,zT0=load("vhf_total.nii.gz"); hyb,zA0=load("vhf_abdominal_muscles.nii.gz"); neck,zN0=load("vhf_headneck_muscles_merged.nii.gz"); es,zE0=load("vhf_erector_columns.nii.gz")
delt,zD0=load("vhf_deltoid_cryo.nii.gz"); cuff,zC0=load("vhf_rotator_cuff_cryo.nii.gz")   # frame voxels (col,row,k)
L=lambda f:{v:int(k) for k,v in json.load(open(R+"mappings/"+f))["labels"].items()}
labs=L("totalsegmentator_labels.json"); ha=L("totalsegmentator_abdominal_muscles_labels.json"); hn=L("totalsegmentator_headneck_muscles_labels.json")
vert=[v for k,v in labs.items() if k.startswith("vertebrae_")]; ribs=[v for k,v in labs.items() if k.startswith("rib_")]
def frame_ct(arr,zoff,k):
    kk=int(round(z0+k-zoff)); f=np.zeros((H,W),np.int32)
    if 0<=kk<arr.shape[2]: f[:,OFF:OFF+480]=ndi.zoom(arr[:,:,kk],480/512,order=0).T
    return f
def frame_fr(arr,zoff,k):
    kk=int(round(z0+k-zoff)); return arr[:,:,kk].T.astype(np.int32) if 0<=kk<arr.shape[2] else np.zeros((H,W),np.int32)
def kr(ids):   # frame k range of CT labels
    z=np.where(np.isin(tot,ids).any(axis=(0,1)))[0]; return int(round(zT0+z.min()-z0)),int(round(zT0+z.max()-z0))
kC7=kr([labs["vertebrae_C7"]]); kT6=kr([labs["vertebrae_T6"]]); kclav=kr([labs["clavicula_right"],labs["clavicula_left"]]); krib6=kr([labs["rib_right_6"],labs["rib_left_6"]])
out=np.zeros((n,H,W),np.uint8); OUT={"pecminor_right":1,"pecminor_left":2,"rhomboid_right":3,"rhomboid_left":4}
for k in range(krib6[0],kclav[1]+1):
    t=frame_ct(tot,zT0,k); hb=frame_ct(hyb,zA0,k); nk=frame_ct(neck,zN0,k); e=frame_ct(es,zE0,k); c=np.asarray(cls[k])
    vb=np.isin(t,vert)
    if not vb.any(): continue
    ys,xs=np.where(vb); mid=xs.mean(); vrow=ys.mean()
    tissue=ndi.binary_fill_holes(ndi.binary_closing(c>0,iterations=3)); dskin=ndi.distance_transform_edt(tissue); yy,xx=np.mgrid[0:H,0:W]
    labelled=(t>0)|(hb>0)|(nk>0)|(e>0)|(frame_fr(cuff,zC0,k)>0)|(frame_fr(delt,zD0,k)>0)
    free=(c==3)&~labelled&(dskin>6)
    for side,sgn,lid in (("right",-1,1),("left",1,2)):
        pm=hb==ha[f"pectoralis_major_{side}"]
        if not pm.any(): continue
        deep=ndi.binary_dilation(pm,iterations=10)&~pm&(yy>np.where(pm)[0].mean())
        rb=np.isin(t,ribs); ant=(yy<vrow-40); lat=(sgn*(xx-mid)>20)&(sgn*(xx-mid)<130)
        m=free&deep&ant&lat&~ndi.binary_dilation(rb,iterations=8)
        if m.any():
            cl,mm=ndi.label(m); sizes=ndi.sum(np.ones_like(cl),cl,np.arange(1,mm+1)); m=cl==(np.argmax(sizes)+1)
            if sizes.max()>=40: out[k][m]=lid
    if kT6[0]<=k<=kC7[1]:
        for side,sgn,lid in (("right",-1,3),("left",1,4)):
            sc=t==labs[f"scapula_{side}"]; tr=nk==hn[f"trapezius_{side}"]
            if not sc.any() or not tr.any(): continue
            xs_=np.where(sc)[1]; medial=xs_.min() if side=="left" else xs_.max()
            band=((xx<medial+5) if side=="left" else (xx>medial-5))&(sgn*(xx-mid)>15)&(yy>vrow)
            deep=ndi.binary_dilation(tr,iterations=25)&~tr&(yy<np.where(tr)[0].max())
            m=free&band&deep&~ndi.binary_dilation(np.isin(t,ribs),iterations=3)
            if m.any():
                cl,mm=ndi.label(m); sizes=ndi.sum(np.ones_like(cl),cl,np.arange(1,mm+1)); m=cl==(np.argmax(sizes)+1)
                if sizes.max()>=40: out[k][m]=lid
rep={kk:round(float((out==v).sum())/1000,1) for kk,v in OUT.items()}; print("volumes cm3",rep,flush=True)
nz=np.where(out.any(axis=(1,2)))[0]; ka,kb=nz.min(),nz.max()+1
aff=np.array([[-1,0,0,350],[0,-1,0,240],[0,0,1,z0+ka],[0,0,0,1]],float); nib.save(nib.Nifti1Image(np.ascontiguousarray(out[ka:kb].transpose(2,1,0)),aff),S+"vhf_ts/pecminor_rhomboids_cryo.nii.gz")
json.dump({"_README":["Female pectoralis minor and rhomboids by the male's position rules on her registered cryosections (scripts/cryo/vhf_pecminor_rhomboids.py). Rule-based, derived data."],"source":"U.S. National Library of Medicine, The Visible Human Project (public domain), female cryosections and CT via the NCI Imaging Data Commons; TotalSegmentator v2.18.0 labels as anchors.","volumes_cm3":rep},open(D+"pmr_report.json","w"),indent=1)
lut=np.zeros((5,3),np.uint8); lut[1]=lut[2]=(255,120,60); lut[3]=lut[4]=(80,200,255); ts=[]
for k in np.linspace(ka+3,kb-4,5).astype(int):
    im=np.asarray(rgb[k]).copy(); m=out[k]; im[m>0]=(0.5*im[m>0]+0.5*lut[m[m>0]]).astype(np.uint8); ts.append(im[:,60:640])
Image.fromarray(np.concatenate(ts,axis=1)).save(D+"pmr.png"); print("PMR_DONE")
