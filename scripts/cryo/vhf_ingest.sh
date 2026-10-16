#!/bin/bash
# Ingest the Visible Human FEMALE 'Normal' CT task outputs as ct_vhf_* subjects with their own femoral-head origin,
# export a SECOND viewer bundle (build/viewer_f) so the two bodies are never mixed.
cd /home/user/NMSK_Atlas; S=/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad
O=$(python3 scripts/ingest_volume_geometry.py inspect $S/vhf_ts/total.nii.gz --labels totalsegmentator 2>&1 | grep -- "--origin" | head -1 | sed "s/.*--origin '\([^']*\)'.*/\1/")
[ -z "$O" ] && { echo "NO_ORIGIN"; exit 1; }; echo "origin $O"
conv(){ # task labels subject
  [ -f $S/vhf_ts/$1.nii.gz ] || { echo "missing $1"; return; }
  python3 scripts/ingest_volume_geometry.py propose $S/vhf_ts/$1.nii.gz --labels $2 --subject $3 --force 2>&1 | grep -E "labels currently"
  python3 - "$3" <<'PY'
import json,sys
p=f"/home/user/NMSK_Atlas/build/vh/{sys.argv[1]}_volume_mapping.json"; d=json.load(open(p)); n=0
for e in d["entries"]:
    # vessels are KEPT on the female: fresh (unfrozen) non-contrast CT, aorta 185 cm3 with the whole course labelled
    if e.get("atlas_id") and e["source_structure"].startswith("platysma"): e["status"]="curated"; e["atlas_id"]=None; e["relationship"]="no_usable_label"; e["note"]="Platysma not trusted at this resolution."; n+=1
json.dump(d,open(p,"w"),indent=1); print("nulled",n)
PY
  python3 scripts/ingest_volume_geometry.py convert $S/vhf_ts/$1.nii.gz --labels $2 --subject $3 --origin="$O" --smooth 1.0 2>&1 | grep -E "wrote|Error|Trace"
  cp build/vh/$3_volume_mapping.json mappings/subjects/
}
conv total totalsegmentator ct_vhf
conv craniofacial_structures totalsegmentator_craniofacial_structures ct_vhf_head
conv head_muscles totalsegmentator_head_muscles ct_vhf_headm
conv oculomotor_muscles totalsegmentator_oculomotor_muscles ct_vhf_orbit
conv headneck_muscles totalsegmentator_headneck_muscles ct_vhf_neck
conv headneck_bones_vessels totalsegmentator_headneck_bones_vessels ct_vhf_neckbv
conv abdominal_muscles totalsegmentator_abdominal_muscles ct_vhf_abd
python3 scripts/export_viewer_bundle.py --subject ct_vhf_head --subject ct_vhf --subject ct_vhf_headm --subject ct_vhf_neck --subject ct_vhf_neckbv --subject ct_vhf_orbit --subject ct_vhf_abd -o build/viewer_f 2>&1 | grep -E "structures from|->"
python3 scripts/build_viewer_html.py --bundle build/viewer_f -o build/viewer_f/atlas_viewer_female.html 2>&1 | tail -1
echo VHF_INGEST_DONE
