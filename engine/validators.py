"""Whole-model validation suite: schema conformance + anatomical
self-consistency checks. Used by both tests/ (pytest wrappers) and
scripts/build_atlas.py (human-readable report). See docs/VERIFICATION.md
for the methodology this implements.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / "schema"
DATA_DIR = REPO_ROOT / "data"


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
        if path.name == "anchors.json":
            continue  # auto-derived (scripts/generate_anchors.py); citation lives on the owning entity
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
    for path in DATA_DIR.rglob("*.json"):
        if "muscles" not in path.parts or path.name == "muscle_index.json":
            continue
        payload = _load_json(path)
        entities = payload if isinstance(payload, list) else [payload]
        for m in entities:
            if isinstance(m, dict) and "id" in m:
                muscle_ids.add(m["id"])
            att = m.get("attachments", {})
            check_ref(att.get("origin_bone"), f"muscle {m.get('id')} origin")
            check_ref(att.get("insertion_bone"), f"muscle {m.get('id')} insertion")

    anchors_path = DATA_DIR / "rig" / "anchors.json"
    if anchors_path.exists():
        for a in _load_json(anchors_path):
            check_ref(a.get("parent_bone_frame"), f"anchor {a.get('id')}")

    for path in DATA_DIR.rglob("*.json"):
        if "fascia" not in path.parts:
            continue
        payload = _load_json(path)
        entities = payload if isinstance(payload, list) else [payload]
        for entity in entities:
            for ba in entity.get("bony_attachments", []):
                check_ref(ba.get("bone"), f"fascia {entity.get('id')} bony_attachment")

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
