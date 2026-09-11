cd /home/user/NMSK_Atlas; S=/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad
python3 - <<'PY'
import nibabel as nib, numpy as np
from scipy import ndimage as ndi
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"
im=nib.load(S+"vh_idc/nii/vhf_torso_0937.nii.gz"); d=np.asarray(im.dataobj); m=np.zeros(d.shape,bool)
for k in range(d.shape[2]): m[:,:,k]=ndi.binary_fill_holes(ndi.binary_opening(d[:,:,k]>-300,iterations=2))
cl,n=ndi.label(m); sizes=ndi.sum(np.ones_like(cl,dtype=np.uint8),cl,np.arange(1,n+1)); body=(cl==(np.argmax(sizes)+1)).astype(np.uint8)
print("female body voxels",int(body.sum()),"components",n)
nib.save(nib.Nifti1Image(body,im.affine,im.header),S+"vhf_ts/skin_ct.nii.gz")
PY
python3 scripts/ingest_volume_geometry.py propose $S/vhf_ts/skin_ct.nii.gz --labels vhm_skin --subject ct_vhf_skin --force 2>&1 | grep -E "labels currently"
python3 scripts/ingest_volume_geometry.py convert $S/vhf_ts/skin_ct.nii.gz --labels vhm_skin --subject ct_vhf_skin --origin='7.769,-885.229,14.137' --smooth 1.5 --step 2 2>&1 | grep -E "wrote|Error|Trace"
cp build/vh/ct_vhf_skin_volume_mapping.json mappings/subjects/
python3 scripts/export_viewer_bundle.py --subject ct_vhf_head --subject ct_vhf --subject ct_vhf_headm --subject ct_vhf_neck --subject ct_vhf_neckbv --subject ct_vhf_orbit --subject ct_vhf_abd --subject ct_vhf_skin -o build/viewer_f 2>&1 | grep -E "structures from|->"
python3 scripts/build_viewer_html.py --bundle build/viewer_f -o build/viewer_f/atlas_viewer_female.html 2>&1 | tail -1; sed -i 's/<title>NMSK Atlas Viewer<\/title>/<title>NMSK Atlas Viewer (VH female)<\/title>/' build/viewer_f/atlas_viewer_female.html
python3 - <<'PY'
import json, numpy as np
from scipy.spatial import cKDTree
R="/home/user/NMSK_Atlas/build/vh/"
def load(sub):
    m=json.load(open(R+sub+"/manifest.json")); v=np.fromfile(R+sub+"/vertices.f32",np.float32).reshape(-1,3); return m,v
ms,vs=load("ct_vhf_skin"); s=ms["structures"][0]; a=s.get("vertex_offset",s.get("vertex_start")); skin=vs[a:a+s["vertex_count"]]; tree=cKDTree(skin[::2])
cat={s["id"]:s["cat"] for s in json.load(open("/home/user/NMSK_Atlas/build/viewer_f/bundle.json"))["structures"]}; rows=[]
for sub in ("ct_vhf","ct_vhf_head","ct_vhf_headm","ct_vhf_neck","ct_vhf_neckbv","ct_vhf_orbit","ct_vhf_abd"):
    m,v=load(sub)
    for st in m["structures"]:
        a=st.get("vertex_offset",st.get("vertex_start")); n=st["vertex_count"]; p=v[a:a+n]
        if n<20: continue
        d,_=tree.query(p[::max(1,n//4000)]); rows.append(dict(atlas_id=st["atlas_id"],subject=sub,category=cat.get(st["atlas_id"]),min_depth_mm=round(float(d.min()),1),median_depth_mm=round(float(np.median(d)),1),max_depth_mm=round(float(d.max()),1)))
json.dump({"_README":["Depth below the body surface for every shipped structure of the Visible Human FEMALE (mm; min/median/max over the structure's surface). Her body surface is the CT body silhouette (HU > -300), not a photograph. Derived data."],"source":"Derived from the Visible Human female meshes in this repository (NLM VHP, public domain; TotalSegmentator segmentations).","generated":"2026-09-11","rows":rows},open("/home/user/NMSK_Atlas/data/derived/skin_depth_vhf.json","w"),indent=1); print("depth rows",len(rows))
PY
echo VHF_SKIN_DONE
