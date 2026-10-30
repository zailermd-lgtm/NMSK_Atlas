"""Q222 rows, part 7: head, neck, deep back (PubMed-verified on 2026-10-12)."""
from rows_common import P, S

S("temporalis.parts", "temporalis", "head_belly", "Temporalis: parts", [
    (1, "sedlmayr2009", "classical single muscle (the deep and zygomatic parts had been regarded as accessory bellies)"),
    (3, "sedlmayr2009", "superficial, zygomatic and deep parts in all 32 specimens")],
  note="Sedlmayr 2009 argues that the zygomatic and deep parts, previously treated as accessory bellies, belong to the temporalis (one structural unit).")
P("temporalis", "superficial_part", "head_belly", "Superficial part", "The classically recognised part; inserts on the lateral surface of the coronoid process (in one female specimen also onto the zygomatic process and the temporomandibular joint).", ["sedlmayr2009"], ev="cadaver n=32 (16 subjects) + CT / MR", setid="temporalis.parts",
  anchor=dict(bone="mandible", landmark="lateral surface of the coronoid process"))
P("temporalis", "zygomatic_part", "head_belly", "Zygomatic part", "Originates from the zygomatic arch and inserts into the superficial part where it reaches the lateral surface of the coronoid process.", ["sedlmayr2009"], ev="cadaver n=32 + CT / MR", setid="temporalis.parts",
  anchor=dict(bone="zygomatic_arch", landmark="zygomatic arch"))
P("temporalis", "deep_part", "head_belly", "Deep part (complex)", "Muscle bundles from various crests of the anterior surface of the temporal fossa to the inner aspect of the coronoid process and the retromolar triangle, interdigitating with buccinator, mylohyoid and the superior constrictor (confluence with buccinator confirmed on CT / MRI).", ["sedlmayr2009"],
  ev="cadaver n=32 + CT / MR", setid="temporalis.parts", anchor=dict(bone="mandible", landmark="inner aspect of the coronoid process and retromolar triangle"), related=["buccinator", "mylohyoid", "superior_pharyngeal_constrictor"])

S("masseter.parts", "masseter", "head_belly", "Masseter: functional parts", [
    (2, "zwijnenburg1999", "superficial and deep part (functional subdivision supported); no further subdivision of the superficial part into anterior / middle / posterior")],
  note="Functional (electrical stimulation, 5 men) rather than dissection evidence for the two-part split; nothing in the abstract supports a three-part superficial subdivision.")
P("masseter", "superficial_part", "head_belly", "Superficial part", "Stimulation of each superficial site moves the incisal point mainly anterovertically; no support for separate anterior, middle and posterior superficial parts.", ["zwijnenburg1999"], ev="electrical stimulation in 5 men with MRI-checked electrode depth", setid="masseter.parts")
P("masseter", "deep_part", "head_belly", "Deep part", "Stimulation of the deep masseter moves the incisal point mainly laterovertically.", ["zwijnenburg1999"], ev="electrical stimulation in 5 men", setid="masseter.parts")
P("masseter", "zygomaticomandibularis_deepest_layer", "head_belly", "Zygomaticomandibularis (deepest layer, covered by the masseter)", "Fan-shaped muscle found in all 15 cadavers: from the deep layer of the deep temporal fascia about 1 cm above the zygomatic arch to the superior border and outer surface of the mandible between the coronoid process and mandibular notch; 25.1 +/- 4.6 mm long; the deepest masseter layer covers it.", ["hwang2005"],
  ev="dissection of 15 cadavers + MRI", var="found in all specimens", anchor=dict(bone="mandible", landmark="between coronoid process and mandibular notch"), related=["temporalis"])

P("multifidus", "fascicles_per_lumbar_spinous_process", "head_belly", "Lumbar fascicle groups attached to each spinous process (segmental innervation)", "The multifidus part attached to a lumbar spinous process is innervated segmentally by the medial branch of the dorsal ramus at that spinous process level; 5 fascicles of the series showed a variant nerve entry.", ["shindo1995"],
  ev="dissection, 10 adults + 10 fetuses", var="5 variant fascicles")
P("scalenus_anterior", "c5_c6_roots_piercing_belly", "fascial_passage", "C5 / C6 roots piercing the belly of the anterior scalene", "In 6.8 % the C5 and C6 roots pierce the belly of the anterior scalene instead of passing between the anterior and middle scalene.", ["fockens2023"],
  ev="review", var="6.8 %", passes=dict(kind="nerve", traversing=[], traversing_text="C5 and C6 roots of the brachial plexus", through="belly of scalenus anterior"),
  note="Prevalence figures come from a review; the primary studies are not retrieved.")
P("rectus_capitis_posterior_major", "doubling_variant", "head_belly", "Variant: doubled belly (single case)", "Unilateral doubling of rectus capitis posterior major; relation to the cervical myodural bridge discussed.", ["damjanovic2024"], ev="case report", var="case report")
P("rectus_capitis_posterior_minor", "doubling_accessory_slip_c2", "head_belly", "Variant: doubled belly with an accessory slip from the spinous process of C2 (single case)", "Doubling of rectus capitis posterior minor with an accessory slip originating from the C2 spinous process.", ["damjanovic2024"], ev="case report", var="case report")
P("sternocleidomastoid", "accessory_clavicular_head_middle_third", "origin_part", "Variant: supernumerary head from the middle third of the clavicle (single case)", "Left accessory head originating from the middle third of the clavicle.", ["ara2025"], ev="case report, 1 cadaver", var="case report", anchor=dict(bone="clavicle", landmark="middle third"))
