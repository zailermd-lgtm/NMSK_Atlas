"""Check the HEIGHT of the female cryosection frame against her CT, level by level.

    python3 scripts/cryo/vhf_check_frame_z.py [--frame DIR] [--out data/derived/vhf_cryo_frame_z_survey.json] [--step 30]

The frame (vh_cryo_f/cryo_frame_cls.npy, vhf_resample_cryo.py) is in-plane registered to her CT, so a CT slice
and the photograph that shows the same anatomy agree pixel for pixel in where the fat and the muscle are. For CT
slices every --step mm, the photograph slice with the best Dice (0.4 fat HU -190..-30 vs class 2, 0.4 muscle HU
20..150 vs class 3, 0.2 body silhouette) is searched from 40 mm above to 160 mm below the expected slice; the
offset is best - expected (parabolic refinement), with the score and its drop 30 mm away (sharpness). Found
2026-09-13: the frame v1 was ~72 mm high over the whole body below the neck (its z line had been fitted with
the thorax anchors left out). Applied by vhf_correct_frame_z.py. Nothing here is anatomy."""
import json, numpy as np, nibabel as nib, argparse
from scipy import ndimage as ndi
ap=argparse.ArgumentParser(); ap.add_argument("--frame", default="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/vh_cryo_f")
ap.add_argument("--ct-dir", default="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/vh_idc/nii")
ap.add_argument("--out", default="data/derived/vhf_cryo_frame_z_survey.json"); ap.add_argument("--step", type=float, default=30.0)
ap.add_argument("--cls", default="cryo_frame_cls.npy"); ap.add_argument("--search", type=int, nargs=2, default=[-40, 160])
a=ap.parse_args(); D=a.frame
cls=np.load(f'{D}/{a.cls}', mmap_mode='r'); fr=json.load(open(f'{D}/frame.json')); z0=fr['z0']
H,W=cls.shape[1],cls.shape[2]

rows,cols=np.mgrid[0:H,0:W]; RASx=350.0-cols; RASy=240.0-rows
def ct_masks(vol,A,k,shift_xy):
    sl=vol[:,:,k].astype(np.float32)
    i=(A[0,3]-(RASx-shift_xy[0]))/(-A[0,0]); j=(A[1,3]-(RASy-shift_xy[1]))/(-A[1,1])
    hu=ndi.map_coordinates(sl,[i.ravel(),j.ravel()],order=1,cval=-1000).reshape(H,W)
    body=ndi.binary_fill_holes(hu>-500)
    return (hu>-190)&(hu<-30)&body, (hu>20)&(hu<150)&body, body
def dice(a,b):
    s=a.sum()+b.sum(); return 2*(a&b).sum()/s if s else 0
rows_out=[]
for name,path,zshift,xy in (('torso',f'{a.ct_dir}/vhf_torso_0937.nii.gz',0.0,(0,0)),('legs',f'{a.ct_dir}/vhf_legs_0723.nii.gz',-943.5,(5.99,-3.59))):
    im=nib.load(path); A=im.affine; vol=np.asanyarray(im.dataobj)
    zs=A[2,3]+np.arange(vol.shape[2])*A[2,2]+zshift
    levels=np.arange(-60,-1000,-a.step) if name=='torso' else np.arange(-1030,-1760,-a.step)
    for z in levels:
        if z<zs.min()+2 or z>zs.max()-2: continue
        kc=int(np.argmin(np.abs(zs-z))); fat,mus,body=ct_masks(vol,A,kc,xy)
        kexp=int(round(z-z0)); sc=[]
        for k in range(max(0,kexp+a.search[0]), min(cls.shape[0],kexp+a.search[1]+1), 2):
            c=np.asarray(cls[k]); sc.append((0.4*dice(fat,c==2)+0.4*dice(mus,c==3)+0.2*dice(body,c>0), k))
        s=np.array([x[0] for x in sc]); ks=np.array([x[1] for x in sc])
        # parabolic refinement around the max
        i=int(np.argmax(s)); best=ks[i]
        if 0<i<len(s)-1:
            d=(s[i-1]-s[i+1])/(2*(s[i-1]-2*s[i]+s[i+1])) if (s[i-1]-2*s[i]+s[i+1])!=0 else 0; best=ks[i]+2*d
        y=z+885.229; off=best-kexp
        # sharpness: score drop 30 mm away
        j=int(np.argmin(np.abs(ks-(best+30)))); sharp=s[i]-s[j]
        rows_out.append({"y": round(float(y),1), "block": name, "offset_mm": round(float(off),1), "score": round(float(s[i]),3), "sharpness": round(float(sharp),3)})
        print(f"{name} y {y:7.1f} offset {off:+6.1f} score {s[i]:.3f} sharp {sharp:.3f}", flush=True)
json.dump({'_README': 'Height survey of the female cryosection frame against her CT (scripts/cryo/vhf_check_frame_z.py); offset_mm > 0: the matching photograph lies that many mm below the expected slice.', 'source': 'U.S. National Library of Medicine, The Visible Human Project (public domain), female CT and cryosections via the NCI Imaging Data Commons. Derived data.', 'frame': a.frame, 'cls': a.cls, 'rows': rows_out}, open(a.out,'w'), indent=0)
