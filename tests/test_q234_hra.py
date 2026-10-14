"""Q234: HRA vagina / ligaments / breast objects (sources, derived meshes), the placement helpers (thoracic registration, column fit, rim push, rest on bone), the honesty of the badges, the template class."""
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest
import trimesh

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
from scripts.anatomy.q234 import chestfit as C, hra_q234 as Q, place as PL  # noqa: E402

INFO = REPO / "data/derived/Q234_hra_meshes.json"
NPZ = REPO / "data/derived/Q234_hra_meshes.npz"
PELVIC = ["vagina", "round_ligament_uterus_l", "round_ligament_uterus_r", "uterosacral_ligament_l", "uterosacral_ligament_r", "cardinal_ligament_uterus_l", "cardinal_ligament_uterus_r", "broad_ligament_uterus",
          "ovarian_ligament_l", "ovarian_ligament_r", "suspensory_ligament_ovary_l", "suspensory_ligament_ovary_r", "mesosalpinx_l", "mesosalpinx_r", "mesovarium_l", "mesovarium_r"]
BREAST = [f"{k}_{s}" for s in "lr" for k in ("breast_fat", "mammary_gland", "lactiferous_ducts", "areola", "nipple", "breast_suspensory_ligaments")]


def test_sources_manifest_and_copies():
    m = json.loads((REPO / "third_party/hra_vh_f/SOURCES_Q234.json").read_text())
    assert m["commit"] == Q.COMMIT and "ccf-3d-reference-object-library" in m["repository"]
    assert set(m["files"]) == set(Q.FILES)
    for k, v in m["files"].items():
        assert v["sha256"] == Q.FILES[k][1] and v["url"].startswith("https://raw.githubusercontent.com/hubmapconsortium/ccf-3d-reference-object-library/" + Q.COMMIT)
        p = REPO / "third_party/hra_vh_f" / f"{k}.glb"
        if v["copied_in_repo"]:
            assert hashlib.sha256(p.read_bytes()).hexdigest() == v["sha256"], k      # the copied GLBs are the library files, unchanged
    md = (REPO / "third_party/hra_vh_f/mammary-gland-female-left.md").read_text()
    assert "sculpted from scratch" in md and "CC BY 4.0" in md.replace("Creative Commons Attribution 4.0 International (", "CC BY 4.0 (") or "Creative Commons Attribution 4.0" in md


def test_notice_attribution():
    n = (REPO / "third_party/hra_vh_f/NOTICE.md").read_text()
    for t in ("Q234", "CC BY 4.0", "VH_F_vagina", "Ligaments_Uterus_Ovaries", "mammary_gland", "sculpted", "NOT data from the Visible Human Female", "f1a3a63f110e27ff0736047d52d04dba5d3087f9"):
        assert t in n, t


def test_derived_meshes_table():
    info = json.loads(INFO.read_text())["structures"]
    assert sorted(info) == sorted(PELVIC + BREAST)
    z = np.load(NPZ)
    tri = 0
    for sid, r in info.items():
        V, F = z[sid + "_v"], z[sid + "_f"]
        assert len(V) < 65000 and F.max() < len(V) and r["triangles"] == len(F)          # 16-bit indices of the bundle / page format
        tri += len(F)
        assert r["decimation_deviation_mm"]["p95"] < 2.0, sid
        if r["mode"] == "closed envelope":
            m = trimesh.Trimesh(V, F, process=False)
            assert m.is_watertight and len(m.split(only_watertight=False)) == 1 and r["volume_cm3"] == pytest.approx(abs(m.volume) / 1000, rel=0.01, abs=0.006), sid
    assert tri < 110000                                  # modest bundle growth
    assert info["vagina"]["volume_cm3"] == pytest.approx(13.7, abs=0.3)
    assert info["breast_fat_l"]["volume_cm3"] == pytest.approx(739.5, abs=3) and info["breast_fat_r"]["volume_cm3"] == pytest.approx(754.5, abs=3)
    assert info["round_ligament_uterus_l"]["cat"] == "ligament" and info["nipple_l"]["region"] == "breast" and info["nipple_l"]["side"] == "left"
    # HRA frame: metres in the library, mm here, +x patient left -> -X (the atlas frame): the left breast lies at negative X, anterior (+Z), above the pelvis
    Vl = z["breast_fat_l_v"]; Vr = z["breast_fat_r_v"]
    assert Vl[:, 0].mean() < -40 and Vr[:, 0].mean() > 40 and Vl[:, 1].mean() > 380 and Vl[:, 2].mean() > 20


def test_thorax_registration_recovers_a_known_transform():
    rng = np.random.default_rng(1)
    A = rng.normal(size=(4000, 3)) * [25, 80, 18]
    th = 0.12
    R = np.array([[np.cos(th), 0, np.sin(th)], [0, 1, 0], [-np.sin(th), 0, np.cos(th)]])
    B = 0.93 * A @ R.T + np.array([5.0, -20.0, 30.0])
    (s, R2, t), reg = PL.thorax_register(A, B)
    assert s == pytest.approx(0.93, abs=0.01) and np.abs(R2 - R).max() < 0.02 and np.abs(t - [5, -20, 30]).max() < 1.0
    assert reg["residual_mm"]["median"] < 0.5 and reg["det_R"] == pytest.approx(1.0, abs=1e-3)


class FakeFields:
    """skin interior: z < 100 inside |x|,|y| < 200; chest wall: z < 50; signed distances in mm"""
    lo = np.zeros(3)

    def column_tops(self, xs, ys):
        return np.full((len(xs), len(ys)), 100.0), np.full((len(xs), len(ys)), 50.0)

    def at(self, name, pts):
        z = np.asarray(pts)[:, 2]
        return (z - 100.0) if name == "skin" else (50.0 - z) * 1.0 if name in ("wall", "pec", "bone", "muscle") else None


