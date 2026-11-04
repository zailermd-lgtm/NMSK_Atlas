"""Q249: unit tests of the rule-based nerve machinery (spline, tube, soft push-out, centre line), the literature table, the Q240 nerve-kind pattern for the new ids, the SUBJECT_LABELS sync and the Source-class fix
(PROCEDURAL/RULE-BASED badges).  No build/ needed."""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest
import trimesh

REPO = Path(__file__).resolve().parents[1]
Q = REPO / "scripts" / "anatomy" / "q249"
for p in (REPO, REPO / "scripts", REPO / "scripts" / "anatomy", REPO / "scripts" / "anatomy" / "q248", REPO / "scripts" / "anatomy" / "q240", REPO / "scripts" / "anatomy" / "q236", Q):
    sys.path.insert(0, str(p))

import nervelib as NL  # noqa: E402
import lm as LMK  # noqa: E402
import lit as LIT  # noqa: E402


def test_spline_passes_the_waypoints_and_is_arc_length_uniform():
    A = np.array([[0, 0, 0], [10, 5, 0], [20, 0, 5], [30, 10, 5.0]])
    P = NL.spline(A, 60)
    assert len(P) == 60
    for a in A:
        assert np.linalg.norm(P - a, axis=1).min() < 0.8
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    assert seg.std() / seg.mean() < 0.05
    assert np.allclose(P[0], A[0]) and np.allclose(P[-1], A[-1], atol=1e-6)


def test_round_tube_is_closed_with_the_cylinder_volume_and_tapers():
    P = np.c_[np.zeros(40), np.zeros(40), np.linspace(0, 60, 40)]
    V, F, c0, c1, d = NL.tube_round(P, 4.0)
    m = trimesh.Trimesh(V, F, process=False)
    assert m.is_watertight
    r, L, n = 2.0, 60.0, NL.NSEG
    expect = 0.5 * n * np.sin(2 * np.pi / n) * r * r * L          # the n-gon prism
    assert abs(abs(m.volume) - expect) / expect < 0.03
    V2, F2, _, _, d2 = NL.tube_round(P, 4.7, 3.0)
    assert d2[0] == pytest.approx(4.7) and d2[-1] == pytest.approx(3.0)
    assert trimesh.Trimesh(V2, F2, process=False).is_watertight


def test_centerline_of_a_curved_tube_recovers_the_axis_length():
    t = np.linspace(0, np.pi, 60)
    ax = np.c_[40 * np.cos(t), 40 * np.sin(t), np.zeros(60)]
    V, F, _, _, _ = NL.tube_round(ax, 3.0)
    C = LMK.centerline(V, F, 40)
    L = np.linalg.norm(np.diff(C, axis=0), axis=1).sum()
    assert abs(L - np.pi * 40) / (np.pi * 40) < 0.06
    assert np.abs(np.linalg.norm(C[:, :2], axis=1) - 40).max() < 1.5


def test_soft_outside_pushes_points_out_of_a_closed_solid():
    sph = trimesh.creation.icosphere(subdivisions=3, radius=10.0)
    E = {"ball": dict(id="ball", sys="muscle", v=np.asarray(sph.vertices), f=np.asarray(sph.faces))}

    class GD:
        def __init__(self): self.E = E; self._soft = {}
        def _field(self, i):
            import lig_pages as PG
            from scipy.spatial import cKDTree
            m = PG.mesh(E[i]); pts, fi = trimesh.sample.sample_surface(m, 20000, seed=0)
            return cKDTree(pts), PG.outward_normals(m)[fi]
    soft = NL.Soft(E, GD())
    Q2 = soft.outside("ball", np.array([[0.0, 0, 6.0], [0, 0, 30.0]]), margin=np.array([1.0, 1.0]))
    assert np.linalg.norm(Q2[0]) >= 10.9 and np.allclose(Q2[1], [0, 0, 30.0])
    p, n = soft.surface_point("ball", np.array([0, 0, 20.0]), margin=0.5)
    assert abs(np.linalg.norm(p) - 10.5) < 0.3 and n[2] > 0.9
    assert soft.surface_point("ball", np.array([0, 0, 40.0]), maxdist=5.0)[0] is None


def test_literature_table_records_only_identified_sources():
    assert len(LIT.LIT) >= 20
    for k, v in LIT.LIT.items():
        assert re.search(r"PMID \d+|doi 10\.|public domain|no DOI / PMID seen", v), k
    for key in ("ebraheim97", "pn05", "pn00", "dnc20", "dnc21", "dnp21", "kutlu22", "kessler08", "rmn20", "mb15", "ssl16", "pfn07", "lan15"):
        assert key in LIT.LIT
    assert "4.67" in LIT.LIT["pn05"] and "9.8 x 4.3" in LIT.LIT["ebraheim97"] and "4.35" in LIT.LIT["kutlu22"] and "0.76" in LIT.LIT["kessler08"]


def test_new_ids_are_nerves_for_the_q240_calibre_table():
    import make_calibre as MC
    ids = []
    for k in ("own_f", "own_m", "comb_f", "comb_m", "base_f", "base_m"):
        p = REPO / "data" / "derived" / f"Q249_rule_{k}.json"
        if p.exists():
            ids += list(json.loads(p.read_text())["cards"])
    if not ids:
        pytest.skip("rule runs not built")
    for i in set(ids):
        assert MC.kind_of(i, "nerve") == "n", i


def test_subject_label_sync_is_idempotent_and_the_template_is_current():
    import sync_subjects_q249 as S
    t = (REPO / "viewer" / "atlas_viewer.template.html").read_text(encoding="utf-8")
    assert S.patch(t) == t
    for s in ("ct_vhf_rule_nerve_q249", "ct_vhm_rule_nerve_q249"):
        m = re.search(r"\n  " + s + r': "([^"]+)"', t)
        assert m and re.search(r"rule", m.group(1), re.I)                 # classifySource: a label containing 'rule' -> rule_based


def test_source_class_accepts_procedural_rule_based_badges():
    t = (REPO / "viewer" / "atlas_viewer.template.html").read_text(encoding="utf-8")
    js = t[t.index("function classifySource"):t.index("function sourceError")]
    rx = re.search(r"if \((/\^\\s\*.*?/i)\.test\(badge", js).group(1)
    assert "procedural" in rx and "rule-based" in rx
    py = re.compile(rx[1:-2].replace("\\/", "/"), re.I)
    for b in ("RULE-BASED (Q249): ...", "PROCEDURAL/RULE-BASED: AC / CC ligaments ...", "  procedural/rule-based ...", "rule-based"):
        assert py.match(b), b
    for b in ("PROCEDURAL: something else", "FILLED from Z-Anatomy", "measured"):
        assert not py.match(b), b
    import audit_q189_model_separation as A
    assert A.classify("ct_vhm_x", "PROCEDURAL/RULE-BASED: acromioclavicular ligament")[0] == "rule_based"
    assert A.classify("ct_vhm_x", "RULE-BASED (Q249): nerve")[0] == "rule_based"
    assert A.classify("ct_vhm_x", "PROCEDURAL: not rule")[0] == "measured"


def test_every_sync_script_still_reports_up_to_date():
    import subprocess
    for s in sorted((REPO / "scripts").glob("sync_*.py")):
        r = subprocess.run([sys.executable, str(s), "--check"], capture_output=True, text=True, cwd=REPO)
        assert r.returncode == 0, (s.name, r.stdout[-300:], r.stderr[-300:])
