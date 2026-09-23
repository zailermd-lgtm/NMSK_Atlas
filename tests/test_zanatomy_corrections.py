"""Q144: the correction-file loader/applier (scripts/zanatomy/apply_corrections.py)
and the radial-nerve correction file it reads (data/corrections/zanatomy/radial_n.json).

Deliberately does not touch build/zanatomy/ (the ~90MB gitignored Z-Anatomy
extraction) or build/vh/zan_ref_* -- those are exercised by actually running
scripts/zanatomy/build_zan_reference.py, not by this fast, always-runnable suite.
"""
import json

import numpy as np
import pytest

from scripts.zanatomy.apply_corrections import (
    DEFAULT_CORRECTIONS_DIR, apply_correction, bump_warp_y, load_corrections,
)


def test_bump_warp_y_anchors_and_clamping():
    anchors = [(0.0, 0.0), (-10.0, -5.0), (-20.0, 0.0)]
    y = np.array([5.0, 0.0, -5.0, -10.0, -15.0, -20.0, -25.0])
    shift = bump_warp_y(y, anchors)
    # exactly on an anchor -> exactly that anchor's shift
    assert shift[1] == pytest.approx(0.0)   # y=0
    assert shift[3] == pytest.approx(-5.0)  # y=-10
    assert shift[5] == pytest.approx(0.0)   # y=-20
    # outside the outermost anchors -> clamped to the nearest anchor's shift
    assert shift[0] == pytest.approx(0.0)    # y=5, above the top anchor
    assert shift[6] == pytest.approx(0.0)    # y=-25, below the bottom anchor
    # between anchors -> strictly between the two anchor shifts (smoothstep)
    assert -5.0 < shift[2] < 0.0   # y=-5, between (0, 0) and (-10, -5)
    assert -5.0 < shift[4] < 0.0   # y=-15, between (-10, -5) and (-20, 0)


def test_bump_warp_y_is_smooth_and_monotonic_for_a_dense_sample():
    # a bump whose shift magnitude is smaller than the anchor spacing must keep
    # y' = y + shift(y) strictly increasing -- no self-intersection/fold in the
    # warped mesh (Q144's own "bounded displacement, no topology change" rule).
    anchors = [(0.0, 0.0), (-20.0, -8.0), (-60.0, 0.0)]
    y = np.linspace(10, -70, 4000)
    shift = bump_warp_y(y, anchors)
    warped = y + shift
    # y is descending here, so warped must be strictly descending too
    assert np.all(np.diff(warped) < 0)


def test_load_corrections_finds_radial_n():
    corrections = load_corrections()
    assert "posterior_interosseous_n_r" in corrections
    assert "posterior_interosseous_n_l" in corrections
    rec = corrections["posterior_interosseous_n_r"]
    assert rec is corrections["posterior_interosseous_n_l"], "both sides share one correction file"
    c = rec["correction"]
    assert set(c["applies_to_ids"]) == {"posterior_interosseous_n_r", "posterior_interosseous_n_l"}
    assert len(c["anchors_offset_from_LE_mm"]) >= 2
    for off, shift in c["anchors_offset_from_LE_mm"]:
        assert isinstance(off, (int, float)) and isinstance(shift, (int, float))
    assert c["procedural_badge_note"]
    # every landmark the audit measured must carry a citation or be explicitly
    # marked unsourced -- "never invented" (task instruction), checked structurally.
    for lm in rec["landmarks"]:
        assert lm["citation"] or lm["status"].startswith("unsourced")


def test_load_corrections_empty_directory_is_a_noop(tmp_path):
    assert load_corrections(tmp_path) == {}


def test_apply_correction_is_a_noop_for_an_uncorrected_id():
    v = np.random.RandomState(0).rand(20, 3).astype(np.float64)
    out, note = apply_correction("some_other_nerve_r", v, DEFAULT_CORRECTIONS_DIR, load_corrections())
    assert note is None
    assert np.array_equal(out, v)


def test_correction_file_is_well_formed_json():
    path = DEFAULT_CORRECTIONS_DIR / "radial_n.json"
    rec = json.loads(path.read_text())
    assert rec["correction"]["applies_to_ids"]
    assert rec["landmarks"]
    # at least one landmark corrected, at least one left alone -- this task's
    # own "only correct what's actually out of range" rule, checked structurally
    # rather than trusting the prose.
    statuses = {lm["corrected"] for lm in rec["landmarks"]}
    assert statuses == {True, False}
