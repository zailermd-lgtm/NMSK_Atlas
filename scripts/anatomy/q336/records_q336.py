#!/usr/bin/env python3
"""Q336: the genital / perineal records that have NO real geometry on the Base pages, as search explanations
(data/anatomy/synonyms_q306.json `cited_but_not_shipped`), and the correction of the one entry Q336 made untrue
("Female perineal skin" now ships on Base · Female as `skin_vulva_cvh`).

    python3 scripts/anatomy/q336/records_q336.py            # dry run: print what would change
    python3 scripts/anatomy/q336/records_q336.py --write    # write data/anatomy/synonyms_q306.json (idempotent)

How they reach a page: scripts/anatomy/q306/build_search_q306.py compiles each entry per page -- where one of its names /
`shipped_as` names ships on that page it becomes a search alias onto that structure (Q311 rule), elsewhere the typed term
returns this explanation and the `offer` structures. Nothing here is geometry. Hebrew = project-supplied translation
(sources.he)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SYN = REPO / "data/anatomy/synonyms_q306.json"
SKIN = "Vulva and perineal skin (CVH, registered)"

SOURCES = {
    "gray1918": "Gray H. Anatomy of the Human Body, 20th ed. (Lewis WH, ed.), Lea & Febiger 1918 (public domain): 'The Muscles "
                "and Fasciae of the Perineum', 'The External Organs' (female), 'The Male Genital Organs', 'The Pudendal Nerve' -- "
                "section names as the project's earlier records cite them; the text was NOT re-opened in Q336 (wikisource / "
                "bartleby / archive.org are outside this session's network).",
    "wu2015": "Wu Y, Dabhoiwala NF, Hagoort J, et al. 3D topography of the young adult anal sphincter complex reconstructed from "
              "undeformed serial anatomical sections. PLoS ONE 2015;10(8):e0132226. doi:10.1371/journal.pone.0132226 (PMID 26305117).",
    "stein2008": "Stein TA, DeLancey JOL. Structure of the perineal membrane in females: gross and microscopic anatomy. Obstet Gynecol "
                 "2008;111(3):686-93. doi:10.1097/AOG.0b013e318163a9a5 (PMID 18310372).",
    "oconnell2005": "O'Connell HE, Sanjeevan KV, Hutson JM. Anatomy of the clitoris. J Urol 2005;174(4 Pt 1):1189-95. "
                    "doi:10.1097/01.ju.0000173639.38898.cd (PMID 16145367).",
    "lloyd2005": "Lloyd J, Crouch NS, Minto CL, Liao LM, Creighton SM. Female genital appearance: 'normality' unfolds. BJOG "
                 "2005;112(5):643-6. doi:10.1111/j.1471-0528.2004.00517.x (PMID 15842291).",
    "q336": "docs/Q336_genital_region.md + data/derived/Q336_vulva_skin_report.json (Q336).",
    "mannan2017": "Noor MA. Mannan's Regional Dissection and Surface Anatomy, 14th ed. Jaypee Brothers, New Delhi 2017 "
                  "(ISBN 978-93-86322-11-1), Abdomen: perineum pp. 347-358 (male), 364-368 (female); cremaster p. 321. Owner's copy, "
                  "read in Q348 (facts only).",
    "grays_atlas": "Gray's Atlas of Anatomy (Drake RL, Vogl AW, Mitchell AWM et al.; Churchill Livingstone / Elsevier), Pelvis and "
                   "perineum: 'Deep pouch and perineal membrane' p. 245, perineal vessels and nerves p. 252. Owner's scanned copy "
                   "(title and edition pages not in the scan), read in Q348 (labels only).",
}

FEMALE_SURFACE = ("Q336: on Base · Female this is a SURFACE FEATURE of `" + SKIN + "` -- the real vulvar skin of the Chinese Visible "
                  "Human female (Wu et al. 2015, CC BY 4.0) registered onto the body; the source has no separate object for it, so "
                  "it is not a structure of its own. Not on the male pages.")

ENTRIES = [
    {"name": "Labia minora", "canon": "Labium minus pudendi (labia minora)", "syn": ["labia minora", "labium minus", "nymphae", "inner labia"],
     "he": ["השפתיים הקטנות", "שפה קטנה"], "src": "gray1918,lloyd2005,wu2015,q336", "why": FEMALE_SURFACE,
     "offer": ["vagina", "vestibular bulb"], "shipped_as": [SKIN]},
    {"name": "Labia majora", "canon": "Labium majus pudendi (labia majora)", "syn": ["labia majora", "labium majus", "outer labia"],
     "he": ["השפתיים הגדולות", "שפה גדולה"], "src": "gray1918,lloyd2005,wu2015,q336", "why": FEMALE_SURFACE,
     "offer": ["vagina", "vestibular bulb"], "shipped_as": [SKIN]},
    {"name": "Mons pubis", "canon": "Mons pubis", "syn": ["mons pubis", "mons veneris", "pubic mound"],
     "he": ["גבעת הערווה", "הר הערווה"], "src": "gray1918,wu2015,q336", "why": FEMALE_SURFACE,
     "offer": ["vagina", "pyramidalis"], "shipped_as": [SKIN]},
    {"name": "Vestibule of the vagina", "canon": "Vestibulum vaginae (vulval vestibule)",
     "syn": ["vestibule of the vagina", "vaginal vestibule", "vulval vestibule", "vulvar vestibule", "introitus", "vaginal introitus"],
     "he": ["פרוזדור הנרתיק", "פתח הנרתיק"], "src": "gray1918,wu2015,q336",
     "why": FEMALE_SURFACE + " The vestibule lies on that surface, but the HRA vagina and the CVH urethra placed by bone end several "
            "mm deep to it, so the introitus and the urethral meatus are surface features, not open channels.",
     "offer": ["vagina", "vestibular bulb"], "shipped_as": [SKIN]},
    {"name": "Clitoris", "canon": "Clitoris (glans, body, crura)", "syn": ["clitoris", "clitoral body", "glans of the clitoris", "glans clitoridis",
                                                                        "prepuce of the clitoris", "clitoral hood"],
     "he": ["דגדגן", "עטרת הדגדגן"], "src": "gray1918,oconnell2005,wu2015,q336",
     "corrected_by": "Q336", "why": "SHIPS on the female pages as 'Cavernous body of the clitoris (both crura and body, CVH)' -- real CVH segmentation; "
            "the CVH source has no separate glans or prepuce object (O'Connell 2005: the glans is the only external part). Not on the "
            "male pages.",
     "offer": ["vestibular bulb", "vagina"], "shipped_as": ["Cavernous body of the clitoris (both crura and body, CVH)"]},
    {"name": "Paraurethral gland", "canon": "Glandulae paraurethrales (Skene's glands)", "syn": ["paraurethral gland", "paraurethral glands",
                                                                                               "skene's gland", "skene gland", "skene's glands"],
     "he": ["בלוטות סקין", "בלוטות פרה-אורתרליות"], "src": "gray1918,ta",
     "why": "Not modelled on any page: no open mesh source this project holds segments them (the CVH set of Wu 2015 has the urethral "
            "sphincters and Bartholin's glands but no paraurethral glands). Recorded gap, not an oversight.",
     "offer": ["vagina", "vestibular bulb"]},
    {"name": "Perineal membrane", "canon": "Membrana perinei (inferior fascia of the urogenital diaphragm)",
     "syn": ["perineal membrane", "membrana perinei", "inferior fascia of the urogenital diaphragm", "urogenital diaphragm"],
     "he": ["הממברנה הפרינאלית", "הסרעפת האורוגניטלית"], "src": "gray1918,stein2008,ta,mannan2017,grays_atlas",
     "why": "Not modelled as a sheet on any Base page: Z-Anatomy and the CVH set have no perineal-membrane object. Stein & DeLancey (2008) "
            "show it is not a simple sheet: a dorsal fibrous part (vagina / perineal body to the ischiopubic ramus) and a ventral part "
            "fused with the compressor urethrae and urethrovaginal sphincter. On Base · Female those CVH muscles and the deep transverse "
            "perineal muscle mark its ventral part; on Base · Male nothing of the deep pouch is modelled (see 'External urethral sphincter'). "
            "'Urogenital diaphragm' (found by this search) is not another name for the membrane: the membrane is the INFERIOR FASCIA of "
            "the urogenital diaphragm; above it, below the superior fascia, lies the deep perineal pouch with the sphincter urethrae and "
            "the deep transverse perineal muscle (Mannan 2017, pp. 357-358). The membrane separates the superficial from the deep "
            "perineal pouch (Mannan p. 357; Gray's Atlas p. 245).",
     "offer": ["deep transverse perineal muscle", "transverse perineal ligament", "levator ani"]},
    {"name": "External urethral sphincter", "canon": "Musculus sphincter urethrae externus",
     "syn": ["external urethral sphincter", "sphincter urethrae", "rhabdosphincter", "urethral sphincter"],
     "he": ["הסוגר החיצוני של השופכה"], "src": "gray1918,wu2015,ta",
     "corrected_by": "Q336", "why": "SHIPS on the female pages as 'External urethral sphincter proper (CVH)' (+ compressor urethrae and urethrovaginal sphincter, "
            "real CVH segmentation). On Base · Male NOT modelled: Z-Anatomy (the male Base body's source) has no external urethral "
            "sphincter, no bulbourethral gland and no superficial / deep transverse perineal, bulbospongiosus or ischiocavernosus muscle; "
            "the only real male geometry this project holds for them is the rule-based segmentation of the Visible Human male's "
            "cryosections on the (frozen) Imaging-based Male page.",
     "offer": ["prostate", "urethra", "levator ani"], "shipped_as": ["External urethral sphincter proper (CVH)"]},
    {"name": "Bulbourethral gland", "canon": "Glandula bulbourethralis (Cowper's gland)", "syn": ["bulbourethral gland", "bulbourethral glands",
                                                                                                "cowper's gland", "cowper gland", "cowper's glands"],
     "he": ["בלוטת קאופר", "הבלוטה הבולבו-אורתרלית"], "src": "gray1918,ta",
     "why": "Male only; not modelled on any page (no open mesh source this project holds has it: Z-Anatomy / BodyParts3D has none).",
     "offer": ["prostate", "urethra"]},
    {"name": "Spermatic cord", "canon": "Funiculus spermaticus", "syn": ["spermatic cord", "funiculus spermaticus"],
     "he": ["חבל הזרע"], "src": "gray1918,ta",
     "why": "Male only. Its contents ship on the male pages as separate structures (ductus deferens, testicular artery / gonadal "
            "artery, testicular vein); its coverings (external / internal spermatic fascia, cremaster) are not modelled: Z-Anatomy "
            "has no object for them.",
     "offer": ["ductus deferens", "testis"]},
    {"name": "Cremaster muscle", "canon": "Musculus cremaster", "syn": ["cremaster", "cremaster muscle", "cremasteric muscle"],
     "he": ["שריר הקרמסטר"], "src": "gray1918,ta,mannan2017",
     "why": "Male only; not modelled on any page (Z-Anatomy has no cremaster object; Q62 never targeted it). Nerve: genital branch of the "
            "genitofemoral nerve (ships; L1-L2, Mannan 2017 p. 321).", "offer": ["testis", "ductus deferens"]},
    {"name": "Dartos", "canon": "Tunica dartos (dartos fascia)", "syn": ["dartos", "dartos fascia", "tunica dartos", "dartos muscle"],
     "he": ["דרטוס"], "src": "gray1918,ta",
     "why": "Male only; not modelled: on Base · Male the scrotum is one Z-Anatomy skin patch ('Urogenital region (skin)') with no "
            "separate dartos layer.", "offer": ["testis"]},
    {"name": "Tunica vaginalis", "canon": "Tunica vaginalis testis", "syn": ["tunica vaginalis", "tunica vaginalis testis"],
     "he": ["המעטפת הנרתיקית של האשך"], "src": "gray1918,ta",
     "why": "Male only; not modelled (Z-Anatomy has the testis and epididymis but no tunica vaginalis).", "offer": ["testis"]},
    {"name": "Ischioanal fossa", "canon": "Fossa ischioanalis (ischiorectal fossa)", "syn": ["ischioanal fossa", "ischiorectal fossa",
                                                                                            "ischioanal fat", "ischiorectal fat"],
     "he": ["הגומה האיסכיו-אנאלית"], "src": "gray1918,ta",
     "corrected_by": "Q336", "why": "SHIPS as part of 'Deep pelvic fat (ischioanal fossa, pelvic visceral, gluteal)' (each body's own imaging, Q295, layer "
            "off by default); there is no separate ischioanal-fossa object.",
     "offer": ["levator ani", "external anal sphincter"], "shipped_as": ["Deep pelvic fat (ischioanal fossa, pelvic visceral, gluteal)"]},
    {"name": "Pudendal canal", "canon": "Canalis pudendalis (Alcock's canal)", "syn": ["pudendal canal", "alcock's canal", "alcock canal"],
     "he": ["תעלת אלקוק", "התעלה הפודנדלית"], "src": "gray1918,ta",
     "why": "A fascial tunnel in the obturator internus fascia, not modelled as an object on any page; its contents ship: pudendal nerve, "
            "internal pudendal artery and vein.", "offer": ["pudendal nerve", "internal pudendal artery"]},
    {"name": "Anal canal", "canon": "Canalis analis", "syn": ["anal canal", "canalis analis"],
     "he": ["תעלת פי הטבעת"], "src": "gray1918,wu2015,ta",
     "why": "Not modelled as its own object on the Base pages. Base · Female carries her own CT rectum and a rule-based external anal "
            "sphincter; Base · Male has NO rectum or anal canal at all (Z-Anatomy ships none), and its Z-Anatomy external anal sphincter "
            "ends 25 mm above the anal-region skin (measured in Q336).",
     "offer": ["external anal sphincter", "levator ani"]},
    {"name": "Perineal nerve", "canon": "Nervus perinealis (perineal branch of the pudendal nerve)",
     "syn": ["perineal nerve", "perineal branch of the pudendal nerve", "posterior labial nerve", "posterior scrotal nerve"],
     "he": ["העצב הפרינאלי"], "src": "gray1918,ta,mannan2017",
     "corrected_by": "Q336", "why": "SHIPS (rule-based) on the Imaging-based pages only. On the four Z pages Q249 built it but Q252 held it back: its rule-based "
            "course ran 15-37 mm outside the skin of those bodies. Its parent, the pudendal nerve, ships on every page. The posterior "
            "scrotal (male) / posterior labial (female) nerves found by this search are not other names for it: they are its "
            "superficial branches; its other branches are muscular, to the urogenital-triangle muscles (Mannan 2017, p. 348).",
     "offer": ["pudendal nerve", "internal pudendal artery"]},
]


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    write = "--write" in argv
    if "--require-page" in argv:
        d = Path(argv[argv.index("--require-page") + 1])
        html = sorted(d.glob("atlas_viewer_base_female.html"))
        if not html or '"id":"skin_vulva_cvh"' not in html[0].read_text(encoding="utf-8"):
            raise SystemExit(f"{d}: skin_vulva_cvh is not on this page -- run vulva_skin_q336.py --write first")
    d = json.loads(SYN.read_text(encoding="utf-8"))
    changes = []
    for k, v in SOURCES.items():
        if d["sources"].get(k) != v:
            d["sources"][k] = v; changes.append(f"source {k}")
    rows = d["cited_but_not_shipped"]
    by = {r["name"]: r for r in rows}
    fps = by.get("Female perineal skin")
    if fps is not None and fps.get("corrected_by") != "Q336":
        fps["why_was"] = fps["why"]
        fps["why"] = ("SHIPS (Q336) on Base · Female as '" + SKIN + "' -- the real vulvar / perineal skin surface of the Chinese Visible "
                      "Human female (Wu et al. 2015, CC BY 4.0; the 'Skin' mesh of the same CVH set as the perineal muscles), registered "
                      "onto the opening Q297 left (method and numbers on its card). Q297 / Q302 recorded that no source held it; the CVH "
                      "skin block does. Absent on the other pages.")
        fps["shipped_as"] = [SKIN]
        fps["corrected_by"] = "Q336"
        fps["src"] = fps["src"] + ",wu2015,q336"
        changes.append("Female perineal skin: corrected")
    for e in ENTRIES:
        if e["name"] in by:
            if by[e["name"]] != e:
                by[e["name"]].clear(); by[e["name"]].update(e); changes.append("updated " + e["name"])
        else:
            rows.append(dict(e)); changes.append("added " + e["name"])
    print("\n".join(changes) or "no change")
    if write and changes:
        SYN.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {SYN.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
