import json

from scripts.apply_continuity_repairs_q152 import merge_apply_log, true_root_subject


# ---------------------------------------------------------------------------
# true_root_subject -- Q156's re-run-hazard fix: never resolve/group an
# already-fixed id through this script's OWN prior '_contfix'/'_contfix_mesh'
# output; always chase back to the real root subject it was produced from.
# ---------------------------------------------------------------------------

def test_strips_own_contfix_suffix_when_base_exists(tmp_path, monkeypatch):
    import scripts.apply_continuity_repairs_q152 as m
    monkeypatch.setattr(m, "BUILD", tmp_path)
    (tmp_path / "xfer_vhm2vhf_sep").mkdir()
    (tmp_path / "xfer_vhm2vhf_sep" / "manifest.json").write_text("{}")

    assert true_root_subject("xfer_vhm2vhf_sep_contfix") == "xfer_vhm2vhf_sep"


def test_strips_own_contfix_mesh_suffix_when_base_exists(tmp_path, monkeypatch):
    import scripts.apply_continuity_repairs_q152 as m
    monkeypatch.setattr(m, "BUILD", tmp_path)
    (tmp_path / "ct_vhf_abd").mkdir()
    (tmp_path / "ct_vhf_abd" / "manifest.json").write_text("{}")

    assert true_root_subject("ct_vhf_abd_contfix_mesh") == "ct_vhf_abd"


def test_leaves_subject_alone_when_no_stripped_base_exists(tmp_path, monkeypatch):
    """A subject that merely happens to end in '_contfix' but has no
    unsuffixed counterpart in this build (never produced by this script)
    must be passed through unchanged -- never guess a base subject that
    doesn't actually exist."""
    import scripts.apply_continuity_repairs_q152 as m
    monkeypatch.setattr(m, "BUILD", tmp_path)

    assert true_root_subject("some_other_subject_contfix") == "some_other_subject_contfix"


def test_leaves_ordinary_subject_names_untouched(tmp_path, monkeypatch):
    import scripts.apply_continuity_repairs_q152 as m
    monkeypatch.setattr(m, "BUILD", tmp_path)
    assert true_root_subject("ct_vhf_dneck") == "ct_vhf_dneck"


# ---------------------------------------------------------------------------
# merge_apply_log -- Q152_apply_log.json must accumulate across runs, never
# be silently replaced (the second half of the same re-run hazard).
# ---------------------------------------------------------------------------

def test_merge_apply_log_appends_rather_than_replacing():
    existing = {
        "log": ["OLD line 1", "OLD line 2"],
        "island_subjects": {"male|ct_vhm_abw_contfix_mesh": True},
        "voxel_subjects": ["ct_vhm_armm_contfix"],
        "runs": [{"island_subjects_this_run": ["male|ct_vhm_abw_contfix_mesh"],
                   "voxel_subjects_this_run": ["ct_vhm_armm_contfix"]}],
    }
    new_log = ["NEW line 1"]
    new_islands = {("female", "ct_vhf_dneck_contfix_mesh"): True}
    new_voxel = {"ct_vhf_pfloor_contfix": {}}

    merged = merge_apply_log(existing, new_log, new_islands, new_voxel)

    # old content survives verbatim, not overwritten
    assert "OLD line 1" in merged["log"]
    assert "OLD line 2" in merged["log"]
    assert "NEW line 1" in merged["log"]
    assert "male|ct_vhm_abw_contfix_mesh" in merged["island_subjects"]
    assert "female|ct_vhf_dneck_contfix_mesh" in merged["island_subjects"]
    assert "ct_vhm_armm_contfix" in merged["voxel_subjects"]
    assert "ct_vhf_pfloor_contfix" in merged["voxel_subjects"]
    assert len(merged["runs"]) == 2


def test_merge_apply_log_dedupes_voxel_subjects_seen_again():
    existing = {"log": [], "island_subjects": {}, "voxel_subjects": ["ct_vhf_dneck_contfix"], "runs": []}
    merged = merge_apply_log(existing, [], {}, {"ct_vhf_dneck_contfix": {}})
    assert merged["voxel_subjects"].count("ct_vhf_dneck_contfix") == 1


def test_merge_apply_log_from_scratch_when_no_existing_file():
    merged = merge_apply_log({}, ["line"], {("male", "x_contfix_mesh"): True}, {"y_contfix": {}})
    assert merged["log"] == ["--- run 1 ---", "line"]
    assert merged["island_subjects"] == {"male|x_contfix_mesh": True}
    assert merged["voxel_subjects"] == ["y_contfix"]
    assert len(merged["runs"]) == 1


def test_merged_log_is_json_serializable_round_trip(tmp_path):
    existing = {"log": ["a"], "island_subjects": {"male|s_contfix_mesh": True},
                "voxel_subjects": ["s_contfix"], "runs": [{}]}
    merged = merge_apply_log(existing, ["b"], {}, {})
    p = tmp_path / "log.json"
    p.write_text(json.dumps(merged, indent=2))
    reloaded = json.loads(p.read_text())
    assert reloaded["log"] == ["a", "--- run 2 ---", "b"]
