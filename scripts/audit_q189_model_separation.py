#!/usr/bin/env python3
"""Q189 (owner: "both kinds must exist, a clear SEPARATION, and Z-Anatomy used only to give continuity / fill the
missing parts of the RECONSTRUCTED models"): provenance audit of the four viewers, in numbers.

    python3 scripts/audit_q189_model_separation.py --m build/viewer_m_hr_q189 --f build/viewer_f_hr_q189 \
        [--zm build/viewer_zan_atlas --zf build/viewer_zan_female] [--out data/derived/Q189_model_separation_audit.json]

Own viewers (bundle.json + bundle.bin): every bundle entry gets ONE provenance class from its subject name, the
subject's description in viewer/atlas_viewer.template.html (SUBJECT_LABELS) and its own badge -- the same rule the
viewer's Source facet applies (classify() below mirrors classifySource() in the template; the headless test compares
the two). Independent evidence per subject (the subject's manifest source_kind, the per-label notes of its volume
mapping) is cross-checked against that class and every disagreement is listed.
Z-Anatomy viewers are read-only: decoded for counts / volumes and scanned for specimen-derived geometry.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts.transfer.bundle_io import read_bundle_dir, decode  # noqa: E402

TEMPLATE = REPO / "viewer" / "atlas_viewer.template.html"
CLASSES = ["measured", "rule_based", "transferred", "filled_zan", "other_specimen"]
PRIORITY = {c: i for i, c in enumerate(CLASSES)}
REGION_MAP = {  # own rec.region -> the six Q168 regions (only used when the id has no Q168 region)
    "head": "head_neck", "neck": "head_neck", "cranium_face": "head_neck", "hyoid": "head_neck",
    "trunk": "trunk", "vertebral_column": "trunk", "spine": "trunk", "pelvis": "trunk", "pelvic_girdle": "trunk",
    "thoracic_cage": "trunk", "hip": "trunk", "whole_body": "trunk",
    "pectoral_girdle": "upper_limb", "shoulder": "upper_limb", "upper_limb": "upper_limb",
    "forearm": "forearm_hand", "wrist_hand": "forearm_hand",
    "lower_limb": "lower_limb", "knee": "lower_limb", "thigh": "lower_limb",
    "ankle": "foot", "ankle_foot": "foot",
}


def template_labels() -> dict:
    txt = TEMPLATE.read_text(encoding="utf-8")
    blk = txt[txt.index("var SUBJECT_LABELS = {"):]
    blk = blk[:blk.index("\n};")]
    return dict(re.findall(r'^\s{2}([A-Za-z0-9_]+):\s*"((?:[^"\\]|\\.)*)"', blk, re.M))


LABELS = template_labels()


def base_subject(s: str) -> str:
    s = re.sub(r"(_contfix_mesh|_contfix)$", "", s or "")
    if s not in LABELS:  # ct_vhm_pfloor_fix -> ct_vhm_pfloor; ct_vhf_xfersepta_fix has its own description
        s = re.sub(r"_fix$", "", s)
    return s


def classify(subject: str, badge: str | None) -> tuple[str, str]:
    """(class, why). Mirrors classifySource() in viewer/atlas_viewer.template.html."""
    b = base_subject(subject or "")
    if b.startswith("xfer_zan2"):
        return "filled_zan", "subject xfer_zan2*"
    if re.search(r"(^|_)xfer", b):
        return "transferred", "subject xfer*"
    if b.startswith("ct_s1159"):
        return "other_specimen", "subject ct_s1159* (another person's CT)"
    lab = LABELS.get(b, "")
    if re.search(r"rule", lab, re.I):
        return "rule_based", "subject description says rule"
    if badge and re.match(r"\s*rule-based", badge, re.I):
        return "rule_based", "badge starts RULE-BASED"
    return "measured", "own segmentation (no rule / transfer marker)"


def vol_cm3(v, f) -> float:
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return abs(float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum()) / 6.0) / 1000.0


def region6(sid: str, rec: dict, qreg: dict) -> str:
    if sid == "skin":
        return "whole_body"
    return qreg.get(sid) or REGION_MAP.get((rec or {}).get("region"), "unassigned")


def manifest_evidence(subject: str) -> dict:
    p = REPO / "build" / "vh" / subject / "manifest.json"
    if not p.exists():
        p = REPO / "build" / "vh" / base_subject(subject) / "manifest.json"
    if not p.exists():
        return {}
    m = json.loads(p.read_text())
    return {"source_kind": m.get("source_kind"), "source_volume": m.get("source_volume")}


def mapping_notes(subject: str) -> list[str]:
    b = base_subject(subject)
    for p in (REPO / "mappings" / "subjects" / f"{b}_volume_mapping.json", REPO / "build" / "vh" / f"{b}_volume_mapping.json"):
        if p.exists():
            return [str(e.get("note") or "") for e in json.loads(p.read_text()).get("entries", []) if e.get("atlas_id")]
    return []


def audit_own(bdir: Path, body: str, qreg: dict) -> dict:
    bundle, blob = read_bundle_dir(bdir)
    ents = []
    for e, v, f in decode(bundle, blob):
        rec = e.get("rec") or {}
        cls, why = classify(e["subject"], rec.get("procedural_badge"))
        ents.append({"id": e["id"], "subject": e["subject"], "base": base_subject(e["subject"]), "cls": cls, "why": why,
                     "cat": e["cat"], "region": region6(e["id"], rec, qreg), "vol": vol_cm3(v, f) if len(f) else 0.0,
                     "hidden": bool(e.get("hidden_default")), "side": e.get("side"), "badge": rec.get("procedural_badge") or "",
                     "name": rec.get("name"), "tris": int(e["nf"]),
                     "bbox": (v.min(0).tolist(), v.max(0).tolist()) if len(v) else None})
    by_id = defaultdict(list)
    for x in ents:
        by_id[x["id"]].append(x)
    id_cls = {i: min((x["cls"] for x in xs), key=PRIORITY.get) for i, xs in by_id.items()}
    out = {"body": body, "dir": str(bdir), "entries": len(ents), "ids": len(by_id), "triangles_shipped": sum(x["tris"] for x in ents)}
    per = {}
    for c in CLASSES:
        xs = [x for x in ents if x["cls"] == c]
        per[c] = {"entries": len(xs), "ids": len({x["id"] for x in xs}), "volume_cm3": round(sum(x["vol"] for x in xs), 1),
                  "hidden_by_default_entries": sum(x["hidden"] for x in xs)}
    out["by_class"] = per
    # without skin (a 105,000 cm3 shell would swamp every volume ratio)
    out["by_class_excl_skin_volume_cm3"] = {c: round(sum(x["vol"] for x in ents if x["cls"] == c and x["id"] != "skin"), 1) for c in CLASSES}
    out["visible_default_by_class"] = {c: len({x["id"] for x in ents if x["cls"] == c and not x["hidden"]}) for c in CLASSES}
    cat = defaultdict(lambda: Counter()); catv = defaultdict(lambda: Counter())
    reg = defaultdict(lambda: Counter()); regv = defaultdict(lambda: Counter())
    for x in ents:
        cat[x["cat"]][x["cls"]] += 1; catv[x["cat"]][x["cls"]] += x["vol"]
        reg[x["region"]][x["cls"]] += 1; regv[x["region"]][x["cls"]] += x["vol"]
    out["by_system"] = {k: {"entries": dict(v), "volume_cm3": {c: round(catv[k][c], 1) for c in v}} for k, v in sorted(cat.items())}
    out["by_region"] = {k: {"entries": dict(v), "volume_cm3": {c: round(regv[k][c], 1) for c in v}} for k, v in sorted(reg.items())}
    # subject table
    subj = {}
    for x in ents:
        s = subj.setdefault(x["subject"], {"class": x["cls"], "why": x["why"], "entries": 0, "volume_cm3": 0.0, "ids": []})
        s["entries"] += 1; s["volume_cm3"] = round(s["volume_cm3"] + x["vol"], 1); s["ids"].append(x["id"])
    for s, v in subj.items():
        ev = manifest_evidence(s); v["manifest"] = ev
        notes = mapping_notes(s)
        v["mapping_notes_mentioning_rule"] = sum(bool(re.search(r"rule", n, re.I)) for n in notes)
        v["mapping_notes_total"] = len(notes)
        v["ids"] = sorted(set(v["ids"]))[:6] + (["..."] if len(set(v["ids"])) > 6 else [])
    out["subjects"] = subj
    # ---- mislabel checks ----
    chk = {"measured_with_zan_or_transfer_marker": [], "zan_without_zan_badge": [], "transfer_without_transfer_badge": [],
           "class_vs_manifest_disagreements": [], "class_vs_mapping_notes_disagreements": []}
    for x in ents:
        txt = x["badge"] + " " + LABELS.get(x["base"], "")
        if x["cls"] in ("measured", "rule_based") and re.search(r"z-anatomy|transferred from|NOT HIS GEOMETRY|not measured on", txt, re.I):
            chk["measured_with_zan_or_transfer_marker"].append(x["id"] + "/" + x["subject"])
        if x["cls"] == "filled_zan" and not re.search(r"z-anatomy", x["badge"], re.I):
            chk["zan_without_zan_badge"].append(x["id"] + "/" + x["subject"])
        if x["cls"] == "transferred" and not re.search(r"transferred", x["badge"] + " " + LABELS.get(x["base"], ""), re.I):
            chk["transfer_without_transfer_badge"].append(x["id"] + "/" + x["subject"])
    for s, v in subj.items():
        sk = ((v["manifest"] or {}).get("source_kind") or "")
        if v["class"] == "filled_zan" and "zanatomy" not in sk.replace("-", "").lower() and sk:
            chk["class_vs_manifest_disagreements"].append(f"{s}: class filled_zan but source_kind '{sk}'")
        if v["class"] in ("measured", "rule_based") and "cross-subject" in sk:
            chk["class_vs_manifest_disagreements"].append(f"{s}: class {v['class']} but source_kind '{sk}'")
        if v["class"] == "measured" and v["mapping_notes_total"] and v["mapping_notes_mentioning_rule"] == v["mapping_notes_total"]:
            chk["class_vs_mapping_notes_disagreements"].append(f"{s}: class measured, every mapped label note says rule ({v['mapping_notes_total']})")
    out["mislabel_checks"] = chk
    out["_ids"] = {i: c for i, c in id_cls.items()}
    out["_bbox"] = {i: xs[0]["bbox"] for i, xs in by_id.items() if xs[0]["bbox"]}
    out["_ents"] = ents
    return out


def decode_zan(hpath: Path) -> list[dict]:
    html = hpath.read_text(encoding="utf-8")
    i = html.index("window.__ANATOMY_MANIFEST__=") + len("window.__ANATOMY_MANIFEST__=")
    man, _ = json.JSONDecoder().raw_decode(html[i:])
    bf = json.loads(re.search(r"window\.__ANATOMY_BIN_FILES__=(\[.*?\]);", html, re.S).group(1))
    blob = b"".join(base64.b64decode((hpath.parent / b["path"]).read_text().strip()) for b in bf)
    out = []
    for m in man["meshes"]:
        n = m["vc"]
        q = np.frombuffer(blob, "<u2", n * 3, m["vo"]).reshape(-1, 3).astype(np.float64)
        span = np.array(m["span"]); span = np.where(span <= 1e-9, 1.0, span)
        v = np.array(m["min"]) + q / 65535.0 * span
        f = np.frombuffer(blob, "<u2", m["ic"] * 3, m["io"]).reshape(-1, 3).astype(np.int64)
        out.append({"id": m["id"], "name": m["name"], "rec_name": (m.get("rec") or {}).get("name"), "side": m.get("side"), "sys": m["sys"], "vol": vol_cm3(v, f) if len(f) else 0.0,
                    "badge": (m.get("rec") or {}).get("procedural_badge") or "", "rec_keys": sorted((m.get("rec") or {}).keys()),
                    "bbox": (v.min(0).tolist(), v.max(0).tolist()), "tris": int(m["ic"]), "matched": not m["id"].startswith("zan_")})
    return out


def audit_zan(path: Path, label: str, own: dict, qreg: dict) -> dict:
    ms = decode_zan(path)
    r = {"viewer": str(path.parent.relative_to(REPO)) if path.is_relative_to(REPO) else str(path.parent), "label": label, "meshes": len(ms),
         "matched_to_project_atlas_id": sum(m["matched"] for m in ms), "orphan_zan_ids": sum(not m["matched"] for m in ms),
         "volume_cm3_total": round(sum(m["vol"] for m in ms if m["sys"] != "skin"), 1)}
    r["by_layer"] = dict(Counter(m["sys"] for m in ms))
    fitted = [m for m in ms if re.search(r"fitted onto the Visible Human female", m["badge"])]
    r["fitted_onto_her_skeleton_badged"] = len(fitted)
    r["fitted_with_error_stated"] = sum(bool(re.search(r"mm", m["badge"])) for m in fitted)
    # specimen-derived geometry: a Z mesh whose bbox equals the own mesh of the same id (a copy) or whose badge/record
    # names a specimen subject as the geometry source
    ob = own["_bbox"] if own else {}
    copies = []
    for m in ms:
        b = ob.get(m["id"])
        if b and np.allclose(m["bbox"][0], b[0], atol=0.05) and np.allclose(m["bbox"][1], b[1], atol=0.05):
            copies.append(m["id"])
    r["bbox_identical_to_own_mesh_of_same_id"] = copies
    r["badge_mentions_specimen_geometry"] = [m["id"] for m in ms if re.search(r"ct_vh[mf]|cryosection photograph|segmented from (him|her)", m["badge"])
                                              and not re.search(r"Measured on her own CT mesh|compared with her own CT skin|anchored on her own CT", m["badge"])][:20]
    r["badges_citing_her_ct_only_for_error_or_anchor"] = sum(bool(re.search(r"her own CT", m["badge"])) for m in ms)
    r["_ms"] = ms
    return r


def norm_name(n: str | None) -> str:
    n = (n or "").lower()
    n = re.sub(r"\([^)]*\)", " ", n)
    n = re.sub(r"\b(muscles?|left|right|l|r)\b", " ", n)
    n = re.sub(r"[^a-z0-9]+", " ", n)
    return n.strip()


GATE_REPORTS = {
    "male": ["Q62s9_vhm_trunk_leg", "Q62s7b_vhm_head_neck", "Q62s7b_vhm_foot_lumbricals"],
    "female": ["Q62s9_vhf_trunk_leg", "Q62s7_vhf_head_neck", "Q62s5_vhf_foot_intrinsics"],
}


def muscle_gate_status(body: str, unmatched: list) -> dict:
    """For each Z-Anatomy muscle that carries a project atlas id and has no counterpart in the own model: was it already
    run through the Q168 gated route (Q62 steps 5/7/7b/9), and which gate held it. Z orphan sub-parts are not listed
    (they are parts of muscles the own model has, or of muscles the atlas has no record for)."""
    held, ships = {}, set()
    for name in GATE_REPORTS[body]:
        d = json.loads((REPO / "data" / "derived" / f"{name}.json").read_text())
        sm = d.get("summary", {})
        held.update({k: f"{name}: {v}" for k, v in sm.get("dropped", {}).items()})
        for k, r in (d.get("rows") or {}).items():
            if k not in held:
                held.setdefault(k, None)
    limb = json.loads((REPO / "data" / "derived" / ("transfer_report_zan2vhm_limb.json" if body == "male" else "transfer_report_zan2vhf_limb.json")).read_text())
    limb_nt = limb.get("not_transferred", {})
    out = {"held_by_gate": {}, "held_by_limb_route_skin_gate": {}, "never_run_through_a_gated_route": []}
    for m in unmatched:
        if m["sys"] != "muscle" or not m["matched"]:
            continue
        if held.get(m["id"]):
            out["held_by_gate"][m["id"]] = held[m["id"]]
        elif m["id"] in limb_nt:
            out["held_by_limb_route_skin_gate"][m["id"]] = limb_nt[m["id"]]
        else:
            out["never_run_through_a_gated_route"].append(m["id"])
    out["counts"] = {k: len(v) for k, v in out.items()}
    return out


def gaps(own: dict, zan: dict, qreg: dict) -> dict:
    """Z-Anatomy structures with no counterpart in the own model, by Q168 region and Z layer. Counterpart tiers: same atlas
    id; else the Z mesh's linked atlas record name (an orphan sub-part such as a deltoid part) or its own name equals an
    own record name on the same side. Own structures of class other_specimen (another person's CT, hidden) never count."""
    own_ids = {i: c for i, c in own["_ids"].items() if c != "other_specimen"}
    nidx = {}
    for x in own["_ents"]:
        if x["cls"] == "other_specimen":
            continue
        side = {"left": "l", "right": "r"}.get(x.get("side"), "m")
        for key in {norm_name(x["name"]), norm_name(x["id"].replace("_", " "))}:
            if key:
                cur = nidx.get((key, side))
                if cur is None or PRIORITY[x["cls"]] < PRIORITY[cur]:
                    nidx[(key, side)] = x["cls"]
    rows = defaultdict(lambda: {"n": 0, "vol": 0.0, "examples": []})
    unmatched = []
    have = {t: Counter() for t in ("atlas_id", "parent_or_own_name")}
    for m in zan["_ms"]:
        if m["sys"] == "skin":
            continue
        reg = qreg.get(m["id"], "unassigned")
        if m["id"] in own_ids:
            have["atlas_id"][own_ids[m["id"]]] += 1
            continue
        side = m["side"] if m["side"] in ("l", "r") else "m"
        hit = None
        for key in (norm_name(m["rec_name"]), norm_name(m["name"]), norm_name(m["id"].replace("zan_", "").replace("_", " "))):
            if key and (key, side) in nidx:
                hit = nidx[(key, side)]; break
            if key and (key, "m") in nidx:
                hit = nidx[(key, "m")]; break
        if hit:
            have["parent_or_own_name"][hit] += 1
            continue
        k = f"{reg}|{m['sys']}"
        unmatched.append(m)
        rows[k]["n"] += 1; rows[k]["vol"] += m["vol"]
        if len(rows[k]["examples"]) < 6:
            rows[k]["examples"].append(m["name"])
    out = {"zan_structures_excl_skin": sum(1 for m in zan["_ms"] if m["sys"] != "skin"),
           "counterpart_by_atlas_id_by_own_class": dict(have["atlas_id"]),
           "counterpart_by_linked_record_or_name_by_own_class": dict(have["parent_or_own_name"]),
           "without_counterpart": sum(r["n"] for r in rows.values()),
           "without_counterpart_volume_cm3": round(sum(r["vol"] for r in rows.values()), 1)}
    tab = {}
    for k, v in sorted(rows.items()):
        reg, sysn = k.split("|")
        tab.setdefault(reg, {})[sysn] = {"n": v["n"], "volume_cm3": round(v["vol"], 1), "examples": v["examples"]}
    out["by_region_and_z_layer"] = tab
    out["muscle_gap_gate_status"] = muscle_gate_status(own["body"], unmatched)
    zids = {m["id"] for m in zan["_ms"]}
    out["own_ids_without_same_id_in_z"] = sorted(i for i in own_ids if i not in zids)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--m", default="build/viewer_m_hr_q189")
    ap.add_argument("--f", default="build/viewer_f_hr_q189")
    ap.add_argument("--zm", default="build/viewer_zan_atlas/atlas_viewer_zan_atlas.html")
    ap.add_argument("--zf", default="build/viewer_zan_female/atlas_viewer_zan_female.html")
    ap.add_argument("--out", default="data/derived/Q189_model_separation_audit.json")
    a = ap.parse_args()
    D = REPO / "data" / "derived"
    qm = json.loads((D / "Q168_zan_to_vhm.json").read_text())["region_of_structure"]
    qf = json.loads((D / "Q168_zan_to_vhf.json").read_text())["region_of_structure"]
    own = {"male": audit_own(REPO / a.m, "male", qm), "female": audit_own(REPO / a.f, "female", qf)}
    zan = {"male": audit_zan(REPO / a.zm, "Z-Anatomy male (reference)", own["male"], qm),
           "female": audit_zan(REPO / a.zf, "Z-Anatomy female (reference, fitted onto her skeleton)", own["female"], qf)}
    g = {"male": gaps(own["male"], zan["male"], qm), "female": gaps(own["female"], zan["female"], qf)}
    # a male Z mesh vs the male own bundle only share ids, never geometry: bbox test of male Z against the FEMALE own too
    zan["male"]["bbox_identical_to_female_own_mesh_of_same_id"] = [
        m["id"] for m in zan["male"]["_ms"] if own["female"]["_bbox"].get(m["id"]) and np.allclose(m["bbox"][0], own["female"]["_bbox"][m["id"]][0], atol=0.05)]
    res = {"task": "Q189 model separation audit", "classes": {
        "measured": "own CT / cryosection segmentation of that body (incl. the DU manual segmentation of the male's cryosections)",
        "rule_based": "derived by rule from that body's own data; subject description says rule / badge starts RULE-BASED",
        "transferred": "carried from the OTHER Visible Human body (xfer_vhm2vhf*, xfer_vhf2vhm*, ct_vhf_xfersepta_fix)",
        "filled_zan": "Z-Anatomy geometry fitted onto this body (xfer_zan2vhm_*, xfer_zan2vhf_*), badge states the error",
        "other_specimen": "ct_s1159*: another person's CT (TotalSegmentator case s1159), hidden by default, badged NOT HIS/HER GEOMETRY"},
        "rule": "viewer/atlas_viewer.template.html classifySource(); subject base name = name without _contfix_mesh/_contfix/_fix"}
    for k in ("male", "female"):
        o = own[k]
        res[f"own_{k}"] = {kk: vv for kk, vv in o.items() if not kk.startswith("_")}
        res[f"zan_{k}"] = {kk: vv for kk, vv in zan[k].items() if not kk.startswith("_")}
        res[f"gaps_{k}"] = g[k]
    Path(REPO / a.out).write_text(json.dumps(res, indent=1, ensure_ascii=False))
    for k in ("male", "female"):
        print(k, {c: (v["ids"], v["entries"], v["volume_cm3"]) for c, v in own[k]["by_class"].items()})
        print(" Z", {kk: vv for kk, vv in res[f"zan_{k}"].items() if kk in ("meshes", "fitted_onto_her_skeleton_badged", "bbox_identical_to_own_mesh_of_same_id")})
        print(" gaps", g[k]["without_counterpart"], g[k]["counterpart_by_atlas_id_by_own_class"], g[k]["counterpart_by_linked_record_or_name_by_own_class"])
        print(" mislabel", {kk: len(vv) for kk, vv in own[k]["mislabel_checks"].items()})


if __name__ == "__main__":
    main()
