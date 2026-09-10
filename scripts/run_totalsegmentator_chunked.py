"""Run one TotalSegmentator task on a z-range of a CT in overlapping z-chunks
and stitch the pieces back into a full-size label volume.

    python3 scripts/run_totalsegmentator_chunked.py ct.nii.gz abdominal_muscles out.nii.gz --z 125 453

Why this exists. The 0.75 mm task models (abdominal_muscles,
headneck_bones_vessels, the head tasks) resample a trunk crop to roughly
578 x 402 x 508 voxels and hold a softmax over every class: ~10 GB for 22
classes. On a 15 GB CPU box the nnU-Net worker is OOM-killed and the parent
process then waits on a futex forever, which looks like a hang rather than a
failure (found 2026-09-10 on case s0913; kernel log confirmed the kill).
Running the task on 96-slice chunks with 16 slices of overlap keeps the peak
near 5 GB. Each chunk is cut with nibabel's slicer, so it carries its own
correct affine, and the stitch is by voxel index -- half the overlap on each
side of an interior boundary is discarded. The z-range should come from the
case's own masks (vertebrae, skull), not from a guess.

Nothing here is anatomy: it only decides which slices go to the model and
how the answers are put back together."""
import argparse, subprocess, tempfile, os, sys, time
import numpy as np, nibabel as nib
ap=argparse.ArgumentParser(); ap.add_argument("inp"); ap.add_argument("task"); ap.add_argument("out")
ap.add_argument("--z",nargs=2,type=int,required=True); ap.add_argument("--chunk",type=int,default=96); ap.add_argument("--overlap",type=int,default=16)
a=ap.parse_args()
im=nib.load(a.inp); lo,hi=a.z; hi=min(hi,im.shape[2]-1)
starts=list(range(lo,hi+1,a.chunk-a.overlap))
chunks=[(s,min(s+a.chunk,hi+1)) for s in starts if s<hi+1]
chunks=[c for c in chunks if c[1]-c[0]>a.overlap] if len(chunks)>1 else chunks
full=np.zeros(im.shape,dtype=np.uint8); tmp=tempfile.mkdtemp(prefix="tschunk_")
for i,(s,e) in enumerate(chunks):
    piece=im.slicer[:,:,s:e]; pin=os.path.join(tmp,f"c{i}.nii.gz"); pout=os.path.join(tmp,f"c{i}_seg.nii.gz"); nib.save(piece,pin)
    t0=time.time(); print(f"chunk {i+1}/{len(chunks)} z={s}-{e-1} shape={piece.shape}",flush=True)
    r=subprocess.run(["TotalSegmentator","-i",pin,"-o",pout,"-ta",a.task,"--ml","-d","cpu","--nr_thr_resamp","1","--nr_thr_saving","1"],capture_output=True,text=True)
    if r.returncode!=0 or not os.path.exists(pout): print("FAILED chunk",i,r.stdout[-800:],r.stderr[-1500:],flush=True); sys.exit(2)
    seg=np.asarray(nib.load(pout).dataobj).astype(np.uint8); assert seg.shape==piece.shape,(seg.shape,piece.shape)
    # keep the central part; drop half the overlap at interior boundaries
    k0=0 if i==0 else a.overlap//2; k1=seg.shape[2] if i==len(chunks)-1 else seg.shape[2]-a.overlap//2
    full[:,:,s+k0:s+k1]=seg[:,:,k0:k1]
    print(f"  done in {time.time()-t0:.0f}s, labels {np.unique(seg).size-1}",flush=True)
nib.save(nib.Nifti1Image(full,im.affine,im.header),a.out); print("WROTE",a.out,"nonzero",int((full>0).sum()),flush=True)
