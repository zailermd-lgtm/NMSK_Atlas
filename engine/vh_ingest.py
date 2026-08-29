"""Ingest support for the Visible Human lower-extremity geometry.

Reads the University of Denver segmentation of the NLM Visible Human
cryosections (Andreassen TE, Hume DR, Hamilton LD, Walker KE, Higinbotham SE,
Shelburne KB, *Sci Data* 10:34, 2023, doi:10.1038/s41597-022-01905-2) and
lines its structures up against this atlas's own entity IDs.

See docs/GEOMETRY_SOURCES.md for why this dataset was chosen and what
attribution travels with it.

WHAT THIS MODULE ASSUMES -- and deliberately does not
=====================================================
The dataset is ~355 GB and was not reachable from the machine this module was
written on, so nothing here hardcodes a filename convention, a structure-name
list, or a coordinate frame. Every one of those is *measured* from whatever
you actually downloaded and reported back for you to confirm.

Concretely:

* Structure names are parsed from filenames and then matched against the
  atlas by normalised token overlap. Matches are proposed with a score and
  written to an editable mapping file -- they are never applied silently.
* The source coordinate frame is inferred (up-axis from the bounding box
  aspect, units from its magnitude) and *reported*. Conversion refuses to run
  on inference alone; you pass the frame explicitly once you have seen it.

The atlas frame is +X right, +Y superior, +Z anterior, in millimetres.
"""
from __future__ import annotations

import json
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

# Directory -> atlas category. Mirrors engine/validators.py's mapping.
CATEGORY_BY_DIR = {
    "muscles": "muscle",
    "skeleton": "bone",          # bones.json and joints.json both live here
    "ligaments": "ligament",
    "cartilage": "cartilage",
    "tendons": "tendon",
    "fascia": "fascia",
}

# Structures the DU release contains, by their own description. Used only to
# sanity-check coverage after mapping -- not to guess filenames.
DU_EXPECTED_COUNTS = {
    "muscle": 76,
    "bone": 28,
    "cartilage": 16,
    "ligament": 8,
    "fat": 2,
}


# --------------------------------------------------------------------------
# STL reading
# --------------------------------------------------------------------------

def _looks_binary_stl(path: Path) -> bool:
    """An ASCII STL starts with 'solid', but so do some binary ones. The
    reliable test is whether the file size matches the binary layout."""
    size = path.stat().st_size
    if size < 84:
        return False
    with path.open("rb") as fh:
        fh.seek(80)
        count = struct.unpack("<I", fh.read(4))[0]
    return size == 84 + count * 50


def read_stl(path: Path) -> np.ndarray:
    """Return an (n, 3, 3) float64 array of triangle vertices."""
    if _looks_binary_stl(path):
        return _read_stl_binary(path)
    return _read_stl_ascii(path)


def _read_stl_binary(path: Path) -> np.ndarray:
    with path.open("rb") as fh:
        fh.seek(80)
        count = struct.unpack("<I", fh.read(4))[0]
        raw = np.frombuffer(fh.read(count * 50), dtype=np.uint8)
    if raw.size != count * 50:
        raise ValueError(f"{path.name}: truncated binary STL")
    # Each 50-byte record: 3 floats normal, 9 floats vertices, 2 bytes attr.
    floats = raw.reshape(count, 50)[:, 12:48].copy().view("<f4")
    return floats.reshape(count, 3, 3).astype(np.float64)


_ASCII_VERTEX = re.compile(rb"vertex\s+(\S+)\s+(\S+)\s+(\S+)")


def _read_stl_ascii(path: Path) -> np.ndarray:
    verts = [
        (float(a), float(b), float(c))
        for a, b, c in _ASCII_VERTEX.findall(path.read_bytes())
    ]
    if not verts or len(verts) % 3:
        raise ValueError(f"{path.name}: {len(verts)} ASCII STL vertices, not a multiple of 3")
    return np.asarray(verts, dtype=np.float64).reshape(-1, 3, 3)


