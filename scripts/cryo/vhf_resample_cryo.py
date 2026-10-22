"""Resample the female 1 mm cryosection RGB + class volumes into her CT frame: the whole-body grid of
vhf_ts/skin_ct.nii.gz (0.9375 mm torso grid extended over both CT blocks; here at 1 mm pixels: 480 rows = RAS y
240-row, 480 CT cols = RAS x 240-col) widened to 700 columns (frame col = CT col + 110) so the arms, which lie
outside the CT field of view, are kept. The mapping comes from vh_cryo_f/anchors.json (vhf_register_cryo.py):
cryo index = -(offset(z)) - z_RAS with offset(z) a LINE fitted through the anchors with muscle-pattern NCC >= 0.55
(both stacks are contiguous, so the offset can only drift by a scale; the thorax anchors scatter by 30 mm and are
left out), and the in-plane shift (rows, cols) interpolated between anchors after a median filter; rows flipped;
cryo pixel 0.99 mm. The frozen block and the fresh CT differ in pose by up to ~15 mm across the
body (row shift -6 at the legs, -13 in the thorax, +14 at the head), which is why the mapping is not one rigid fit.
Output: vh_cryo_f/cryo_frame_rgb.npy (n,480,700,3), cryo_frame_cls.npy (n,480,700), frame.json."""
import numpy as np, json, nibabel as nib
from scipy import ndimage as ndi
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"; D=S+"vh_cryo_f/"
vol=np.load(D+"cryo_1mm.npy",mmap_mode="r"); cls=np.load(D+"cryo_1mm_classes.npy",mmap_mode="r"); Z,H,W=cls.shape
skin=nib.load(S+"vhf_ts/skin_ct.nii.gz"); z0=float(skin.affine[2,3]); n=skin.shape[2]
A=json.load(open(D+"anchors.json")); A=[a for a in A if a["flip"]=="fy" and a["iou"]>=0.7]
zs=np.array([a["ct_z"] for a in A]); r_sh=np.array([a["shift"][0] for a in A],float); c_sh=np.array([a["shift"][1] for a in A],float)
# z: the photographs are one contiguous 1 mm stack and so is the CT, so the offset can only drift slowly (a scale):
# a LINE through the anchors whose muscle-pattern NCC is >= 0.55 (the thorax anchors, NCC 0.26-0.45, scatter by 30 mm and are left out)
good=[a for a in A if a.get("ncc",0)>=0.55]; gz=np.array([a["ct_z"] for a in good]); go=np.array([a["cryo_z_refined"]+a["ct_z"] for a in good],float)
b,a0=np.polyfit(gz,go,1); resid=go-(a0+b*gz); print("z offset line: offset = %.2f + %.5f*z ; %d anchors, residual rms %.1f mm, max %.1f"%(a0,b,len(good),np.sqrt((resid**2).mean()),abs(resid).max()),flush=True)
r_sh=ndi.median_filter(r_sh,size=5,mode="nearest"); c_sh=ndi.median_filter(c_sh,size=5,mode="nearest")
o=np.argsort(zs); zs,r_sh,c_sh=zs[o],r_sh[o],c_sh[o]
zk=z0+np.arange(n); OFF=a0+b*zk; RS=np.interp(zk,zs,r_sh); CS=np.interp(zk,zs,c_sh)
json.dump({"z0":z0,"n":n,"cols":700,"col_offset":110,"scale":0.99,"anchors_used":len(A),"z_offset_line":[float(a0),float(b)],"z_line_residual_rms_mm":float(np.sqrt((resid**2).mean())),"row_shift_by_z":{str(int(z)):float(v) for z,v in zip(zs,r_sh)},"col_shift_by_z":{str(int(z)):float(v) for z,v in zip(zs,c_sh)}},open(D+"frame.json","w"),indent=1)
rgb=np.lib.format.open_memmap(D+"cryo_frame_rgb.npy",mode="w+",dtype=np.uint8,shape=(n,480,700,3))
cl=np.lib.format.open_memmap(D+"cryo_frame_cls.npy",mode="w+",dtype=np.uint8,shape=(n,480,700))
sc=0.99; rr,cc=np.mgrid[0:480,0:700]
for k in range(n):
    zi=int(round(-OFF[k]-zk[k]))
    if zi<0 or zi>=Z: continue
    src_r=(H-1)-(rr-RS[k])/sc; src_c=(cc-110-CS[k])/sc
    s=np.asarray(vol[zi]); c=np.asarray(cls[zi])
    for ch in range(3): rgb[k,:,:,ch]=ndi.map_coordinates(s[...,ch],[src_r,src_c],order=1,mode="constant",cval=0)
    cl[k]=ndi.map_coordinates(c,[src_r,src_c],order=0,mode="constant",cval=0)
    if k%300==0: print(k,"z",zk[k],"cryo",zi,"shift",round(RS[k],1),round(CS[k],1),flush=True)
rgb.flush(); cl.flush(); print("RESAMPLE_DONE",flush=True)
