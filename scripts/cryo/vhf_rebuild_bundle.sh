#!/bin/bash
# Rebuild the Visible Human FEMALE viewer bundle from what the repository holds (task outputs in
# data/ct_sources/task_outputs, per-subject mappings in mappings/subjects) after a container reset wiped build/.
# The body surface (ct_vhf_skin) needs her torso CT restacked in the scratchpad (scripts/cryo/vhf_skin_and_depth.sh);
# it is skipped when that volume is absent. Idempotent: converts every subject, then exports and builds the HTML.
set -u; cd /home/user/NMSK_Atlas; S=/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad
T=data/ct_sources/task_outputs; mkdir -p build/vh
O=$(python3 scripts/ingest_volume_geometry.py inspect $T/vhf_total.nii.gz --labels totalsegmentator 2>&1 | grep -- "--origin" | head -1 | sed "s/.*--origin '\([^']*\)'.*/\1/")
[ -z "$O" ] && { echo "NO_ORIGIN"; exit 1; }; echo "origin $O"
conv(){ # volume labels subject [extra convert args]
  local vol=$1 labels=$2 sub=$3; shift 3
  [ -f "$vol" ] || { echo "missing $vol"; return; }
  [ -z "${RECONVERT:-}" ] && [ -f build/vh/$sub/manifest.json ] && { echo "have $sub"; return; }   # idempotent: RECONVERT=1 forces
  cp mappings/subjects/${sub}_volume_mapping.json build/vh/ 2>/dev/null || python3 scripts/ingest_volume_geometry.py propose $vol --labels $labels --subject $sub --force 2>&1 | grep -E "labels currently"
  python3 scripts/ingest_volume_geometry.py convert $vol --labels $labels --subject $sub --origin="$O" "$@" 2>&1 | grep -E "wrote|Error|Trace"
  cp build/vh/${sub}_volume_mapping.json mappings/subjects/
}
# Q115: descending_thoracic_aorta only, reconverted at --smooth 0.0 (ct_vhf's own aorta split
# clustered a source that measures ONE piece into 2 below the vessel budget's default 1500 tris --
# BUDGET_OVERRIDES now also covers this, but the smoothing-vs-source gap was real and worth keeping
# separately reconverted; see PROJECT_STATE Q115). Listed BEFORE ct_vhf so it wins the one atlas_id
# it carries; ct_vhf's own arch/abdominal aorta parts are untouched.
if [ -f mappings/subjects/ct_vhf_descaorta_volume_mapping.json ] && ! grep -q descending_thoracic_aorta build/vh/ct_vhf_descaorta/manifest.json 2>/dev/null; then
  cp mappings/subjects/ct_vhf_descaorta_volume_mapping.json build/vh/
  python3 scripts/ingest_volume_geometry.py convert $T/vhf_total.nii.gz --labels totalsegmentator --subject ct_vhf_descaorta --origin="$O" --smooth 0.0 2>&1 | grep -E "wrote|Error|Trace"
fi
conv $T/vhf_total.nii.gz totalsegmentator ct_vhf --smooth 1.0
conv $T/vhf_craniofacial_structures.nii.gz totalsegmentator_craniofacial_structures ct_vhf_head --smooth 1.0
conv $T/vhf_head_muscles.nii.gz totalsegmentator_head_muscles ct_vhf_headm --smooth 1.0
conv $T/vhf_oculomotor_muscles.nii.gz totalsegmentator_oculomotor_muscles ct_vhf_orbit --smooth 1.0
conv $T/vhf_headneck_muscles_merged.nii.gz totalsegmentator_headneck_muscles ct_vhf_neck --smooth 1.0
conv $T/vhf_headneck_bones_vessels.nii.gz totalsegmentator_headneck_bones_vessels ct_vhf_neckbv --smooth 1.0
conv $T/vhf_abdominal_muscles.nii.gz totalsegmentator_abdominal_muscles ct_vhf_abd --smooth 1.0
[ -n "${STOP_BEFORE_LEGS:-}" ] && { echo CONV_DONE; exit 0; }   # torso subjects only (run while the legs volume is still being made)
conv $T/vhf_lower_limb_bones.nii.gz vhf_legs ct_vhf_legs --smooth 1.0
# her seven tarsal bones: her CT tarsal label split by the male's separately segmented tarsals transferred onto her
# (scripts/transfer/name_tarsal_pieces.py -> cross_subject_transfer m2f -> scripts/vhf_split_tarsals.py); the split volume is in the repo
if [ ! -f $T/vhf_tarsals_split.nii.gz ] || [ -n "${RECONVERT:-}" ]; then
  python3 - <<'PY'
