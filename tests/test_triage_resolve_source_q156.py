"""Q156: resolve_source must chase THROUGH a mesh-space island-drop fix
(apply_continuity_repairs_q152.py's own '#mesh-island-drop' provenance
marker) back to the real, still-diagnosable raw source -- not report it as an
unresolvable 'recovered from a published viewer bundle' mesh, which would
permanently hide an already-fixed id's true source from any later Q152
diagnosis pass (the same re-run hazard class as apply's own true_root_subject)."""
import json

import scripts.triage_continuity_q115 as triage
from scripts.triage_continuity_q115 import resolve_source, strip_own_fix_suffix


def _reset_caches():
    triage._manifest_cache.clear()
    triage._volmap_cache.clear()


def test_strip_own_fix_suffix_requires_base_to_exist(tmp_path, monkeypatch):
    monkeypatch.setattr(triage, "BUILD", tmp_path)
    assert strip_own_fix_suffix("q156_base_a_contfix_mesh") is None  # base doesn't exist yet
    (tmp_path / "q156_base_a").mkdir()
    (tmp_path / "q156_base_a" / "manifest.json").write_text("{}")
    assert strip_own_fix_suffix("q156_base_a_contfix_mesh") == "q156_base_a"
    assert strip_own_fix_suffix("q156_base_a_contfix") == "q156_base_a"
    assert strip_own_fix_suffix("q156_base_a") is None


def test_resolve_source_chases_mesh_island_drop_to_real_source(tmp_path, monkeypatch):
    monkeypatch.setattr(triage, "BUILD", tmp_path)
    _reset_caches()

    base_dir = tmp_path / "q156_root_subject"
    base_dir.mkdir()
    real_volume = tmp_path / "fake_source.nii.gz"
    real_volume.write_bytes(b"not a real nifti, path existence is all resolve_source checks")
    (base_dir / "manifest.json").write_text(json.dumps({
        "subject": "q156_root_subject",
        "source_volume": str(real_volume),
        "label_map": "some_label_map",
        "structures": [{"atlas_id": "fake_muscle_l", "side": "left",
                         "source_file": "fake_source.nii.gz#5"}],
    }))

    fixed_dir = tmp_path / "q156_root_subject_contfix_mesh"
    fixed_dir.mkdir()
    (fixed_dir / "manifest.json").write_text(json.dumps({
        "subject": "q156_root_subject_contfix_mesh",
        "source_volume": str(real_volume),
        "structures": [{"atlas_id": "fake_muscle_l", "side": "left",
                         "source_file": "q156_root_subject/manifest.json#mesh-island-drop"}],
    }))

    src = resolve_source("q156_root_subject_contfix_mesh", "fake_muscle_l", "left")
    assert src["kind"] == "volume"
    assert src["label"] == 5
    assert src["path"] == str(real_volume)
    assert src["resolved_subject"] == "q156_root_subject"
    assert "q156_root_subject_contfix_mesh" in src["chased_via"]


def test_resolve_source_reports_unclear_when_base_no_longer_exists(tmp_path, monkeypatch):
    """A genuine recovered-published-bundle mesh (never produced by
    apply_continuity_repairs_q152.py, no stripped base subject in this build)
    must still be reported unclear, exactly as before this fix."""
    monkeypatch.setattr(triage, "BUILD", tmp_path)
    _reset_caches()

    fixed_dir = tmp_path / "q156_orphan_contfix_mesh"
    fixed_dir.mkdir()
    (fixed_dir / "manifest.json").write_text(json.dumps({
        "subject": "q156_orphan_contfix_mesh",
        "structures": [{"atlas_id": "fake_muscle_r", "side": "right",
                         "source_file": "q156_orphan/manifest.json#mesh-island-drop"}],
    }))

    src = resolve_source("q156_orphan_contfix_mesh", "fake_muscle_r", "right")
    assert src["kind"] == "unclear"
