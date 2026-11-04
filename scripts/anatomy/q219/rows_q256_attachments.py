"""Q256 rows: extend the ORIGIN / INSERTION marker concept (Q219/Q240) from muscles to tendons, ligaments and fascia.

Owner's request (Q256): "Add an ORIGIN and INSERTION option for muscles, tendons, ligaments, fascia etc." Muscles already have it
(rows_upper.py / rows_lower.py). This module adds the SAME two part types (origin_part / insertion_point), with the SAME geometry
rules (end_snap_bone: the structure's own mesh end snapped to the named bone; mtj_interface for a tendon's muscular end), generated
PROGRAMMATICALLY from this project's own already-authored attachment data:
  data/tendons/*.json   attachments.{proximal_attachment,distal_attachment}  (51/51 records: proximal = the parent muscle, distal = bone)
  data/ligaments/*.json attachments.{bone_a,landmark_a,bone_b,landmark_b}    (91/91 records, bone-to-bone)
  data/fascia/*.json    bony_attachments: [ {bone, landmark}, ... ]         (a LIST -- most fascia do NOT have exactly two bony ends)

Honesty / anatomical judgement applied here, not assumed:
- A ligament has no muscle-style directional pull, so "origin" / "insertion" is not a standard TA distinction for one -- but clinical and
  anatomical literature commonly labels a ligament's two bone ends this way anyway (e.g. the ACL's "femoral attachment" / "tibial
  attachment"). To satisfy the owner's request without claiming a pull direction that does not exist, `bone_a` is always called
  "origin" and `bone_b` "insertion" HERE BY THIS PROJECT'S OWN CONVENTION ONLY (stated in every row's `note`), never as an anatomical fact.
- A tendon's proximal end is its own parent muscle (continuous tissue, not a bony origin): that end is placed as a `muscle_tendon_junction`
  (the existing, correct part type for this), not as `origin_part`. Only the distal, bony end is `insertion_point`.
- Fascia: `bony_attachments` is a list, not a fixed pair -- 36/104 fascia records have NO bony attachment at all (blend into adjacent
  fascia/skin only), 34/104 have exactly ONE (a free margin at the other end), 2/104 have three and 1/104 has four. Forcing an
  origin/insertion PAIR onto any of those would misrepresent real anatomy the owner explicitly warned against fabricating, so only the
  31/104 fascia records with EXACTLY two listed bony attachments get an origin/insertion pair here; every other fascia keeps none
  (see data/derived/Q256_attachment_coverage.json for the exact counts and which ids were skipped and why).
- Q219's own per-side geometry resolver (build_geometry.py) only ever tries sides "r"/"l" (never a true midline side): a handful of these
  records are genuinely midline (e.g. ligamentum_flavum, linea_alba, central_tendon_diaphragm) with no left/right mesh at all. Giving
  those a `geom` rule would silently duplicate one real 3D point under BOTH a spurious "r" and "l" tag -- so midline records get the
  origin/insertion catalogue ROW (visible as text in that structure's Parts list, citing the attachment) but deliberately NO `geom`
  key, so they resolve to `text_only` with an honest reason instead of a placed-but-mislabeled marker. Flagged in
  docs/OPEN_ITEMS_FOR_OWNER.md as a real, if narrow, gap for whoever next touches build_geometry.py's side handling.

Citations: every tendon/ligament/fascia record already carries its own authored `source` string (Gray's Anatomy for Students 4th ed.,
Terminologia Anatomica, Moore 8th ed. and/or Stecco's Functional Atlas of the Human Fascial System, in various combinations -- 45 unique
strings across 246 records, checked). `refs_for()` below maps that string to the matching textbook ref key(s) in refs.py (added by this
round: gray_students4, moore8, ta1998, stecco2015) and every row's `note` field quotes the record's exact `source` string verbatim, so
nothing is paraphrased away from the data this project already had."""
from __future__ import annotations
import glob
import json
import re
from pathlib import Path

from rows_common import P

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SIDE = re.compile(r"_(r|l)$")
COVERAGE = REPO / "data/derived/Q256_attachment_coverage.json"