import json,shutil,os
b=json.load(open('data/derived/viewer_bundles/vhm_v25/bundle.json')); ren=json.load(open('mappings/subjects/vhm_both_piece_names.json'))['rename']; seen={}
for e in b['structures']:
    k=seen.get(e['id'],0); seen[e['id']]=k+1; new=ren.get(e['id'],{}).get(str(k))
    if new: e['id']=new
os.makedirs('build/vhm_named',exist_ok=True); json.dump(b,open('build/vhm_named/bundle.json','w')); shutil.copy('data/derived/viewer_bundles/vhm_v25/bundle.bin','build/vhm_named/bundle.bin')
PY
  python3 scripts/transfer/cross_subject_transfer.py --direction m2f --male-html build/vhm_named --ids calcaneus_r talus_r cuboid_r navicular_r cuneiform_medial_r cuneiform_intermediate_r cuneiform_lateral_r calcaneus_l talus_l cuboid_l navicular_l cuneiform_medial_l cuneiform_intermediate_l cuneiform_lateral_l -o build/vh/xfer_tarsals --report data/derived/transfer_report_tarsals.json 2>&1 | grep -v Deprec | tail -1 | cut -c1-160
  python3 scripts/vhf_split_tarsals.py --xfer build/vh/xfer_tarsals 2>&1 | grep -v Deprec | tail -3
