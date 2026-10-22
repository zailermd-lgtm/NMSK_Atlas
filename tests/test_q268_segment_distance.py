"""Q268 (item 2): the needle tool's exact segment -> triangle / mesh distance math (clinical/needle_tool.js, pure exports),
checked in node against an INDEPENDENT computation: hand-worked cases, and trimesh's closest_point on densely sampled
segments (an upper bound on the true segment distance, tight to half the sample step). The tool measures and displays;
these tests pin the measurement, nothing here judges a distance."""
from __future__ import annotations
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
MODULE = REPO / "clinical" / "needle_tool.js"
NODE = shutil.which("node")
trimesh = pytest.importorskip("trimesh")


def js(expr: str):
    if not NODE:
        pytest.skip("node not available")
    code = f"const M = require({json.dumps(str(MODULE))}); process.stdout.write(JSON.stringify({expr}));"
    return json.loads(subprocess.run([NODE, "-e", code], check=True, capture_output=True, text=True).stdout)


TRI = ([-1.0, -1.0, 0.0], [1.0, -1.0, 0.0], [0.0, 1.0, 0.0])   # in the z = 0 plane


def seg_tri(a, b, tri=TRI):
    return js(f"M.segTriDist({json.dumps(a)}, {json.dumps(b)}, {json.dumps(tri[0])}, {json.dumps(tri[1])}, {json.dumps(tri[2])})")


def test_hand_worked_cases():
    assert seg_tri([0, 0, 5], [0, 0, 10]) == pytest.approx(5.0)                 # endpoint above the face
    assert seg_tri([0, 0, -1], [0, 0, 1]) == 0.0                                # crosses the face
    assert seg_tri([0, 0, 2], [0, 0, 2]) == pytest.approx(2.0)                  # degenerate segment = point distance
    assert seg_tri([5, 0, 0], [10, 0, 0]) == pytest.approx(np.sqrt(17.0))       # in-plane: nearest is vertex b (1, -1, 0) from the endpoint (5, 0, 0)
    assert seg_tri([0, 0, 3], [0, 0, 9]) == seg_tri([0, 0, 9], [0, 0, 3])       # symmetric in the segment's direction
    assert seg_tri([3, 3, 1], [3, 3, 1]) == pytest.approx(js("M.pointTriDist([3,3,1],[-1,-1,0],[1,-1,0],[0,1,0])"))   # degenerate = point case


def test_point_triangle_matches_trimesh():
    rng = np.random.default_rng(268)
    tri = rng.normal(size=(3, 3)) * 20
    pts = rng.normal(size=(300, 3)) * 30
    mesh = trimesh.Trimesh(vertices=tri, faces=[[0, 1, 2]], process=False)
    _, ref, _ = trimesh.proximity.closest_point(mesh, pts)
    got = js(f"{json.dumps(pts.tolist())}.map(function(p){{ return M.pointTriDist(p, {json.dumps(tri[0].tolist())}, {json.dumps(tri[1].tolist())}, {json.dumps(tri[2].tolist())}); }})")
    assert np.allclose(got, ref, atol=1e-6)


def test_segment_triangle_matches_densely_sampled_trimesh():
    rng = np.random.default_rng(2680)
    n_step = 2000
    worst = 0.0
    for _ in range(120):
        tri = rng.normal(size=(3, 3)) * 20
        a, b = rng.normal(size=3) * 30, rng.normal(size=3) * 30
        mesh = trimesh.Trimesh(vertices=tri, faces=[[0, 1, 2]], process=False)
        t = np.linspace(0, 1, n_step + 1)[:, None]
        samples = a + t * (b - a)
        _, d, _ = trimesh.proximity.closest_point(mesh, samples)
        ref = float(d.min())                                        # upper bound; within step / 2 of the true minimum
        step = float(np.linalg.norm(b - a)) / n_step
        got = seg_tri(a.tolist(), b.tolist(), [tri[0].tolist(), tri[1].tolist(), tri[2].tolist()])
        assert got <= ref + 1e-6, (got, ref)                        # an exact minimum can never exceed the sampled one
        assert got >= ref - step / 2 - 1e-6, (got, ref, step)       # ... nor fall below it by more than the sampling error
        worst = max(worst, ref - got)
    assert worst < 0.05


def test_mesh_distance_prune_equals_brute_force_and_trimesh():
    rng = np.random.default_rng(26800)
    sphere = trimesh.creation.icosphere(subdivisions=3, radius=6.0)
    sphere.apply_translation([10, 4, -3])
    pos = sphere.vertices.astype(np.float32).ravel().tolist()
    idx = sphere.faces.ravel().tolist()
    for _ in range(12):
        a = rng.normal(size=3) * 25
        b = a + rng.normal(size=3) * 40
        got = js(f"M.meshSegDist({json.dumps(pos)}, {json.dumps(idx)}, {json.dumps(a.tolist())}, {json.dumps(b.tolist())}, 1e9)")
        brute = js(f"(function(){{ var P={json.dumps(pos)}, I={json.dumps(idx)}, best=Infinity; for (var f=0; f<I.length; f+=3){{ var t=[0,1,2].map(function(k){{ var v=I[f+k]*3; return [P[v],P[v+1],P[v+2]]; }});"
                   f" best=Math.min(best, M.segTriDist({json.dumps(a.tolist())}, {json.dumps(b.tolist())}, t[0], t[1], t[2])); }} return best; }})()")
        assert got["d"] == pytest.approx(brute, abs=1e-9)
        t = np.linspace(0, 1, 4001)[:, None]
        _, d, _ = trimesh.proximity.closest_point(sphere, a + t * (b - a))
        step = float(np.linalg.norm(b - a)) / 4000
        if got["d"] > 0:
            assert got["d"] <= d.min() + 1e-5 and got["d"] >= d.min() - step / 2 - 1e-5
        else:                                                       # crosses the sphere: the sampled minimum is also ~0
            assert d.min() < step


def test_mesh_distance_bound_and_empty():
    tri = [-1, -1, 0, 1, -1, 0, 0, 1, 0]
    assert js(f"M.meshSegDist({tri}, [0,1,2], [0,0,3], [0,0,4], 2.5)") == {"d": None, "tri": -1}   # Infinity -> null in JSON: nothing under the bound
    assert js(f"M.meshSegDist({tri}, [0,1,2], [0,0,3], [0,0,4], 3.5)")["d"] == pytest.approx(3.0)


def test_candidate_ranking_prefers_clearance_then_length():
    c = [{"minD": 10.0, "L": 50}, {"minD": 10.6, "L": 70}, {"minD": 4.0, "L": 20}, {"minD": 9.8, "L": 30}]
    out = js(f"M.rankCandidates({json.dumps(c)}, 1.0).map(function(x){{ return [x.minD, x.L]; }})")
    assert out == [[9.8, 30], [10.0, 50], [10.6, 70], [4.0, 20]]  # the three within 1 mm of the best clearance: shortest first; the 4 mm one last


def test_cone_directions_are_unit_and_inside_the_cone():
    dirs = np.array(js("M.coneDirs([0,0,1], 35*Math.PI/180, 48)"))
    assert dirs.shape == (49, 3)
    assert np.allclose(np.linalg.norm(dirs, axis=1), 1, atol=1e-9)
    assert np.all(dirs[:, 2] >= np.cos(np.radians(35)) - 1e-9)
    assert np.allclose(dirs[0], [0, 0, 1])
