"""Anterolateral abdominal wall from the photographs (rule-based). Muscle-class voxels within 60 mm of the
skin, between the xiphoid level and the bottom of the torso block, not labelled by the CT/hybrid runs
(erector, psoas, pec, lat, serratus, ribs), anterior to the vertebral-body centre.
rectus abdominis: |x - midline| <= 80 mm and within 60 mm behind the anterior midline skin point.
lateral wall: the rest with |x - midline| > 55 mm, split by depth fraction from the outer surface:
external oblique (outer 40 %), internal oblique (middle 35 %), transversus abdominis (inner 25 %)."""
import numpy as np, nibabel as nib, json
from scipy import ndimage as ndi
from PIL import Image
from totalsegmentator.map_to_binary import class_map
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"
cls=np.load(S+"vh_cryo/cryo_torso_frame_cls.npy",mmap_mode="r"); rgb=np.load(S+"vh_cryo/cryo_torso_frame_rgb.npy",mmap_mode="r")
n,H,W=cls.shape; OFF=110
tot=np.asarray(nib.load(S+"vhm_ts/total.nii.gz").dataobj); hyb=np.asarray(nib.load(S+"vhm_hyb/abdominal_muscles.nii.gz").dataobj)
inv={v:k for k,v in class_map['total'].items()}; vert=[k for k,v in class_map['total'].items() if v.startswith('vertebrae_')]
armb=np.load(S+"vh_cryo/arm_bones_completed_frame.npy",mmap_mode="r"); armm=np.load(S+"vh_cryo/arm_muscles_frame.npy",mmap_mode="r")
ribs=[k for k,v in class_map['total'].items() if v.startswith('rib_') or v=='costal_cartilages']
ztop=int(np.where((tot==inv['sternum']).any(axis=(0,1)))[0].min())   # xiphoid level
def frame(vol,k):
    z=ndi.zoom(vol[:,:,k],480/512,order=0).T; f=np.zeros((H,W),z.dtype); f[:,OFF:OFF+480]=z; return f
OUT={"rectus_right":1,"external_right":2,"internal_right":3,"transversus_right":4,"rectus_left":5,"external_left":6,"internal_left":7,"transversus_left":8}
out=np.zeros((n,H,W),np.uint8)
for k in range(0,ztop):
    t=frame(tot,k); hb=frame(hyb,k); c=np.asarray(cls[k]); c=np.roll(np.roll(c,0,0),0,1)
    vb=np.isin(t,vert)
    if not vb.any(): continue
    ys,xs=np.where(vb); mid=xs.mean(); vrow=ys.mean()
    tissue=ndi.binary_fill_holes(c>0); dskin=ndi.distance_transform_edt(tissue)
    yy,xx=np.mgrid[0:H,0:W]
    excl=ndi.binary_dilation(t>0,iterations=8)|(hb>0)|ndi.binary_dilation(np.isin(t,ribs),iterations=6)   # organs (bowel photographs like muscle), bones, labelled muscles
    arms=ndi.binary_dilation((np.asarray(armb[k])>0)|(np.asarray(armm[k])>0),iterations=40); excl|=arms   # the arms lie against the flanks
    excl[:, :OFF+15]=True; excl[:, OFF+465:]=True                                                         # outside the CT field of view
    trunk=ndi.label(tissue)[0]; trunk=trunk==trunk[int(vrow),int(mid)]                                    # the tissue component holding the spine
    wall=(c==3)&(dskin<=60)&~excl&(yy<vrow)&trunk     # anterior to the vertebral body centre (row increases posteriorly)
    col=tissue[:,int(mid)]; A=np.where(col)[0].min() if col.any() else 0   # anterior midline skin row
    rect=wall&(np.abs(xx-mid)<=70)&(yy<=A+70)
    lat=wall&~rect&(np.abs(xx-mid)>55)
    o=out[k]
    o[rect&(xx>=mid)]=1; o[rect&(xx<mid)]=5
    if lat.any():
        cl,m=ndi.label(lat); sizes=ndi.sum(np.ones_like(cl),cl,np.arange(1,m+1)); lat=np.isin(cl,[i+1 for i,v in enumerate(sizes) if v>=200])
        if lat.any():
            d_out=ndi.distance_transform_edt(lat|~tissue)  # distance from the outer boundary approximated by skin side
            d_o=ndi.distance_transform_edt(~(~lat&(dskin<dskin.mean())))  # placeholder (replaced below)
            # depth fraction: distance to the outer (skin-side) boundary over total thickness along the normal
            bnd=lat&~ndi.binary_erosion(lat); outer=bnd&(dskin<np.median(dskin[bnd]))   # skin-facing half of the boundary
            inner=bnd&~outer
            do=ndi.distance_transform_edt(~outer); di=ndi.distance_transform_edt(~inner); frac=do/(do+di+1e-6)
            for side,sgn,base in (("r",1,2),("l",-1,6)):
                sm=lat&((xx>=mid) if sgn>0 else (xx<mid))
                o[sm&(frac<0.40)]=base; o[sm&(frac>=0.40)&(frac<0.75)]=base+1; o[sm&(frac>=0.75)]=base+2
rep={k:round(float((out==v).sum())/1000,1) for k,v in OUT.items()}; print("volumes cm3",rep)
np.save(S+"vh_cryo/abdwall_frame.npy",out)
aff=np.array([[-1,0,0,350],[0,-1,0,240],[0,0,1,-863],[0,0,0,1]],float); nib.save(nib.Nifti1Image(np.ascontiguousarray(out.transpose(2,1,0)),aff),S+"vhm_ts/abdominal_wall_cryo.nii.gz")
lut=np.zeros((9,3),np.uint8); lut[1]=lut[5]=(255,80,80); lut[2]=lut[6]=(255,200,60); lut[3]=lut[7]=(80,200,255); lut[4]=lut[8]=(160,255,120)
ks=np.where((out>0).any(axis=(1,2)))[0]; ts=[]
for k in np.linspace(ks.min()+5,ks.max()-5,5).astype(int):
    im=np.asarray(rgb[k]).copy(); m=out[k]; im[m>0]=(0.5*im[m>0]+0.5*lut[m[m>0]]).astype(np.uint8); ts.append(im[:, 60:640])
Image.fromarray(np.concatenate(ts,axis=1)).save(S+"vh_cryo/abdwall.png"); print("done")
