"""Q248: what ships on which page.  collect(key) -> list of dict(id, name, latin, side('l','r','m'), z_sys, cat, V, F, rec, kind('xfer'|'rule'|'cvh'), report, subject).
Sources: data/derived/Q248_xfer_<own key>.{npz,json} (Z-Anatomy ligaments carried onto the own pages), Q248_rule_<key>.{npz,json} (rule-based, all six pages), Q248_cvh_<key>.{npz,json} (CVH anococcygeal ligament, female own / Combined)."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[2]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(REPO))
import lig_pages as PG  # noqa: E402

D = REPO / "data/derived"
COMB = {"own_f": "comb_f", "own_m": "comb_m"}
SUBJ = {"own_f": dict(xfer="xfer_zan2vhf_lig_q248", rule="ct_vhf_rule_lig_q248", cvh="xfer_cvh2vhf_q248"),
        "own_m": dict(xfer="xfer_zan2vhm_lig_q248", rule="ct_vhm_rule_lig_q248", cvh=None)}
CAT = {"joint": "ligament", "cartilage": "cartilage", "fascia": "fascia", "ligament": "ligament"}
ZNAME = {"own_f": "her", "own_m": "him"}


def xfer_badge(key, zrec, rep, src="comb"):
    who = ZNAME[key]
    srctxt = ("the Z-Anatomy structure of the Combined page (itself a fit of the Z-Anatomy mesh to the same donor, CC BY-SA 4.0)" if src == "comb" else
              "the Z-Anatomy structure of the Base page (the original Z-Anatomy mesh at its Z position, CC BY-SA 4.0; used where the Combined-page copy did not pass the guards)")
    carr = "; ".join(f"{g}: {f['mode']}, residual median {f.get('median_mm')} / p90 {f.get('p90_mm')} mm" for g, f in rep["carriers"].items())
    ag = rep.get("attachment_gap_before_snap_mm")
    att = (f"{rep['attachment_vertices']} attachment vertices (<= 1.5 mm from a Z-Anatomy bone) snapped onto {who} bone surface (gap before the snap: median {ag['median']} / p90 {ag['p90']} / max {ag['max']} mm; "
           f"after: 0 mm by construction)") if ag else "no vertex touches a bone in the Z-Anatomy model (nothing to snap)"
    vol = rep["volume_cm3"]
    vtxt = (f"volume {vol['own']} cm3 (Z-Anatomy {vol['z']} cm3)" if vol.get("own") is not None else "mesh not closed (no volume)")
    so = rep["soft_overlap"]
    return (f"FILLED from Z-Anatomy (Q248): this structure is NOT measured on {who}; it is {srctxt} carried onto {who} OWN bones. "
            f"Carrier-bone fits (rigid, scale of the bone's global fit, local ICP on the bone surface within 28 mm of the attachment): {carr}. {att}. "
            f"{rep['pushed_out_vertices']} of {rep['n_vertices']} vertices were pushed out of bones (max {rep['max_push_mm']} mm); no vertex deeper than 1 mm inside a bone ({rep['vertices_deeper_1mm_in_bone']}). "
            f"Length (principal extent) {rep['length_mm']['own']} mm vs {rep['length_mm']['z']} mm in Z-Anatomy; edge stretch p05 / median / p95 {rep['edge_stretch']['p05']} / {rep['edge_stretch']['median']} / {rep['edge_stretch']['p95']}; {vtxt}. "
            f"Overlap: {round(100 * so['muscle_fraction_deeper_6mm'])} % of the vertices deeper than 6 mm inside a closed muscle, {round(100 * so['organ_fraction_deeper_3mm'])} % deeper than 3 mm inside an organ; "
            f"depth inside the skin {rep['skin_min_depth_mm']} mm; left / right by x position checked. An estimate of position: Z-Anatomy shape and arrangement on {who} bones, not a measurement.")


def collect(key):
    items = []
    if key in COMB:
        done = set()
        for src, tag, ckey in (("comb", key, COMB[key]), ("base", f"{key}_from_base_{key[-1]}", "base_" + key[-1])):
            if not (D / f"Q248_xfer_{tag}.json").exists():
                continue
            z = np.load(D / f"Q248_xfer_{tag}.npz"); rj = json.loads((D / f"Q248_xfer_{tag}.json").read_text())
            Cz = PG.load(ckey)
            for zid, rep in rj["structures"].items():
                if rep.get("status") != "ship" or f"{zid}__v" not in z.files or zid in done:
                    continue
                done.add(zid)
                e = Cz[zid]
                rec = dict(e["rec"]); rec["procedural_badge"] = xfer_badge(key, rec, rep, src)
                rec["source"] = (rec.get("source", "") + "; geometry: Z-Anatomy (CC BY-SA 4.0), carried by Q248").lstrip("; ")
                rep = dict(rep); rep["source_page"] = ckey
                items.append(dict(id=zid, name=e["name"], latin=rec.get("latin", ""), side=e["side"], z_sys=e["sys"], cat=CAT.get(e["sys"], "ligament"), V=z[f"{zid}__v"], F=z[f"{zid}__f"], rec=rec, kind="xfer",
                                  report=rep, subject=SUBJ[key]["xfer"]))
    r = D / f"Q248_rule_{key}.json"
    if r.exists():
        z = np.load(D / f"Q248_rule_{key}.npz"); rj = json.loads(r.read_text())
        for sid, rep in rj["structures"].items():
            if rep.get("status") != "ship" or f"{sid}__v" not in z.files:
                continue
            c = rj["cards"][sid]
            items.append(dict(id=sid, name=c["name"], latin=c["latin"], side=c["side"], z_sys="joint", cat="ligament", V=z[f"{sid}__v"], F=z[f"{sid}__f"], rec=c["rec"], kind="rule", report=rep["report"],
                              subject=SUBJ.get(key, {}).get("rule")))
    c = D / f"Q248_cvh_{key}.json"
    if c.exists():
        z = np.load(D / f"Q248_cvh_{key}.npz"); cj = json.loads(c.read_text())
        for sid, rep in cj.items():
            if rep["status"] != "ship": continue
            g = rep["gates"]
            rec = dict(name=rep["name"], latin=rep["latin"], folder="ligaments", region="pelvis",
                       source="Wu et al. 2015, PLoS ONE 10(8):e0132226 (Chinese Visible Human female, S3 Fig; CC BY 4.0), registered onto this page's pelvis by this atlas (Q235 bone registration)")
            rec["procedural_badge"] = (f"REGISTERED OTHER PERSON (Q248): this structure is NOT segmented from this body: it is the real segmentation of the Chinese Visible Human female (Wu et al. 2015, CC BY 4.0; a different woman) carried onto this "
                                       f"page's pelvis with the Q235 bone registration (rigid + uniform scale x1.1067, bone residual median 1.8 / p90 4.35 mm). The CVH object is large (about 21 cm3 in the CVH frame: it contains the whole retro-anal "
                                       f"fibro-muscular mass the authors labelled 'anococcygeal ligament'). {g['pushed_out_of_bone']} of {g['vertices']} vertices ({round(100 * g['pushed_fraction'], 1)} %) were pushed out of bones (max {g['max_push_mm']} mm); "
                                       f"decimated to 5000 triangles; overlap {round(100 * g['soft_overlap']['muscle_fraction_deeper_6mm'])} % muscle / {round(100 * g['soft_overlap']['organ_fraction_deeper_3mm'])} % organ; skin depth {g['skin_min_depth_mm']} mm.")
            items.append(dict(id=sid, name=rep["name"], latin=rep["latin"], side="m", z_sys="joint", cat="ligament", V=z[f"{sid}__v"], F=z[f"{sid}__f"], rec=rec, kind="cvh", report=rep, subject=SUBJ.get(key, {}).get("cvh")))
    # a rule-based ligament never replaces / duplicates a structure of the page or a Z-Anatomy transfer of the same id
    have = set(PG.load(key)) | {i["id"] for i in items if i["kind"] == "xfer"}
    items = [i for i in items if not (i["kind"] == "rule" and i["id"] in have)]
    # the CVH anococcygeal ligament replaces the rule-based one on the female Imaging-based / Combined pages
    if any(i["id"] == "anococcygeal_ligament_cvh" for i in items):
        items = [i for i in items if i["id"] != "anococcygeal_ligament"]
    return items