def base(i: str) -> str:
    return SIDE.sub("", i)


def strip_side(s: str) -> str:
    return SIDE.sub("", s) if s else s


def refs_for(source: str) -> list[str]:
    keys = []
    if "Gray's Anatomy for Students" in source:
        keys.append("gray_students4")
    if "Clinically Oriented Anatomy, 8th ed" in source:
        keys.append("moore8")
    if "Terminologia Anatomica" in source:
        keys.append("ta1998")
    if "Functional Atlas of the Human Fascial System" in source:
        keys.append("stecco2015")
    return keys or ["gray_students4"]      # every source string checked in fact starts with this one


def load_pairs(pattern: str):
    """side-agnostic base id -> the (first, by file order) record for it; also returns whether it is sided (_r/_l pair) or midline."""
    by_base: dict[str, dict] = {}
    sided: dict[str, bool] = {}
    for f in sorted(glob.glob(pattern)):
        for r in json.load(open(f)):
            b = base(r["id"])
            if b not in by_base:
                by_base[b] = r
                sided[b] = bool(SIDE.search(r["id"]))
    return by_base, sided


report = {"ligaments": {"total": 0, "placed": 0}, "tendons": {"total": 0, "placed": 0},
          "fascia": {"total": 0, "placed": 0, "skipped": []}}


# ------------------------------------------------------------------ ligaments: bone_a -> "origin", bone_b -> "insertion" (project convention)
lig, lig_sided = load_pairs(str(REPO / "data/ligaments/*.json"))
for sid, rec in sorted(lig.items()):
    report["ligaments"]["total"] += 1
    att = rec.get("attachments") or {}
    ba, la, bb, lb = att.get("bone_a"), att.get("landmark_a"), att.get("bone_b"), att.get("landmark_b")
    if not (ba and bb):
        continue
    ba, bb = strip_side(ba), strip_side(bb)
    source = rec.get("source", "")
    refs = refs_for(source)
    note = ("Ligaments have no muscle-style directional pull: by THIS PROJECT'S OWN CONVENTION (not a TA distinction), the first-listed "
            f"bone attachment is called 'origin' and the second 'insertion', purely for consistency with the muscle markers. Source "
            f"(verbatim, from data/ligaments/*.json): {source}")
    geom_a = dict(rule="end_snap_bone", end="proximal", bone=ba, tol_mm=10) if lig_sided[sid] else None
    geom_b = dict(rule="end_snap_bone", end="distal", bone=bb, tol_mm=10) if lig_sided[sid] else None
    nm = rec.get("name_common", sid)
    P(sid, "origin_q256", "origin_part", f"Origin (by convention): {la or ba}", f"{nm}: attachment onto the {ba.replace('_', ' ')} ({la}).", refs, cls="ligament",
      ver="unverified", ev="textbook", anchor=dict(bone=ba, landmark=la), geom=geom_a, note=note)
    P(sid, "insertion_q256", "insertion_point", f"Insertion (by convention): {lb or bb}", f"{nm}: attachment onto the {bb.replace('_', ' ')} ({lb}).", refs, cls="ligament",
      ver="unverified", ev="textbook", anchor=dict(bone=bb, landmark=lb), geom=geom_b, note=note)
    report["ligaments"]["placed"] += 1

