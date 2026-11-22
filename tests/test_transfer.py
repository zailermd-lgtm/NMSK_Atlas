"""Cross-subject transfer: bundle round trip, bone frames and the affine that maps one bone box onto another."""
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts.transfer import bundle_io, bone_frames, lean_envelope as le  # noqa: E402


def _box_mesh(size=(10.0, 40.0, 6.0), centre=(0.0, 0.0, 0.0)):
    sx, sy, sz = [s / 2 for s in size]
    v = np.array([[x, y, z] for x in (-sx, sx) for y in (-sy, sy) for z in (-sz, sz)], np.float32) + np.array(centre, np.float32)
    f = np.array([[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5], [0, 4, 5], [0, 5, 1],
                  [2, 3, 7], [2, 7, 6], [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]], np.int32)
    return v, f


def test_bundle_round_trip(tmp_path):
    v, f = _box_mesh()
    q = np.rint(v / 0.25).astype(np.int16)
    blob = q.tobytes() + f.astype(np.uint16).tobytes()
    bundle = {"quantum_mm": 0.25, "structures": [{"id": "femur_r", "cat": "bone", "side": "right",
                                                   "nv": 8, "nf": 12, "subject": "t"}]}
    (tmp_path / "bundle.json").write_text(json.dumps(bundle)); (tmp_path / "bundle.bin").write_bytes(blob)
    b2, blob2 = bundle_io.read_bundle_dir(tmp_path)
    m = bundle_io.meshes_by_id(b2, blob2)
    assert np.allclose(m["femur_r"]["v"], v) and m["femur_r"]["f"].shape == (12, 3)
    assert abs(bundle_io.mesh_volume_cm3(m["femur_r"]["v"], m["femur_r"]["f"]) - 10 * 40 * 6 / 1000) < 1e-6
    html = ('<script id="bundle-json" type="application/json">' + json.dumps(bundle) + '</script>'
            '<script id="bundle-b64" type="text/plain">' + __import__("base64").b64encode(blob).decode() + '</script>')
    (tmp_path / "v.html").write_text(html)
    b3, blob3 = bundle_io.read_bundle_html(tmp_path / "v.html")
    assert blob3 == blob and b3["structures"][0]["id"] == "femur_r"


def test_bone_frame_long_axis_and_extents():
    rng = np.random.default_rng(0)
    pts = rng.uniform(-1, 1, (4000, 3)) * np.array([10, 200, 15])       # long along atlas Y
    fr = bone_frames.bone_frame(pts)
    assert abs(abs(fr["R"][1, 0]) - 1) < 0.02 and fr["R"][1, 0] > 0      # first axis = +Y (superior)
    assert 380 < fr["ext"][0] < 400 and np.linalg.det(fr["R"]) > 0


def test_bone_affine_maps_source_box_onto_target_box():
    rng = np.random.default_rng(1)
    src = rng.uniform(-1, 1, (3000, 3)) * np.array([12, 240, 10]) + np.array([100, -200, 0])
    dst = rng.uniform(-1, 1, (3000, 3)) * np.array([11, 210, 9]) + np.array([90, -180, 5])
    fs, fd = bone_frames.bone_frame(src), bone_frames.bone_frame(dst)
    A, t = bone_frames.bone_affine(fs, fd)
    moved = bone_frames.apply(A, t, src)
    fm = bone_frames.bone_frame(moved)
    assert np.allclose(fm["centre"], fd["centre"], atol=2.0)
    assert np.allclose(fm["ext"], fd["ext"], rtol=0.03)
    # uniform (truncated bone): one scale only
    A2, _ = bone_frames.bone_affine(fs, fd, uniform=True)
    s = np.linalg.svd(A2, compute_uv=False)
    assert np.allclose(s, s[0], rtol=1e-6)


def test_lean_envelope_keeps_radial_fraction():
    # source: muscle points on a cylinder of radius 80 about the femur (0,0); target compartment radius 40
    th = np.linspace(-np.pi, np.pi, 720, endpoint=False)
    src_tab = {float(y): {"centre": [0.0, 0.0], "bone": "femur", "r": [80.0] * le.NBINS} for y in np.arange(-20, -400, -10)}
    dst_tab = {float(y): {"centre": [10.0, 5.0], "bone": "femur", "r": [40.0] * le.NBINS} for y in np.arange(-20, -400, -10)}
    v_src = np.stack([40 * np.cos(th), np.full_like(th, -200.0), 40 * np.sin(th)], 1)      # at half radius
    v_bone = v_src + np.array([10.0, 0.0, 5.0])                                            # bone-driven result
    out, frac = le.apply_envelope(v_src, v_bone, src_tab, dst_tab)
    r = np.hypot(out[:, 0] - 10, out[:, 2] - 5)
    assert abs(frac - 0.5) < 1e-6 and np.allclose(r, 20.0, atol=1e-6)
    assert le.frame_y_correction(-300, {"legs": {"d_mm": -70, "valid_below_y": -140},
                                        "torso": {"d_mm": 0, "valid_above_y": -40}}) == -70
