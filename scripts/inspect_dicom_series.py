"""Read one DICOM series' per-slice geometry and group it by pixel spacing / orientation.

    python3 scripts/inspect_dicom_series.py [--root DIR] UUID [UUID ...]

Prints, per group: spacing, orientation, slice count, z-range, the set of
inter-slice steps (duplicates show as 0, gaps as >1) and the first slice's
corner. Writes `DIR/dcm/<UUID>.meta.json`, which stack_dicom_series.py reads.
Used to find that the Visible Human frozen CT series mix three
reconstruction fields of view and that its three blocks were scanned in
separate table sessions (their z ranges overlap and do not register)."""
import pydicom, glob, os, sys, collections, json
args=sys.argv[1:]; S=os.path.dirname(os.path.abspath(__file__))
if args and args[0]=="--root": S=args[1]; args=args[2:]
for u in args:
    fs=sorted(glob.glob(f"{S}/dcm/{u}/*"))
    rows=[]
    for f in fs:
        ds=pydicom.dcmread(f,stop_before_pixels=True)
        rows.append(dict(f=os.path.basename(f),z=float(ds.ImagePositionPatient[2]),x=float(ds.ImagePositionPatient[0]),y=float(ds.ImagePositionPatient[1]),
            ps=round(float(ds.PixelSpacing[0]),4),iop=tuple(round(float(v),3) for v in ds.ImageOrientationPatient),
            rows=int(ds.Rows),cols=int(ds.Columns),inst=int(getattr(ds,'InstanceNumber',-1)),
            rd=float(getattr(ds,'ReconstructionDiameter',0)),tilt=float(getattr(ds,'GantryDetectorTilt',0)),
            desc=str(getattr(ds,'SeriesDescription','')),kvp=getattr(ds,'KVP',None),ri=float(getattr(ds,'RescaleIntercept',0)),rs=float(getattr(ds,'RescaleSlope',1))))
    json.dump(rows,open(f"{S}/dcm/{u}.meta.json","w"))
    g=collections.defaultdict(list)
    for r in rows: g[(r['ps'],r['iop'],r['tilt'],r['rows'],r['cols'])].append(r)
    print("==",u,len(rows))
    for k,v in sorted(g.items(),key=lambda kv:-max(r['z'] for r in kv[1])):
        zs=sorted(r['z'] for r in v); dz=sorted(set(round(b-a,2) for a,b in zip(zs,zs[1:])))
        print(" ps",k[0],"iop",k[1],"tilt",k[2],"n",len(v),"z",zs[0],zs[-1],"dz",dz[:6],"xy0",v[0]['x'],v[0]['y'],"ri",v[0]['ri'])