def weld(tris: np.ndarray, tol_mm: float = 1e-4) -> Tuple[np.ndarray, np.ndarray]:
    """Collapse an STL triangle soup into indexed (vertices, faces).

    STL stores every triangle independently, so a mesh arrives with roughly
    three times as many vertices as it needs and no connectivity at all.
    Quantising to `tol_mm` before deduplicating is what recovers shared
    vertices -- and therefore smooth normals downstream.
    """
    flat = tris.reshape(-1, 3)
    keys = np.round(flat / tol_mm).astype(np.int64)
    _, first, inverse = np.unique(keys, axis=0, return_index=True, return_inverse=True)
    return flat[first], inverse.reshape(-1, 3).astype(np.int64)


# --------------------------------------------------------------------------
# Name normalisation and matching
# --------------------------------------------------------------------------

# Anatomical synonyms and spelling variants. Left-hand side is normalised
# away to the right-hand side before comparison, in both datasets.
#
# Deliberately contains NO truncated-word expansions ("long" -> "longus",
# "lat" -> "lateralis", "med" -> "medialis" and friends). Those look helpful
# but several are real anatomical words in their own right: expanding "long"
# turns the biceps femoris *long head* into a "longus head", and "lat" is
# both an abbreviation for lateralis and the name of a muscle. Nothing is
# known about whether this dataset abbreviates at all, so the risk buys
# nothing. Add them back only against an observed naming convention.
SYNONYMS = {
    "peroneus": "fibularis",
    "peroneal": "fibular",
    "great toe": "hallux",
    "big toe": "hallux",
    "little toe": "digiti minimi",
    "thumb": "pollicis",
    "kneecap": "patella",
    "quads": "quadriceps",
    # Latin forms used in the atlas's name_ta vs the English forms datasets
    # normally use for the same bone.
    "naviculare": "navicular",
    "cuboideum": "cuboid",
    "scaphoideum": "scaphoid",
    "lunatum": "lunate",
    "pisiforme": "pisiform",
    "trapezoideum": "trapezoid",
    "capitatum": "capitate",
    "hamatum": "hamate",
    "cuneiforme": "cuneiform",
    "tarsi": "tarsal",
    "carpi": "carpal",
    "coxae": "hip",
    "pelvis": "hip",
    # Standard clinical abbreviations for the knee ligaments. The atlas names
    # the collaterals by the bone they attach to, which is what these expand to.
    "acl": "anterior cruciate",
    "pcl": "posterior cruciate",
    "mcl": "tibial collateral",
    "lcl": "fibular collateral",
    # Misspellings present in the DU Visible Human release itself, confirmed
    # against the actual file listing (VHM_Right_Bone_Calcaneous_smooth.stl,
    # VHM_Right_Muscle_Illiacus_smooth.stl,
    # VHM_Right_Muscle_QuadratisFemoris_smooth.stl). These are corrections to
    # observed strings, not guesses about how the dataset *might* abbreviate,
    # which is the distinction the note above insists on.
    "calcaneous": "calcaneus",
    "illiacus": "iliacus",
    "quadratis": "quadratus",
    # The two sides of the release are not spelled consistently with each
    # other. Right says QuadratisFemoris where left says QuadratusFemoris
    # (left is the correct one); left says Hallicus and Semitendonosus where
    # right says Hallucis and Semitendinosus (right is correct there). Both
    # spellings of each are normalised to the correct form, so a mapping made
    # against one side applies to the other.
    "hallicus": "hallucis",
    "semitendonosus": "semitendinosus",
}

# Structures that lie on the midline but are filed under one side in the
# release: VHM_Left_Bone_Sacrum_smooth.stl is not a left sacrum, it is the
# sacrum, in the folder someone put it in. Taking the folder's word for it
# would stamp side="left" on a midline bone and carry that falsehood into
# every manifest downstream.
MIDLINE_STRUCTURES = {"sacrum", "coccyx", "pubic symphysis", "sacrum coccyx"}


