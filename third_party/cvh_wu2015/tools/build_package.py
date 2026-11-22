#!/usr/bin/env python3
"""Convert the OBJ + structures.tsv written by an RHAdobeMeshResource decoder into
binary little-endian PLY (float32, mm) plus structures.json (names, volumes, bounding boxes, checks).

Usage: python3 -I build_package.py DECODER_OUT_DIR OUT_DIR
(DECODER_OUT_DIR holds structures.tsv and the *.obj written by the upstream decoder, see ../NOTICE.md.)
Own code, no third-party code. Checks are computed here, independently of the decoder.
"""
import json, os, re, struct, sys
import numpy as np

src, out = sys.argv[1], sys.argv[2]
os.makedirs(os.path.join(out, 'meshes'), exist_ok=True)
rows = [l.rstrip('\n').split('\t') for l in open(os.path.join(src, 'structures.tsv'), encoding='utf-8')][1:]


def load(p):
    V, F = [], []
    for l in open(p, encoding='utf-8'):
        if l.startswith('v '):
            V.append([float(x) for x in l.split()[1:4]])
        elif l.startswith('f '):
            F.append([int(t.split('/')[0]) - 1 for t in l.split()[1:4]])
    return np.array(V, np.float64), np.array(F, np.int64)


def checks(V, F):
    q = np.round(V / 1e-3).astype(np.int64)
    _, inv = np.unique(q, axis=0, return_inverse=True)
    inv = inv.ravel()
    W = np.zeros((inv.max() + 1, 3)); W[inv] = V
    G = inv[F]
    G = G[(G[:, 0] != G[:, 1]) & (G[:, 1] != G[:, 2]) & (G[:, 0] != G[:, 2])]
    n = len(W) + 1
    d = np.concatenate([G[:, [0, 1]], G[:, [1, 2]], G[:, [2, 0]]])
    k = d[:, 0] * n + d[:, 1]
    uk, c = np.unique(k, return_counts=True)
    s = set(uk.tolist())
    open_e = sum(1 for x in uk.tolist() if (x % n) * n + x // n not in s)
    nonman = int((c > 1).sum())
    a, b, cc = W[G[:, 0]], W[G[:, 1]], W[G[:, 2]]
    vol = float(np.einsum('ij,ij->i', a, np.cross(b, cc)).sum() / 6000.0)
    return open_e, nonman, vol


def write_ply(path, name, V, F):
    hdr = ('ply\nformat binary_little_endian 1.0\ncomment structure: %s\ncomment units: mm\n'
           'comment source: Wu et al. 2015 PLoS ONE doi:10.1371/journal.pone.0132226 S3 Fig (CC BY 4.0)\n'
           'element vertex %d\nproperty float x\nproperty float y\nproperty float z\n'
           'element face %d\nproperty list uchar int vertex_indices\nend_header\n') % (name, len(V), len(F))
    with open(path, 'wb') as f:
        f.write(hdr.encode('ascii', 'replace'))
        f.write(V.astype('<f4').tobytes())
        rec = np.zeros(len(F), dtype=[('n', 'u1'), ('i', '<i4', 3)])
        rec['n'] = 3; rec['i'] = F
        f.write(rec.tobytes())


items = []
for r in rows:
    if len(r) < 6:
        continue
    fn, raw, nv, nt, enc, consumed = r[0], r[1], int(r[2]), int(r[3]), r[4], r[5]
    V, F = load(os.path.join(src, fn))
    assert len(V) == nv and len(F) == nt and F.min() >= 0 and F.max() < len(V)
    name = raw.strip().replace('’', "'")
    idx = int(fn[:2])
    slug = re.sub(r'[^A-Za-z0-9]+', '_', name).strip('_')
    ply = '%02d_%s.ply' % (idx, slug)
    write_ply(os.path.join(out, 'meshes', ply), name, V, F)
    open_e, nonman, vol = checks(V, F)
    closed = open_e == 0 and nonman == 0
    items.append(dict(
        index=idx, name=name, name_original_raw=raw, file='meshes/' + ply, units='mm',
        vertices=nv, triangles=nt, bbox_min_mm=V.min(0).round(3).tolist(), bbox_max_mm=V.max(0).round(3).tolist(),
        extent_mm=(V.max(0) - V.min(0)).round(3).tolist(), centroid_mm=V.mean(0).round(3).tolist(),
        decoder_payload_consumed=consumed, decoder_int_encodings=enc,
        open_edges_after_welding=open_e, nonmanifold_edges=nonman, closed_manifold=closed,
        signed_volume_cm3=round(vol, 3),
        volume_cm3=round(abs(vol), 3) if closed else None,
        volume_note=('closed surface: volume valid' if closed else
                     'open or non-manifold sheet: signed volume is NOT a tissue volume, do not use')))
json.dump(dict(source='Wu et al. 2015 PLoS ONE 10(8):e0132226, S3_Fig.pdf (Figshare item 1519992, file 2224397)',
               license='CC BY 4.0', units='mm', frame='see README.md', structures=items),
          open(os.path.join(out, 'structures.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
print(len(items), 'structures;', sum(i['vertices'] for i in items), 'vertices;', sum(i['triangles'] for i in items), 'triangles')
