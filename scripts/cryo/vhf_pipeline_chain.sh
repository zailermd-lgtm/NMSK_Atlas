#!/bin/bash
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 nnUNet_n_proc_DA=0
S=/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad; R=/home/user/NMSK_Atlas; U=b9cf8e7a-2505-4137-9ae3-f8d0cf756c13
mkdir -p $S/vhf_ts; cd $S/vh_idc
[ $(df --output=avail -m $S | tail -1) -lt 2500 ] && { echo LOW_DISK; exit 1; }
[ -f dcm/$U.meta.json ] || python3 groups.py $U
if [ ! -f nii/vhf_headneck_0488.nii.gz ]; then
python3 stack.py $U nii/vhf_torso_0937.nii.gz > stack_vhf.log 2>&1 || { echo STACK_FAILED; exit 1; }
python3 stack.py $U nii/vhf_headneck_0488.nii.gz --ps 0.4883 --zmin -330 --xybox -125 124.6 -125 124.6 > stack_vhf_head.log 2>&1
python3 - <<'PY'
import nibabel as nib, numpy as np
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/vh_idc/nii/"
for name in ("vhf_torso_0937","vhf_headneck_0488"):
    im=nib.load(S+name+".nii.gz"); d=np.asanyarray(im.dataobj).astype(np.int16); mx=d.max(axis=(0,1))
    gaps=[k for k in range(1,d.shape[2]-1) if mx[k]<=-1000 and mx[k-1]>-1000 and mx[k+1]>-1000]
    for k in gaps: d[:,:,k]=((d[:,:,k-1].astype(np.int32)+d[:,:,k+1])//2).astype(np.int16)
    nib.save(nib.Nifti1Image(d,im.affine,im.header),S+name+".nii.gz"); print(name,d.shape,"gaps",gaps)
PY
fi
N=$(python3 -c "import nibabel as nib;print(nib.load('$S/vh_idc/nii/vhf_torso_0937.nii.gz').shape[2]-1)")
[ -f $S/vhf_ts/total.nii.gz ] || { echo "=== $(date +%T) START vhf total 0-$N"; python3 $R/scripts/run_totalsegmentator_chunked.py $S/vh_idc/nii/vhf_torso_0937.nii.gz total $S/vhf_ts/total.nii.gz --z 0 $N --chunk 230 --overlap 30 2>&1 | tail -3; }
read ZC7 ZT4 ZL5 ZSK <<<$(python3 - <<'PY'
import nibabel as nib, numpy as np
from totalsegmentator.map_to_binary import class_map
inv={v:k for k,v in class_map['total'].items()}
a=np.asarray(nib.load("/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/vhf_ts/total.nii.gz").dataobj)
def zr(n):
    z=np.where((a==inv[n]).any(axis=(0,1)))[0]; return (int(z.min()),int(z.max())) if z.size else (-1,-1)
print(zr('vertebrae_C7')[0], zr('vertebrae_T4')[0], zr('vertebrae_L5')[0], zr('skull')[1])
PY
)
echo "z: C7lo=$ZC7 T4lo=$ZT4 L5lo=$ZL5 skulltop=$ZSK"
run(){ [ -f $S/vhf_ts/$1.nii.gz ] && { echo "skip $1 (exists)"; return; }; echo "=== $(date +%T) START $1 z=$3-$4"; python3 $R/scripts/run_totalsegmentator_chunked.py $2 $1 $S/vhf_ts/$1.nii.gz --z $3 $4 --chunk $5 --overlap ${6:-24} 2>&1 | tail -3; echo "=== $(date +%T) END $1"; }
T=$S/vh_idc/nii/vhf_torso_0937.nii.gz; H=$S/vh_idc/nii/vhf_headneck_0488.nii.gz
run abdominal_muscles $T $((ZL5-10)) $((ZC7+10)) 96 16
run headneck_muscles $T $((ZT4-20)) $N 120
run headneck_bones_vessels $T $((ZC7-20)) $N 120
HN=$(python3 -c "import nibabel as nib;print(nib.load('$H').shape[2]-1)")
for t in craniofacial_structures head_muscles oculomotor_muscles; do run $t $H 0 $HN 400; done
echo VHF_ALL_DONE
