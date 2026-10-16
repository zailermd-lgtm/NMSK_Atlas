"""Row helper for the Q219 parts table."""
import sys
ROWS = []
SETS = {}

PART_TYPES = ["head_belly", "origin_part", "insertion_point", "ligament_component", "muscle_tendon_junction", "fascial_passage"]


def S(set_id, sid, ptype, name, counts, note=None):
    """A set of parts whose NUMBER the literature disagrees on.  counts = [(n, ref, note), ...]"""
    SETS[set_id] = dict(id=set_id, structure_id=sid, part_type=ptype, name=name,
                        reported_counts=[dict(n=n, ref=r, note=t) for n, r, t in counts], note=note)


def P(sid, slug, ptype, name, desc, refs, *, cls="muscle", ev=None, ver="verified", var=None, anchor=None, z=None, own=None,
      geom=None, setid=None, passes=None, related=None, note=None, order=None):
    """sid = side-agnostic structure id; slug unique within sid.  z = Z-Anatomy part mesh id patterns ({s} = r|l or '' for midline).
    ver: 'verified' (the claim is in the cited PubMed record's abstract/title) or 'unverified' (textbook / owner statement, not checked)."""
    assert ptype in PART_TYPES, ptype
    assert ver in ("verified", "unverified")
    pid = f"{sid}.{slug}"
    added_in = "Q222" if sys._getframe(1).f_globals.get("__name__", "").startswith("rows_q222_") else "Q219"
    if ver == "unverified" and not note:
        note = "Unverified: textbook-level statement (edition cited, page not checked) or owner list; see refs."
    assert all(r["id"] != pid for r in ROWS), pid
    ROWS.append(dict(id=pid, structure_id=sid, structure_class=cls, part_type=ptype, name=name, description=desc, refs=list(refs),
                     evidence=ev, verification=ver, variability=var, anchor=anchor, z_part_ids=z or [], own_part_ids=own or [],
                     geometry=geom, set_id=setid, passes=passes, related_structure_ids=related or [], note=note, order=order, added_in=added_in))
