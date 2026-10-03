"""Deltoid deep boundary on the 0.33 mm photographs (Q5). Within a working region = the rule-based deltoid
mask dilated 12 mm, restricted to muscle-coloured pixels not labelled cuff/arm/pec/lat/trapezius, a marker
watershed on the fascial-line map (white top-hat of the green channel): superficial marker = rule mask
within 10 mm of the skin, deep marker = pixels within 5 mm of the humerus, scapula or cuff labels. The
watershed's superficial basin becomes the deltoid. Adopted only if the volume moves toward 350-500 cm3."""
import numpy as np, nibabel as nib, json
from scipy import ndimage as ndi
from skimage.segmentation import watershed
from skimage.morphology import white_tophat, disk
from PIL import Image
from totalsegmentator.map_to_binary import class_map
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"
delt=np.load(S+"vh_cryo/deltoid_frame.npy"); cuff=np.load(S+"vh_cryo/cuff_frame.npy",mmap_mode="r"); arm=np.load(S+"vh_cryo/arm_muscles_frame.npy",mmap_mode="r")
bones=np.load(S+"vh_cryo/arm_bones_ext_frame.npy",mmap_mode="r"); EXT=250; cls=np.load(S+"vh_cryo/cryo_torso_frame_cls.npy",mmap_mode="r"); n,H,W=delt.shape; OFF=110
tot=nib.load(S+"vhm_ts/total.nii.gz").dataobj; hyb=nib.load(S+"vhm_hyb/abdominal_muscles.nii.gz").dataobj; neck=nib.load(S+"vhm_ts/headneck_muscles_merged.nii.gz").dataobj
inv={v:k for k,v in class_map['total'].items()}
bb=json.load(open(S+"vh_cryo/arm_full_bbox.json")); zs=bb["slices"]; win=bb["windows"]; pos={z:j for j,z in enumerate(zs)}
full={side:np.load(S+f"vh_cryo/arm_full_{side}.npy",mmap_mode="r") for side in ("right","left")}
def frame(vol,k): z=ndi.zoom(np.asarray(vol[:,:,k]),480/512,order=0).T; f=np.zeros((H,W),z.dtype); f[:,OFF:OFF+480]=z; return f
new=np.zeros_like(delt); renders=[]; done=0
for side,lid,cols in (("right",1,slice(0,300)),("left",2,slice(400,700))):
    ks=np.where((delt==lid).any(axis=(1,2)))[0]
    for k in ks:
        i=-16-(-863+int(k))
        if i not in pos or side not in win[str(i)]: new[k][delt[k]==lid]=lid; continue
        w=win[str(i)][side]; crop=np.asarray(full[side][pos[i]])[:w[1]-w[0],:w[3]-w[2]]
        rows,colsg=np.mgrid[0:crop.shape[0],0:crop.shape[1]]; r=(rows+w[0])/3.0; c=(colsg+w[2])/3.0
        frow=np.clip(np.round((404-r)*0.99),0,H-1).astype(int); fcol=np.clip(np.round(0.99*c+12),0,W-1).astype(int)
        D=(delt[k]==lid)[frow,fcol]; t=frame(tot,k); hb=frame(hyb,k); nk=frame(neck,k)
        labelled=((np.asarray(cuff[k])>0)|(np.asarray(arm[k])>0)|(hb>0)|(nk>0)|(t>0))[frow,fcol]
        bone=((t==inv[f"humerus_{side}"])|(t==inv[f"scapula_{side}"])|(np.asarray(bones[k+EXT])>0))[frow,fcol]
        deepref=bone|(np.asarray(cuff[k])>0)[frow,fcol]
        c3=crop.astype(np.float32); v=c3.max(-1); mn=c3.min(-1); sat=(v-mn)/(v+1e-3); rr,gg,bch=c3[...,0],c3[...,1],c3[...,2]
        tissue=(rr>bch+15)&(v>60); muscle=tissue&(rr>gg+15)&(v<170)
        region=muscle&~labelled&ndi.binary_dilation(D,iterations=36)   # 12 mm at 0.33 mm
        if region.sum()<300 or not deepref.any(): new[k][delt[k]==lid]=lid; continue
        tis=ndi.binary_fill_holes(tissue); dskin=ndi.distance_transform_edt(tis)/3.0; ddeep=ndi.distance_transform_edt(~deepref)/3.0
        mk=np.zeros(region.shape,np.int32); mk[region&D&(dskin<=10)]=1; mk[region&(ddeep<=5)]=2
        if not (mk==1).any() or not (mk==2).any(): new[k][delt[k]==lid]=lid; continue
        th=white_tophat(crop[...,1],disk(5)).astype(np.float32); ws=watershed(th,mk,mask=region)
        cnt=np.zeros((H,W),int); np.add.at(cnt,(frow[ws==1],fcol[ws==1]),1); tot_=np.zeros((H,W),int); np.add.at(tot_,(frow[region],fcol[region]),1)
        sel=(cnt>=0.5*np.maximum(tot_,1))&(tot_>0); new[k][sel]=lid; done+=1
        if k in (int(ks.min())+40,int(ks.min())+80):
            im=crop.copy(); e=(ws==1)&~ndi.binary_erosion(ws==1,iterations=2); im[e]=(255,60,60); e2=D&~ndi.binary_erosion(D,iterations=2); im[e2]=(255,255,0); renders.append(im[::2,::2])
print("slices re-traced",done,"volumes cm3 right",round(float((new==1).sum())/1000,1),"left",round(float((new==2).sum())/1000,1),"(rule:",round(float((delt==1).sum())/1000,1),round(float((delt==2).sum())/1000,1),")")
np.save(S+"vh_cryo/deltoid_fullres_frame.npy",new)
if renders:
    h=max(x.shape[0] for x in renders); w=max(x.shape[1] for x in renders); Image.fromarray(np.concatenate([np.pad(x,((0,h-x.shape[0]),(0,w-x.shape[1]),(0,0))) for x in renders],axis=1)).save(S+"vh_cryo/deltoid_fullres.png")
print("done")