def test_column_warp_compresses_into_the_space_between_wall_and_skin():
    rng = np.random.default_rng(2)
    ref = np.column_stack([rng.uniform(-40, 40, 400000), rng.uniform(-40, 40, 400000), rng.uniform(55, 150, 400000)])
    W = C.ColumnWarp(FakeFields(), ref, m_wall=1.0, m_skin=2.5, rest_gap=0.0)
    Y = W(ref)
    assert Y[:, 2].min() >= 51.0 - 1e-6 and Y[:, 2].max() <= 97.5 + 1e-6               # between wall + margin and skin - margin
    assert np.allclose(Y[:, :2], ref[:, :2])                                           # anteroposterior only
    # order along z is preserved inside a column
    i = np.argsort(ref[:, 2]); j = np.argsort(Y[:, 2])
    assert np.corrcoef(ref[:, 2], Y[:, 2])[0, 1] > 0.99
    assert W.stats["ratio_median"] < 0.6 and W.stats["room_min_mm"] > 0


def test_push_field_moves_overhanging_vertices_inside_and_leaves_the_rest():
    class Sph:
        lo = np.zeros(3)
        def at(self, name, pts):          # sphere radius 30 around the origin, skin interior = ball; no wall
            r = np.linalg.norm(np.asarray(pts), axis=1)
            return r - 30.0 if name == "skin" else np.full(len(pts), 99.0)
    rng = np.random.default_rng(3)
    P = rng.normal(size=(500, 3)); P = P / np.linalg.norm(P, axis=1, keepdims=True) * rng.uniform(10, 36, 500)[:, None]
    Y, hist = C.push_field(Sph(), {"a": P}, [("skin", 1.0, "inside")], sigma=4.0, iters=40)
    r0, r1 = np.linalg.norm(P, axis=1), np.linalg.norm(Y["a"], axis=1)
    assert r1.max() <= 29.0 + 0.25 and hist[-1][1] == 0 or r1.max() <= 29.5
    assert np.abs(Y["a"][r0 < 15] - P[r0 < 15]).max() < 0.2                         # far from the rim: untouched


def test_rest_on_bone_moves_buried_vertices_out_along_the_normal():
    box = trimesh.creation.box(extents=[40, 40, 40])
    pts = np.array([[0, 0, 19.2], [0, 0, 25.0], [5, 5, 18.0], [30, 0, 0.0]])
    V, n, mx = PL.rest_on_bone(pts, [box], margin=0.3)
    assert n == 2 and mx == pytest.approx(2.3, abs=0.05)
    assert V[0, 2] == pytest.approx(20.3, abs=0.05) and V[1, 2] == 25.0 and V[3, 0] == 30.0
    sd, _ = PL.bone_signed([box], V)
    assert sd.min() >= 0.25


def test_badges_state_what_the_breast_and_the_pelvic_objects_are():
    info = json.loads(INFO.read_text())["structures"]
    g = dict(triangles=7000, vertices=3500, watertight=True, skin_inside_min_mm=1.0, pectoralis_major_min_mm=-0.4, bone_min_mm=12.0, other_muscle_min_mm=1.0, skin_median_mm=14.0,
             vertices_moved_over_1mm_by_rim_push=800, rim_push_max_mm=21.0, volume_cm3=325.0, volume_hra_cm3=739.0)
    reg = dict(scale=1.0025, residual_mm=dict(median=0.7, p90=1.76, rms=1.1))
    warp = dict(ratio_median=0.5)
    for z in (False, True):
        b = PL.breast_badge("breast_fat_l", info["breast_fat_l"], g, reg, warp, [], "this page's" if z else "her", "this page's" if z else "her", z=z)
        assert b.startswith("REFERENCE MODEL, NOT donor data") and "sculpted from scratch" in b and "Krstic 1994" in b
        assert "SAME DONOR" not in b and "same donor" not in b
        assert "FITTED INTO THE SKIN ENVELOPE" in b and "325.0 cm3" in b and "739.0" in b and "vulva" in b
    gp = dict(skin_distance_min_mm=70.0, bone_min_mm=5.0, vertices_inside_page_organ_pct={}, bladder_rectum_sigmoid_pct_of_vertices=0.0, volume_cm3=0.3, vertices_within_1mm_of_bone=0,
              vertices_moved_out_of_bone=0, max_move_out_of_bone_mm=0.0, area_cm2=1.0)
    b = PL.pelvic_badge("round_ligament_uterus_l", info["round_ligament_uterus_l"], gp, "REG", "her")
    assert "gives no description of how this object was built" in b and "labia" in b and "clitoris" in b


def test_template_has_the_reference_model_class_and_both_subjects():
    t = (REPO / "viewer/atlas_viewer.template.html").read_text()
    assert 'k:"reference_model"' in t and 'b.indexOf("xfer_hrasculpt2") === 0) return "reference_model"' in t
    assert t.index('indexOf("xfer_hrasculpt2")') < t.index('indexOf("xfer_hra2")')
    for sub in ("xfer_hra2vhf_q234", "xfer_hrasculpt2vhf_q234"):
        assert re.search(r"^\s*" + sub + r': "', t, re.M), sub
    assert "SCULPTED" not in t.split("xfer_hra2vhf_q234")[1].split("\n")[0]            # the vagina / ligament label does not claim the breast provenance
    assert "NOT donor data" in t.split("xfer_hrasculpt2vhf_q234")[1].split("\n")[0]
