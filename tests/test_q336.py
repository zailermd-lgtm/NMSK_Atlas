"""Q336: the genital / perineal region of the Base pages -- the CVH vulvar skin on Base · Female and the text-only records."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts/anatomy/q336"))
sys.path.insert(0, str(REPO / "scripts/anatomy/q235"))
sys.path.insert(0, str(REPO / "scripts/anatomy/q241"))

PAGE = REPO / "build/q309/viewer_base_female"


def test_the_cvh_skin_block_really_carries_the_vulvar_surface():
    """The finding the round stands on: Q235 / Q297 recorded 'no labia surface' in the CVH skin block. Its non-crop faces
    between the thighs (|x - midline| < 25 mm, the lowest 60 mm above the crop plane) form a folded surface (the labia),
    not a flat cap."""
    import cvh as CV
    V, F = CV.load_raw(46)
    lo, hi = V.min(0), V.max(0)
    cap = np.zeros(len(F), bool)
    for ax in range(3):
        for val in (lo[ax], hi[ax]):
            cap |= np.all(np.abs(V[F][:, :, ax] - val) < 2.0, axis=1)
    c = V[F].mean(1)
    zone = (~cap) & (np.abs(c[:, 0] - CV.MID) < 25) & (c[:, 2] > hi[2] - 60)
    assert zone.sum() > 300, zone.sum()
    n = np.cross(V[F[zone]][:, 1] - V[F[zone]][:, 0], V[F[zone]][:, 2] - V[F[zone]][:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True)
    # a folded surface: its face normals spread widely (a flat crop cap would be one direction)
    assert np.linalg.norm(n.mean(0)) < 0.8


def test_records_are_well_formed_and_cited():
    import records_q336 as R
    syn = json.loads((REPO / "data/anatomy/synonyms_q306.json").read_text(encoding="utf-8"))
    srcs = set(syn["sources"]) | set(R.SOURCES)
    names = [e["name"] for e in R.ENTRIES]
    assert len(names) == len(set(names))
    for e in R.ENTRIES:
        assert e["syn"] and e["he"] and e["offer"] and len(e["why"]) > 60, e["name"]
        assert set(e["src"].split(",")) <= srcs, e["name"]
        if e.get("corrected_by"):
            assert e["corrected_by"] == "Q336" and "SHIPS" in e["why"], e["name"]


def test_records_refuse_without_the_geometry(tmp_path):
    import records_q336 as R
    d = tmp_path / "viewer_base_female"; d.mkdir()
    (d / "atlas_viewer_base_female.html").write_text("window.__ANATOMY_MANIFEST__={\"meshes\":[]};\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        R.main(["--require-page", str(d)])


def _rig(n):
    return {"schema": "s", "key": "base_f", "label": "x",
            "rig": {"v": 1, "key": "base_f", "count": n, "nv": [10] * n, "segs": [["pelvis"], ["thigh_l"]], "joints": [],
                    "regions": [], "rom": {}, "rom_meta": {}, "rigid": [[0, [0]], [1, [1]]],
                    "skin": [[2, 10, 1, [1], 0, 3]], "notes": "n"},
            "weights_zlib_b64": "AAAA"}


def test_rig_splice_appends_one_rigid_entry_and_keeps_everything_else(tmp_path):
    import vulva_skin_q336 as VS
    f = tmp_path / "rig.json"; f.write_text(json.dumps(_rig(3)), encoding="utf-8")
    old = {"meshes": [{"id": "a", "vc": 10}, {"id": "b", "vc": 10}, {"id": "c", "vc": 10}]}
    new = {"meshes": old["meshes"] + [{"id": VS.NEW_ID, "vc": 77}]}
    VS.splice_rig(old, new, True, f)
    r = json.loads(f.read_text())["rig"]
    assert r["count"] == 4 and r["nv"] == [10, 10, 10, 77]
    assert [0, [0, 3]] in r["rigid"] and r["skin"] == _rig(3)["rig"]["skin"]
    assert json.loads(f.read_text())["weights_zlib_b64"] == "AAAA"
    # a re-run on the applied page only updates that entry's vertex count
    new2 = {"meshes": old["meshes"] + [{"id": VS.NEW_ID, "vc": 80}]}
    VS.splice_rig(new, new2, True, f)
    r2 = json.loads(f.read_text())["rig"]
    assert r2["count"] == 4 and r2["nv"][-1] == 80 and r2["rigid"] == r["rigid"]
    # a rig that does not describe the page is refused
    with pytest.raises(AssertionError):
        VS.splice_rig({"meshes": old["meshes"][:2]}, new, False, f)


def _manifest(d):
    import pagegeo_q336 as G
    return G.manifest(d)


@pytest.mark.skipif(not (PAGE / "atlas_viewer_base_female.html").exists(), reason="build page not on disk")
def test_applied_page_rig_and_cards_agree():
    man = _manifest(PAGE)
    ids = [m["id"] for m in man["meshes"]]
    rig = json.loads((REPO / "data/anatomy/pose_rig_base_f.json").read_text(encoding="utf-8"))["rig"]
    assert rig["count"] == len(ids), "the shared pose rig must describe the build page as it is now"
    if "skin_vulva_cvh" not in ids:
        pytest.skip("Q336 not applied to the build page yet")
    assert ids[-1] == "skin_vulva_cvh"
    pelvis = next(i for i, s in enumerate(rig["segs"]) if s[0] == "pelvis")
    assert len(ids) - 1 in dict((g[0], g[1]) for g in rig["rigid"])[pelvis]
    m = man["meshes"][-1]
    assert m["sys"] == "skin" and "REAL SURFACE OF ANOTHER PERSON" in m["rec"]["procedural_badge"]
    for x in man["meshes"]:
        assert "perineum of this page is deliberately shown OPEN" not in json.dumps(x.get("rec", {})), x["id"]
