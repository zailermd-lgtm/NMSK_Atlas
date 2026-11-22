"""Female body surface over the WHOLE body including the arms: the CT silhouette (vhf_whole_body_skin.py; her CT
clips the arms laterally) united with the photograph silhouette (colour classes > 0, closed, hole-filled, pieces
>= 20 cm2 per slice, the ruler rows at the top of the frame dropped) on the registered 1 mm frame (480 x 700), photographs used only
above RAS z -950 (the arm levels; lower down they would add a registration rim along the legs).
The trunk and legs therefore stay CT-exact; the arms come from the photographs (+-10 mm, the registration). Output
vhf_ts/skin_union.nii.gz (label 1 = body) in torso RAS on the frame grid, for `ct_vhf_skin` and the depth tags.

Q74: visual QA found a step/ridge encircling each upper arm at the shoulder/axilla. Root cause, confirmed by
inspecting the raw classification frames directly: `cryo_frame_cls.npy` frames k=1242-1246 (RAS z -534..-530,
atlas_y ~351-355, i.e. exactly shoulder/axilla height) are completely blank -- zero classified pixels, a genuine
5-frame gap in the cryosection data, not a per-slice-operator artifact (the originally suspected cause in
vhf_whole_body_skin.py's silhouette() was checked and is NOT it: that script's per-slice opening is a steady,
low-amplitude effect, nothing like this). With the photograph silhouette `t` collapsing to nothing for those
slices (and the closing/fill_holes drawing near-empty results a few slices either side, as the classifier's
per-slice connected-component size filter -- >=2000 px -- keeps rejecting the sparse partial data at the gap's
edges), the union `t|ctm` falls back to the CT-only silhouette there, which is narrower ("her CT clips the arms
laterally", hence this whole union script) -- a real, measured ~11 mm-tall notch (extra-vs-CT area sags from
~12,800 to 0 and back to ~10,500 across k=1239..1250) that appears as an encircling step once marching cubes
reconstructs the surface. Fix: detect any fully-blank frame inside the "photographs used" band (there is exactly
one such gap in her data, but the detection is general) and, over that gap plus a small MARGIN either side (to
also cover the classifier's partial-data ramp at the edges), replace the per-slice silhouette with a shape
interpolation (signed-distance blend) between the nearest good frames below and above -- not a new measurement,
just closing a data gap with the closest real evidence on each side, the same way a dropped CT slice would be
patched."""
import numpy as np, nibabel as nib, json
from scipy import ndimage as ndi
S="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"; D=S+"vh_cryo_f/"
MARGIN=3   # slices either side of a blank-frame run to also treat as degraded (the classifier's partial-data ramp)
cls=np.load(D+"cryo_frame_cls.npy",mmap_mode="r"); z0=json.load(open(D+"frame.json"))["z0"]; n,H,W=cls.shape; OFF=110
sk=nib.load(S+"vhf_ts/skin_ct.nii.gz"); skd=np.asarray(sk.dataobj); zS0=float(sk.affine[2,3])


def raw_t(k):
    c = np.asarray(cls[k]) > 0; c[:60] = False   # the Kodak ruler / label rows
    t = ndi.binary_fill_holes(ndi.binary_closing(c, iterations=3)); l, m = ndi.label(t)
    if m:
        sz = ndi.sum(np.ones_like(l), l, np.arange(1, m + 1))
        t = np.isin(l, np.arange(1, m + 1)[sz >= 2000])
    return t


def interp_mask(t_lo, t_hi, w):
    d_lo = ndi.distance_transform_edt(~t_lo) - ndi.distance_transform_edt(t_lo)
    d_hi = ndi.distance_transform_edt(~t_hi) - ndi.distance_transform_edt(t_hi)
    return (1 - w) * d_lo + w * d_hi <= 0


# Q74: find fully-blank classification frames within the "photographs used" band and interpolate across them.
blank = np.array([not (np.asarray(cls[k])[60:] > 0).any() for k in range(n)])
active = np.array([z0 + k >= -950 for k in range(n)])
gap = blank & active
interp_span = ndi.binary_dilation(gap, structure=np.ones(2 * MARGIN + 1, bool)) if gap.any() else gap
interp_t = {}
k = 0
while k < n:
    if interp_span[k]:
        j = k
        while j < n and interp_span[j]:
            j += 1
        a, b = k, j - 1
        if a > 0 and b < n - 1:   # need a real frame on both sides to interpolate from
            t_lo, t_hi = raw_t(a - 1), raw_t(b + 1)
            for kk in range(a, b + 1):
                interp_t[kk] = interp_mask(t_lo, t_hi, (kk - (a - 1)) / ((b + 1) - (a - 1)))
            print(f"Q74: interpolated silhouette for k={a}..{b} (RAS z {z0+a}..{z0+b}, atlas_y "
                  f"{z0+a+885.229:.1f}..{z0+b+885.229:.1f}) across a blank-frame gap", flush=True)
        k = j
    else:
        k += 1

out=np.zeros((n,H,W),np.uint8); ncryo=0; nct=0
for k in range(n):
    t = interp_t[k] if k in interp_t else raw_t(k)
    kk=int(round(z0+k-zS0)); ctm=np.zeros((H,W),bool)
    if 0<=kk<skd.shape[2]: ctm[:,OFF:OFF+480]=ndi.zoom(skd[:,:,kk],480/512,order=0).T>0
    if z0+k<-950: t=np.zeros_like(t)   # below the arms (RAS z < -950) the CT silhouette is exact; the photographs would add a registration rim along the legs
    u=t|ctm; out[k]=u; ncryo+=int((t&~ctm).sum()); nct+=int(ctm.sum())
print("CT silhouette voxels",nct,"added from the photographs",ncryo,"(%.1f %%)"%(100*ncryo/max(nct,1)),flush=True)
aff=np.array([[-1,0,0,350],[0,-1,0,240],[0,0,1,z0],[0,0,0,1]],float)
nib.save(nib.Nifti1Image(np.ascontiguousarray(out.transpose(2,1,0)),aff),S+"vhf_ts/skin_union.nii.gz"); print("SKIN_UNION_DONE")
