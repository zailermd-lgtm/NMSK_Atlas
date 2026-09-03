"""Tests for the labelled-volume (CT/MRI) ingest.

No scan is vendored, so these build small synthetic NIfTI label maps whose
right answer is known by construction: a sphere of a stated radius at a
stated centre, and a shape whose left-right placement is known.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

nib = pytest.importorskip("nibabel")
pytest.importorskip("skimage")

from engine import volume_ingest as vol  # noqa: E402


def _write_nifti(path, volume, spacing=(1.0, 1.0, 1.0), flip_x=False):
    """A NIfTI whose affine is plain RAS at the given spacing.

    flip_x writes the volume with a POSITIVE-determinant affine, which is how
    a mirrored scan arrives.
    """
    affine = np.diag([spacing[0], spacing[1], spacing[2], 1.0])
    affine[0, 0] = -spacing[0] if flip_x else spacing[0]
    img = nib.Nifti1Image(volume.astype(np.int16), affine)
    nib.save(img, str(path))
    return affine


def _ball(volume, centre, radius, label):
    g = np.stack(np.meshgrid(*[np.arange(s) for s in volume.shape],
                             indexing="ij"), axis=-1)
    volume[np.linalg.norm(g - np.array(centre), axis=-1) <= radius] = label
    return volume


def test_label_surface_is_closed_even_at_the_volume_edge(tmp_path):
    """A structure touching the edge of the scan comes back as an open sheet
    without padding, and every inside/outside test downstream inverts on an
    open mesh."""
    volume = np.zeros((30, 30, 30), np.int16)
    volume[:12, :12, :12] = 7          # jammed into the corner
    verts, faces = vol.label_surface(volume, 7)
    assert len(verts) and len(faces)
    # Closed means every edge is shared by exactly two triangles.
    edges = {}
    for tri in faces:
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            edges[(min(a, b), max(a, b))] = edges.get((min(a, b), max(a, b)), 0) + 1
    assert set(edges.values()) == {2}, "surface is not closed"


def test_voxels_to_atlas_puts_superior_on_y_and_anterior_on_z(tmp_path):
    """NIfTI world is RAS -- +y anterior, +z superior. The atlas is
    +Y superior, +Z anterior. Getting that swap wrong lays the body on its
    face and nothing downstream would notice."""
    affine = np.eye(4)
    pts = np.array([[1.0, 2.0, 3.0]])          # right 1, anterior 2, superior 3
    out = vol.voxels_to_atlas(pts, affine)
    np.testing.assert_allclose(out, [[1.0, 3.0, 2.0]])


def test_a_mirrored_scan_is_detected_and_not_corrected():
    """Mirroring a patient's scan without saying so is how the wrong knee
    gets operated on."""
    good = np.diag([1.0, 1.0, 1.0, 1.0])
    good[0, 0] = -1.0                      # LAS: a normal radiological affine
    assert vol.is_right_handed(good)       # flagged
    plain_ras = np.diag([1.0, 1.0, 1.0, 1.0])
    assert not vol.is_right_handed(plain_ras)


def _femur(volume, head_vox, label, lateral_sign):
    """A femur with a head AND a greater trochanter sitting higher than it.

    The trochanter is the point of the fixture: on many people it is the more
    superior of the two, so a rule that took the superior fraction of the
    bone would fit the trochanter and call it the hip joint centre.
    """
    hx, hy, hz = head_vox
    _ball(volume, head_vox, 12, label)                       # head, r=24 mm
    _ball(volume, (hx + 15 * lateral_sign, hy + 10, hz), 10, label)  # trochanter
    x0 = hx + 8 * lateral_sign
    lo, hi = sorted((x0 - 4, x0 + 4))
    volume[lo:hi, hy - 75:hy, hz - 4:hz + 4] = label         # shaft
    return volume


def test_femoral_head_is_fitted_to_its_known_radius_and_centre():
    """The head is isolated from a whole-femur label by DIRECTION, not
    height: the greater trochanter is the more superior of the two on many
    people, so a superior-fraction rule fits the trochanter instead."""
    volume = np.zeros((120, 120, 120), np.int16)
    _femur(volume, (40, 95, 60), 3, lateral_sign=-1)   # a LEFT femur (low x)
    verts, _faces = vol.label_surface(volume, 3)
    # 2 mm voxels, so a 12-voxel ball is a 24 mm femoral head -- the size the
    # plausibility gate in hip_joint_origin() is written for.
    pts = vol.voxels_to_atlas(verts, np.diag([2.0, 2.0, 2.0, 1.0]))
    centre, radius, rms = vol.femoral_head_centre(pts, "left")
    assert 21.0 <= radius <= 27.0, radius
    assert rms < 2.0, rms
    # voxel (40,95,60) at 2 mm -> RAS (80,190,120) -> atlas (80,120,190)
    np.testing.assert_allclose(centre, [80.0, 120.0, 190.0], atol=5.0)


def test_hip_origin_needs_both_sides():
    """The atlas origin is the MIDPOINT of the two hip joint centres, so one
    side alone cannot give it, and returning a single centre as if it were
    the midpoint would shift the whole atlas by half a pelvis."""
    volume = np.zeros((120, 120, 120), np.int16)
    _femur(volume, (40, 95, 60), 1, lateral_sign=-1)
    verts, _ = vol.label_surface(volume, 1)
    pts = vol.voxels_to_atlas(verts, np.diag([2.0, 2.0, 2.0, 1.0]))
    report = vol.hip_joint_origin({"femur_left": pts})
    assert report["sides"]["left"]["plausible"], report
    assert report["origin_mm"] is None
    assert "midpoint" in report["from"].lower()


def test_label_map_covers_every_id_it_claims():
    names = vol.load_label_names("totalsegmentator")
    assert len(names) == 117
    assert names[73] == "clavicula_left" and names[74] == "clavicula_right"
    assert names[69] == "humerus_left" and names[43] == "vertebrae_T1"


def test_a_probability_volume_is_refused(tmp_path):
    """Rounding a probability map would invent structures that are not there."""
    path = tmp_path / "probs.nii.gz"
    _write_nifti(path, np.zeros((4, 4, 4)))
    img = nib.Nifti1Image(np.full((4, 4, 4), 0.37, dtype=np.float32), np.eye(4))
    nib.save(img, str(path))
    with pytest.raises(ValueError, match="not a label map"):
        vol.load_labels(path)


def test_inspect_runs_end_to_end_and_recovers_the_origin(tmp_path):
    """The whole point of inspect: read a real file, say what is in it, and
    hand back an --origin the operator can paste into convert."""
    volume = np.zeros((140, 140, 140), np.int16)
    # left femur (label 75) at low x, right femur (76) at high x
    _femur(volume, (45, 100, 70), 75, lateral_sign=-1)
    _femur(volume, (95, 100, 70), 76, lateral_sign=+1)
    path = tmp_path / "seg.nii.gz"
    _write_nifti(path, volume, spacing=(2.0, 2.0, 2.0))

    out = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "ingest_volume_geometry.py"),
         "inspect", str(path), "--labels", "totalsegmentator"],
        capture_output=True, text=True, timeout=600)
    assert out.returncode == 0, out.stderr
    assert "femur_left" in out.stdout and "femur_right" in out.stdout
    assert "--origin" in out.stdout, out.stdout
    # midpoint of the two heads: voxel x 45 and 95, at 2 mm -> atlas x 140
    line = next(l for l in out.stdout.splitlines() if "--origin" in l)
    x = float(line.split("'")[1].split(",")[0])
    assert abs(x - 140.0) < 6.0, line


def test_merging_per_structure_masks_produces_the_ingest_s_label_map(tmp_path):
    """The released dataset gives one BINARY mask per structure, not the
    single label volume the ingest reads."""
    seg = tmp_path / "s0001" / "segmentations"
    seg.mkdir(parents=True)
    shape = (20, 20, 20)
    affine = np.diag([1.5, 1.5, 1.5, 1.0])
    for name, box in (("humerus_left", (slice(2, 6),) * 3),
                      ("clavicula_right", (slice(10, 14),) * 3),
                      ("liver", (slice(16, 19),) * 3)):
        m = np.zeros(shape, np.uint8)
        m[box] = 1
        nib.save(nib.Nifti1Image(m, affine), str(seg / f"{name}.nii.gz"))

    out = tmp_path / "merged.nii.gz"
    r = subprocess.run(
        [sys.executable,
         str(REPO_ROOT / "scripts" / "merge_totalsegmentator_masks.py"),
         str(tmp_path / "s0001"), "-o", str(out)],
        capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr

    volume, got_affine, _codes = vol.load_labels(out)
    names = vol.load_label_names("totalsegmentator")
    present = {names[i] for i in set(np.unique(volume).tolist()) - {0}}
    assert present == {"humerus_left", "clavicula_right"}, present
    assert "liver" in r.stdout and "not musculoskeletal" in r.stdout
    np.testing.assert_allclose(got_affine, affine)
    # the ids must be the ones the ingest will look up, not 1..n
    assert volume[3, 3, 3] == 69 and volume[11, 11, 11] == 74


def test_merging_refuses_masks_from_a_different_scan(tmp_path):
    """Two subjects' masks share no grid, and merging them would produce a
    body assembled from two people without saying so."""
    seg = tmp_path / "s0002" / "segmentations"
    seg.mkdir(parents=True)
    a = np.zeros((20, 20, 20), np.uint8); a[2:6, 2:6, 2:6] = 1
    b = np.zeros((24, 20, 20), np.uint8); b[2:6, 2:6, 2:6] = 1
    nib.save(nib.Nifti1Image(a, np.eye(4)), str(seg / "humerus_left.nii.gz"))
    nib.save(nib.Nifti1Image(b, np.eye(4)), str(seg / "scapula_left.nii.gz"))
    r = subprocess.run(
        [sys.executable,
         str(REPO_ROOT / "scripts" / "merge_totalsegmentator_masks.py"),
         str(tmp_path / "s0002"), "-o", str(tmp_path / "x.nii.gz")],
        capture_output=True, text=True, timeout=600)
    assert r.returncode != 0
    assert "different scans" in (r.stdout + r.stderr)


def test_overlapping_masks_are_counted_not_hidden(tmp_path):
    seg = tmp_path / "s0003" / "segmentations"
    seg.mkdir(parents=True)
    a = np.zeros((20, 20, 20), np.uint8); a[2:8, 2:8, 2:8] = 1
    b = np.zeros((20, 20, 20), np.uint8); b[6:12, 2:8, 2:8] = 1   # overlaps
    nib.save(nib.Nifti1Image(a, np.eye(4)), str(seg / "humerus_left.nii.gz"))
    nib.save(nib.Nifti1Image(b, np.eye(4)), str(seg / "scapula_left.nii.gz"))
    r = subprocess.run(
        [sys.executable,
         str(REPO_ROOT / "scripts" / "merge_totalsegmentator_masks.py"),
         str(tmp_path / "s0003"), "-o", str(tmp_path / "y.nii.gz")],
        capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr
    assert "claimed by more than" in r.stdout
    assert "That is a lot" in r.stdout


def test_every_ct_structure_reaches_a_decision():
    """Without the reviewed mapping, 63 of the 90 musculoskeletal and vascular
    structures in this release map to nothing: the matcher scores
    'rib_left_7' against an atlas carrying one 'ribs_l' entity and gets 0.17,
    and 'vertebrae_T8' against 'thoracic_vertebrae' and gets 0.33. Every
    structure must end up either mapped or refused for a stated reason -- an
    unmatched one is a silent hole in whatever is measured afterwards."""
    import sys as _sys
    _sys.path.insert(0, str(REPO_ROOT))
    from engine import vh_ingest as vh

    names = vol.load_label_names("totalsegmentator")
    reviewed = vol.load_atlas_mapping("totalsegmentator")
    atlas = vh.load_atlas_index()
    visceral = ("spleen", "kidney", "gallbladder", "liver", "stomach",
                "pancreas", "adrenal", "lung", "esophagus", "trachea",
                "thyroid", "bowel", "duodenum", "colon", "bladder",
                "prostate", "heart", "atrial", "brain", "cyst")

    undecided = []
    for raw in names.values():
        if raw in reviewed or any(k in raw for k in visceral):
            continue
        pretty = raw.replace("_", " ")
        _b, side = vh.split_side(pretty)
        cands = vh.propose_matches(pretty, atlas, side=side, top_n=2)
        best = cands[0] if cands else None
        runner = cands[1] if len(cands) > 1 else None
        confident = (best is not None and best.score >= 0.55
                     and not (runner and best.score - runner.score < 0.08))
        if not confident:
            undecided.append(f"{raw} (best {best.score if best else 0:.2f})")
    assert not undecided, "\n".join(undecided)


def test_every_reviewed_mapping_names_an_entity_that_exists():
    """A mapping to an id the atlas does not carry does nothing at all, and
    looks identical to a mapping that worked."""
    import sys as _sys
    _sys.path.insert(0, str(REPO_ROOT))
    from engine import vh_ingest as vh
    known = {e.entity_id for e in vh.load_atlas_index()}
    bad = [f"{n} -> {m['atlas_id']}"
           for n, m in vol.load_atlas_mapping("totalsegmentator").items()
           if m.get("atlas_id") and m["atlas_id"] not in known]
    assert not bad, "\n".join(bad)


def test_a_refusal_to_map_carries_its_reason():
    """atlas_id null is a decision, not an omission. Two opposite kinds live
    here and both must say which they are: the ribs and vertebrae are cases
    where the RELEASE is finer than the atlas, handled by part_of; autochthon
    is a case where the ATLAS is finer than the release, which no mapping can
    fix because the information is not in the mask."""
    reviewed = vol.load_atlas_mapping("totalsegmentator")
    # A split has no atlas_id either, but it is the opposite of a refusal.
    refused = {n: m for n, m in reviewed.items()
               if not m.get("atlas_id") and m.get("relationship") != "split"}
    assert refused, "expected some structures to be deliberately unmapped"
    for name, entry in refused.items():
        assert len(entry.get("note", "")) > 40, f"{name} refused without a reason"
    assert "autochthon_left" in refused
    assert "finer" in refused["autochthon_left"]["note"]


# --------------------------------------------------------------------------
# splitting one label into several atlas entities
# --------------------------------------------------------------------------

def _ids():
    return {n: i for i, n in vol.load_label_names("totalsegmentator").items()}


def _thorax(volume, ids, with_arch_level=True, with_hiatus_level=True):
    """A stylised trunk in voxel RAS: x right, y anterior, z superior.

    Vertebral bodies posterior (low y). The aorta is an inverted U: the
    ascending column anterior, the arch over the top, the descending column
    against the spine and continuing down past the hiatus.
    """
    if with_arch_level:
        volume[26:34, 8:16, 90:98] = ids["vertebrae_T4"]
        volume[26:34, 8:16, 80:88] = ids["vertebrae_T5"]
    if with_hiatus_level:
        volume[26:34, 8:16, 30:38] = ids["vertebrae_T12"]
        volume[26:34, 8:16, 20:28] = ids["vertebrae_L1"]
    a = ids["aorta"]
    volume[28:33, 18:23, 10:96] = a            # descending, posterior
    volume[28:33, 48:53, 60:96] = a            # ascending, anterior
    volume[28:33, 18:53, 96:101] = a           # the arch joining them
    return volume


def test_the_aorta_is_cut_at_the_vertebral_levels_the_scan_itself_labels():
    """Arch above the T4/T5 disc, abdominal below the T12/L1 disc, and
    between them the POSTERIOR column is the descending aorta -- the
    ascending aorta runs in front of it at the same heights, so no
    horizontal plane separates those two and connected components must."""
    ids = _ids()
    volume = _thorax(np.zeros((60, 80, 120), np.int16), ids)
    affine = np.diag([2.0, 2.0, 2.0, 1.0])
    parts, notes = vol.split_aorta(volume, ids["aorta"], affine, ids)

    mask = volume == ids["aorta"]
    union = np.zeros_like(mask)
    for p in parts.values():
        assert not (union & p).any(), "parts overlap"
        union |= p
    assert (union == mask).all(), "parts do not add up to the label"

    # T4 centroid z=93.5, T5 z=83.5 -> disc at z=88.5 voxels (177 mm)
    assert parts["arch"][30, 20, 97] and parts["arch"][30, 50, 90]
    assert not parts["arch"][30, 20, 88]
    # T12 z=33.5, L1 z=23.5 -> hiatus at z=28.5 voxels
    assert parts["abdominal"][30, 20, 15] and parts["abdominal"][30, 20, 28]
    assert parts["descending_thoracic"][30, 20, 29]
    assert parts["descending_thoracic"][30, 20, 70]
    assert parts["ascending"][30, 50, 70] and not parts["descending_thoracic"][30, 50, 70]
    assert not parts["ascending"][30, 20, 70]
    assert any("T4/T5" in n for n in notes) and any("T12/L1" in n for n in notes)


def test_a_scan_without_the_heart_has_no_arch_and_says_so():
    """An abdominal CT starts below T4: the whole label is one column, all
    of it descending or abdominal, and the missing level is reported rather
    than guessed at."""
    ids = _ids()
    volume = np.zeros((60, 80, 60), np.int16)
    volume[26:34, 8:16, 30:38] = ids["vertebrae_T12"]
    volume[26:34, 8:16, 20:28] = ids["vertebrae_L1"]
    volume[28:33, 18:23, 5:55] = ids["aorta"]
    parts, notes = vol.split_aorta(volume, ids["aorta"], np.eye(4), ids)
    assert not parts["arch"].any() and not parts["ascending"].any()
    assert parts["descending_thoracic"][30, 20, 50]
    assert parts["abdominal"][30, 20, 10]
    assert any("T4/T5 not in the scan" in n for n in notes)


def test_an_aorta_with_no_vertebral_level_at_all_is_refused():
    ids = _ids()
    volume = np.zeros((20, 20, 20), np.int16)
    volume[8:12, 8:12, 2:18] = ids["aorta"]
    with pytest.raises(ValueError, match="neither T4/T5 nor T12/L1"):
        vol.split_aorta(volume, ids["aorta"], np.eye(4), ids)


def test_an_upside_down_scan_is_caught_by_the_vertebral_order():
    """If T4 comes out BELOW T5 the affine's superior axis is wrong, and a cut
    placed from it would be wrong in a way nothing downstream could see."""
    ids = _ids()
    volume = np.zeros((60, 80, 120), np.int16)
    volume[26:34, 8:16, 80:88] = ids["vertebrae_T4"]     # swapped heights
    volume[26:34, 8:16, 90:98] = ids["vertebrae_T5"]
    volume[28:33, 18:23, 10:96] = ids["aorta"]
    with pytest.raises(ValueError, match="not above"):
        vol.split_aorta(volume, ids["aorta"], np.eye(4), ids)


def test_costal_cartilages_are_cut_at_the_subject_s_midline_not_the_scanner_s():
    """The sternum sits at voxel x=30 here while the scanner's X=0 is the
    corner of the volume: a split at X=0 would put everything on one side."""
    ids = _ids()
    volume = np.zeros((60, 40, 40), np.int16)
    volume[28:33, 25:30, 5:35] = ids["sternum"]
    volume[10:20, 22:28, 10:30] = ids["costal_cartilages"]   # subject's LEFT (low x)
    volume[40:50, 22:28, 10:30] = ids["costal_cartilages"]   # subject's RIGHT
    parts, notes = vol.split_at_midline(volume, ids["costal_cartilages"],
                                        np.eye(4), ids)
    assert parts["right"][45, 25, 20] and not parts["left"][45, 25, 20]
    assert parts["left"][15, 25, 20] and not parts["right"][15, 25, 20]
    assert "sternum" in notes[0]
    # With no sternum the thoracic vertebrae give the midline instead.
    volume[volume == ids["sternum"]] = 0
    volume[28:33, 5:10, 5:35] = ids["vertebrae_T6"]
    parts, notes = vol.split_at_midline(volume, ids["costal_cartilages"],
                                        np.eye(4), ids)
    assert parts["right"][45, 25, 20] and parts["left"][15, 25, 20]
    assert "vertebra" in notes[0]
    volume[volume == ids["vertebrae_T6"]] = 0
    with pytest.raises(ValueError, match="midline cannot be measured"):
        vol.split_at_midline(volume, ids["costal_cartilages"], np.eye(4), ids)


def test_every_split_in_the_mapping_names_a_real_splitter_and_real_entities():
    """A split whose splitter does not exist, or whose parts name entities
    the atlas does not carry, would refuse at convert time -- or worse, map
    silently to nothing."""
    from engine import vh_ingest as vh
    known = {e.entity_id for e in vh.load_atlas_index()}
    splits = {n: m for n, m in vol.load_atlas_mapping("totalsegmentator").items()
              if m.get("relationship") == "split"}
    assert {"aorta", "costal_cartilages"} <= set(splits)
    for name, m in splits.items():
        assert m["splitter"] in vol.LABEL_SPLITTERS, name
        assert m["split_parts"], name
        for part, target in m["split_parts"].items():
            assert target is None or target in known, f"{name}[{part}] -> {target}"
        assert len(m.get("note", "")) > 40, f"{name}: a split needs its reason"


def test_convert_writes_one_manifest_record_per_split_part(tmp_path):
    """End to end: a volume holding one aorta label and one costal label
    comes out as five atlas entities, and the part with no entity (the
    ascending aorta) is dropped by name rather than silently."""
    ids = _ids()
    volume = _thorax(np.zeros((60, 80, 120), np.int16), ids)
    volume[28:33, 60:65, 40:100] = ids["sternum"]
    volume[10:20, 58:64, 50:90] = ids["costal_cartilages"]
    volume[40:50, 58:64, 50:90] = ids["costal_cartilages"]
    path = tmp_path / "seg.nii.gz"
    _write_nifti(path, volume, spacing=(2.0, 2.0, 2.0))

    subject = "_pytest_split"
    script = REPO_ROOT / "scripts" / "ingest_volume_geometry.py"
    mapping_file = REPO_ROOT / "build" / "vh" / f"{subject}_volume_mapping.json"
    try:
        r = subprocess.run([sys.executable, str(script), "propose", str(path),
                            "--subject", subject, "--force"],
                           capture_output=True, text=True, timeout=600)
        assert r.returncode == 0, r.stderr
        entries = {e["source_structure"]: e
                   for e in json.loads(mapping_file.read_text())["entries"]}
        assert entries["aorta"]["status"] == "curated"
        assert entries["aorta"]["splitter"] == "aorta_by_vertebral_level"
        r = subprocess.run([sys.executable, str(script), "convert", str(path),
                            "--subject", subject, "--out", str(tmp_path / "out")],
                           capture_output=True, text=True, timeout=600)
        assert r.returncode == 0, r.stderr + r.stdout
    finally:
        mapping_file.unlink(missing_ok=True)

    manifest = json.loads((tmp_path / "out" / "manifest.json").read_text())
    by_id = {s["atlas_id"]: s for s in manifest["structures"]}
    assert {"aortic_arch_and_great_vessels", "descending_thoracic_aorta",
            "abdominal_aorta", "costal_cartilage_r", "costal_cartilage_l"} <= set(by_id)
    assert "ascending: no atlas entity, not ingested" in r.stdout
    for part in ("descending_thoracic_aorta", "costal_cartilage_r"):
        assert by_id[part]["split_from"] in ("aorta", "costal_cartilages")
    # the abdominal part sits below the thoracic part, in atlas Y
    assert by_id["abdominal_aorta"]["bbox_max_mm"][1] <= \
        by_id["descending_thoracic_aorta"]["bbox_min_mm"][1] + 2.0
    # right cartilage at higher atlas X than left
    assert by_id["costal_cartilage_r"]["bbox_min_mm"][0] > \
        by_id["costal_cartilage_l"]["bbox_max_mm"][0]


def test_a_ct_gets_bone_only_frames_because_it_ships_no_cartilage():
    """Every lower-limb frame in the landmark audit keys on a CARTILAGE mesh,
    because the Denver release happens to carry them. TotalSegmentator labels
    bone and nothing else, so on a CT all of those find nothing and the audit
    reported "no bone had both a measurable frame and geometry" for a scan
    that was perfectly good.

    The femoral head is still in the scan; it is inside the femur label and
    has to be isolated by direction rather than read off its own mesh. The
    frame must come back, must say in its own description that no cartilage
    was involved, and must NOT claim to have fitted the acetabulum -- the
    femoral head centre stands in for it, and saying so is the point.
    """
    import sys as _sys
    _sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import audit_landmarks_vs_geometry as audit

    # A femur in ATLAS coordinates: head at the top, shaft running inferior.
    def femur(side_sign):
        rng = np.random.default_rng(4)
        u = rng.normal(size=(1400, 3))
        u /= np.linalg.norm(u, axis=1)[:, None]
        head = u * 24.0 + np.array([90.0 * side_sign, 0.0, 0.0])
        t = np.linspace(0, 1, 900)[:, None]
        shaft = (np.array([90.0 * side_sign + 24 * side_sign, -30.0, 0.0]) * (1 - t)
                 + np.array([95.0 * side_sign, -420.0, 0.0]) * t)
        shaft = shaft + rng.normal(scale=1.2, size=shaft.shape)
        return np.vstack([head, shaft])

    by_id = {"femur_r": femur(+1), "femur_l": femur(-1)}
    frames = audit.build_frames(by_id, {}, {})

    for side in ("r", "l"):
        assert f"femur_{side}" in frames, f"no femur_{side} frame from bone alone"
        how = frames[f"femur_{side}"][2]
        assert "NO cartilage" in how, how
        assert frames[f"femur_{side}"][3] == "long", "transverse axis is not fitted here"
        assert f"hip_bone_{side}" in frames, f"no hip_bone_{side} frame"
        hip_how = frames[f"hip_bone_{side}"][2]
        assert "FEMORAL HEAD centre standing in" in hip_how, hip_how
        assert "acetabular sphere fit," not in hip_how, \
            "a femoral head fit must not be reported as a fit of the socket"

    # The origin is the head centre, and the two are a hip-width apart.
    across = np.linalg.norm(frames["hip_bone_r"][0] - frames["hip_bone_l"][0])
    assert 150 < across < 210, f"hip centres {across:.0f} mm apart"
    # +Y of the femur frame must point superior, back up the shaft.
    assert frames["femur_r"][1][1][1] > 0.9, frames["femur_r"][1]


def test_the_bone_only_frame_refuses_a_head_it_cannot_fit():
    """A femur label that is all shaft and no head must produce no frame at
    all, rather than a frame centred on whatever the sphere fit converged to.
    """
    import sys as _sys
    _sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import audit_landmarks_vs_geometry as audit
    rng = np.random.default_rng(11)
    t = np.linspace(0, 1, 1500)[:, None]
    shaft = (np.array([90.0, 0.0, 0.0]) * (1 - t) + np.array([95.0, -420.0, 0.0]) * t)
    shaft = shaft + rng.normal(scale=1.0, size=shaft.shape)
    frames = audit.build_frames({"femur_r": shaft}, {}, {})
    assert "femur_r" not in frames, "a shaft with no head must not yield a frame"