def resolve_side(name: str) -> Tuple[str, Optional[str]]:
    """split_side(), with the side dropped for known midline structures."""
    base, side = split_side(name)
    if normalise(base) in MIDLINE_STRUCTURES:
        return base, None
    return base, side

# Tokens that describe the FILE rather than the anatomy: which subject the
# scan came from, and which processing variant of the mesh this is. The DU
# release encodes both in every filename -- VHM_Right_Bone_Femur_smooth.stl
# is subject, side, tissue class, structure, variant -- so without stripping
# these, every single name carries two junk tokens that dilute the score
# enough to sink an otherwise exact match. 'vhm calcaneus smooth' against
# 'calcaneus' scored 0.
#
# Unlike the truncation expansions this file deliberately refuses to make,
# these are safe: they are not anatomical words in a musculoskeletal atlas,
# and they are added against an observed naming convention rather than a
# guessed one.
DATASET_TOKENS = {
    "vhm", "vhf",                                    # subject
    "smooth", "smoothed", "final", "original", "raw",  # processing variant
    "remesh", "remeshed", "decimated",
}

# Words that carry no discriminating information.
#
# Note the absence of bare "l" and "r": those are side markers, handled by
# split_side(). Listing them here silently made 'biceps_femoris_l_long_head'
# and 'biceps_femoris_r_long_head' normalise identically, which mapped
# right-side meshes onto left-side entities.
STOPWORDS = {
    "muscle", "muscles", "bone", "bones", "ligament", "ligaments",
    "cartilage", "tendon", "the", "of", "and", "m", "lig", "os", "ossa",
}

# Tissue class as the dataset states it, mapped to the atlas's category.
#
# The DU filenames name the tissue outright -- VHM_Right_Bone_Calcaneous,
# VHM_Right_Cartilage_FemurDistal -- and that is hard information, not a hint.
# It was previously thrown away into STOPWORDS, which let the calcaneus BONE
# match achilles_tendon_r at 0.90 and be written out as "confident", because
# the Achilles is also called the calcaneal tendon. It also let the femoral
# CARTILAGE meshes match femur_r, colliding with the actual femur.
#
# So the class is now a disqualifier, exactly like the side marker: a bone
# mesh may not become a tendon entity however well the words line up.
TISSUE_CLASS_TO_CATEGORY = {
    "bone": "bone", "bones": "bone", "osseous": "bone",
    "muscle": "muscle", "muscles": "muscle",
    "cartilage": "cartilage", "cartilages": "cartilage",
    "ligament": "ligament", "ligaments": "ligament",
    "tendon": "tendon", "tendons": "tendon",
    "fascia": "fascia",
}


def tissue_category(name: str) -> Optional[str]:
    """Read the tissue class out of a structure name, if it states one.

    Returns an atlas category, or None when the name says nothing about
    tissue -- in which case callers must not constrain, since plenty of
    datasets do not encode it.
    """
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)
    for token in re.split(r"[_\-.,()\[\]/\s]+", text.lower()):
        category = TISSUE_CLASS_TO_CATEGORY.get(token)
        if category:
            return category
    return None


# The trailing delimiter is a lookahead, not a consumed group, so that two
# adjacent markers -- "Left_VHM_Left_..." -- can both be found. Consuming it
# left the second one without a preceding delimiter and it survived.
_SIDE_PATTERNS = [
    (re.compile(r"(?:^|[_\-\s])(left|lt|l)(?=$|[_\-\s])", re.I), "left"),
    (re.compile(r"(?:^|[_\-\s])(right|rt|r)(?=$|[_\-\s])", re.I), "right"),
]


def side_markers(name: str) -> set:
    """Every side a name claims. More than one means the name disagrees with
    itself, which is a data problem and not something to resolve by picking
    the first."""
    found = set()
    for pattern, side in _SIDE_PATTERNS:
        if pattern.search(name):
            found.add(side)
    return found


