"""Q142 phase 2: load Z-Anatomy's extracted meshes as a `cross_subject_transfer.py` SOURCE.

Reuses Q141's own outputs unchanged: `data/derived/zanatomy_inventory.json` (per-object
metadata) and `data/derived/zanatomy_name_map.json` (name -> atlas_id, confident/exact
only -- "never guess" is inherited verbatim from that mapping). The only new work here is:

1. THE AXIS/SCALE CONVERSION from Z-Anatomy's raw frame into this project's atlas frame
   (+X subject right, +Y superior, +Z anterior, mm). Verified the same way
   docs/GEOMETRY_SOURCES.md verified the Visible Human STL frame -- an anatomical test per
   axis on Z-Anatomy's OWN geometry, not read off a filename or assumed:

   | Atlas axis    | Raw axis | Test (Z-Anatomy inventory bboxes, right side unless noted) |
   |---------------|----------|--------------------------------------------------------------|
   | +X (right)    | -x       | Lateral-minus-medial, gastrocnemius heads: -47.2 mm (raw x). Femur.r centroid x -90.2 vs Femur.l +90.2 (exact mirror) confirms which raw sign is which named side. |
   | +Y (superior) | +z       | Hip bone centroid minus calcaneus centroid: dominant component +867.6 mm (raw z). |
   | +Z (anterior) | -y       | Tibialis anterior minus soleus: dominant component -53.3 mm (raw y); cross-checked by the sternum (very anterior), raw y in [-130.8, -31.6] throughout. |

   Scale is 1:1 mm; no unit conversion (Femur.r raw z-extent 454.4 mm matches Q141's own
   reported femur length exactly, in the RAW frame already).

2. CANONICAL-OBJECT PICKING when more than one Z-Anatomy object maps to the same atlas_id.
   This happens for two real reasons, not mapping bugs:
   - Z-Anatomy ships small ".e*"/".o*" DUPLICATE objects per structure for its own app's
     interactive highlight/origin-insertion overlays (confirmed by inspection: e.g.
     "Brachioradialis muscle.r" is 3658 vertices, "Brachioradialis muscle.er" is 258 and
     ".or" is 254 -- decorative highlight copies, not separate tissue). These clear
     extract_fbx.py's --min-vertices pin-marker filter (12) but are not the real surface.
     Picking the candidate with the LARGEST vertex_count per (atlas_id, side) resolves
     this without a name blocklist.
   - A handful of matches are simply wrong at the phase-1 min-score/margin policy (e.g.
     "Ligament of head of femur.l" -> femur_l at score 0.90, a substring artifact) --
     these lose to the real object's score of 1.0 (exact) under the same max-score rule,
     so no separate handling is needed.
   - A second, more dangerous phase-1 artifact found while building this loader:
     `extensor_carpi_ulnaris_r` (a muscle) has NO merged Z-Anatomy object at all --
     only "Humeral head of ECU", "Ulnar head of ECU" (its two real heads) and "Tendon
     sheath of ECU" (a synovial sheath, not muscle) all score as confident matches on
     the SAME atlas_id, and the tendon sheath (482 vertices) has more vertices than
     either head alone, so a naive largest-vertex-count pick would ship a tendon sheath
     as if it were the muscle belly. Fixed by (a) dropping any candidate whose name
     names a different tissue than the target category (tendon sheath / bursa / fascia
     / "ligament of" against a `muscle` or `bone` target -- see `_CROSS_CATEGORY_JUNK`),
     then (b) grouping the survivors by their name with the .r/.l/.er/.or/... suffix
     stripped (map_names.strip_suffix): objects sharing that stripped name are the
     highlight-duplicate case above (pick the largest); objects with DIFFERENT stripped
     names are genuinely different real sub-parts (e.g. the two ECU heads) and are
     concatenated together, the same way this project's own multi-piece structures are
     already read back as one mesh by bundle_io.meshes_by_id().

3. SIDE HANDLING for the rare atlas id that carries no _r/_l suffix (e.g. this project's
   `sciatic_n`, which represents a single measured side, not "both sides under one id"):
   if the atlas_id ends in _r/_l, only same-side Z-Anatomy candidates are considered;
   otherwise every matching side is kept and concatenated, matching how
   scripts/transfer/bundle_io.py's own meshes_by_id() already treats a multi-piece
   structure sharing one id for real subjects.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

DEFAULT_INVENTORY = REPO / "data/derived/zanatomy_inventory.json"
DEFAULT_NAMEMAP = REPO / "data/derived/zanatomy_name_map.json"
DEFAULT_ZAN_DIR = REPO / "build/zanatomy"
DEFAULT_EXTRA_LINKS = REPO / "data/derived/Q158_new_links.json"

_SAFE_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def safe_filename(name: str) -> str:
    """Exactly scripts/zanatomy/extract_fbx.py's own safe_filename() (duplicated here
    rather than imported: that module requires bpy and is not importable by the
    project's main numpy 2.x interpreter -- see its own module docstring)."""
    return _SAFE_RE.sub("_", name).strip("_") or "unnamed"


