"""Whole-model validation suite: schema conformance + anatomical
self-consistency checks. Used by both tests/ (pytest wrappers) and
scripts/build_atlas.py (human-readable report). See docs/VERIFICATION.md
for the methodology this implements.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / "schema"
DATA_DIR = REPO_ROOT / "data"

# Words that mark a field as "we did not know", written where a real value
# belongs. They pass every emptiness check and read like content, which makes
# them more dangerous in clinical data than a blank.
_NON_LANDMARKS = ("unspecified", "unknown", "not specified", "not stated",
                  "tbd", "todo", "n/a", "none", "?")


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _all_data_files() -> List[Path]:
    return sorted(DATA_DIR.rglob("*.json"))


def _schema_for_file(path: Path) -> str | None:
    """Maps a data file to its schema id by directory convention."""
    rel = path.relative_to(DATA_DIR)
    parts = rel.parts
    if parts[0] == "skeleton" and "bone" in path.stem:
        return "bone.schema.json"
    if parts[0] == "skeleton" and "joint" in path.stem:
        return "joint.schema.json"
    if parts[0] == "muscles":
        return "muscle.schema.json"
    if parts[0] == "nerves" and path.name == "spinal_and_cranial_nerve_roots.json":
        return None  # reference table, not a nerve_branch entity list -- shape documented in docs/DATA_MODEL.md
    if parts[0] == "nerves":
        return "nerve_branch.schema.json"
    if parts[0] == "vascular":
        return "vessel_branch.schema.json"
    if parts[0] == "fascia":
        return "fascia.schema.json"
    if parts[0] == "ligaments":
        return "ligament.schema.json"
    if parts[0] == "cartilage":
        return "cartilage.schema.json"
    if parts[0] == "tendons":
        return "tendon.schema.json"
    if parts[0] == "rig" and "anchor" in path.stem:
        return "rig.schema.json"
    return None


def _resolver():
    store = {}
    for f in SCHEMA_DIR.glob("*.schema.json"):
        s = _load_json(f)
        store[s["$id"]] = s
        store[f.name] = s
    return store


def validate_schemas() -> List[str]:
    """Validates every array-of-entities JSON file in data/ against its
    corresponding schema. A data file is a JSON array of entities of one
    kind; each entity is validated individually."""
    problems = []
    if jsonschema is None:
        return ["jsonschema package not installed -- cannot run schema validation"]
    store = _resolver()
    for path in _all_data_files():
        schema_name = _schema_for_file(path)
        if schema_name is None:
            continue
        schema = store.get(schema_name)
        if schema is None:
            problems.append(f"{path}: no schema found named {schema_name}")
            continue
        resolver = jsonschema.RefResolver(base_uri=f"{SCHEMA_DIR.as_uri()}/", referrer=schema, store=store)
        validator = jsonschema.Draft7Validator(schema, resolver=resolver)
        payload = _load_json(path)
        entities = payload if isinstance(payload, list) else payload.get("items", [payload])
        for i, entity in enumerate(entities):
            for err in validator.iter_errors(entity):
                problems.append(f"{path}[{i}] ({entity.get('id', '?')}): {err.message}")
    return problems


def validate_source_coverage() -> List[str]:
    """Every entity must carry a non-empty 'source' citation somewhere on
    it (top-level, or on each functional_compartment / dof for
    fine-grained data)."""
    problems = []
    for path in _all_data_files():
        # Generated artifacts carry no citation of their own -- the citation
        # lives on the entities they were derived from.
        #   anchors.json           <- scripts/generate_anchors.py
        #   scene_3d_preview.json  <- scripts/export_3d_scene.py
        if path.name in ("anchors.json", "scene_3d_preview.json"):
            continue
        payload = _load_json(path)
        entities = payload if isinstance(payload, list) else payload.get("items", [payload])
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            has_top = bool(entity.get("source")) or bool(entity.get("sources"))
            has_nested = any(
                isinstance(v, list) and v and all(isinstance(x, dict) and x.get("source") for x in v)
                for k, v in entity.items()
                if k in ("functional_compartments", "degrees_of_freedom")
            )
            if not has_top and not has_nested:
                problems.append(f"{path} ({entity.get('id', '?')}): missing 'source' citation")
    return problems


def validate_bone_references() -> List[str]:
    """Every bone id referenced anywhere in the dataset (attachments,
    anchors, joints) must exist in skeleton/bones.json."""
    problems = []
    bones_path = DATA_DIR / "skeleton" / "bones.json"
    if not bones_path.exists():
        return ["data/skeleton/bones.json not found"]
    bone_ids = {b["id"] for b in _load_json(bones_path)}

    def check_ref(ref: str, context: str):
        if ref and ref not in bone_ids:
            problems.append(f"{context}: references unknown bone id '{ref}'")

    joints_path = DATA_DIR / "skeleton" / "joints.json"
    if joints_path.exists():
        for j in _load_json(joints_path):
            check_ref(j.get("parent_bone"), f"joint {j.get('id')}")
            check_ref(j.get("child_bone"), f"joint {j.get('id')}")

    muscle_ids = set()
    compartment_ids = set()
    for path in DATA_DIR.rglob("*.json"):
        if "muscles" not in path.parts or path.name == "muscle_index.json":
            continue
        payload = _load_json(path)
        entities = payload if isinstance(payload, list) else [payload]
        for m in entities:
            if isinstance(m, dict) and "id" in m:
                muscle_ids.add(m["id"])
                for comp in m.get("functional_compartments", []):
                    if isinstance(comp, dict) and comp.get("id"):
                        compartment_ids.add(comp["id"])
            att = m.get("attachments", {})
            check_ref(att.get("origin_bone"), f"muscle {m.get('id')} origin")
            check_ref(att.get("insertion_bone"), f"muscle {m.get('id')} insertion")

    # A nerve's targets hold three kinds of value: a muscle or
    # functional-compartment id for a motor branch, a dermatome label such as
    # 'lateral_trunk_skin_T4', and free prose such as 'skin of the medial
    # sole'. Only the first kind is a reference that has to resolve.
    #
    # Muscle and compartment ids always carry a side marker -- they end in
    # '_l'/'_r' or contain '_l_'/'_r_' -- which the other two kinds never do.
    # That is what separates a typo'd muscle reference from a territory label.
    motor_targets = muscle_ids | compartment_ids
    sided = re.compile(r"(^|_)[lr](_|$)")

    def check_motor_ref(value: str, context: str):
        if not isinstance(value, str) or " " in value.strip():
            return
        if not sided.search(value):
            return  # dermatome label or other non-muscle target
        if value not in motor_targets:
            problems.append(f"{context}: unknown muscle/compartment id '{value}'")

    for path in DATA_DIR.rglob("*.json"):
        if "nerves" not in path.parts:
            continue
        payload = _load_json(path)
        if not isinstance(payload, list):
            continue  # reference tables, not nerve_branch entities
        for entity in payload:
            if not isinstance(entity, dict):
                continue
            nid = entity.get("id")
            for target in entity.get("targets", []):
                check_motor_ref(target, f"nerve {nid} targets")
            entry = entity.get("motor_entry_point") or {}
            check_motor_ref(entry.get("target_muscle_compartment") or "",
                            f"nerve {nid} motor_entry_point")

    # Every muscle names the nerve that supplies it. Before this check existed,
    # over half the muscle set pointed at ids that resolved to nothing --
    # sided forms of unsided nerve entities, and branch names spelled
    # differently from the entity that already represented them.
    #
    # A minority of muscles genuinely have more than one source (adductor
    # magnus, the lumbricals, pectoralis major) or are supplied by a group
    # rather than a named branch. innervation.nerve holds a LIST for those,
    # every element of which must resolve, and each compartment names its
    # own nerves in innervation_branch_ids. For a while the schema held one
    # string and those muscles carried a packed pseudo-id that an allow-list
    # here excused; that is how 64 muscles came to point at nothing while
    # every check passed.
    nerve_ids = set()
    for path in DATA_DIR.rglob("*.json"):
        if "nerves" not in path.parts:
            continue
        payload = _load_json(path)
        if isinstance(payload, list):
            nerve_ids |= {e["id"] for e in payload
                          if isinstance(e, dict) and "id" in e}

    for path in DATA_DIR.rglob("*.json"):
        if "muscles" not in path.parts or path.name == "muscle_index.json":
            continue
        payload = _load_json(path)
        for m in (payload if isinstance(payload, list) else [payload]):
            if not isinstance(m, dict):
                continue
            # innervation.nerve is one id or a list of ids, and every one of
            # them has to be a nerve entity. Until it was made a list, muscles
            # with two nerves carried a packed pseudo-id such as
            # 'femoral_n_and_obturator_n' that an allow-list here excused --
            # which meant 64 muscles pointed at nothing and the validator said
            # so was fine. The allow-list is gone; the data was fixed instead.
            nerve = (m.get("innervation") or {}).get("nerve")
            for one in (nerve if isinstance(nerve, list) else [nerve]):
                if one and one not in nerve_ids:
                    problems.append(
                        f"muscle {m.get('id')} innervation.nerve: "
                        f"references unknown nerve id '{one}'")
            for c in m.get("functional_compartments") or []:
                for one in (c.get("innervation_branch_ids") or []):
                    if one not in nerve_ids:
                        problems.append(
                            f"compartment {c.get('id')} innervation_branch_ids: "
                            f"references unknown nerve id '{one}'")

    # Motor endplate data comes in two forms that answer different questions,
    # and conflating them would put an injection in the wrong place:
    #
    #   position_fraction_along_fascicle -- where the endplate sits along an
    #       individual fascicle. Near its midpoint for essentially every
    #       muscle, so 0.5 is a defensible default rather than a measurement.
    #   motor_endplate_zones -- where the endplate band sits along the whole
    #       MUSCLE, as a percentage of a named external landmark line. This is
    #       the published, muscle-specific figure and the one a clinician
    #       measures against.
    #
    # Every zone must therefore say which it is, and must never claim the
    # fascicle fraction is measured just because a published muscle-level zone
    # was added alongside it.
    for path in DATA_DIR.rglob("*.json"):
        if "muscles" not in path.parts or path.name == "muscle_index.json":
            continue
        payload = _load_json(path)
        for m in (payload if isinstance(payload, list) else [payload]):
            if not isinstance(m, dict):
                continue
            for comp in m.get("functional_compartments", []):
                cid = comp.get("id")
                zone = comp.get("neuromuscular_junction_zone")
                if zone is not None and not zone.get("evidence"):
                    problems.append(
                        f"compartment {cid} neuromuscular_junction_zone: missing "
                        f"'evidence' -- say whether the fascicle fraction is "
                        f"'measured' or a 'modelling_default'")
                for mz in comp.get("motor_endplate_zones", []):
                    rng = mz.get("zone_percent_range")
                    if not (isinstance(rng, list) and len(rng) == 2):
                        problems.append(
                            f"compartment {cid} motor_endplate_zones: "
                            f"zone_percent_range must be [low, high]")
                    elif rng[0] > rng[1]:
                        problems.append(
                            f"compartment {cid} motor_endplate_zones: "
                            f"zone_percent_range {rng} is inverted")
                    if not mz.get("reference_line_from") or not mz.get("reference_line_to"):
                        problems.append(
                            f"compartment {cid} motor_endplate_zones: a percentage "
                            f"is meaningless without both ends of its reference line")
                    else:
                        # A placeholder is not a landmark. Some published zones
                        # define their reference line only in a figure; when the
                        # endpoints are not known, the honest record is NO zone
                        # plus a note (see gluteus maximus), not a zone whose
                        # line reads 'unspecified'. Such an entry would pass the
                        # emptiness check above while still being unusable, and
                        # worse, would look like a target.
                        for end in ("reference_line_from", "reference_line_to"):
                            text = str(mz[end]).strip().lower()
                            if any(text.startswith(p) for p in _NON_LANDMARKS):
                                problems.append(
                                    f"compartment {cid} motor_endplate_zones: "
                                    f"{end} is a placeholder ({mz[end]!r}), not a "
                                    f"landmark -- record the gap in notes and "
                                    f"omit the zone rather than publishing an "
                                    f"unusable target")
                    if not mz.get("source"):
                        problems.append(
                            f"compartment {cid} motor_endplate_zones: missing source")
                    # A zone the source rules out is still recorded -- the
                    # anatomy is real and "do not put a needle here" is worth
                    # knowing -- but it must say why, or it reads as an
                    # unexplained downgrade of a perfectly good target.
                    if mz.get("recommended_as_injection_target") is False \
                            and not mz.get("notes"):
                        problems.append(
                            f"compartment {cid} motor_endplate_zones: a zone "
                            f"marked not recommended must say why in 'notes'")

                # An injection_target_point names a point in the limb, not a
                # level along a muscle, so the ways it can be wrong are worse.
                # A depth with no stated surface is the dangerous one: 40% of
                # forearm thickness from the front and 40% from the back are
                # different places, and nothing in the number says which.
                for pt in comp.get("injection_target_points", []):
                    for end in ("transverse_line_from", "transverse_line_to",
                                "longitudinal_line_from",
                                "longitudinal_line_to"):
                        text = str(pt.get(end, "")).strip().lower()
                        if not text or any(text.startswith(p)
                                           for p in _NON_LANDMARKS):
                            problems.append(
                                f"compartment {cid} injection_target_points: "
                                f"{end} must name a palpable landmark, not "
                                f"{pt.get(end)!r}")
                    if not pt.get("source"):
                        problems.append(
                            f"compartment {cid} injection_target_points: "
                            f"missing source")
                    if pt.get("depth_percent_of_limb_thickness") is not None \
                            and not pt.get("depth_measured_from") \
                            and not pt.get("notes"):
                        problems.append(
                            f"compartment {cid} injection_target_points: a "
                            f"depth with neither 'depth_measured_from' nor a "
                            f"note explaining its absence does not say which "
                            f"surface it is measured from, and is a needle "
                            f"depth in no particular direction")

            approach = m.get("ultrasound_injection_approach")
            if approach is not None:
                if not approach.get("transducer_placement"):
                    problems.append(
                        f"muscle {m.get('id')} ultrasound_injection_approach: "
                        f"a probe position is the whole point -- "
                        f"transducer_placement is required")
                if not approach.get("source"):
                    problems.append(
                        f"muscle {m.get('id')} ultrasound_injection_approach: "
                        f"missing source")

    anchors_path = DATA_DIR / "rig" / "anchors.json"
    if anchors_path.exists():
        for a in _load_json(anchors_path):
            check_ref(a.get("parent_bone_frame"), f"anchor {a.get('id')}")

    # Fascia is a network, not a tree: 'adjacent_fascia' is how continuity
    # between sheets is recorded, and a name that resolves to nothing breaks
    # exactly the traversal that makes the layer useful.
    fascia_ids = set()
    fascia_entities = []
    for path in DATA_DIR.rglob("*.json"):
        if "fascia" not in path.parts:
            continue
        payload = _load_json(path)
        entities = payload if isinstance(payload, list) else [payload]
        for entity in entities:
            if isinstance(entity, dict) and "id" in entity:
                fascia_ids.add(entity["id"])
                fascia_entities.append(entity)
            for ba in entity.get("bony_attachments", []):
                check_ref(ba.get("bone"), f"fascia {entity.get('id')} bony_attachment")

    for entity in fascia_entities:
        for neighbour in entity.get("adjacent_fascia", []):
            if neighbour not in fascia_ids:
                problems.append(
                    f"fascia {entity['id']} adjacent_fascia: "
                    f"references unknown fascia id '{neighbour}'")

    joint_ids = set()
    if joints_path.exists():
        joint_ids = {j["id"] for j in _load_json(joints_path)}

    def check_joint_ref(ref: str, context: str):
        if ref and ref not in joint_ids:
            problems.append(f"{context}: references unknown joint id '{ref}'")

    for path in DATA_DIR.rglob("*.json"):
        if "ligaments" not in path.parts:
            continue
        payload = _load_json(path)
        entities = payload if isinstance(payload, list) else [payload]
        for entity in entities:
            eid = entity.get("id")
            check_joint_ref(entity.get("joint"), f"ligament {eid} joint")
            att = entity.get("attachments", {})
            check_ref(att.get("bone_a"), f"ligament {eid} attachments.bone_a")
            check_ref(att.get("bone_b"), f"ligament {eid} attachments.bone_b")
            for band in entity.get("bands", []):
                batt = band.get("attachments", {})
                check_ref(batt.get("bone_a"), f"ligament {eid} band {band.get('id')} bone_a")
                check_ref(batt.get("bone_b"), f"ligament {eid} band {band.get('id')} bone_b")

    for path in DATA_DIR.rglob("*.json"):
        if "cartilage" not in path.parts:
            continue
        payload = _load_json(path)
        entities = payload if isinstance(payload, list) else [payload]
        for entity in entities:
            eid = entity.get("id")
            check_joint_ref(entity.get("joint"), f"cartilage {eid} joint")
            check_ref(entity.get("parent_bone"), f"cartilage {eid} parent_bone")
            att = entity.get("attachments", {})
            if att:
                check_ref(att.get("bone_a"), f"cartilage {eid} attachments.bone_a")
                check_ref(att.get("bone_b"), f"cartilage {eid} attachments.bone_b")

    def check_attachment_endpoint(endpoint: dict, context: str):
        if not endpoint:
            return
        t, ref = endpoint.get("type"), endpoint.get("ref")
        if t == "bone":
            check_ref(ref, context)
        elif t == "muscle" and ref and ref not in muscle_ids:
            problems.append(f"{context}: references unknown muscle id '{ref}'")

    for path in DATA_DIR.rglob("*.json"):
        if "tendons" not in path.parts:
            continue
        payload = _load_json(path)
        entities = payload if isinstance(payload, list) else [payload]
        for entity in entities:
            eid = entity.get("id")
            for pm in entity.get("parent_muscles", []):
                if pm not in muscle_ids:
                    problems.append(f"tendon {eid} parent_muscles: references unknown muscle id '{pm}'")
            att = entity.get("attachments", {})
            check_attachment_endpoint(att.get("proximal_attachment"), f"tendon {eid} proximal_attachment")
            check_attachment_endpoint(att.get("distal_attachment"), f"tendon {eid} distal_attachment")
            for part in entity.get("parts", []):
                pm = part.get("parent_muscle")
                if pm and pm not in muscle_ids:
                    problems.append(f"tendon {eid} part {part.get('id')} parent_muscle: references unknown muscle id '{pm}'")
    return problems


# Fields whose values are ids of other entities. Anything in one of these
# that looks like an id and resolves to nothing is a hole in the graph. The
# list is explicit rather than inferred from field names, because the same
# word means different things in different records: `targets` on a nerve
# holds compartment ids AND dermatome prose, and `articulates_with` on a
# bone may name a bone this skeleton groups away.
_CROSS_REFERENCE_FIELDS = (
    "parent_id", "owner_entity", "parent_bone_frame", "bone_frame",
    "origin_bone", "insertion_bone", "supplies_or_drains", "targets",
    "anastomoses_with", "root_contributions", "innervation_branch_ids",
    "parent_muscles", "target_muscle_compartment",
)

# Referenced ids this atlas knowingly does not carry, each with the reason.
# An allow-list without reasons is a place to hide missing data.
_KNOWN_ABSENT = {
    # The skeleton groups the facial bones; a mandible's articulation with the
    # maxilla is real, and the maxilla is not an entity here.
    "parietal": "skull bones are not modelled individually",
    "nasal": "skull bones are not modelled individually",
    "zygomatic": "skull bones are not modelled individually",
    "maxilla": "skull bones are not modelled individually",
    "lacrimal": "skull bones are not modelled individually",
    "temporal": "skull bones are not modelled individually",
    "frontal": "skull bones are not modelled individually",
    "sphenoid": "skull bones are not modelled individually",
    "ethmoid": "skull bones are not modelled individually",
    "palatine": "skull bones are not modelled individually",
    "hyoid": "not carried as a bone entity",
    # Regions a vessel supplies, named in prose in supplies_or_drains. One
    # lowercase word is indistinguishable from an id by shape alone --
    # 'sacrum' and 'sternum' are ids -- so these are named here instead.
    "breast": "a region, not an entity",
    "perineum": "a region, not an entity",
    "acromion": "a region of the scapula, not an entity",
}

_BARE_ID = re.compile(r"^[a-z][a-z0-9_]*$")


def validate_cross_references() -> List[str]:
    """Every id-valued reference field must point at an entity that exists.

    This found lateral_circumflex_femoral_a_r supplying
    'quadriceps_femoris_group_r', an id the atlas has never carried, and the
    22 packed innervation strings that 64 muscles pointed at. Free text is
    allowed in fields the schema says hold prose -- "laryngeal mucosa below
    the vocal folds" is a legitimate nerve target -- so only values shaped
    like a bare id are checked, and a bare id that resolves to nothing is
    reported unless it is in _KNOWN_ABSENT with a reason.
    """
    known = set()

    def collect(node):
        if isinstance(node, dict):
            if isinstance(node.get("id"), str):
                known.add(node["id"])
            for v in node.values():
                collect(v)
        elif isinstance(node, list):
            for v in node:
                collect(v)

    payloads = {}
    for path in _all_data_files():
        payloads[path] = _load_json(path)
        collect(payloads[path])

    problems = []

    def check(value, where):
        if not isinstance(value, str) or not _BARE_ID.match(value):
            return
        if value in known or value in _KNOWN_ABSENT:
            return
        problems.append(f"{where}: references unknown id '{value}'")

    def scan(node, where):
        if isinstance(node, dict):
            label = node.get("id", where) if isinstance(node.get("id"), str) else where
            for k, v in node.items():
                if k in _CROSS_REFERENCE_FIELDS:
                    if isinstance(v, list):
                        for x in v:
                            check(x, f"{label}.{k}")
                    else:
                        check(v, f"{label}.{k}")
                scan(v, label)
        elif isinstance(node, list):
            for v in node:
                scan(v, where)

    for path, payload in payloads.items():
        scan(payload, str(path.relative_to(DATA_DIR)))
    return problems


def validate_symmetry() -> List[str]:
    """Every 'right'-sided bilateral entity should have a matching 'left'
    counterpart with the same base id (id minus the _r/_l suffix).

    Collected GLOBALLY across all data files first, then checked -- entities
    are one-per-file in some directories (e.g. data/muscles/upper_limb/*.json),
    so a sibling's 'left' counterpart is often in a different file, not the
    same one.
    """
    problems = []
    all_sided: Dict[str, Path] = {}  # id -> file it was found in
    for path in _all_data_files():
        payload = _load_json(path)
        entities = payload if isinstance(payload, list) else [payload]
        for e in entities:
            if isinstance(e, dict) and e.get("side") in ("left", "right") and "id" in e:
                all_sided[e["id"]] = path

    for eid, path in all_sided.items():
        if eid.endswith("_r"):
            mirror = eid[:-2] + "_l"
            if mirror not in all_sided:
                problems.append(f"{path}: '{eid}' has no left-side counterpart '{mirror}'")
        elif eid.endswith("_l"):
            mirror = eid[:-2] + "_r"
            if mirror not in all_sided:
                problems.append(f"{path}: '{eid}' has no right-side counterpart '{mirror}'")
    return problems


def validate_rom_bounds() -> List[str]:
    """Sanity-bounds check (not equality) on ROM: every joint DOF's range
    must be physiologically plausible (nonzero span for a genuine DOF,
    within +/-360 of neutral, min < max)."""
    problems = []
    joints_path = DATA_DIR / "skeleton" / "joints.json"
    if not joints_path.exists():
        return []
    for j in _load_json(joints_path):
        for dof in j.get("degrees_of_freedom", []):
            lo, hi = dof.get("min_deg"), dof.get("max_deg")
            if lo is None or hi is None:
                problems.append(f"joint {j['id']} dof {dof.get('axis_name')}: missing min/max")
                continue
            if lo >= hi:
                problems.append(f"joint {j['id']} dof {dof.get('axis_name')}: min >= max ({lo} >= {hi})")
            if abs(lo) > 360 or abs(hi) > 360:
                problems.append(f"joint {j['id']} dof {dof.get('axis_name')}: range implausible ({lo}..{hi})")
    return problems


def run_all() -> Dict[str, List[str]]:
    return {
        "schema_validation": validate_schemas(),
        "source_coverage": validate_source_coverage(),
        "bone_references": validate_bone_references(),
        "symmetry": validate_symmetry(),
        "rom_bounds": validate_rom_bounds(),
    }


if __name__ == "__main__":
    results = run_all()
    total_problems = sum(len(v) for v in results.values())
    for check, problems in results.items():
        status = "PASS" if not problems else f"FAIL ({len(problems)})"
        print(f"[{status}] {check}")
        for p in problems[:50]:
            print(f"    - {p}")
    raise SystemExit(1 if total_problems else 0)