def split_side(name: str) -> Tuple[str, Optional[str]]:
    """Strip side markers off a structure name.

    Returns (name_without_side, "left"|"right"|None). Bare single-letter
    markers are only honoured when delimited, so 'Soleus_L' resolves but
    'Iliacus' is not read as ending in a side.

    EVERY marker is removed, not just the first. A release stored as
    `.../Left/VHM_Left_Bone_Sacrum.stl` puts the side in both the folder and
    the filename, and removing only one left "left" behind as an anatomical
    token. That extra token pushed extensor digitorum longus from an exact
    1.00 match down to 0.95 -- under the exact-match rule, and within the
    ambiguity margin of extensor digitorum, which is a different muscle. It
    also broke midline detection, because "left sacrum" is not "sacrum".

    A name claiming BOTH sides returns side=None, because a file called
    `Left/..._Right_...` is a genuine contradiction and guessing which half
    of its own name to believe is exactly the silent error this module
    exists to avoid. Callers should check side_markers() and report it.
    """
    found = side_markers(name)
    text = name
    changed = True
    while changed:
        changed = False
        for pattern, _ in _SIDE_PATTERNS:
            m = pattern.search(text)
            if m:
                text = text[: m.start()] + " " + text[m.end():]
                changed = True
    text = " ".join(text.split()).strip(" _-")
    return text, (found.pop() if len(found) == 1 else None)


def normalise(name: str) -> str:
    """Lowercase, split camelCase and underscores, expand synonyms, drop
    stopwords -- so 'VastusLateralis_R.stl' and 'Vastus lateralis (right)'
    reduce to the same token string."""
    text = re.sub(r"\.(stl|obj|ply|nrrd|nii|nii\.gz|seg\.nrrd)$", "", name, flags=re.I)
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)          # camelCase
    text = re.sub(r"[_\-.,()\[\]/]+", " ", text).lower()
    for src, dst in SYNONYMS.items():
        text = re.sub(rf"\b{re.escape(src)}\b", dst, text)
    tokens = [
        t for t in text.split()
        if t and t not in STOPWORDS and t not in DATASET_TOKENS and not t.isdigit()
    ]
    return " ".join(tokens)


# A subset only counts as "the same structure, worded differently" when the
# two names are close in length. Beyond this gap it is containment -- a part
# named inside a group -- which is a different relationship and is routed to
# find_grouping_entity() instead.
SUBSET_TOKEN_GAP = 2


def similarity(a: str, b: str) -> float:
    """Token-set Jaccard, with a bonus when one side is a near-subset of the
    other.

    The bonus matters because dataset names are often terser than atlas names
    ('rectus femoris' vs 'rectus femoris (quadriceps)'), and plain Jaccard
    would penalise that as harshly as a genuine mismatch.

    It is deliberately withheld for large size gaps. 'talus' is a subset of
    'ossa tarsi (talus, calcaneus, naviculare, cuneiforme, cuboideum)', but
    they are not the same structure -- one is a bone, the other is the group
    of seven containing it, and scoring that as a confident match silently
    collapses four distinct source meshes onto one atlas entity.
    """
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    if not inter:
        return 0.0
    jaccard = inter / len(ta | tb)
    if (ta <= tb or tb <= ta) and abs(len(ta) - len(tb)) <= SUBSET_TOKEN_GAP:
        jaccard = max(jaccard, 0.80 + 0.20 * jaccard)
    return jaccard


# --------------------------------------------------------------------------
# Atlas entity index
# --------------------------------------------------------------------------

_ID_SIDE_TOKEN = re.compile(r"(?:^|_)(l|r)(?=_|$)")


def _id_to_name(entity_id: str) -> str:
    """'biceps_femoris_l_long_head' -> 'biceps femoris long head'.

    The side token has to come out here rather than via STOPWORDS, or the
    left and right variants of the same structure normalise identically.
    """
    return _ID_SIDE_TOKEN.sub(" ", entity_id).replace("_", " ").strip()


