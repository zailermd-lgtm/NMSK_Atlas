"""Q296: minimal legacy-VTK POLYDATA reader (ASCII and BINARY/big-endian), POINTS + POLYGONS / TRIANGLE_STRIPS.

The Open Anatomy atlases ship their models as legacy `.vtk` polydata written by 3D Slicer. Neither `vtk` nor `meshio`
is installed in this container (and 3D Slicer cannot be installed: `/` has ~2.5 GB free), so the few fields the
atlases actually use are parsed here. Downloads are untrusted data: this reader never evaluates anything from the
file, only reads fixed-width numeric blocks whose lengths the header declares.
"""
from __future__ import annotations

import numpy as np


def read_polydata(path):
    """-> (V (n,3) float64, F (m,3) int64). Polygons are fan-triangulated; triangle strips are unrolled."""
    raw = open(path, "rb").read()
    hdr, pos = [], 0
    while len(hdr) < 4:
        e = raw.index(b"\n", pos); hdr.append(raw[pos:e].decode("ascii", "replace").strip()); pos = e + 1
    if not hdr[0].lower().startswith("# vtk datafile"):
        raise ValueError(f"not a legacy VTK file: {path}")
    binary = hdr[2].upper().startswith("BINARY")
    if "POLYDATA" not in hdr[3].upper():
        raise ValueError(f"not POLYDATA: {hdr[3]}")
    V, F = None, None
    while pos < len(raw):
        e = raw.find(b"\n", pos)
        if e < 0:
            break
        line = raw[pos:e].decode("ascii", "replace").strip(); pos = e + 1
        if not line:
            continue
        up = line.upper(); tok = line.split()
        if up.startswith("POINTS"):
            n = int(tok[1]); dt = {"float": ">f4", "double": ">f8"}[tok[2].lower()]
            if binary:
                V = np.frombuffer(raw, dt, n * 3, pos).reshape(-1, 3).astype(np.float64); pos += n * 3 * np.dtype(dt).itemsize
            else:
                vals = []
                while len(vals) < n * 3:
                    e = raw.find(b"\n", pos); vals += raw[pos:e].split(); pos = e + 1
                V = np.array(vals[:n * 3], float).reshape(-1, 3)
        elif up.startswith(("POLYGONS", "TRIANGLE_STRIPS")):
            n, size = int(tok[1]), int(tok[2])
            if binary:
                a = np.frombuffer(raw, ">i4", size, pos).astype(np.int64); pos += size * 4
            else:
                vals = []
                while len(vals) < size:
                    e = raw.find(b"\n", pos); vals += raw[pos:e].split(); pos = e + 1
                a = np.array(vals[:size], np.int64)
            tris, i = [], 0
            for _ in range(n):
                k = int(a[i]); c = a[i + 1:i + 1 + k]; i += 1 + k
                if up.startswith("POLYGONS"):
                    tris += [(c[0], c[j], c[j + 1]) for j in range(1, len(c) - 1)]
                else:
                    tris += [(c[j], c[j + 1], c[j + 2]) if j % 2 == 0 else (c[j + 1], c[j], c[j + 2]) for j in range(len(c) - 2)]
            Fn = np.array(tris, np.int64) if tris else np.zeros((0, 3), np.int64)
            F = Fn if F is None else np.vstack([F, Fn])
        elif up.startswith(("POINT_DATA", "CELL_DATA", "LINES", "VERTICES")):
            break
    if V is None:
        raise ValueError(f"no POINTS in {path}")
    return V, (F if F is not None else np.zeros((0, 3), np.int64))