fi
conv $T/vhf_tarsals_split.nii.gz vhf_tarsals ct_vhf_tarsal --smooth 1.0
conv $T/vhf_arm_bones_ct.nii.gz vhf_arm_bones ct_vhf_armb --smooth 1.0
# Q125: her right metacarpals I-V individually split from the merged metacarpals_right CT mask
# (scripts/vhf_split_metacarpals.py, marker-controlled watershed on her own torso CT raw HU);
# ct_vhf_armb's own metacarpals_r mapping is nulled out above so this replaces it, not duplicates it
conv $T/vhf_metacarpals_split.nii.gz vhf_metacarpals_split ct_vhf_mcsplit --smooth 1.0
conv $T/vhf_deltoid_cryo.nii.gz vhf_deltoid ct_vhf_delt --smooth 1.0
# shoulder girdle split (Q62): infraspinatus / teres minor / teres major out of the cuff's merged mass (scripts/cryo/split_shoulder_girdle.py); listed BEFORE the cuff so the split wins
conv $T/vhf_shoulder_split_cryo.nii.gz vhf_shoulder_split ct_vhf_shsp --smooth 1.0
conv $T/vhf_rotator_cuff_cryo.nii.gz vhf_rotator_cuff ct_vhf_cuff --smooth 1.0
conv $T/vhf_erector_columns.nii.gz vhf_erector ct_vhf_es --smooth 1.0
conv $T/vhf_arm_muscles_cryo.nii.gz vhf_arm_muscles ct_vhf_armm --smooth 1.0
# Q62 step 1: her right forearm muscles from the full-resolution crops (rule-based; twelve muscles, the rest merged/unshipped)
conv $T/vhf_forearm_muscles_cryo.nii.gz vhf_forearm_muscles ct_vhf_forearm --smooth 1.0
# Q71/Q97: her LEFT forearm from a proximal-only cryosection track (Q71, ~60% of the forearm length); five of
# twenty muscles clear Q97's mesh-topology/skin-containment/render bar (extensor_digitorum_l,
# extensor_digiti_minimi_l, abductor_pollicis_longus_l, extensor_pollicis_brevis_l, extensor_pollicis_longus_l),
# the rest stay null (0 cm3 unseeded compartments or gross bilateral volume mismatches, confirmed defects, not
# soft doubt)
conv $T/vhf_left_forearm_muscles_cryo.nii.gz vhf_left_forearm_muscles ct_vhf_left_forearm --smooth 1.0
# Q62 step 3: deep neck + suboccipitals from her 1 mm frame (rule-based; splenius and erector_cervical sinks unshipped)
conv $T/vhf_deep_neck_cryo.nii.gz vhf_deep_neck ct_vhf_dneck --smooth 1.0
# Q62 step 6: diaphragm + intercostal sheets from her total-task labels (rule-based, 4 mm sheet)
conv $T/vhf_trunk_wall.nii.gz vhf_trunk_wall ct_vhf_twall --smooth 1.0
# Q62 step 7a: suprahyoid + extrinsic tongue muscles from her 1 mm frame (rule-based; the straps are fragments and unshipped)
conv $T/vhf_hyoid_muscles_cryo.nii.gz vhf_hyoid_muscles ct_vhf_hyoid --smooth 1.0
# Q62 step 4: her right hand intrinsics from the full-resolution crops (rule-based; the thenar group stays merged and unshipped)
conv $T/vhf_hand_muscles_cryo.nii.gz vhf_hand_muscles ct_vhf_hand --smooth 1.0
# Q55: the femoral artery, vein and nerve trunk tracked in her full-resolution anterior-thigh crops (triangle only)
conv $T/vhf_femoral_bundle_cryo.nii.gz vhf_femoral_bundle ct_vhf_femoral --smooth 1.0
# Q56: the popliteal artery, vein and the tibial nerve in her popliteal fossa, same tracker
conv $T/vhf_popliteal_cryo.nii.gz vhf_popliteal ct_vhf_popliteal --smooth 1.0
# Q62: her pelvic floor and perineum from the CT labels with the 1 mm photographs as tissue evidence (rule-based)
conv $T/vhf_pelvic_floor_cryo.nii.gz vhf_pelvic_floor ct_vhf_pfloor --smooth 1.0
conv $T/vhf_pecminor_rhomboids_cryo.nii.gz vhf_pecminor_rhomboids ct_vhf_pmr --smooth 1.0
# nerves tracked through her FULL-RESOLUTION cryosections (scripts/cryo/vhf_nerve_track.py + vhf_nerve_volume.py; 0.5 mm label volume in the repo)
[ -f $T/vhf_nerves_cryo.nii.gz ] && conv $T/vhf_nerves_cryo.nii.gz vhf_nerves ct_vhf_nerve --smooth 1.0
SUBJ="--subject ct_vhf_head --subject ct_vhf_legs --subject ct_vhf_tarsal --subject ct_vhf_armb --subject ct_vhf_mcsplit"
[ -f build/vh/ct_vhf_descaorta/manifest.json ] && SUBJ="$SUBJ --subject ct_vhf_descaorta"
# Q116: genioglossus_r only, reconverted at --smooth 0.0 (ct_vhf_hyoid_fix); listed BEFORE
# ct_vhf_hyoid so it wins just this one atlas_id.
[ -f build/vh/ct_vhf_hyoid_fix/manifest.json ] && SUBJ="$SUBJ --subject ct_vhf_hyoid_fix"
SUBJ="$SUBJ --subject ct_vhf --subject ct_vhf_headm --subject ct_vhf_neck --subject ct_vhf_neckbv --subject ct_vhf_orbit --subject ct_vhf_abd --subject ct_vhf_shsp --subject ct_vhf_delt --subject ct_vhf_cuff --subject ct_vhf_es --subject ct_vhf_armm --subject ct_vhf_forearm --subject ct_vhf_left_forearm --subject ct_vhf_dneck --subject ct_vhf_hyoid --subject ct_vhf_hand --subject ct_vhf_femoral --subject ct_vhf_popliteal --subject ct_vhf_pfloor --subject ct_vhf_twall --subject ct_vhf_pmr --subject xfer_vhm2vhf_rhom"
[ -f build/vh/ct_vhf_nerve/manifest.json ] && SUBJ="$SUBJ --subject ct_vhf_nerve"   # ct_vhf_legs precedes ct_vhf so its united femur (both blocks) wins over the torso stub
[ -f $S/vhf_ts/skin_ct.nii.gz ] || python3 scripts/cryo/vhf_whole_body_skin.py   # torso + legs silhouettes on one grid
SKIN=$S/vhf_ts/skin_ct.nii.gz; [ -f $S/vhf_ts/skin_union.nii.gz ] && SKIN=$S/vhf_ts/skin_union.nii.gz   # CT silhouette united with the photograph silhouette (arms) when available
if [ -f $SKIN ]; then
  conv $SKIN vhm_skin ct_vhf_skin --smooth 1.5 --step 2; SUBJ="$SUBJ --subject ct_vhf_skin"
elif [ -f build/vh/ct_vhf_skin/manifest.json ]; then
  # Q116 lesson: the scratchpad-only source volume (skin_ct.nii.gz/skin_union.nii.gz) doesn't survive a
  # container reset and regeneration can itself fail silently if ITS OWN scratchpad inputs are gone too.
  # A prior successful conversion already sits in build/vh/ct_vhf_skin -- reuse it rather than silently
  # dropping the skin/depth-tag subject from the bundle. --skin-nii below stays unset in this branch (no
  # source volume to pass cross_subject_transfer.py), so the m2f transfer's own skin-containment clip is
  # skipped this run; that transfer step already warns loudly when --skin-nii is absent.
  echo "WARNING: skin source volume absent, REUSING existing build/vh/ct_vhf_skin (regenerate scripts/cryo/vhf_whole_body_skin.py's inputs to get a fresh conversion)" >&2
  SUBJ="$SUBJ --subject ct_vhf_skin"; SKIN=""