@dataclass(frozen=True)
class AtlasEntity:
    entity_id: str
    category: str
    side: Optional[str]
    names: Tuple[str, ...]
    source_file: str

    @property
    def normalised(self) -> Tuple[str, ...]:
        return tuple(normalise(n) for n in self.names)


def _iter_entities(payload) -> Iterable[dict]:
    """Yield top-level entities only.

    Deliberately does NOT descend into functional_compartments, bands, or
    parts. Geometry attaches to a whole muscle, not to one of its fibre
    compartments, and indexing compartments as if they were entities makes
    every muscle collide with its own sub-parts in the matcher.
    """
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict) and "id" in item:
                yield item
    elif isinstance(payload, dict):
        if "id" in payload:
            yield payload
            return
        for value in payload.values():
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and "id" in item:
                        yield item


OVERRIDES_PATH = REPO_ROOT / "mappings" / "du_vh_overrides.json"


def override_key(source_name: str) -> Optional[str]:
    """The key an override entry is looked up by: 'class|normalised name'.

    The tissue class is part of the key because the release ships both
    Bone_Patella and Cartilage_Patella, which normalise identically once the
    class token is dropped. Returns None when the name states no class, since
    a key that cannot distinguish those two would be worse than no key.
    """
    category = tissue_category(source_name)
    if not category:
        return None
    name, _ = split_side(source_name)
    normalised = normalise(name)
    return f"{category}|{normalised}" if normalised else None


def load_overrides(path: Path = OVERRIDES_PATH) -> Dict[str, dict]:
    """Reviewed decisions that no name matcher can or should make itself.

    Kept in version control rather than in the per-run mapping file, because
    build/ is ignored and everything learned by reading the release once has
    to survive the next run.
    """
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    table: Dict[str, dict] = {}
    for entry in payload.get("entries", []):
        key = entry.get("match")
        if not key:
            continue
        if key in table:
            raise ValueError(f"{path.name}: duplicate override for {key!r}")
        table[key] = entry
    return table


def apply_override(entry: dict, side: Optional[str]) -> dict:
    """Fill the {side} placeholders from the mesh's own side marker."""
    marker = {"right": "r", "left": "l"}.get(side or "")
    resolved = dict(entry)
    for field_name in ("atlas_id", "compartment_id"):
        value = entry.get(field_name)
        if not value:
            continue
        if "{side}" in value:
            if not marker:
                # A sided template with no side marker would silently produce
                # a broken ID. Refuse rather than guess a side.
                raise ValueError(
                    f"override {entry['match']!r} needs a side but the mesh "
                    f"name carries no side marker")
            value = value.replace("{side}", marker)
        resolved[field_name] = value
    return resolved


def load_atlas_index(categories: Optional[Sequence[str]] = None) -> List[AtlasEntity]:
    """Every atlas entity that geometry could attach to, with its names."""
    wanted = set(categories) if categories else None
    entities: List[AtlasEntity] = []
    for path in sorted(DATA_DIR.rglob("*.json")):
        rel = path.relative_to(DATA_DIR)
        category = CATEGORY_BY_DIR.get(rel.parts[0])
        if category is None:
            continue
        if category == "bone" and path.name != "bones.json":
            continue
        if wanted and category not in wanted:
            continue
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: {exc}") from exc
        for entity in _iter_entities(payload):
            entity_id = entity.get("id")
            if not entity_id:
                continue
            names = tuple(
                dict.fromkeys(
                    n for n in (
                        entity.get("name_common"),
                        entity.get("name_ta"),
                        entity.get("name"),
                        _id_to_name(entity_id),
                    ) if isinstance(n, str) and n.strip()
                )
            )
            side = entity.get("side")
            entities.append(AtlasEntity(
                entity_id=entity_id,
                category=category,
                side=side if side in ("left", "right") else None,
                names=names,
                source_file=str(rel),
            ))
    return entities


