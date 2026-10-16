"""Q172: his pelvic floor rebuilt the right way round (labels row-flipped onto his photographs, Stage-2 in-plane offset,
ischial-spine level carried from the female by proportion) and, for BOTH bodies, the external anal sphincter around the
rectum's anal end with the coccygeus behind it. Output checks skip when build/vh (not in git) is absent."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts.cryo import vhm_pelvic_floor_from_cryo as pm  # noqa: E402

VH = REPO / "build/vh"
BODIES = {"vhf": ("ct_vhf_pelvis", ["ct_vhf_pfloor"]), "vhm": ("ct_vhm_pelvis", ["ct_vhm_pfloor_fix", "ct_vhm_pfloor"])}


def meshes(subjects, ids=None):
    out = {}
    for sub in subjects:
        d = VH / sub
        if not (d / "manifest.json").exists():
            continue
        man = json.loads((d / "manifest.json").read_text())
        V = np.fromfile(d / "vertices.f32", np.float32).reshape(-1, 3).astype(float)
        for st in man["structures"]:
            if st["atlas_id"] not in out and (not ids or st["atlas_id"] in ids):
                out[st["atlas_id"]] = V[st["vertex_offset"]:st["vertex_offset"] + st["vertex_count"]]
    return out


def anal_end(body):
    rect = meshes([BODIES[body][0]], {"rectum"}).get("rectum")
    pf = meshes(BODIES[body][1])
    if rect is None or "external_anal_sphincter" not in pf:
        pytest.skip(f"{body}: rectum or pelvic-floor meshes absent (build/vh is not in git)")
    low = rect[rect[:, 1].argmin()]
    return rect, rect[rect[:, 1] < low[1] + 5.0].mean(0), pf


@pytest.mark.parametrize("body", BODIES)
def test_external_anal_sphincter_surrounds_the_anal_end(body):
    rect, cap, pf = anal_end(body)
    e = pf["external_anal_sphincter"]
    axis = e.mean(0)
    radius = np.median(np.linalg.norm((e - axis)[:, [0, 2]], axis=1))
    off = np.linalg.norm((cap - axis)[[0, 2]])          # atlas X-Z = the horizontal plane
    assert off < 10.0 and off < 0.5 * radius, (off, radius)
    assert e[:, 1].min() - 3.0 <= rect[:, 1].min() <= e[:, 1].max() + 3.0


@pytest.mark.parametrize("body", BODIES)
def test_coccygeus_lies_posterior_to_the_anal_end(body):
    _, cap, pf = anal_end(body)
    for sid in ("coccygeus_r", "coccygeus_l"):
        assert sid in pf, sid
        assert pf[sid].mean(0)[2] < cap[2] - 10.0, (sid, pf[sid].mean(0)[2], cap[2])   # atlas +Z anterior


def test_male_frame_is_flipped_onto_the_photographs():
    assert pm.LABEL_ROW_FLIP and pm.POST_ROW_SIGN == 1
    assert np.allclose(pm.label_rows([0, 511]), [479, 479 - 479.0625], atol=1e-6)
    a = pm.volume_affine(-963.0)
    assert np.allclose(a[:3, 3], [242.72, 239.11, -963.0]) and a[0, 0] == -1 and a[1, 1] == -1


def test_spine_level_by_her_proportion():
    # her builder: spine z -884.0, head centres -885.31, tuberosity -950.0 -> 1.31 mm above the heads
    assert pm.FEMALE_SPINE_FRACTION == pytest.approx(-1.31 / 64.69, abs=1e-4)
    # his heads -202.73 and tuberosity -270.0 in legs_total's own z (k0 at -978) -> legs slice 777
    assert pm.spine_k_by_female_proportion(-202.73, -270.0, -978.0) == 777


def test_femoral_head_sphere_fit_recovers_a_sphere():
    lab = np.zeros((80, 80, 80), np.int16)
    g = np.indices(lab.shape).transpose(1, 2, 3, 0)
    lab[np.linalg.norm(g - [40, 40, 50], axis=-1) <= 20] = 76
    lab[35:46, 35:46, 5:40] = 76                                   # a shaft below the head
    z, r = pm.femoral_head_z(lab, np.eye(4), 76)
    assert z == pytest.approx(50, abs=0.6) and r == pytest.approx(20, abs=1.0)


def test_male_report_records_the_rule_and_zero_overlap():
    rep = REPO / "data/ct_sources/task_outputs/vhm_pelvic_floor_cryo_report.json"
    if not rep.exists():
        pytest.skip("his pelvic-floor report absent")
    d = json.loads(rep.read_text())
    if "frame_orientation" not in d:
        pytest.skip("pre-Q172 report")
    assert d["frame_orientation"]["label_row_flip"] is True
    rule = d["levels"]["ischial_spine"]["rule"]
    assert rule["male"]["kk_spine_used"] == d["levels"]["ischial_spine"]["legs_ct_slice"]
    assert sum(d["checks"]["overlap_bone_voxels"].values()) == 0
    assert sum(d["checks"]["overlap_organ_voxels"].values()) == 0


def test_male_fix_mapping_labels_match_the_key():
    key = json.loads((REPO / "mappings/vhm_pelvic_floor_labels.json").read_text())["labels"]
    fix = json.loads((REPO / "mappings/subjects/ct_vhm_pfloor_fix_volume_mapping.json").read_text())
    for e in fix["entries"]:
        assert key[str(e["label"])] == e["source_structure"]
        assert (REPO / f"data/muscles/trunk/{e['atlas_id']}.json").exists()