def to_atlas_frame(v: np.ndarray) -> np.ndarray:
    """Z-Anatomy raw mm -> this project's atlas mm frame. See module docstring for the
    anatomical tests that fixed each axis. Origin is left as extracted (the per-bone
    affine registration in cross_subject_transfer.py fits translation per bone, so a
    global origin offset here would cancel out; it is not this function's job)."""
    v = np.asarray(v, dtype=np.float64)
    out = np.empty_like(v)
    out[:, 0] = -v[:, 0]
    out[:, 1] = v[:, 2]
    out[:, 2] = -v[:, 1]
    return out


def _side_of_atlas_id(aid: str) -> str | None:
    if aid.endswith("_r"):
        return "right"
    if aid.endswith("_l"):
        return "left"
    return None


# name substrings that mean "a different tissue than the muscle/bone/nerve/vessel this
# was matched to", found by inspection while building this loader (see module docstring,
# extensor_carpi_ulnaris_r). Checked only against categories where the substring is never
# itself the right answer.
_CROSS_CATEGORY_JUNK = {
    "muscle": ("tendon sheath", "bursa", "fascia", "ligament of", " ligament"),
    "bone": ("tendon", "muscle", "ligament", "fascia"),
    "nerve": ("artery", "vein", "ganglion", "plexus of"),
    "vessel": ("nerve",),
}


def _is_cross_category_junk(name: str, cat: str) -> bool:
    low = name.lower()
    return any(bad in low for bad in _CROSS_CATEGORY_JUNK.get(cat, ()))


# a THIRD phase-1 artifact found while building this loader, worse than the two in the
# module docstring: "Infraspinatus muscle.or"/".ol" (6728 vertices, a muscle-scale
# bounding box) is not the muscle at all -- Z-Anatomy filed it under system=Skeletal, not
# Muscular (it is a scapula-surface insertion-footprint highlight, essentially a flat
# decal, which is why its own enclosed volume comes out near zero despite the large
# bbox and vertex count -- neither of those catches it, only the system mismatch does).
# Restricting each atlas category to the Z-Anatomy systems it can plausibly come from
# fixes this directly, ahead of the name-substring and vertex-count checks above.
_ALLOWED_SYSTEMS = {
    "muscle": {"Muscular"}, "bone": {"Skeletal"}, "ligament": {"Joints"},
    "cartilage": {"Joints", "Skeletal"}, "tendon": {"Muscular", "Joints"},
    "fascia": {"Muscular", "Joints"}, "nerve": {"Nervous"}, "vessel": {"CardioVascular"},
    "bursa": {"Joints", "Muscular"},
}


# Q144 (radial nerve pathway audit): a FOURTH phase-1/2 name-map artifact, found
# while auditing the radial nerve for the owner's first named correction.
# "Deep branch of radial nerve" IS the posterior interosseous nerve -- this
# project's own registry already carries a dedicated `posterior_interosseous_n`
# entity for it (data/nerves/brachial_plexus.json) -- but map_names.py's generic
# substring scorer (engine.vh_ingest.similarity(), unchanged and not touched
# here) happens to score it as a *confident* 0.90 match against `radial_n` (the
# trunk) instead, because "radial nerve" is a substring of "deep branch of
# radial nerve" while "posterior interosseous nerve" shares no tokens with it at
# all. Left uncorrected, this folds the PIN's own mesh into the trunk (worse
# fragmentation on top of the left+right union bug below) and ships the
# registry's own `posterior_interosseous_n` id with NO geometry at all -- which
# would make items (d)/(e) of the pathway audit (bifurcation level, arcade-of-
# Frohse passage) impossible to check. Fixed the same way Q142's three
# precedents above were: a small by-name override here, not a change to the
# reusable matcher (map_names.py, or its committed
# data/derived/zanatomy_name_map.json output, are both left exactly as Q141
# produced them).
_ATLAS_ID_OVERRIDE = {
    "Deep branch of radial nerve": "posterior_interosseous_n",
}


