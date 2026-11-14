"""Biceps / brachialis boundary traced on the 0.33 mm photographs: within the 1 mm anterior-compartment
mask (biceps+brachialis+coracobrachialis labels), a marker watershed on the white top-hat of the green
channel (fascial planes are bright lines) with markers 'deep' (within 8 mm of the humerus) and
'superficial' (more than 28 mm from it). The result replaces the depth-rule boundary in the 1 mm arm
muscle volume (labels biceps/brachialis); coracobrachialis keeps its rule."""
import numpy as np, json
from scipy import ndimage as ndi
from skimage.segmentation import watershed
from skimage.morphology import white_tophat, disk
from PIL import Image
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/vh_cryo/"
armm=np.load(S+"arm_muscles_frame.npy"); bones=np.load(S+"arm_bones_ext_frame.npy",mmap_mode="r"); EXT=250
bb=json.load(open(S+"arm_full_bbox.json")); zs=bb["slices"]; win=bb["windows"]; pos={z:j for j,z in enumerate(zs)}
full={side:np.load(S+f"arm_full_{side}.npy",mmap_mode="r") for side in ("right","left")}
n,H,W=armm.shape; changed={"right":0,"left":0}; renders=[]
for side,(bic,bra,hum) in (("right",(1,2,1)),("left",(5,6,5))):
    ks=np.where(np.isin(armm,[bic,bra]).any(axis=(1,2)))[0]
    for k in ks:
        i=-16-(-863+int(k)); 
        if i not in pos or side not in win[str(i)]: continue
        w=win[str(i)][side]; crop=np.asarray(full[side][pos[i]])[:w[1]-w[0],:w[3]-w[2]]
        # 1 mm frame (row,col) -> cryo 1 mm (r,c): r = 404 - row/0.99 ; c = (col-12)/0.99 ; full-res = 3x, minus window
        ant=np.isin(armm[k],[bic,bra]); hm=np.asarray(bones[k+EXT])==hum
        rows,cols=np.mgrid[0:crop.shape[0],0:crop.shape[1]]; r=(rows+w[0])/3.0; c=(cols+w[2])/3.0
        frow=np.clip(np.round((404-r)*0.99),0,H-1).astype(int); fcol=np.clip(np.round(0.99*c+12),0,W-1).astype(int)
        A=ant[frow,fcol]; Hm=hm[frow,fcol]
        if A.sum()<500 or not Hm.any(): continue
        g=crop[...,1]; th=white_tophat(g,disk(5)).astype(np.float32)
        d=ndi.distance_transform_edt(~Hm)/3.0   # mm
        mk=np.zeros(A.shape,np.int32); mk[A&(d<=8)]=2; mk[A&(d>=28)]=1
        if not (mk==1).any() or not (mk==2).any(): continue
        ws=watershed(th,mk,mask=A)
        # back to 1 mm: majority vote per frame voxel
        lab1=np.zeros((H,W),np.uint8); cnt1=np.zeros((H,W),int); cnt2=np.zeros((H,W),int)
        np.add.at(cnt1,(frow[ws==1],fcol[ws==1]),1); np.add.at(cnt2,(frow[ws==2],fcol[ws==2]),1)
        sel=ant&((cnt1+cnt2)>0); newb=sel&(cnt1>=cnt2); newr=sel&(cnt2>cnt1)
        before=armm[k].copy(); armm[k][newb]=bic; armm[k][newr]=bra; changed[side]+=int((armm[k]!=before).sum())
        if k in (300,350,400): 
            im=crop.copy(); e1=(ws==1)&~ndi.binary_erosion(ws==1,iterations=2); e2=(ws==2)&~ndi.binary_erosion(ws==2,iterations=2); im[e1]=(255,60,60); im[e2]=(255,220,60); renders.append(im[::2,::2])
print("voxels relabelled",changed)
for side,(bic,bra) in (("right",(1,2)),("left",(5,6))): print(side,"biceps cm3",round(float((armm==bic).sum())/1000,1),"brachialis cm3",round(float((armm==bra).sum())/1000,1))
np.save(S+"arm_muscles_frame.npy",armm)
import nibabel as nib
aff=np.array([[-1,0,0,350],[0,-1,0,240],[0,0,1,-863],[0,0,0,1]],float); nib.save(nib.Nifti1Image(np.ascontiguousarray(armm.transpose(2,1,0)),aff),S.replace("vh_cryo/","")+"vhm_ts/arm_muscles_cryo.nii.gz")
if renders:
    h=max(r_.shape[0] for r_ in renders); w=max(r_.shape[1] for r_ in renders)
    Image.fromarray(np.concatenate([np.pad(r_,((0,h-r_.shape[0]),(0,w-r_.shape[1]),(0,0))) for r_ in renders],axis=1)).save(S+"biceps_brachialis_fullres.png")
print("done")