@dataclass
class MatchCandidate:
    entity_id: str
    category: str
    score: float
    matched_name: str


def propose_matches(
    source_name: str,
    atlas: Sequence[AtlasEntity],
    *,
    side: Optional[str] = None,
    category: Optional[str] = None,
    top_n: int = 3,
) -> List[MatchCandidate]:
    """Rank atlas entities against one dataset structure name.

    A side mismatch is disqualifying rather than merely penalised: mapping a
    left soleus onto the right one would be silently wrong in exactly the way
    that is hardest to notice downstream. A tissue-class mismatch is treated
    the same way and for the same reason -- see TISSUE_CLASS_TO_CATEGORY.
    Pass category=None to leave the class unconstrained.
    """
    query = normalise(source_name)
    if not query:
        return []
    if category is None:
        category = tissue_category(source_name)
    scored: List[MatchCandidate] = []
    for entity in atlas:
        if side and entity.side and entity.side != side:
            continue
        if category and entity.category != category:
            continue
        best = max(
            ((similarity(query, n), raw) for n, raw in zip(entity.normalised, entity.names)),
            default=(0.0, ""),
        )
        if best[0] > 0.0:
            scored.append(MatchCandidate(entity.entity_id, entity.category, round(best[0], 4), best[1]))
    scored.sort(key=lambda c: (-c.score, c.entity_id))
    return scored[:top_n]


EXACT = 0.999


def find_grouping_entity(
    source_name: str,
    atlas: Sequence[AtlasEntity],
    *,
    side: Optional[str] = None,
    category: Optional[str] = None,
) -> List[MatchCandidate]:
    """Find a coarser atlas entity that *contains* this structure by name.

    The DU release is finer-grained than this atlas's skeleton in places: it
    ships a separate talus, calcaneus, navicular and cuboid, where the atlas
    carries one `tarsals_l` whose name_ta lists them all. Those are not
    failed matches, they are many-to-one, and they need saying so explicitly
    rather than sitting in the unmatched pile.
    """
    query = set(normalise(source_name).split())
    if not query:
        return []
    if category is None:
        category = tissue_category(source_name)
    hits: List[MatchCandidate] = []
    for entity in atlas:
        if side and entity.side and entity.side != side:
            continue
        if category and entity.category != category:
            continue
        for norm, raw in zip(entity.normalised, entity.names):
            tokens = set(norm.split())
            # The whole source name appears inside a strictly larger name.
            if query < tokens and len(tokens) > len(query):
                hits.append(MatchCandidate(
                    entity.entity_id, entity.category,
                    round(len(query) / len(tokens), 4), raw,
                ))
                break
    hits.sort(key=lambda c: (-c.score, c.entity_id))
    return hits[:3]


# --------------------------------------------------------------------------
# Coordinate frame
# --------------------------------------------------------------------------

# Typical adult lower-limb extents, used only to guess units from magnitude.
_PLAUSIBLE_MM = (200.0, 2500.0)

_AXIS_SPEC = re.compile(r"^\s*([+-]?)([xyz])\s*,\s*([+-]?)([xyz])\s*,\s*([+-]?)([xyz])\s*$", re.I)

UNIT_SCALE_TO_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4}


@dataclass
class FrameReport:
    bbox_min: Tuple[float, float, float]
    bbox_max: Tuple[float, float, float]
    extent: Tuple[float, float, float]
    longest_axis: int
    guessed_units: Optional[str]
    notes: List[str] = field(default_factory=list)


