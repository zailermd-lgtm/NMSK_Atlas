"""Q181 / Q181b: her Q48 thigh boundaries re-fitted on the femur-registered photographs (output checks skip when absent)."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts.cryo import vhf_thigh_refit_q181 as R  # noqa: E402

need_store = pytest.mark.skipif(not (R.STORE.exists() and R.OUT_VOL.exists()), reason="Q181b store / volume absent")
need_subject = pytest.mark.skipif(not (R.VH / R.OUT_SUBJ / "manifest.json").exists(), reason="Q181b subject absent")


def test_shift2d_moves_and_zero_fills():
    S = np.zeros((6, 5), np.uint8); S[1, 1] = 7
    assert R.shift2d(S, 2, -1)[3, 0] == 7 and R.shift2d(S, 2, -1).sum() == 7
    assert R.shift2d(S, -3, 0).sum() == 0


def test_blend_labels_endpoints_and_midway():
    a = np.zeros((30, 30), np.uint8); b = a.copy(); a[5:15, 5:15] = 1; b[5:15, 9:19] = 1; a[20:28, 20:28] = 2
    assert np.array_equal(R.blend_labels(a, b, 0.0), a) and np.array_equal(R.blend_labels(a, b, 1.0), b)
    m = R.blend_labels(a, b, 0.5); ys, xs = np.nonzero(m == 1)
    assert 10 <= xs.mean() <= 13 and (m == 2).sum() < (a == 2).sum()


def _toy():
    L0 = np.zeros((60, 60), np.uint8); L0[10:50, 10:30] = 1; L0[10:50, 30:50] = 2
    B = np.zeros_like(L0, bool); B[25:35, 5:12] = True          # a bone touching muscle 1's lateral face
    C = np.zeros_like(B)
    mus = np.where(np.zeros_like(L0) == 0, 2, 0).astype(np.uint8); mus[B] = 1
    th = np.zeros(L0.shape, np.float32); th[:, 35] = 50.0              # the photographed septum: 5 px right of the Q48 boundary
    return L0, B, C, mus, th


def test_refit_level_holds_bone_band_and_moves_septum():
    L0, B, C, mus, th = _toy(); known = np.ones_like(B)
    Ls = R.shift2d(L0, 0, 4)                                            # the lost frame's offset: markers move 4 px
    res = R.refit_level(L0, Ls, (th, known), mus, B, C, 8, set())
    F = R.ndi.binary_dilation(B, iterations=R.HOLD_PX)
    assert np.array_equal(res[F], L0[F])
    assert (res[20, 31:35] == 1).all() and (res[20, 37:50] == 2).all()   # the boundary moved onto the ridge
    assert not (res[B] != L0[B]).any()


def test_refit_level_held_label_keeps_exactly_its_voxels():
    L0, B, C, mus, th = _toy(); known = np.ones_like(B)
    res = R.refit_level(L0, L0, (th, known), mus, B, C, 8, {1})
    assert np.array_equal(res == 1, L0 == 1)


def test_rebuild_script_smoothing_as_shipped():
    s = (REPO / "scripts/cryo/vhf_rebuild_bundle.sh").read_text()
    assert "conv $T/vhf_nerves_cryo.nii.gz vhf_nerves ct_vhf_nerve --smooth 0.0" in s
    assert "conv $T/vhf_popliteal_cryo.nii.gz vhf_popliteal ct_vhf_popliteal --smooth 0.0" in s
    assert "conv $T/vhf_femoral_bundle_cryo.nii.gz vhf_femoral_bundle ct_vhf_femoral --smooth 1.0" in s


def test_rebuild_script_wiring():
    s = (REPO / "scripts/cryo/vhf_rebuild_bundle.sh").read_text()
    if "vhf_thigh_refit_q181.py apply" not in s:
        pytest.skip("Q181b not wired")
    assert "--subject xfer_vhm2vhf_sep_q181b" in s
    i_apply = s.index("vhf_thigh_refit_q181.py apply"); i_fix = s.index('SUBJ="$SUBJ --subject ct_vhf_xfersepta_fix_contfix"')
    assert i_apply < i_fix
    assert s.index("ct_vhf_femoral_q181 ct_vhf_popliteal_q181 ct_vhf_nerve_q181") < s.index('SUBJ="$SUBJ --subject ct_vhf --subject')


def test_tracked_mappings_keep_tibial_out():
    if not (REPO / "mappings/subjects/ct_vhf_popliteal_q181_volume_mapping.json").exists():
        pytest.skip("Q181 tracked mappings not present (not shipped)")
    m = json.loads((REPO / "mappings/subjects/ct_vhf_popliteal_q181_volume_mapping.json").read_text())
    assert m["source_volume"].endswith("vhf_popliteal_cryo_q179.nii.gz")
    assert [e["atlas_id"] for e in m["entries"] if e["label"] == 3] == [None]
    for sub, src in (("ct_vhf_nerve_q181", "vhf_nerves_cryo_q179.nii.gz"), ("ct_vhf_femoral_q181", "vhf_femoral_bundle_cryo_q179.nii.gz")):
        assert json.loads((REPO / f"mappings/subjects/{sub}_volume_mapping.json").read_text())["source_volume"].endswith(src)


@need_store
def test_store_matches_volume_and_gates():
    st = json.loads(R.STORE.read_text())
    assert st["out_vol_md5"] == R.md5(R.OUT_VOL) and st["q48_vol_md5"] == R.md5(R.Q48_VOL)
    for aid in st.get("ship_ids", []):
        b, a = st["voxels_before_after"][aid]; xv = st["xfer_refs"][aid][0]
        assert abs(100 * (a - b) / b) <= R.MAX_DVOL_PCT or abs(100 * (a - xv) / xv) <= R.MAX_DVOL_XFER_PCT, aid
        assert not st["gates"][aid]["fail"], aid
    assert not set(st.get("ship_ids", [])) & set(st["held"])


@need_store
def test_held_and_untouched_ids_equal_q48_outside_repaired_levels():
    import nibabel as nib
    L = np.asarray(nib.load(str(R.Q48_VOL)).dataobj); N = np.asarray(nib.load(str(R.OUT_VOL)).dataobj); A = nib.load(str(R.Q48_VOL)).affine
    st = json.loads(R.STORE.read_text()); ids = R.label_ids()
    bad = set()
    for s in ("right", "left"):
        bad |= {int(round(y + R.ORIGIN[1] - A[2, 3])) for y in st["levels"].get(f"{s}:broken_q48_levels", [])}
    keep = np.ones(L.shape[2], bool); keep[sorted(bad)] = False
    for aid in st["held"]:
        l = ids[aid]; assert np.array_equal((L == l)[:, :, keep], (N == l)[:, :, keep]), aid
    for aid in set(ids) - set(st["changed_ids"]):
        l = ids[aid]; assert np.array_equal(L == l, N == l), aid


@need_store
@need_subject
def test_apply_is_byte_reproducible(tmp_path, monkeypatch):
    d = R.VH / R.OUT_SUBJ
    if R.stamp() not in (d / "manifest.json").read_text():
        pytest.skip("subject older than the store")
    before = {k: hashlib.md5((d / k).read_bytes()).hexdigest() for k in ("vertices.f32", "faces.u32", "manifest.json")}
    work = tmp_path / "vh"; work.mkdir(); (work / "xfer_vhm2vhf_sep").symlink_to(R.VH / "xfer_vhm2vhf_sep")
    monkeypatch.setattr(R, "VH", work)
    R.do_apply(type("A", (), {"if_stale": False, "origin": "7.769,-885.229,14.137"})())
    after = {k: hashlib.md5((work / R.OUT_SUBJ / k).read_bytes()).hexdigest() for k in before}
    assert after["vertices.f32"] == before["vertices.f32"] and after["faces.u32"] == before["faces.u32"]


def test_traced_obstacles_include_tibial_as_shipped():
    assert ("vhf_popliteal_cryo.nii.gz", (3,)) in R.TRACED_VOLS          # Q181b option (a)


def test_fill_notches_bridges_a_collapsed_section_only():
    ks = list(range(40)); res_of = {}
    for k in ks:
        S = np.zeros((40, 40), np.uint8); S[5:25, 5:25] = 1; S[5:25, 25:35] = 2
        if 18 <= k <= 20:
            S[S == 1] = 2                                                  # muscle 1 collapses over 3 levels
        res_of[k] = (S, np.zeros((40, 40), bool), np.zeros((40, 40), bool))
    done = R.fill_notches(res_of, [1, 2], set(), None, 0, 40)
    assert done == [(1, 18, 20)] and all((res_of[k][0] == 1).sum() == 400 for k in ks)
    assert all((res_of[k][0] == 2).sum() == 200 for k in ks)


def test_drop_pieces_gives_small_pieces_to_neighbour_or_background():
    out = np.zeros((20, 20, 20), np.uint8); out[2:12, 2:12, 2:12] = 5; out[14, 14, 14] = 5; out[13:18, 13:18, 15:18] = 7; out[0, 19, 19] = 5
    mv = R.drop_pieces(out, 5, set())
    assert sorted(mv) == [(1, 0), (1, 7)] and (out == 5).sum() == 1000
    out[14, 14, 14] = 5; assert R.drop_pieces(out, 5, {7}) == [(1, 0)]   # never to a held muscle


def test_main_frac_matches_q112_and_mesh_drop():
    sys.path.insert(0, str(REPO / "scripts"))
    import audit_full_continuity_q112 as AU
    import trimesh
    a = trimesh.creation.box(); b = trimesh.creation.icosphere(3); b.vertices += 5
    v = np.r_[a.vertices, b.vertices]; f = np.r_[a.faces, b.faces + len(a.vertices)]
    assert abs(R.main_frac(f)[0] - AU.analyze_group([(None, f, len(v))])["main_frac"]) < 1e-12
    v2, f2, nd = R.drop_mesh_pieces(v, f)
    assert nd == 8 and len(v2) == len(b.vertices) and R.main_frac(f2)[0] == 1.0