# ------------------------------------------------------------------ tendons: proximal (muscle) -> MTJ, distal (bone) -> insertion
ten, ten_sided = load_pairs(str(REPO / "data/tendons/*.json"))
for sid, rec in sorted(ten.items()):
    report["tendons"]["total"] += 1
    att = rec.get("attachments") or {}
    prox, dist = att.get("proximal_attachment") or {}, att.get("distal_attachment") or {}
    source = rec.get("source", "")
    refs = refs_for(source)
    note = f"Source (verbatim, from data/tendons/*.json): {source}"
    nm = rec.get("name_common", sid)
    if prox.get("type") == "muscle" and prox.get("ref"):
        muscle_base = strip_side(prox["ref"])
        geom = dict(rule="mtj_interface", muscle=muscle_base, tendon=sid) if ten_sided[sid] else None
        P(sid, "mtj_q256", "muscle_tendon_junction", f"Musculotendinous junction with {muscle_base.replace('_', ' ')}",
          f"{nm}: continuous proximally with {muscle_base.replace('_', ' ')} ({prox.get('landmark', '')}).", refs, cls="tendon",
          ver="unverified", ev="textbook", anchor=dict(bone=None, landmark=prox.get("landmark")), geom=geom, note=note)
    elif prox.get("type") == "bone" and prox.get("ref"):
        bone_base = strip_side(prox["ref"])
        geom = dict(rule="end_snap_bone", end="proximal", bone=bone_base, tol_mm=10) if ten_sided[sid] else None
        P(sid, "origin_q256", "origin_part", f"Origin: {prox.get('landmark', bone_base)}",
          f"{nm}: attachment onto the {bone_base.replace('_', ' ')} ({prox.get('landmark', '')}).", refs,
          cls="tendon", ver="unverified", ev="textbook", anchor=dict(bone=bone_base, landmark=prox.get("landmark")), geom=geom, note=note)
    if dist.get("type") == "bone" and dist.get("ref"):
        bone_base = strip_side(dist["ref"])
        geom = dict(rule="end_snap_bone", end="distal", bone=bone_base, tol_mm=10) if ten_sided[sid] else None
        P(sid, "insertion_q256", "insertion_point", f"Insertion: {dist.get('landmark', bone_base)}",
          f"{nm}: attachment onto the {bone_base.replace('_', ' ')} ({dist.get('landmark', '')}).", refs,
          cls="tendon", ver="unverified", ev="textbook", anchor=dict(bone=bone_base, landmark=dist.get("landmark")), geom=geom, note=note)
        report["tendons"]["placed"] += 1

# ------------------------------------------------------------------ fascia: ONLY the 2-bony-attachment records get an origin/insertion pair
fas, fas_sided = load_pairs(str(REPO / "data/fascia/*.json"))
for sid, rec in sorted(fas.items()):
    report["fascia"]["total"] += 1
    atts = rec.get("bony_attachments")
    n = len(atts) if isinstance(atts, list) else 0
    if n != 2:
        reason = {0: "no bony attachment listed (blends into adjacent fascia / skin only)",
                  1: "only one bony attachment listed (a free margin at the other end)"}.get(n, f"{n} bony attachments listed (not a pair)")
        report["fascia"]["skipped"].append(dict(id=sid, bony_attachments=n, reason=reason))
        continue
    a, b = atts
    ba, bb = strip_side(a.get("bone")), strip_side(b.get("bone"))
    source = rec.get("source", "")
    refs = refs_for(source)
    note = ("Fascia sheets rarely have a muscle-style origin/insertion; this one is offered a pair ONLY because it lists exactly two "
            f"bony attachments. By THIS PROJECT'S OWN CONVENTION the first-listed is called 'origin', the second 'insertion'. Source "
            f"(verbatim, from data/fascia/*.json): {source}")
    geom_a = dict(rule="end_snap_bone", end="proximal", bone=ba, tol_mm=12) if fas_sided[sid] else None
    geom_b = dict(rule="end_snap_bone", end="distal", bone=bb, tol_mm=12) if fas_sided[sid] else None
    nm = rec.get("name", sid)
    P(sid, "origin_q256", "origin_part", f"Origin (by convention): {a.get('landmark', ba)}", f"{nm}: one of its two listed bony attachments, onto the {ba.replace('_', ' ')} ({a.get('landmark', '')}).", refs, cls="fascia",
      ver="unverified", ev="textbook", anchor=dict(bone=ba, landmark=a.get("landmark")), geom=geom_a, note=note)
    P(sid, "insertion_q256", "insertion_point", f"Insertion (by convention): {b.get('landmark', bb)}", f"{nm}: its other listed bony attachment, onto the {bb.replace('_', ' ')} ({b.get('landmark', '')}).", refs, cls="fascia",
      ver="unverified", ev="textbook", anchor=dict(bone=bb, landmark=b.get("landmark")), geom=geom_b, note=note)
    report["fascia"]["placed"] += 1

COVERAGE.write_text(json.dumps(report, indent=1) + "\n")
