"""Hand bones separated on the 0.33 mm photographs: within the 1 mm hand-group masks (carpals, metacarpals,
phalanges) mapped into the full-resolution crops, a marker watershed on the photograph luminance with
markers from the distance-transform peaks of the bone-coloured region (each bone is a blob separated from
its neighbours by the darker joint line). The bones are NOT named; the result refines the group masks'
surfaces (each group's voxels re-derived from the union of full-res bone blobs assigned to that group).
Output: refined 1 mm hand masks in the extended frame."""
import numpy as np, json
from scipy import ndimage as ndi
from skimage.segmentation import watershed
from skimage.feature import peak_local_max
from PIL import Image
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/vh_cryo/"
ext=np.load(S+"arm_bones_ext_frame.npy"); EXT=250; n,H,W=ext.shape
bb=json.load(open(S+"arm_full_bbox.json")); zs=bb["slices"]; win=bb["windows"]; pos={z:j for j,z in enumerate(zs)}
full={side:np.load(S+f"arm_full_{side}.npy",mmap_mode="r") for side in ("right","left")}
renders=[]; stats={}
for side,ids in (("right",(9,10,11)),("left",(12,13,14))):
    ks=np.where(np.isin(ext,ids).any(axis=(1,2)))[0]; nblobs=[]
    for k in ks:
        i=-16-(-1113+int(k))
        if i not in pos or side not in win[str(i)]: continue
        w=win[str(i)][side]; crop=np.asarray(full[side][pos[i]])[:w[1]-w[0],:w[3]-w[2]].astype(np.float32)
        hand=np.isin(ext[k],ids)
        rows,cols=np.mgrid[0:crop.shape[0],0:crop.shape[1]]; r=(rows+w[0])/3.0; c=(cols+w[2])/3.0
        frow=np.clip(np.round((404-r)*0.99),0,H-1).astype(int); fcol=np.clip(np.round(0.99*c+12),0,W-1).astype(int)
        prior=ndi.binary_dilation(hand[frow,fcol],iterations=6)
        if prior.sum()<200: continue
        v=crop.max(-1); mn=crop.min(-1); sat=(v-mn)/(v+1e-3); r_,g_,b_=crop[...,0],crop[...,1],crop[...,2]
        bonecol=prior&(v>150)&(sat<0.45)&(r_>b_+15)          # cream/white (cortex, marrow is paler in the small bones)
        bonecol=ndi.binary_opening(ndi.binary_closing(bonecol,iterations=2),iterations=2)
        if bonecol.sum()<100: continue
        dist=ndi.distance_transform_edt(bonecol); pk=peak_local_max(dist,min_distance=12,threshold_abs=5,labels=bonecol.astype(int))
        mk=np.zeros(dist.shape,int)
        for j,(y,x) in enumerate(pk): mk[y,x]=j+1
        lum=ndi.gaussian_filter(v,1.5); ws=watershed(-lum,mk,mask=bonecol); nblobs.append(int(ws.max()))
        # re-derive the 1 mm group masks: full-res bone pixels -> frame voxels, group by the original label (majority) or nearest
        newmask=np.zeros((H,W),bool); np.logical_or.at(newmask,(frow[ws>0],fcol[ws>0]),True)
        old=ext[k].copy(); grp=np.where(np.isin(old,ids),old,0)
        dist_g,ind=ndi.distance_transform_edt(grp==0,return_indices=True); assign=grp[ind[0],ind[1]]
        keep=newmask&(dist_g<=3); ext[k][np.isin(ext[k],ids)]=0; ext[k][keep&(ext[k]==0)]=assign[keep&(ext[k]==0)]
        if k in (int(ks.min())+20,int(ks.min())+60,int(ks.min())+100):
            im=crop.astype(np.uint8).copy(); e=(ws>0)&~ndi.binary_erosion(ws>0,iterations=2); im[e]=(0,255,0)
            for j in range(1,ws.max()+1):
                ej=(ws==j)&~ndi.binary_erosion(ws==j); im[ej]=(255,60,60)
            renders.append(im[::2,::2])
    stats[side]=dict(slices=len(nblobs),blobs_per_slice_median=float(np.median(nblobs)) if nblobs else 0)
print(stats)
np.save(S+"arm_bones_ext_frame.npy",ext)
import nibabel as nib
F=np.array([[-1,0,0,350],[0,-1,0,240],[0,0,1,-1113],[0,0,0,1]],float); nib.save(nib.Nifti1Image(np.ascontiguousarray(ext.transpose(2,1,0)),F),S.replace("vh_cryo/","")+"vhm_ts/arm_bones_cryo_completed.nii.gz")
if renders:
    h=max(x.shape[0] for x in renders); w=max(x.shape[1] for x in renders); Image.fromarray(np.concatenate([np.pad(x,((0,h-x.shape[0]),(0,w-x.shape[1]),(0,0))) for x in renders],axis=1)).save(S+"carpals_fullres.png")
print("done")
