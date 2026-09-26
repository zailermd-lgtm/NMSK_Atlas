"""Stack a DICOM CT series whose slices do not share one pixel spacing.

    python3 scripts/stack_dicom_series.py UUID OUT.nii.gz [--ps 0.9375] [--only-ps 0.5273]
                                          [--zmin Z] [--xybox x0 x1 y0 y1]

Written for the Visible Human male frozen CT on IDC (series 5d409385-...),
which was reconstructed with a 270 mm field of view over the head, 400 mm
over the upper neck and 480 mm over the trunk. dcm2niix stacks it as one
volume at one spacing, which draws the head 1.8x too large. This reads the
per-slice metadata written by inspect_dicom_series.py (`dcm/<UUID>.meta.json`)
and resamples every spacing group onto one grid in the scanner's own
millimetres, finest group winning where they overlap, missing slices
interpolated from their neighbours. It assumes axial slices with identity
orientation (checked by inspect_dicom_series.py) and writes RAS NIfTI.
Expects the DICOMs under `dcm/<UUID>/` next to the meta file (set by --root).
Nothing here is anatomy."""
import pydicom, json, os, sys, numpy as np, nibabel as nib, argparse
from scipy.ndimage import map_coordinates
ap=argparse.ArgumentParser(); ap.add_argument("uuid"); ap.add_argument("out"); ap.add_argument("--ps",type=float,default=0.9375); ap.add_argument("--only-ps",type=float,default=None); ap.add_argument("--zmin",type=float,default=None); ap.add_argument("--xybox",type=float,nargs=4,default=None,help="LPS x0 x1 y0 y1 crop")
ap.add_argument("--root",default=os.path.dirname(os.path.abspath(__file__)),help="directory holding dcm/<UUID>/ and dcm/<UUID>.meta.json")
a=ap.parse_args(); S=a.root
meta=json.load(open(f"{S}/dcm/{a.uuid}.meta.json"))
if a.only_ps: meta=[r for r in meta if abs(r['ps']-a.only_ps)<1e-3]
if a.zmin is not None: meta=[r for r in meta if r['z']>=a.zmin]
# dedupe z within a group (keep first), sort by z
groups={}
for r in meta: groups.setdefault(r['ps'],{}).setdefault(r['z'],r)
# global extents (LPS world)
xmin=min(r['x'] for r in meta); ymin=min(r['y'] for r in meta)
xmax=max(r['x']+r['ps']*(r['cols']-1) for r in meta); ymax=max(r['y']+r['ps']*(r['rows']-1) for r in meta)
zs=sorted(set(r['z'] for r in meta)); z0,z1=zs[0],zs[-1]
if a.xybox: xmin,xmax,ymin,ymax=a.xybox
nx=int(round((xmax-xmin)/a.ps))+1; ny=int(round((ymax-ymin)/a.ps))+1; nz=int(round(z1-z0))+1
print("grid",nx,ny,nz,"x",xmin,xmax,"y",ymin,ymax,"z",z0,z1,flush=True)
out=np.full((nx,ny,nz),-1024,np.float32)
# fill from coarsest to finest so finest wins
for ps in sorted(groups,reverse=True):
    g=groups[ps]; gz=sorted(g); vol=np.zeros((g[gz[0]]['cols'],g[gz[0]]['rows'],len(gz)),np.float32)
    for k,z in enumerate(gz):
        r=g[z]; ds=pydicom.dcmread(f"{S}/dcm/{a.uuid}/{r['f']}"); vol[:,:,k]=(ds.pixel_array.astype(np.float32)*r['rs']+r['ri']).T
    gx0,gy0=g[gz[0]]['x'],g[gz[0]]['y']
    # target voxels covered by this group
    ix0=int(np.ceil((gx0-xmin)/a.ps)); ix1=int(np.floor((gx0+ps*(vol.shape[0]-1)-xmin)/a.ps))
    iy0=int(np.ceil((gy0-ymin)/a.ps)); iy1=int(np.floor((gy0+ps*(vol.shape[1]-1)-ymin)/a.ps))
    iz0=int(round(gz[0]-z0)); iz1=int(round(gz[-1]-z0))
    ix0,ix1=max(ix0,0),min(ix1,nx-1); iy0,iy1=max(iy0,0),min(iy1,ny-1)
    print("group ps",ps,"n",len(gz),"z",gz[0],gz[-1],"-> target",ix0,ix1,iy0,iy1,iz0,iz1,flush=True)
    X=(np.arange(ix0,ix1+1)*a.ps+xmin-gx0)/ps; Y=(np.arange(iy0,iy1+1)*a.ps+ymin-gy0)/ps
    Z=np.interp(np.arange(iz0,iz1+1)+z0, gz, np.arange(len(gz)))  # handles missing slices by interpolation
    for zi,zc in zip(range(iz0,iz1+1),Z):
        cx,cy=np.meshgrid(X,Y,indexing="ij")
        sl=map_coordinates(vol,[cx.ravel(),cy.ravel(),np.full(cx.size,zc)],order=1,mode="nearest").reshape(cx.shape)
        out[ix0:ix1+1,iy0:iy1+1,zi]=sl
    del vol
# LPS -> RAS affine: world_x = -(xmin + i*ps), world_y = -(ymin + j*ps), world_z = z0 + k
aff=np.array([[-a.ps,0,0,-xmin],[0,-a.ps,0,-ymin],[0,0,1.0,z0],[0,0,0,1]])
img=nib.Nifti1Image(np.round(out).astype(np.int16),aff); img.header.set_xyzt_units("mm"); nib.save(img,a.out); print("saved",a.out,out.shape,flush=True)
