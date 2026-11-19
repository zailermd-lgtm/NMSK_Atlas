"""Female erector spinae columns by the male's rule (erector_columns_from_autochthon.py), from her MODEL labels
alone (unfrozen CT, no photographs): base mass = her `abdominal_muscles` erector_spinae label (transversospinalis
removed), completed by the `total` autochthon label outside that task's T4-L4 window; each side's paraspinal mass
is split by the distance of each voxel from the midline of the vertebral bodies at that level: spinalis <= 20 mm
(above L2 only), longissimus 20-50 mm, iliocostalis > 50 mm. Textbook columns; boundaries are rules, not fascial
planes. Output: vhf_ts/erector_columns.nii.gz on her torso grid + a report."""
import numpy as np, nibabel as nib, json
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"; R="/home/user/NMSK_Atlas/"
im=nib.load(R+"data/ct_sources/task_outputs/vhf_total.nii.gz"); t=np.asarray(im.dataobj); ps=float(abs(im.affine[0,0])); vox=float(np.prod(im.header.get_zooms()))
labs={v:int(k) for k,v in json.load(open(R+"mappings/totalsegmentator_labels.json"))["labels"].items()}
alabs={v:int(k) for k,v in json.load(open(R+"mappings/totalsegmentator_abdominal_muscles_labels.json"))["labels"].items()}
ab=np.asarray(nib.load(R+"data/ct_sources/task_outputs/vhf_abdominal_muscles.nii.gz").dataobj)
vert=[v for k,v in labs.items() if k.startswith("vertebrae_")]; L2=labs["vertebrae_L2"]
out=np.zeros(t.shape,np.uint8); rep={}; zL2=np.where((t==L2).any(axis=(0,1)))[0].min()
for side,base in (("right",1),("left",4)):
    es=ab==alabs[f"erector_spinae_{side}"]; ts=ab==alabs[f"transversospinalis_{side}"]; aut=t==labs[f"autochthon_{side}"]
    m=es|(aut&~ts&~(ab>0)); ks=np.where(m.any(axis=(0,1)))[0]
    for k in ks:
        vb=np.isin(t[:,:,k],vert)
        if not vb.any(): continue
        xm=np.where(vb)[0].mean(); xx=np.arange(t.shape[0])[:,None]*np.ones((1,t.shape[1])); d=np.abs(xx-xm)*ps
        sl=m[:,:,k]; o=out[:,:,k]
        o[sl&(d<=20)&(k>=zL2)]=base; o[sl&(d>20)&(d<=50)]=base+1; o[sl&(d>50)]=base+2; o[sl&(d<=20)&(k<zL2)]=base+1
    for i,name in enumerate(("spinalis","longissimus","iliocostalis")): rep[f"{name}_{side}"]=round(float((out==base+i).sum())*vox/1000,1)
rep["multifidus_from_model"]={s:round(float((ab==alabs[f"transversospinalis_{s}"]).sum())*vox/1000,1) for s in ("right","left")}
print("volumes cm3",rep,flush=True)
nib.save(nib.Nifti1Image(out,im.affine,im.header),S+"vhf_ts/erector_columns.nii.gz")
json.dump({"_README":["Female erector spinae columns by the distance-from-midline rule on her model labels (scripts/cryo/vhf_erector_columns.py). Rule-based, derived data."],"source":"U.S. National Library of Medicine, The Visible Human Project (public domain), female CT via the NCI Imaging Data Commons; TotalSegmentator v2.18.0 `total` and `abdominal_muscles` labels.","volumes_cm3":rep},open(S+"vhf_ts/erector_columns_report.json","w"),indent=1); print("ES_DONE")