else
  echo "WARNING: skin volume absent and no prior build/vh/ct_vhf_skin exists -- bundle will ship WITHOUT the skin subject or depth tags" >&2
  SKIN=""
fi
# cross-subject transfer: everything the male has and she lacks (lower-limb muscles, ligaments, cartilage, ...) carried onto
# her bones and inside her measured muscle compartment; badged subject, listed LAST so her own structures always win
if [ ! -f build/vh/xfer_vhm2vhf/manifest.json ] || [ -n "${RECONVERT:-}" ]; then
  # $SKIN can be "" (see the skin-volume fallback above) -- pass --skin-nii only when there's a real path,
  # since an unquoted empty $SKIN would otherwise vanish and shift --skin-origin into its place.
  SKIN_ARGS=(); [ -n "$SKIN" ] && SKIN_ARGS=(--skin-nii "$SKIN")
  python3 scripts/transfer/cross_subject_transfer.py --direction m2f --male-html data/derived/viewer_bundles/vhm_v25 \
    --envelope-src data/derived/lean_envelope_vhm.json --envelope-dst data/derived/lean_envelope_vhf.json \
    "${SKIN_ARGS[@]}" --skin-origin="$O" -o build/vh/xfer_vhm2vhf --report data/derived/transfer_report_vhm2vhf.json 2>&1 | grep -v Deprec | head -1 | cut -c1-200
fi
# the transferred lower-limb muscles with their boundaries refined to HER septa (scripts/transfer/refine_transfer_to_septa.py,
# label volume in the repo); listed BEFORE xfer_vhm2vhf so the refined muscle wins and the unrefined transfer supplies the rest
if [ -f $T/vhf_xfer_lowerlimb_septa.nii.gz ]; then
  conv $T/vhf_xfer_lowerlimb_septa.nii.gz vhf_xfer_septa xfer_vhm2vhf_sep --smooth 1.0
  # Q115: extensor_hallucis_longus_l + flexor_digitorum_longus_l only, reconverted at --smooth 0.0
  # (raw source is 0.997-1.000 main_frac but xfer_vhm2vhf_sep's own smooth=1.0 conversion shipped
  # 0.669/0.825 for these two). extensor_hallucis_longus_r was investigated and DECLINED -- its
  # pre-decimation mesh measures ~0.55 at EITHER smoothing value, a marching-cubes surface defect,
  # not this bug class -- so it is deliberately excluded from this mapping and still comes from
  # xfer_vhm2vhf_sep, unchanged. Listed BEFORE xfer_vhm2vhf_sep so it wins only these 2 ids.
  if [ -f mappings/subjects/ct_vhf_xfersepta_fix_volume_mapping.json ] && ! grep -q flexor_digitorum_longus_l build/vh/ct_vhf_xfersepta_fix/manifest.json 2>/dev/null; then
    cp mappings/subjects/ct_vhf_xfersepta_fix_volume_mapping.json build/vh/
    python3 scripts/ingest_volume_geometry.py convert $T/vhf_xfer_lowerlimb_septa.nii.gz --labels vhf_xfer_septa --subject ct_vhf_xfersepta_fix --origin="$O" --smooth 0.0 2>&1 | grep -E "wrote|Error|Trace"
  fi
  [ -f build/vh/ct_vhf_xfersepta_fix/manifest.json ] && SUBJ="$SUBJ --subject ct_vhf_xfersepta_fix"
  [ -f build/vh/xfer_vhm2vhf_sep/manifest.json ] && SUBJ="$SUBJ --subject xfer_vhm2vhf_sep"
fi
# Q149: xfer_vhm2vhf's transversus pair came from the male's MIRRORED abdominal wall (vhm_v25); re-transfer
# just that pair from the corrected male bundle (build/viewer_m, rebuilt by scripts/vhm_rebuild_bundle.sh first)
# and list it BEFORE xfer_vhm2vhf so it wins those two ids.
if [ ! -f build/vh/xfer_vhm2vhf_tva/manifest.json ] && [ -f build/viewer_m/bundle.json ]; then
  python3 scripts/transfer/cross_subject_transfer.py --direction m2f --male-html build/viewer_m \
    --ids transversus_abdominis_r transversus_abdominis_l \
    --envelope-src data/derived/lean_envelope_vhm.json --envelope-dst data/derived/lean_envelope_vhf.json \
    --skin-origin="$O" -o build/vh/xfer_vhm2vhf_tva --report data/derived/transfer_report_vhm2vhf_tva.json 2>&1 | grep -v Deprec | head -1 | cut -c1-200
