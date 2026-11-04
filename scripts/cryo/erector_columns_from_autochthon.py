"""Erector spinae columns of the VH male: base mass = the hybrid-CT erector spinae label (transversospinalis
removed), completed by the `total` autochthon mask outside that task's T4-L4 window; each side's
paraspinal mass is split by the distance of each voxel from the midline of the vertebral bodies at that
level: spinalis <= 20 mm (thoracic and upper lumbar only, it fades below L2), longissimus 20-50 mm,
iliocostalis > 50 mm. The classic textbook columns; the boundaries are rules, not the fascial planes."""
import numpy as np, nibabel as nib, json
from totalsegmentator.map_to_binary import class_map
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"
im=nib.load(S+"vhm_ts/total.nii.gz"); t=np.asarray(im.dataobj); inv={v:k for k,v in class_map['total'].items()}
hyb=np.asarray(nib.load(S+"vhm_hyb/abdominal_muscles.nii.gz").dataobj); ha={v:k for k,v in class_map['abdominal_muscles'].items()}
vert=[k for k,v in class_map['total'].items() if v.startswith('vertebrae_')]; L2=inv['vertebrae_L2']
out=np.zeros(t.shape,np.uint8); rep={}
zL2=np.where((t==L2).any(axis=(0,1)))[0].min()
for side,aid,base in (("right",inv['autochthon_right'],1),("left",inv['autochthon_left'],4)):
    # base mass: the hybrid-CT erector spinae label (transversospinalis already separated); the autochthon
    # label fills in only where the hybrid run has no label (above T4 / below L4, outside its window)
    es=hyb==ha[f'erector_spinae_{side}']; ts=hyb==ha[f'transversospinalis_{side}']
    m=es|((t==aid)&~ts&~(hyb>0)); ks=np.where(m.any(axis=(0,1)))[0]
    for k in ks:
        vb=np.isin(t[:,:,k],vert)
        if not vb.any(): continue
        xm=np.where(vb)[0].mean()
        xx=np.arange(t.shape[0])[:,None]*np.ones((1,t.shape[1])); d=np.abs(xx-xm)*0.9375
        sl=m[:,:,k]; o=out[:,:,k]
        o[sl&(d<=20)&(k>=zL2)]=base; o[sl&(d>20)&(d<=50)]=base+1; o[sl&(d>50)]=base+2; o[sl&(d<=20)&(k<zL2)]=base+1
    for i,name in enumerate(("spinalis","longissimus","iliocostalis")): rep[f"{name}_{side}"]=round(float((out==base+i).sum())*0.879/1000,1)
print("volumes cm3",rep)
nib.save(nib.Nifti1Image(out,im.affine,im.header),S+"vhm_ts/erector_columns.nii.gz")