def infer_frame(bbox_min: np.ndarray, bbox_max: np.ndarray) -> FrameReport:
    """Describe what the raw coordinates look like. Reports, never decides."""
    extent = np.asarray(bbox_max, float) - np.asarray(bbox_min, float)
    longest = int(np.argmax(extent))
    notes: List[str] = []

    guessed = None
    for unit, scale in UNIT_SCALE_TO_MM.items():
        if _PLAUSIBLE_MM[0] <= extent[longest] * scale <= _PLAUSIBLE_MM[1]:
            guessed = unit
            break
    if guessed is None:
        notes.append(
            f"Longest extent is {extent[longest]:.4g} raw units, which is not a "
            f"plausible lower-limb length in mm, cm, m or in. Check the file."
        )
    elif guessed != "mm":
        notes.append(f"Coordinates look like {guessed}; pass --units {guessed}.")

    notes.append(
        f"Longest axis is index {longest} ({'xyz'[longest]}) at {extent[longest]:.4g} "
        f"raw units. For a pelvis-to-foot scan that axis is almost certainly "
        f"superior-inferior, i.e. the atlas's +Y."
    )
    notes.append(
        "This is an inference from the bounding box only. It cannot tell "
        "superior from inferior, left from right, or anterior from posterior. "
        "Confirm the direction against a known landmark before converting."
    )
    return FrameReport(
        bbox_min=tuple(float(v) for v in bbox_min),
        bbox_max=tuple(float(v) for v in bbox_max),
        extent=tuple(float(v) for v in extent),
        longest_axis=longest,
        guessed_units=guessed,
        notes=notes,
    )


def fit_sphere(points: np.ndarray) -> Tuple[np.ndarray, float, float]:
    """Least-squares sphere through a point cloud: (centre, radius, rms).

    Used on the femoral head cartilage to recover the hip joint centre, which
    is what the atlas puts its origin on. The rms residual is returned and
    must be looked at: a good femoral head fits to well under a millimetre,
    and anything worse means the mesh is not the near-spherical surface this
    assumes.
    """
    design = np.hstack([2.0 * points, np.ones((len(points), 1))])
    solution, *_ = np.linalg.lstsq(design, (points ** 2).sum(axis=1), rcond=None)
    centre = solution[:3]
    radius = float(np.sqrt(solution[3] + (centre ** 2).sum()))
    rms = float(np.sqrt((( np.linalg.norm(points - centre, axis=1) - radius) ** 2).mean()))
    return centre, radius, rms


def parse_origin(spec: str) -> np.ndarray:
    """Parse an explicit '--origin x,y,z' in source units."""
    parts = [p.strip() for p in spec.split(",")]
    if len(parts) != 3:
        raise ValueError(
            f"Bad origin {spec!r}. Expected three comma-separated numbers in "
            f"source units, e.g. '-346,-425.4,176.4'."
        )
    try:
        return np.asarray([float(p) for p in parts], dtype=np.float64)
    except ValueError as exc:
        raise ValueError(f"Bad origin {spec!r}: {exc}") from exc


def parse_axes(spec: str) -> np.ndarray:
    """Build a 3x3 signed permutation from a spec like '+x,+z,-y'.

    The spec reads as: atlas X takes source <first>, atlas Y takes source
    <second>, atlas Z takes source <third>.
    """
    m = _AXIS_SPEC.match(spec)
    if not m:
        raise ValueError(
            f"Bad axis spec {spec!r}. Expected three comma-separated signed axes, "
            f"e.g. '+x,+z,-y' (atlas X<-source x, atlas Y<-source z, atlas Z<-source -y)."
        )
    groups = m.groups()
    picks = [(groups[i], groups[i + 1].lower()) for i in (0, 2, 4)]
    if len({axis for _, axis in picks}) != 3:
        raise ValueError(f"Bad axis spec {spec!r}: each of x, y and z must appear exactly once.")
    matrix = np.zeros((3, 3), dtype=np.float64)
    for row, (sign, axis) in enumerate(picks):
        matrix[row, "xyz".index(axis)] = -1.0 if sign == "-" else 1.0
    return matrix


def to_atlas_frame(points: np.ndarray, axes: np.ndarray, scale: float) -> np.ndarray:
    """Apply the signed permutation and unit scale. Shape (n, 3) -> (n, 3)."""
    return (points @ axes.T) * scale