fi
[ -f build/vh/xfer_vhm2vhf_tva/manifest.json ] && SUBJ="$SUBJ --subject xfer_vhm2vhf_tva"
[ -f build/vh/xfer_vhm2vhf/manifest.json ] && SUBJ="$SUBJ --subject xfer_vhm2vhf"
# his rhomboid minor carried onto her (her own rhomboid mass was unusable, Q62 step 2); the forearm/hand transfer was
# measured and REJECTED (see docs/GEOMETRY_SOURCES.md): that map distorts limb volumes by 2-3x
if [ ! -f build/vh/xfer_vhm2vhf_rhom/manifest.json ]; then
  python3 scripts/transfer/cross_subject_transfer.py --direction m2f --male-html build/viewer_m/atlas_viewer_male.html --female-bundle build/viewer_f \
    --ids rhomboid_minor_l rhomboid_minor_r -o build/vh/xfer_vhm2vhf_rhom --report data/derived/transfer_report_vhm2vhf_rhom.json 2>&1 | tail -1 | cut -c1-140
fi
# Q147: forearm/hand/foot soft tissue from Z-Anatomy, PER-BONE registration onto HER own bones
# (scripts/transfer/limb_per_bone_transfer.py) -- radius vs ulna kept separate, never the broad
# multi-bone blend the rejected m2f forearm/hand transfer above used (that map distorted limb
# volumes 2-3x). Fills gaps only, listed LAST. Her LEFT forearm/hand has no bone at all (outside
# her CT field of view -- same limitation as everywhere else in this file) so those ids are
# skipped by the script itself, not shipped as ungrounded geometry.
# 29.1mm median / 91.0mm max: centroid error validating this exact method on her own real
# ct_vhf_forearm muscles (n=13; her 5 ct_vhf_left_forearm ids could not be validated the same way,
# no bone to register onto) -- see PROJECT_STATE.md Q147 and data/derived/
# Q147_validation_female.json. NOTE: re-running this by hand against an ALREADY-built
# build/viewer_f (e.g. only to change the badge text) silently ships 0 structures -- see the
# matching comment in scripts/vhm_rebuild_bundle.sh; Q150 worked around it with a one-off
# pre-transfer bundle built from the SUBJ list above (everything up to and including
# xfer_vhm2vhf).
if [ ! -f build/vh/xfer_zan2vhf_limb/manifest.json ]; then
  python3 scripts/transfer/limb_per_bone_transfer.py --direction zan2f --female-bundle build/viewer_f \
    --badge-error-mm 29.1 --badge-max-error-mm 91.0 -o build/vh/xfer_zan2vhf_limb --report data/derived/transfer_report_zan2vhf_limb.json 2>&1 | tail -1 | cut -c1-200
fi
# Q150/Q150b: a forearm-compartment refinement onto her OWN segmented tissue was TRIED
# (scripts/transfer/refine_limb_transfer.py) but a lead review found the first cut's leave-one-
# out validation leaked ground truth (a held-out id was searched for inside its OWN already-
# known true label, scoring a fraudulent ~4mm median); the CORRECTED validation (neighbouring
# real labels folded into the open competitive region too, a "neighbor" and a stricter
# "whole_limb" variant -- data/derived/Q150_validation_female.json) measures forearm median
# 18.9-20.6mm / max 25.7-32.1mm and hand median 22.2-28.9mm / max 50.9-51.5mm, both over the
# 15mm median bar -- NOT shipped, either region. xfer_zan2vhf_limb above (its badge now also
# discloses its own max error) stands as this specimen's forearm/hand/foot estimate, unchanged.
[ -f build/vh/xfer_zan2vhf_limb/manifest.json ] && SUBJ="$SUBJ --subject xfer_zan2vhf_limb"
python3 scripts/export_viewer_bundle.py $SUBJ -o build/viewer_f --budget-scale 0.85 2>&1 | grep -E "structures from|->|Error|Trace"
python3 scripts/build_viewer_html.py --bundle build/viewer_f -o build/viewer_f/atlas_viewer_female.html 2>&1 | tail -1
sed -i 's/<title>NMSK Atlas Viewer<\/title>/<title>NMSK Atlas Viewer (VH female)<\/title>/' build/viewer_f/atlas_viewer_female.html
echo VHF_REBUILD_DONE