def load_extra_links(path=DEFAULT_EXTRA_LINKS) -> list[dict]:
    """Q158b: curated, rule-tagged Z-Anatomy name -> PARENT atlas id links this
    project's own downstream review found for cases `map_names.py`'s generic
    matcher correctly declined to guess (grouped many-to-one containment,
    tissue-category tie-breaks on an ambiguous pair, and a small set of
    numbered-series regexes -- see `scripts/zanatomy/build_q158_links.py`'s own
    module docstring for exactly which).

    Q158's first cut fed these into `load_source()`'s own per-atlas-id `groups`
    dict, MERGING each linked Z-Anatomy object's geometry into its parent's
    mesh (e.g. all 8 carpal bones unioned into one `carpals_l` blob). Lead
    review (Q158b) reverted that: for an anatomy atlas, merging destroys the
    ability to select a single named structure (no more picking "scaphoid" on
    its own once it is fused into a carpal blob). This loader is now READ-ONLY
    metadata -- `scripts/zanatomy/build_zan_atlas_viewer.py` uses it to attach
    a `part_of`/`part_of_id` reference (and the parent's own cited facts,
    clearly labelled as the parent's) onto that Z-Anatomy object's OWN,
    still-separate orphan mesh, never to combine geometry. `load_source()`
    itself is back to reading only `map_names.py`'s own exact/confident
    matches (plus `_ATLAS_ID_OVERRIDE`), unchanged from before Q158.

    Kept in their own committed file rather than edited into `map_names.py`'s
    frozen output, per the same standing rule this module's own docstring
    states for its `_ATLAS_ID_OVERRIDE`/`_CROSS_CATEGORY_JUNK`/
    `_ALLOWED_SYSTEMS` tables. Returns `[]` if the file does not exist (this
    loader is optional, unlike the namemap itself)."""
    p = Path(path)
    if not p.exists():
        return []
    return json.loads(p.read_text()).get("links", [])


