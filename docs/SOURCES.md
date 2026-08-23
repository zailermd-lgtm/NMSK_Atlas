# NMSK Atlas — Sources & Citation Policy

## Policy

Every entity in `data/` carries a `source` (or, for reference tables, a
top-level `sources`) field. `tests/test_source_coverage.py` enforces this
mechanically — no entity may ship without one. Two honesty notes that apply
throughout the dataset, stated once here rather than repeated on every file:

1. **Representative vs. exact values.** Numeric biomechanical parameters
   (fascicle length, pennation angle, PCSA, joint ROM) are given as
   representative typical values consistent with the architecture
   classification and magnitude reported in the cited literature — not
   exact digitized transcriptions from one specimen. This is stated
   explicitly because published cadaver/imaging studies themselves disagree
   by 20–40% (normal biological + measurement variation between studies),
   so a bare "measured" number would overstate precision the field itself
   doesn't have. Where a formula is used to derive a value (e.g.
   `max_isometric_force = PCSA × specific_tension`), the formula and its
   literature-based constant are shown, not just the result.
2. **Skeletal coordinates.** Bone landmark `position_local_mm` values are
   placed consistently with documented average adult long-bone lengths and
   standard descriptive landmark locations — not digitized from a scanned
   specimen (no such source was available in this session; see
   docs/ROADMAP.md Stage 5 for the real path to genuine scan-derived
   geometry). They are geometrically self-consistent (correct relative
   position, correct bone length) and sufficient to drive the rig/generator
   pipeline correctly, but are an engineering approximation, not a
   measurement.

## Primary references used

**General gross anatomy / nomenclature**
- Drake RL, Vogl AW, Mitchell AWM. *Gray's Anatomy for Students*, 4th ed. Elsevier, 2019.
- Terminologia Anatomica (FICAT/IFAA 1998) — official anatomical nomenclature standard.
- Moore KL, Dalley AF, Agur AMR. *Clinically Oriented Anatomy*, 8th ed. Wolters Kluwer.

**Joint kinematics / coordinate systems**
- Wu G et al. (2002) "ISB recommendation on definitions of joint coordinate systems of various joints for the reporting of human joint motion — part I: ankle, hip, and spine." *J Biomech* 35:543–548.
- Wu G et al. (2005) "ISB recommendation on definitions of joint coordinate systems of various joints for the reporting of human joint motion — part II: shoulder, elbow, wrist and hand." *J Biomech* 38:981–992.
- American Academy of Orthopaedic Surgeons. *Joint Motion: Method of Measuring and Recording* (1965) — standard clinical ROM norms.
- Delp SL et al. (1990) "An interactive graphics-based model of the lower extremity to study orthopaedic surgical procedures." *IEEE Trans Biomed Eng* 37:757–767 — source of the ankle-complex (talocrural+subtalar combined) simplification convention adopted here.

**Muscle architecture**
- Holzbaur KR, Murray WM, Delp SL (2005) "A model of the upper extremity for simulating musculoskeletal surgery and analyzing neuromuscular control." *Ann Biomed Eng* 33(6):829–840.
- Lieber RL, Fridén J (2000) "Functional and clinical significance of skeletal muscle architecture." *Muscle Nerve* 23:1647–1666.
- Ward SR et al. (2009) "Are current measurements of lower extremity muscle architecture accurate?" *Clin Orthop Relat Res* 467:1074–1082 (cited for the lower-limb roadmap stage; not yet used in committed data).
- Fridén J, Lieber RL (2003) "Spec ific tension of human skeletal muscle" — representative in-vivo specific-tension estimate used to compute illustrative `max_isometric_force_N`.

**Intramuscular functional compartmentalization**
- Wickham JB, Brown JM (1998) "Muscles within muscles: a mechanomyographic analysis of muscle segment contractile properties within human deltoid." *Eur J Appl Physiol* 78:6–17.
- Brown JM et al. (2007) "Muscles within muscles: coordination of 19 muscle segments within three shoulder muscles during isometric motor tasks." *J Electromyogr Kinesiol* 17:57–73.
- Fabrizio PA, Clemente FR (2011) "Anatomic compartmentalization of infraspinatus." *J Anat* 219(3):303–310.
- von Schroeder HP, Botte MJ (1993) "Anatomy of the extensor tendons of the fingers: variations and multiplicity." *J Hand Surg Am* 18(1):16–20 (FDP/extensor compartment anatomy).

**Fascia**
- Stecco C. *Functional Atlas of the Human Fascial System*. Churchill Livingstone/Elsevier, 2015.

**Nerve root maps**
- ASIA (American Spinal Injury Association) International Standards for Neurological Classification of Spinal Cord Injury — standard myotome/dermatome charts.

## Sources considered but not reachable this session

An automated multi-agent PubMed/web literature research pass (12 parallel
research agents covering ROM, muscle architecture, plexus trees, vasculature,
fascia and joint kinematics) was attempted to independently ground every
number against live-searched literature. It failed entirely — every agent
hit a tool-level structured-output error after multiple retries, a systemic
issue rather than a content problem (see the workflow run for
`nmsk-atlas-research`, all 12/12 agents errored identically). Rather than
retry at similar cost, the data in this pass was authored directly from the
well-established references above (the same standard I used successfully
for the skeleton, joints, and nerve-root map), and then spot-verified by a
second, smaller round of adversarial fact-check agents — see
docs/VERIFICATION.md for what they checked and found.

## Data sources for future full-body scale-up (not used in this pass)

- NIH Visible Human Project — public domain, ~15GB of 1mm axial cryosection/CT/MRI data. https://www.nlm.nih.gov/research/visible/visible_human.html
- AIST BodyParts3D / Anatomography — CC BY-SA segmented 3D anatomy meshes. https://lifesciencedb.jp/bp3d/
- OpenSim (Stanford) musculoskeletal models — BSD-licensed, published moment-arm/muscle-path data usable for Stage 6 validation. https://opensim.stanford.edu
