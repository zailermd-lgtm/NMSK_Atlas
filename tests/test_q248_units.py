"""Q248: unit tests of the ligament audit checklist, the band builder, the bone push-out, the carrier-bone ICP, the soft guards and the SUBJECT_LABELS sync (no build/ needed)."""
import re
import sys
from pathlib import Path

import numpy as np
import pytest
import trimesh

REPO = Path(__file__).resolve().parents[1]
Q = REPO / "scripts" / "anatomy" / "q248"
for p in (REPO, REPO / "scripts", REPO / "scripts" / "anatomy", Q):
    sys.path.insert(0, str(p))

import checklist as CL  # noqa: E402
import lig_fit as FT  # noqa: E402
import lig_pages as PG  # noqa: E402
import rulelig as RL  # noqa: E402


def test_checklist_is_consistent():
    keys = [i[1] for i in CL.ITEMS]
    assert len(keys) == len(set(keys))
    assert {i[0] for i in CL.ITEMS} == set(CL.GROUPS)
    for g, k, label, sex, sided, inc, exc in CL.ITEMS:
        assert sex in "bfm" and sided in "pm"
        re.compile(inc)
        if exc:
            re.compile(exc)
    # the pelvic floor and the owner's lists are covered
    for must in ("tendinous_arch_levator_ani", "arcus_tendineus_fasciae_pelvis", "perineal_membrane", "transverse_perineal_ligament", "anococcygeal_ligament", "sacrospinous", "sacrotuberous", "iliolumbar",
                 "inguinal", "obturator_membrane", "uterosacral", "cardinal", "patellar_ligament", "acl", "pcl", "atfl", "flava", "all", "pll"):
        assert must in keys


@pytest.mark.parametrize("text,key,hit", [
    ("sacrospinous_ligament_l | sacrospinous ligament", "sacrospinous", True),
    ("zan_meniscopatellar_ligament_l | meniscopatellar ligament", "patellar_ligament", False),
    ("patellar_ligament_r | patellar ligament", "patellar_ligament", True),
    ("anterior_cruciate_ligament_l | anterior cruciate ligament (acl)", "transverse_atlantal", False),
    ("zan_ulnar_collateral_ligament_of_wrist_joint_l | ulnar collateral ligament of wrist joint", "ucl", False),
    ("zan_ulnar_collateral_ligament_l | ulnar collateral ligament", "ucl", True),
])
def test_checklist_regexes(text, key, hit):
    item = next(i for i in CL.ITEMS if i[1] == key)
    ok = bool(re.search(item[5], text)) and not (item[6] and re.search(item[6], text))
    assert ok == hit


def test_tube_is_closed_and_has_the_cross_section_volume():
    P = np.stack([np.linspace(0, 60, 40), np.zeros(40), np.zeros(40)], 1)
    V, F, c0, c1 = RL.tube(P, 6.0, 2.0, np.array([0, 1.0, 0]), nseg=24)
    m = trimesh.Trimesh(V, F, process=False)
    assert m.is_watertight and m.volume > 0
    expect = np.pi / 4 * 6.0 * 2.0 * 60.0
    assert abs(m.volume - expect) / expect < 0.03
    assert np.allclose(V[c0], P[0]) and np.allclose(V[c1], P[-1])


def _sphere_page():
    s = trimesh.creation.icosphere(subdivisions=4, radius=20.0)
    E = {"hip_bone_l": dict(v=np.asarray(s.vertices), f=np.asarray(s.faces), sys="bone", side="l", id="hip_bone_l")}
    return E, PG.BoneField(E)


def test_boneField_sign_and_route_leaves_the_bone():
    E, bf = _sphere_page()
    sd = bf.signed(np.array([[0, 0, 0.0], [0, 0, 30.0], [0, 0, 20.0]]), ["hip_bone_l"])[0]
    assert sd[0] < -19 and 9 < sd[1] < 11 and abs(sd[2]) < 0.5

    class C:  # minimal Ctx
        pass
    c = C(); c.E = E; c.bf = bf
    c.near_bones = lambda P, m: ["hip_bone_l"]
    P = RL.route(c, np.array([-30, 0, 24.0]), np.array([30, 0, 24.0]), n=40, clear=1.5)   # the straight line grazes the sphere (z = 24 vs r = 20 is outside) -> make it cut through
    sd = bf.signed(P, ["hip_bone_l"])[0]
    assert sd.min() > 1.0
    P2 = RL.route(c, np.array([-30, 0, 5.0]), np.array([30, 0, 5.0]), n=60, clear=1.5)    # straight line through the sphere
    sd2 = bf.signed(P2[1:-1], ["hip_bone_l"])[0]
    assert sd2.min() > 0.9                                                              # pushed out (ends are the attachments)


def test_icp_recovers_a_similarity():
    rng = np.random.RandomState(0)
    m = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
    pts = np.asarray(m.vertices) * np.array([30, 18, 10.0])           # an ellipsoid ...
    pts = pts + 3.0 * np.sin(pts[:, [1, 2, 0]] / 4.0)               # ... with bumps (a bone-like, well-conditioned surface)
    th = np.deg2rad(7.0)
    R = np.array([[np.cos(th), -np.sin(th), 0], [np.sin(th), np.cos(th), 0], [0, 0, 1.0]])
    dst = 1.04 * pts @ R.T + np.array([3.0, -2.0, 1.5])
    T, st = FT.icp(pts, dst)
    assert abs(T[0] - 1.04) < 0.03 and st["median_mm"] < 0.8


def test_umeyama_scale_is_clamped():
    X = np.random.RandomState(1).randn(200, 3) * 10
    s, R, t = FT.umeyama(X, 2.0 * X)
    assert FT.SCALE_LIM[0] <= s <= FT.SCALE_LIM[1]


def test_outward_normals_corrects_an_inverted_winding():
    s = trimesh.creation.icosphere(subdivisions=2, radius=5.0)
    inv = trimesh.Trimesh(s.vertices, s.faces[:, ::-1], process=False)
    n = PG.outward_normals(inv)
    c = inv.triangles_center
    assert ((n * c).sum(1) > 0).all()


def test_sync_subjects_q248_is_idempotent_and_minimal():
    import sync_subjects_q248 as S
    text = "var SUBJECT_LABELS = {\n  a: \"x\",\n  xfer_hrasculpt2vhf_q234: \"y\",\n  b: \"z\"\n};\n"
    n = S.patch(text)
    assert S.patch(n) == n
    assert n.count("\n") == text.count("\n") + len(S.LINES)
    for l in S.LINES:
        assert l.split(":")[0].strip() in n
    # classes: zan -> filled, cvh -> registered, rule label contains 'rule'
    assert any(re.search(r"rule", l, re.I) for l in S.LINES if "_rule_lig_q248" in l)
    assert not any(re.search(r"rule", l, re.I) for l in S.LINES if "xfer_zan2" in l or "xfer_cvh2" in l)
    # the real template still has the single anchor
    t = (REPO / "viewer" / "atlas_viewer.template.html").read_text(encoding="utf-8")
    assert t.count(S.ANCHOR) == 1