def load_source(*, inventory_path=DEFAULT_INVENTORY, namemap_path=DEFAULT_NAMEMAP,
                 zan_dir=DEFAULT_ZAN_DIR, min_vertices: int = 1):
    """Return {atlas_id: {'v','f','cat','side','subject','rec'}} -- the same shape
    scripts/transfer/bundle_io.py's own_only(meshes_by_id(...)) returns for a real
    bundle, so scripts/transfer/cross_subject_transfer.py's build_bone_maps() and
    blend_transfer() need no changes to accept it as `src`.

    `min_vertices` only drops degenerate single candidates (cross_subject_transfer.py's
    own MIN_VERTICES=64 filter in main() already screens fragments after this)."""
    from engine import vh_ingest as vh                       # noqa: E402  (project's main venv only)
    from scripts.zanatomy.map_names import load_full_atlas, strip_suffix  # noqa: E402
    from scripts.export_viewer_bundle import load_atlas_records  # noqa: E402

    inventory = json.loads(Path(inventory_path).read_text())
    namemap = json.loads(Path(namemap_path).read_text())
    objs_by_name = {o["name"]: o for o in inventory["objects"]}
    id_to_cat = {e.entity_id: e.category for e in load_full_atlas()}
    atlas_records = load_atlas_records()

    # atlas_id -> side -> [ (vertex_count, zanatomy_name, status, score, system) ]
    groups: dict[str, dict] = {}
    for e in namemap["entries"]:
        aid = e.get("atlas_id")
        if not aid or e["status"] not in ("exact", "confident"):
            continue
        aid = _ATLAS_ID_OVERRIDE.get(strip_suffix(e["zanatomy_name"]), aid)
        cat = id_to_cat.get(aid)
        if cat is None or _is_cross_category_junk(e["zanatomy_name"], cat):
            continue
        obj = objs_by_name.get(e["zanatomy_name"])
        if obj is None or obj["vertex_count"] < min_vertices:
            continue
        if obj["system"] not in _ALLOWED_SYSTEMS.get(cat, {obj["system"]}):
            continue
        wanted_side = _side_of_atlas_id(aid)
        obj_side = obj.get("side")
        if wanted_side and obj_side and obj_side != wanted_side:
            continue  # e.g. a mismatched-side name-match artifact; never trust it over the id's own side
        groups.setdefault(aid, {}).setdefault(obj_side, []).append(
            (obj["vertex_count"], e["zanatomy_name"], e["status"], e["score"], obj["system"]))

    def _mesh_for_cands(cands):
        """One (atlas_id[, side]) group's own Z-Anatomy candidates -> concatenated
        (v, f, parts_used) in that group's own local vertex numbering, or
        (None, None, []) if nothing on disk survives. Applies the highlight-copy
        dedup + tiny-orphan-drop policy (module docstring, point 2) -- factored out
        of the old single per-aid loop so the Q144 side-split below (which needs
        this run once PER SIDE instead of once per id) reuses it exactly, rather
        than duplicating the policy a second time."""
        by_base: dict[str, tuple] = {}
        for c in cands:
            base = strip_suffix(c[1])
            if base not in by_base or c[0] > by_base[base][0]:
                by_base[base] = c
        reps = list(by_base.values())
        max_vc = max(c[0] for c in reps)
        reps = [c for c in reps if c[0] >= max(30, 0.25 * max_vc)]
        reps.sort(key=lambda c: (c[2] != "exact", -c[3], -c[0]))
        vs, fs, voff, parts_used = [], [], 0, []
        for _, name, status, score, system in reps:
            path = Path(zan_dir) / system / f"{safe_filename(name)}.npz"
            if not path.exists():
                continue
            d = np.load(path)
            vs.append(to_atlas_frame(d["vertices_mm"]))
            fs.append(d["faces"].astype(np.int64) + voff)
            voff += len(vs[-1])
            parts_used.append(name)
        if not vs:
            return None, None, []
        return np.concatenate(vs), np.concatenate(fs), parts_used

    out = {}
    for aid, by_side in groups.items():
        cat = id_to_cat[aid]
        folder, rec = atlas_records.get(aid, (None, None))
        region = (rec or {}).get("region")
        wanted_side = _side_of_atlas_id(aid)
        real_sides = {s for s in by_side if s in ("right", "left")}

        # Q144 (radial nerve pathway audit's own queued side-field fix, generalised):
        # this project's nerve entities carry no side field at all (`radial_n`,
        # `sciatic_n`, `femoral_n`, ... -- the "nerve-category data gap" Q142/Q143
        # both found and left alone), but Z-Anatomy always ships a real object per
        # side. Unfiltered, `wanted_side` above is None for every one of them, so
        # nothing in the loop below ever restricts by side and left+right get
        # unioned into one fragmented mesh under the bare id -- confirmed (see
        # PROJECT_STATE.md Q144) on 63 sideless nerve ids this way, `radial_n`
        # included. Restricted to category=="nerve": the same both-sides-present
        # pattern also turns up on 5 non-nerve ids (ethmoid, procerus,
        # external_anal_sphincter, interclavicular_ligament,
        # intertransverse_ligament) where a bilateral geometry legitimately IS one
        # combined structure (paired halves of one bone/ligament/midline muscle,
        # not two independent organs) and unioning is the correct behaviour --
        # left alone here, logged in the Q144 audit report only. A nerve, in
        # contrast, is never one structure across both sides. Ships each side as
        # its own `<aid>_r`/`<aid>_l`, this project's own bilateral-structure
        # convention, instead of the base id -- the base id is never written for
        # these. A candidate whose OWN side is unresolved (side=None; one case
        # release-wide, `brachial_cord_posterior`) is dropped rather than guessed
        # onto either side ("never guess", this loader's standing rule).
        if wanted_side is None and cat == "nerve" and len(real_sides) > 1:
            for side, suffix in (("right", "_r"), ("left", "_l")):
                cands = by_side.get(side)
                if not cands:
                    continue
                v, f, parts_used = _mesh_for_cands(cands)
                if v is None:
                    continue
                out[aid + suffix] = {
                    "v": v.astype(np.float32), "f": f.astype(np.int64), "cat": cat,
                    "side": side, "subject": "zanatomy", "rec": {"region": region},
                    "pieces": 1, "zanatomy_parts": parts_used,
                    # Q144: the real entity record is still filed under the bare
                    # `aid` (nerve entity records are not split by side in this
                    # project's own registry, unlike muscles/bones) -- carried
                    # through so build_zan_reference.py can fall back to its
                    # name/region for display, the same way it already does for
                    # an ORPHAN id with no entity record at all.
                    "base_atlas_id": aid,
                    "base_name": (rec or {}).get("name_common") or (rec or {}).get("name"),
                }
            continue

        vs, fs, voff, parts_used, chosen_side = [], [], 0, [], None
        for side, cands in by_side.items():
            v, f, used = _mesh_for_cands(cands)
            if v is None:
                continue
            vs.append(v); fs.append(f + voff); voff += len(v)
            parts_used.extend(used)
            chosen_side = side if len(by_side) == 1 else None  # None (mixed) once >1 side is combined
        if not vs:
            continue
        v = np.concatenate(vs).astype(np.float32)
        f = np.concatenate(fs).astype(np.int64)
        out[aid] = {"v": v, "f": f, "cat": cat, "side": chosen_side or wanted_side,
                    "subject": "zanatomy", "rec": {"region": region}, "pieces": len(vs),
                    "zanatomy_parts": parts_used}
    return out
