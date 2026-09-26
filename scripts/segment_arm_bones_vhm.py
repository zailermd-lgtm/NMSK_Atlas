"""Upper-limb bones of the VH male frozen CT by marker-controlled watershed on the smoothed CT.
Body = HU>=200 opened once (drops the block/FOV-edge streak sheets), minus the 10 lateral FOV-edge
columns (truncation artefact) and everything `total` labels other than the humerus.
Markers: humerus = eroded `total` humerus label; radius/ulna = the two largest HU>=800 fragments
below the labelled humerus whose extents overlap along the forearm axis; hand = HU>=600 seed
components lying beyond the distal end of those fragments along the forearm axis.
Basins meet at the darkest voxels between bones = the joint spaces. Cavities filled per label.
Identity: radius = wider distal end (also reaches further distally, the radial styloid); both printed."""
import nibabel as nib, numpy as np, json
from scipy import ndimage as ndi
from skimage.segmentation import watershed
from PIL import Image
from totalsegmentator.map_to_binary import class_map
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"
im=nib.load(S+"vh_idc/nii/vhm_torso_0937.nii.gz"); ct=np.asarray(im.dataobj); seg=np.asarray(nib.load(S+"vhm_ts/total.nii.gz").dataobj)
inv={v:k for k,v in class_map['total'].items()}
LAB={"humerus_right":1,"radius_right":2,"ulna_right":3,"hand_right":4,"humerus_left":5,"radius_left":6,"ulna_left":7,"hand_left":8}
out=np.zeros(ct.shape,np.uint8); report={}
sp=np.array([0.9375,0.9375,1.0])
def comps(mask,minvox):
    lab,n=ndi.label(mask,structure=np.ones((3,3,3))); sizes=ndi.sum(np.ones_like(lab),lab,np.arange(1,n+1))
    return lab,[(i+1,int(sizes[i])) for i in np.argsort(-sizes) if sizes[i]>=minvox]
for side,(x0,x1) in (("right",(0,140)),("left",(380,512))):
    hum=inv[f'humerus_{side}']; zh=np.where((seg==hum).any(axis=(0,1)))[0]
    box=(slice(x0,x1),slice(0,512),slice(0,int(zh.max())+1)); c=ct[box]; s=seg[box]
    other=ndi.binary_dilation((s>0)&(s!=hum),iterations=3)
    edge=np.zeros(c.shape,bool)
    if side=="right": edge[:10]=True
    else: edge[-10:]=True
    other|=edge
    body=ndi.binary_opening((c>=200)&~other,iterations=1)|(s==hum)
    below=np.arange(c.shape[2])[None,None,:]<zh.min()
    lab,big=comps(ndi.binary_opening((c>=800)&~other&below,iterations=1),3000)
    a=big[0][0]; ia=np.argwhere(lab==a)*sp
    # forearm axis from fragment a; orient distal->proximal (towards the humerus centroid)
    hc=np.array(ndi.center_of_mass(s==hum))*sp; mu=ia.mean(0); u=np.linalg.svd(ia-mu,full_matrices=False)[2][0]; u*=np.sign(np.dot(hc-mu,u))
    t=lambda idx:(idx*sp-mu)@u
    ta=t(ia); b=None
    for i,_ in big[1:]:
        ti=t(np.argwhere(lab==i))
        if min(ta.max(),ti.max())-max(ta.min(),ti.min())>40: b=i; tb=ti; break
    assert b, (side,big[:5])
    print(side,"fragments a,b",a,b,"t-range a",ta.min().round(),ta.max().round(),"b",tb.min().round(),tb.max().round(),flush=True)
    mk=np.zeros(c.shape,np.int32); mk[ndi.binary_erosion(s==hum,iterations=2)]=1; mk[lab==a]=2; mk[lab==b]=3
    tdist=min(ta.min(),tb.min())
    hl,hc_=comps(ndi.binary_opening((c>=600)&~other&(lab!=a)&(lab!=b),iterations=1),100)
    nh=0
    for i,_ in hc_:
        idx=np.argwhere(hl==i)
        if t(idx).mean()<tdist-8: mk[hl==i]=4; nh+=1
    print(side,"hand seed components",nh,flush=True)
    sm=ndi.gaussian_filter(c.astype(np.float32),1.0); ws=watershed(-sm,mk,mask=body)
    cut=max(0,int(zh.min())-80); sub=ws[:,:,:cut]; sub[sub==1]=0
    # the humerus may extend below its `total` label only away from the FOV edge band (truncation cupping, ~20 columns)
    far=np.ones(c.shape,bool)
    if side=="right": far[:25]=False
    else: far[-25:]=False
    ext=(ws==1)&~(s==hum)&~far; ws[ext]=0
    for l in (1,2,3,4):
        m=ws==l; f=np.stack([ndi.binary_fill_holes(m[:,:,k]) for k in range(m.shape[2])],axis=2); ws[f&(ws==0)]=l
    # identity
    stats={}
    for l in (2,3):
        idx=np.argwhere(ws==l); tt=t(idx); lo=tt.min()
        stats[l]=dict(tmin=float(lo),tmax=float(tt.max()),distal_vox_per_mm=float((tt<lo+25).sum()/25))
    radius=2 if stats[2]['distal_vox_per_mm']>stats[3]['distal_vox_per_mm'] else 3; ulna=5-radius
    agree=stats[radius]['tmin']<stats[ulna]['tmin']
    print(side,"stats",{k:{kk:round(vv) for kk,vv in v.items()} for k,v in stats.items()},"-> radius",radius,"| radius reaches further distally:",agree,flush=True)
    names={1:f"humerus_{side}",radius:f"radius_{side}",ulna:f"ulna_{side}",4:f"hand_{side}"}
    o=out[box]
    for l,name in names.items():
        m=ws==l; o[m&(o==0)]=LAB[name]; idx=np.argwhere(m); tt=t(idx) if len(idx) else np.zeros(1)
        report[name]=dict(vox=int(m.sum()),cm3=round(float(m.sum())*0.879/1000,1),axis_length_mm=int(tt.max()-tt.min()) if len(idx) else 0,identity_rules_agree=bool(agree) if l in (2,3) else None)
        print(name,report[name],flush=True)
nib.save(nib.Nifti1Image(out,im.affine),S+"vhm_ts/arm_bones_labels.nii.gz"); json.dump(report,open(S+"vhm_ts/arm_bones_report.json","w"),indent=1)
lut=np.array([[0,0,0],[200,200,200],[255,80,80],[80,160,255],[255,220,60],[200,200,200],[255,120,200],[90,230,120],[240,160,60]],np.uint8)
for side,(x0,x1) in (("right",(0,140)),("left",(380,512))):
    for ax,nm in ((1,"cor"),(0,"sag")):
        p=out[x0:x1,:,:330].max(axis=ax); rgb=lut[p]; base=np.clip((ct[x0:x1,:,:330].max(axis=ax)+200)/1400,0,1)*140
        img=np.where(p[...,None]>0,rgb,np.repeat(base[...,None],3,2)).astype(np.uint8)
        Image.fromarray(img.transpose(1,0,2)[::-1]).resize((img.shape[0]*2,660)).save(S+f"vhm_ts/arm_zoom_{side}_{nm}.png")
